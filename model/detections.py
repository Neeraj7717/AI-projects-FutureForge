import os
import json
import logging
from kafka import KafkaProducer
from ultralytics import YOLO
from utils.cv2Operations import cv2_operations
from instruction.instructions import complete_task
from config.var import Settings
from utils.directoryOperations import directory_operations

# Configuring logging settings
logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load configurations from settings
config = Settings()

class Detections:
    """Class for performing object detection and assigning tasks based on detections."""

    def __init__(self):
        """Initialize object detection model and other necessary parameters."""
        self.model_path = config.path_of_model
        self.model = YOLO(self.model_path, "v8")
        self.frames_path = config.frames_path
        self.kafka_url = config.kafka_url
        self.video_details_kafka_topic = config.video_details_kafka_topic
        self.detections = {}  # Dictionary to store detections for each sourceId
        self.shared_path = config.shared_path

    def action_detector(self, sourceId, file, sessionId, manualId):
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
            classs = dic["boxes"].cpu().numpy()
            things_present = list(map(lambda i: names[i], classs.cls))

            # Draw bounding boxes on the image
            a = detection_output[0].boxes
            xyxy = a.xyxy.cpu().numpy()
            file_name = os.path.basename(file)
            path_to_save_frames = directory_operations.get_frames_path(sourceId)
            path_to_save_frames = path_to_save_frames + file_name
            
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
            task = self.assign_task(things_present, sourceId)
            if task is not None:
                response = complete_task(file={"sourceId": sourceId, "task": task, "manualId": manualId,"sessionId":sessionId})
                logging.info(f"Response from graph: {response}")
            return things_present
        except Exception as e:
            logging.error(f"Error occurred: {e}")
            return e

    def assign_task(self, things_present, sourceId):
        """Assign task based on detected objects.

        Args:
            things_present (list): List of objects detected in the image.
            sourceId (str): Unique identifier for the source.

        Returns:
            int: Task identifier.
        """
        task = None
        if "case" in things_present and "mobile" in things_present:
            task = 1
        elif "charger" in things_present:
            task = 3
        elif "flash" in things_present:
            task = 4
        elif not things_present:
            task = 5
        elif "case" in things_present:
            task = 2

        # Store detected tasks for each sourceId
        if sourceId in self.detections:
            self.detections[sourceId].append(task)
        else:
            self.detections[sourceId] = [task]

        # Check if a consistent task has been detected
        if len(self.detections[sourceId]) == 3 and len(set(self.detections[sourceId])) == 1:
            return task
        elif len(set(self.detections[sourceId])) > 1:
            self.detections[sourceId] = []  # Reset detections if inconsistent
            return None
