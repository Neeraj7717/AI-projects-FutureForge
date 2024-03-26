import os
import json
import logging
import pymongo
from kafka import KafkaProducer
from ultralytics import YOLO
from utils.cv2Operations import cv2_operations
# from instruction.instructions import complete_task
from config.settings import Settings
from utils.directoryOperations import directory_operations
from instruction.instructions import TaskManager

# Configuring logging settings
logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load configurations from settings
config = Settings()

map = {
    1 : ["case", "mobile"],
    2 : ["case"],
    3 : ["case", "charger"],
    4 : ["flash"],
    0 : []
}

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
        self.model_path = config.path_of_model
        self.model = YOLO(self.model_path, "v8")
        self.frames_path = config.frames_path
        self.kafka_url = config.kafka_url
        self.video_details_kafka_topic = config.video_details_kafka_topic
        self.detections = {}  # Dictionary to store detections for each sourceId
        self.shared_path = config.shared_path
        self.client = pymongo.MongoClient("mongodb://Eizen:Eizen123@183.82.116.237:27017/")  # Connect to MongoDB
        self.db = self.client["testing"]  # Use or create a database
        self.collection = self.db["detections"]
        self.task_manager = TaskManager(steps=self.steps)
    
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
            detection_output = self.model.predict(source=file, conf=0.25, save=False)
            dic = vars(detection_output[0])
            names = dic["names"]
            detected_class = dic["boxes"].cpu().numpy()
            things_present = [names[i] for i in detected_class.cls]
            print("things_present==================", things_present)

            # Draw bounding boxes on the image
            a = detection_output[0].boxes
            xyxy = a.xyxy.cpu().numpy()
            file_name = os.path.basename(file)
            path_to_save_frames = directory_operations.get_frames_path(sourceId)
            path_to_save_frames = path_to_save_frames + file_name
            print(path_to_save_frames)
            try:
                cv2_operations().draw_bounding_boxes(file, xyxy, things_present, path_to_save_frames)
                logging.info("Bounding Boxes done")
            except Exception as e:
                logging.error(f"Error in CV2 Operations {e}")
                return e

            # Connect to Kafka producer and send message
            try:
                producer = KafkaProducer(bootstrap_servers=self.kafka_url)
            except Exception as e:
                logging.error(f"Error in connecting to Kafka instance: {e}")
                return e
            message = {"sessionId": sessionId, "videoUrl": self.shared_path + sourceId + "/" + "frames/" + file_name, "manualId": manualId}
            try:
                producer.send(self.video_details_kafka_topic, value=json.dumps(message).encode("utf-8"))
            except Exception as e:
                logging.error(f"Error in writing to Kafka topic {self.video_details_kafka_topic}: {e}")
                return e

            # Assign task based on detections
            task = self.assign_task(things_present, sourceId, sessionId)
            if task is not None:
                print("===========task", task)
                response = self.task_manager.get_next_step(sessionId, sourceId, task, manualId)
                logging.info(f"Response from graph: {response}")
                return things_present, response
            return things_present
        except Exception as e:
            logging.error(f"Error occurred: {e}")
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
            if saved_detections:
                print("Retrieved detections from MongoDB:", saved_detections)

            if len(saved_detections) == 3 and len(set(saved_detections)) == 1:
                return task
            elif len(set(saved_detections)) > 1:
                self.remove_detection(sourceId)
                return None

        except Exception as e:
            logging.error(f"Error occurred: {e}")
            return e
