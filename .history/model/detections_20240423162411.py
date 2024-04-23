import base64
import os
import json
import logging
import subprocess
import numpy as np
import requests
import pymongo
from kafka import KafkaProducer
from ultralytics import YOLO
from utils.cv2Operations import cv2_operations
from config.settings import Settings
from utils.directoryOperations import directory_operations
from instruction.instructions_graph import TaskManager
from utils.api_client import APIClient
from instruction.instructions_llava import LlavaInference
import cv2
 
# Load configurations from settings
config = Settings()
 
# Configure the root logger to output logs to the terminal
logging.basicConfig(level=config.log_level, format='%(asctime)s - %(levelname)s - %(message)s')
 
# Get the root logger
logger = logging.getLogger()
 
# Add a StreamHandler to the logger to output logs to the terminal
console_handler = logging.StreamHandler()
logger.addHandler(console_handler)
 
map = {
    1 : ["case", "mobile"],
    2 : ["case"],
    3 : ["case", "charger"],
    4 : ["flash"],
    0 : []
}
# map = {
#     1 : ["paper"],
#     0 : []
# }
 
class Detections:
    """Class for performing object detection and assigning tasks based on detections."""
 
    def __init__(self):
        """Initialize object detection model and other necessary parameters."""
        self.steps = {
            1: "Pick up the phone and its cases.",
            2: "Assemble the Case to phone.",
            3: "Take the charger in your hand and connect it to phone.",
            4: "Turn on the flashlight on your phone.",
            5: "Turn off the flashlight and put your phone down"
        }
        # self.steps = {
        #     1: "Please write an equation showing the formation of Water.",
        #     2: "Please write an equation showing the formation of Hydrochloric Acid."
        # }
        self.model_path = "./checkpoints/bestVIA.pt"
        self.model = YOLO(self.model_path, "v8")
        self.frames_path = config.frames_path
        self.kafka_url = config.kafka_url
        self.video_details_kafka_topic = config.video_details_kafka_topic
        self.shared_path = config.shared_path
        self.client = pymongo.MongoClient(config.mongo_connection_string_stateless)  # Connect to MongoDB
        self.db = self.client[config.stateless_db]  # Use or create a database
        self.collection = self.db[config.stateless_collection_detections]
        self.task_manager = TaskManager(steps=self.steps)
        self.llava = LlavaInference(steps=self.steps)
        self.api_client = APIClient(config.llava_endpoint)
    
    def store_detection(self, sourceId, task, sessionId):
        """Store or update detections in MongoDB."""
        # Check if the document with the given sourceId already exists
        existing_document = self.collection.find_one({"sourceId": sourceId})
        if existing_document:
            # Check if the sessionId matches the existing one
            if existing_document.get("sessionId") == sessionId:
                # Update the existing document by appending the new task
                updated_tasks = existing_document.get("tasks", [])  # Get existing tasks or an empty list
                updated_tasks.append(task)  # Append the new task
                # Update the document with the updated tasks list
                self.collection.update_one(
                    {"sourceId": sourceId},
                    {"$set": {"tasks": updated_tasks}}
                )
            else:
                # Empty the existing task list and update with the new item
                self.collection.update_one(
                    {"sourceId": sourceId},
                    {"$set": {"tasks": [task], "sessionId": sessionId}}
                )
        else:
            # Insert a new document with the task as a list
            data = {"sourceId": sourceId, "tasks": [task], "sessionId": sessionId}
            self.collection.insert_one(data)
 
    def get_detection(self, sourceId):
        """Retrieve tasks from MongoDB."""
        data = self.collection.find_one({"sourceId": sourceId})
        if data:
            return data["tasks"]
        else:
            return None
 
    def remove_detection(self, sourceId):
        """Remove detections from MongoDB."""
        self.collection.delete_one({"sourceId": sourceId})
    
    def action_detector(self, file, sourceId, sessionId, manualId):
        """Perform object detection on the provided image file.
 
        Args:
            sourceId (str): Unique identifier for the source.
            file (str): Path to the image file for detection.
            sessionId (str): Unique identifier for the session.
            manualId (str): Unique identifier for the manual.
 
        Returns:
            list: List of objects detected in the image.
        """
        try:
            # Perform object detection
            image_bytes = base64.b64decode(file)
            file = np.frombuffer(image_bytes, dtype=np.uint8)
            # Decode the numpy array to an image
            file = cv2.imdecode(file, cv2.IMREAD_COLOR)
            detection_output = self.model.predict(source=file, conf=0.25, save=False)   
            dic = vars(detection_output[0])
            names = dic["names"]
            detected_class = dic["boxes"].cpu().numpy()
            things_present = [names[name] for name in detected_class.cls]
            logger.debug(f"The Detections are {things_present}")
 
            print("==========================", things_present)
            
            # Draw bounding boxes on the image
            a = detection_output[0].boxes
            xyxy = a.xyxy.cpu().numpy()
 
            try:
                image = cv2_operations().draw_bounding_boxes(file, xyxy, things_present, "1.jpg")
                height, width = image.shape[:2]
 
                # Calculate the new dimensions (half of original)
                new_width = width // 2
                new_height = height // 2
                image=cv2.resize(image,(new_width,new_height))
                _, buffer = cv2.imencode(".jpg", image)
                frame_bytes = base64.b64encode(buffer).decode("utf-8")
                logger.debug("Finished drawing bounding boxes")
            except Exception as e:
                logger.error(f"Error in CV2 Operations: {e}")
                return e
 
            # Connect to Kafka producer and send message
            try:
                producer = KafkaProducer(bootstrap_servers=self.kafka_url)
            except Exception as e:
                logger.error(f"Error in connecting to Kafka instance: {e}")
                return e
            message = {"sessionId": sessionId, "image_byte": frame_bytes, "manualId": manualId}
            try:
                producer.send(self.video_details_kafka_topic, value=json.dumps(message).encode("utf-8"))
            except Exception as e:
                logger.error(f"Error in writing to Kafka topic {self.video_details_kafka_topic}: {e}")
                return e
 
            # Assign task based on detections
            task = self.assign_task(things_present, sourceId, sessionId)
            if task is not None:
                logger.debug(f"The task number is: {task}")
                response = self.task_manager.get_next_step(sessionId, sourceId, task, manualId, frame_bytes)
                logger.debug(f"Response from graph: {response}")
                return things_present, response
            return things_present
                
        except Exception as e:
            logger.error(f"Error occurred: {e}")
            return e
 
    def assign_task(self, things_present, sourceId, sessionId):
        """Perform object detection on the provided image file."""
        try:
            matching_keys = filter(lambda key: map[key] == sorted(things_present), map)
            # Converting the filter object to a list and getting the first item
            task = next(matching_keys, None)
 
            # Store detections in MongoDB
            self.store_detection(sourceId, task, sessionId)
 
            # Retrieve detections from MongoDB
            saved_detections = self.get_detection(sourceId)
            print("saved_detections", saved_detections)
            if saved_detections:
                logger.debug(f"Retrieved detections from MongoDB: {saved_detections}")
 
            if len(saved_detections) == config.continuity and len(set(saved_detections)) == 1:
                print("task", task)
                self.remove_detection(sourceId)
                return task
            elif len(set(saved_detections)) > 1:
                self.remove_detection(sourceId)
                return None
 
        except Exception as e:
            logger.error(f"Error occurred: {e}")
            return e