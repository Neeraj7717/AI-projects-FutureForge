import base64
import datetime
import os
import json
import logging
import os
import time
import subprocess
import traceback
import faiss
import zlib
import numpy as np
import requests
import pymongo
import torch
import yaml
import easyocr
from kafka import KafkaProducer
from ultralytics import YOLO
from utils.cv2Operations import cv2_operations
from Config.settings import Settings
from utils.directoryOperations import directory_operations
from instruction.instructions_graph import TaskManager
from utils.api_client import APIClient
from instruction.instructions_llava import LlavaInference
import cv2
import concurrent.futures
from s3utils import generaloperations
from utils.llmOperations import QuestionAnswerModel
from transformers import AutoImageProcessor, AutoModel
import time
import mediapipe as mp
pose = mp.solutions.pose

# Load configurations from settings
config = Settings()
 
# Configure the root logger to output logs to the terminal
logging.basicConfig(level=config.log_level, format='%(asctime)s - %(levelname)s - %(message)s')
 
# Get the root logger
logger = logging.getLogger()
 
# Add a StreamHandler to the logger to output logs to the terminal
console_handler = logging.StreamHandler()
logger.addHandler(console_handler)
 
reader = easyocr.Reader(['en'])



 
class Detections:
    """Class for performing object detection and assigning tasks based on detections."""
 
    def __init__(self):
        """Initialize object detection model and other necessary parameters."""
        with open('Config/viaconfig.yaml', 'r') as file:
            self.data = yaml.safe_load(file)

        self.model_path = config.path_of_model
        self.model = YOLO(self.model_path, "v8")
        self.frames_path = config.frames_path
        self.kafka_url = config.kafka_url
        self.ekycmodel=YOLO(config.path_of_ekyc_model, "v8")
        self.chairmodel=YOLO(config.path_of_chair_model,"v8")
        self.video_details_kafka_topic = config.video_details_kafka_topic
        self.shared_path = config.shared_path
        self.client = pymongo.MongoClient(config.mongo_connection_string_stateless)  # Connect to MongoDB
        self.db1 = self.client[config.database_name]
        self.db = self.client[config.stateless_db]  # Use or create a database
        self.collection = self.db[config.stateless_collection_detections]
        self.lagcollection = self.db["lag"]
        self.monualCollection=self.db1["manual"]
        self.sessionSteps=self.db1["sessionSteps"]
        self.producer=KafkaProducer(bootstrap_servers=config.kafka_url)
        # self.llava = LlavaInference(steps=self.steps)
        self.api_client = APIClient(config.llava_endpoint)
        self.contextCollection=self.db1["contexts"]
        self.device = torch.device('cuda' if torch.cuda.is_available() else "cpu")
        self.processor = AutoImageProcessor.from_pretrained('facebook/dinov2-small')
        self.similarmodel = AutoModel.from_pretrained('facebook/dinov2-small').to(self.device)

        self.pose_model = pose.Pose(static_image_mode=True, min_detection_confidence=0.5)


    def get_manual_name(self,manual_id):
        for model in self.data['models']:
            for manual in model['manuals']:
                if manual_id in manual['ids']:
                    return manual['name']
        return None

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
            
    def reduce_lag(self, sourceId, sessionId):
        """Store or update detections in MongoDB."""
        # Check if the document with the given sourceId already exists
        existing_document = self.lagcollection.find_one({"sessionId": sessionId})
        
        print(existing_document["lag"],"=====================================")
        lag=existing_document["lag"]
        if existing_document:
            # Check if the sessionId matches the existing one
            
            self.lagcollection.update_one(
                {"sessionId": sessionId},
                {"$set": {"lag":lag-1}}
            )
        else:
            # Insert a new document with the task as a list
            data = {"lag": 0, "sessionId": sessionId}
            self.lagcollection.insert_one(data)
    def add_lag(self, sourceId, sessionId,time):
        """Store or update detections in MongoDB."""
        # Check if the document with the given sourceId already exists
        existing_document = self.lagcollection.find_one({"sessionId": sessionId})
        if existing_document:
            # Check if the sessionId matches the existing one

            self.lagcollection.update_one(
                {"sessionId": sessionId},
                {"$set":{"lag":time}}
            )
        else:
            # Insert a new document with the task as a list
            data = {"lag": time, "sessionId": sessionId}
            self.lagcollection.insert_one(data)

    def get_detection(self, sessionId):
        """Retrieve tasks from MongoDB."""
        data = self.collection.find_one({"sessionId": sessionId})
        if data:
            return data["tasks"]
        else:
            return None
    def get_lag(self, sourceId,sessionId):
        """Retrieve tasks from MongoDB."""
        data = self.lagcollection.find_one({"sessionId": sessionId})
        if data:
            return data["lag"]
        else:
            data = self.lagcollection.insert_one({"sessionId": sessionId,"lag":0})
            return 0
    def remove_detection(self, sessionId):
        """Remove detections from MongoDB."""
        self.collection.delete_one({"sessionId": sessionId})
    
    def send_instruction(self,xyxy,new_width,new_height,sourceId,sessionId,manualId,things_present):
        xyxy=xyxy.tolist()
        print(type(xyxy))
        key_component=sessionId.encode('utf-8') 
        message = {"sessionId": sessionId, "classes": things_present, "coordinates": list(xyxy),"frameDimensions":[new_width,new_height]}
        try:
            self.producer.send("vip-bounding-box-details",key=key_component, value=json.dumps(message).encode("utf-8"))
            
        except Exception as e:
            print(f"Error sending message: {str(e)}")
            traceback.print_exc()
            pass
        print({"sessionId":sessionId,"manualId":manualId,"sourceId":sourceId,"thingsPresent":things_present})
        print("________________________sending_bounding_boxes_________________________",config.java_endpoint)
        response  = requests.post(config.java_endpoint, json={"sessionId":sessionId,"manualId":manualId,"sourceId":sourceId,"thingsPresent":things_present})
        return
        # lag=self.get_lag(sourceId,sessionId)
        # if lag<=0:

        #     task,map = self.assign_task(things_present, sourceId, sessionId,manualId)

        #     if task is not None:

        #         document = self.monualCollection.find_one({"_id": int(manualId)})
        #         steps = {step["_id"]: step["text"] for step in document["steps"][:-1]}
        #         task_manager = TaskManager(steps=steps)                
        #         print(f"The task number is: {task}") 
        #         response = task_manager.get_next_step(sessionId, sourceId, task, manualId, "",things_present,map)
        #         logger.debug(f"Response from graph: {response}")


        #         if response !=0 and response!=None:

        #             self.add_lag(sourceId,sessionId,response)

        #         logger.debug(f"Response from graph: {response}")
        # else:

        #     self.reduce_lag(sourceId,sessionId)

    def ekyc_action_detector(self, file, sourceId, sessionId, manualId):
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
            
            # if manualId!=str(4):
            try:
                header,encoded=file.split(",",1)
                image_bytes = base64.b64decode(encoded)
                file = np.frombuffer(image_bytes, dtype=np.uint8)
                file = cv2.imdecode(file, cv2.IMREAD_COLOR)
                # cv2.imwrite("1.jpg",file)
                detection_output = self.ekycmodel.predict(source=file, conf=0.25, save=False)   
            except Exception as e:
                print("ERROR",e)
                traceback.print_exc()
            dic = vars(detection_output[0])
            names = dic["names"]
            print(names)
            # print(names)
            detected_class = dic["boxes"].cpu().numpy()
            things_present = [names[name] for name in detected_class.cls]
            logger.debug(f"The Detections are {things_present}")
            a = detection_output[0].boxes
            xyxy = a.xyxy.cpu().numpy()
            new_height, new_width = file.shape[:2]
            

 
            # try:
            #     image = cv2_operations().draw_bounding_boxes(file, xyxy, things_present, "1.jpg")
            #     height, width = image.shape[:2]
 
            #     # Calculate the new dimensions (half of original)
            #     new_width = width 
            #     new_height = height 
            #     image=cv2.resize(image,(new_width,new_height))
            #     compressed_frame= zlib.compress(cv2.imencode(".jpg", image)[1])
            #     frame_bytes = base64.b64encode(compressed_frame).decode("utf-8")
            #     logger.debug("Finished drawing bounding boxes")
            # except Exception as e:
            #     logger.error(f"Error in CV2 Operations: {e}")
            #     pass
                
            
            # return 

            with concurrent.futures.ThreadPoolExecutor(max_workers=1000) as executor:
                # Assign task based on detections
                executor.submit(self.send_instruction(xyxy,new_width,new_height,sourceId,sessionId,manualId,things_present))
                return

            
                
        except Exception as e:
            logger.error(f"Error occurred: {e}")
            return e
        




    

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
            print("Detection Started")
            header,encoded=file.split(",",1)
            print("decoding")
            image_bytes = base64.b64decode(encoded)
            file = np.frombuffer(image_bytes, dtype=np.uint8)
            # Decode the numpy array to an image
            file = cv2.imdecode(file, cv2.IMREAD_COLOR)

            # cv2.imwrite("1.jpg",file)
            # if manualId!=str(4):
            detection_output = self.model.predict(source=file, conf=0.25, save=False)   
            dic = vars(detection_output[0])
            names = dic["names"]
            detected_class = dic["boxes"].cpu().numpy()
            things_present = [names[name] for name in detected_class.cls]
            logger.debug(f"The Detections are {things_present}")
            a = detection_output[0].boxes
            xyxy = a.xyxy.cpu().numpy()
            new_height, new_width = file.shape[:2]
            print(detected_class)

            # try:
            #     image = cv2_operations().draw_bounding_boxes(file, xyxy, things_present, "1.jpg")
            #     height, width = image.shape[:2]
 
            #     # Calculate the new dimensions (half of original)
            #     new_width = width 
            #     new_height = height 
            #     image=cv2.resize(image,(new_width,new_height))
            #     compressed_frame= zlib.compress(cv2.imencode(".jpg", image)[1])
            #     frame_bytes = base64.b64encode(compressed_frame).decode("utf-8")
            #     logger.debug("Finished drawing bounding boxes")
            # except Exception as e:
            #     logger.error(f"Error in CV2 Operations: {e}")
            #     pass
                
            
            # Connect to Kafka producer and send message
            with concurrent.futures.ThreadPoolExecutor(max_workers=1000) as executor:
                # Assign task based on detections
                executor.submit(self.send_instruction(xyxy,new_width,new_height,sourceId,sessionId,manualId,things_present))
                return
                
        except Exception as e:
            print("Error: ", e)
            logger.error(f"Error occurred: {e}")
            return e






    def pose_detector(self, file, sourceId, sessionId, manualId):
        try:
            print("Starting pose detection...")

            # Decode base64 image
            header, encoded = file.split(",", 1)
            image_bytes = base64.b64decode(encoded)
            np_arr = np.frombuffer(image_bytes, dtype=np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            print(f"Image decoded, shape: {frame.shape}")

            # Convert image to RGB for MediaPipe
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Perform pose detection
            results = self.pose_model.process(rgb_image)

            # Check if person is present
            person_present = results.pose_landmarks is not None

            things_present = []
            hand_status = "noHandsRaised"
            keypoint_data = {}

            if person_present:
                things_present.append("personPresent")
                hand_status, keypoint_data = self.detect_raised_hands(results.pose_landmarks, frame.shape)
                things_present.append(hand_status)
            print(things_present)
            # Generate output image with annotations
            annotated_image = self.draw_annotations(frame, results.pose_landmarks)

            # Save the debug image
            debug_path = "pose_detection_debug.jpg"
            cv2.imwrite(debug_path, annotated_image)

            print(f"Debug image saved to: {debug_path}")
            print(things_present)

            lag = self.get_lag(sourceId, sessionId)
            if lag <= 0:

                task, map = self.assign_task(things_present, sourceId, sessionId, manualId)

                if task is not None:

                    document = self.monualCollection.find_one({"_id": int(manualId)})
                    steps = {step["_id"]: step["text"] for step in document["steps"][:-1]}
                    task_manager = TaskManager(steps=steps)
                    print(f"The task number is: {task}")
                    response = task_manager.get_next_step(sessionId, sourceId, task, manualId, frame, things_present, map)
                    print(f"Response from graph: {response}")

                    if response != 0 and response is not None:
                        self.add_lag(sourceId, sessionId, response)

                    print(f"Response from graph: {response}")
            else:
                self.reduce_lag(sourceId, sessionId)

        except Exception as e:
            print(f"Error occurred: {e}")
            traceback.print_exc()


        except Exception as e:
            print(f"Error occurred: {e}")
            traceback.print_exc()


    def detect_raised_hands(self, landmarks, frame_shape):
        height, width, _ = frame_shape

        left_wrist_y = landmarks.landmark[pose.PoseLandmark.LEFT_WRIST].y * height
        right_wrist_y = landmarks.landmark[pose.PoseLandmark.RIGHT_WRIST].y * height

        left_shoulder_y = landmarks.landmark[pose.PoseLandmark.LEFT_SHOULDER].y * height
        right_shoulder_y = landmarks.landmark[pose.PoseLandmark.RIGHT_SHOULDER].y * height

        hand_status = "noHandsRaised"
        keypoint_data = {
            "left_wrist": (left_wrist_y),
            "right_wrist": (right_wrist_y),
            "left_shoulder": (left_shoulder_y),
            "right_shoulder": (right_shoulder_y)
        }

        if left_wrist_y < left_shoulder_y:
            hand_status = "leftHandRaised"
        if right_wrist_y < right_shoulder_y:
            hand_status = "rightHandRaised"
        if left_wrist_y < left_shoulder_y and right_wrist_y < right_shoulder_y:
            hand_status = "bothHandsRaised"

        return hand_status, keypoint_data

    def draw_annotations(self, image, landmarks):
        if not landmarks:
            return image

        # Draw keypoints
        for landmark in landmarks.landmark:
            x = int(landmark.x * image.shape[1])
            y = int(landmark.y * image.shape[0])
            cv2.circle(image, (x, y), 5, (0, 255, 0), -1)

        return image


    def image_input(self, file, sourceId, sessionId, manualId):
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
            bucket_name = 'eizen-dev'
            cloud_path = '/'.join(file.split('/')[3:])
            local_store_path = file.split('/')[-1]
            file = generaloperations.download_from_s3_bucket(bucket_name, cloud_path, local_store_path)
            print(f"Downloaded file: {file}")
            # Perform object detection
            # if manualId!=str(4):
            modelname=self.get_manual_name(int(manualId))
            if modelname=="phone":
                detection_output = self.model.predict(source=file, conf=0.25, save=False)   
            elif modelname=="ekyc":
                detection_output = self.ekycmodel.predict(source=file, conf=0.25, save=False)   
            elif modelname=="chair":
                detection_output = self.chairmodel.predict(source=file, conf=0.25, save=False)   
            elif modelname=="similar":
                file=cv2.imread(file)
                with torch.no_grad():
                    inputs = self.processor(images=file, return_tensors="pt").to(self.device)
                    outputs = self.similarmodel(**inputs)
                embeddings = outputs.last_hidden_state
                embeddings = embeddings.mean(dim=1)
                vector = embeddings.detach().cpu().numpy()
                vector = np.float32(vector)
                faiss.normalize_L2(vector)
            
                # Search the FAISS index
                if manualId!="16":
                    index = faiss.read_index("vectordb/vector.index")
                    d, i = index.search(vector, 1)
                    print(i)
                    json_file_path = 'vectordb/images.json'

                    # Load JSON data
                    with open(json_file_path, 'r') as f:
                        data = json.load(f)

                    images=list(data.keys())
                    # Retrieve image paths from the indices (assuming 'images' is a list of image paths)
                    image_paths = images[i[0][0]]
                
                    # Retrieve object names from the data dictionary
                    object_names = data[image_paths]
                    response  = requests.post(config.t2v_endpoint, json={"text" : f"The object you picked is {object_names}", "gender": 0})
                    data = json.loads(response.content.decode("utf-8"))
                    message={
                            "sessionId": sessionId,
                            "videoUrl": "",
                            "audioUrl": data["file_path"],
                            "contextUrl": image_paths,
                            "contextType": "img",
                            "manualId": manualId,
                            "stepId": 1,
                            "step": f"The object you picked is {object_names}",
                            "status": "failed",
                            "repetition": 0,
                            "feedback": "",
                            "feedbackUrl": "",
                            "startTime": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00"),
                            "endTime": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00"),
                        }
                else:
                    index = faiss.read_index("vectordb/orienation_images_vector.index")
                    d, i = index.search(vector, 1)
                    print(i)
                    with open("vectordb/orienation_images_vector.json", 'r') as f:
                        data = json.load(f)

                    # Access the 'images' array
                    images_list = data['images']

                    response  = requests.post(config.t2v_endpoint, json={"text" : f"The object you picked is similar to the object shown", "gender": 0})
                    data = json.loads(response.content.decode("utf-8"))
                    message={
                            "sessionId": sessionId,
                            "videoUrl": "",
                            "audioUrl": data["file_path"],
                            "contextUrl": images_list[i[0][0]],
                            "contextType": "img",
                            "manualId": manualId,
                            "stepId": 1,
                            "step": f"The object you picked is similar to the object shown",
                            "status": "failed",
                            "repetition": 0,
                            "feedback": "",
                            "feedbackUrl": "",
                            "startTime": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00"),
                            "endTime": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00"),
                        }
                self.producer.send(config.video_instruction_kafka_topic,value=json.dumps(message).encode("utf-8"))
                return
            else:
                document = self.monualCollection.find_one({"_id": int(manualId)})

                steps = {step["_id"]: step["text"] for step in document["steps"][:-1]}

                task_manager = TaskManager(steps=steps) 
                try:
                    task,map = self.assign_current_task([], sourceId, sessionId,manualId)
                except:
                    map={}
                response = task_manager.get_next_step(sessionId, sourceId, 0, manualId, "image_bytes",[],map)
                os.remove(file)
                return
            os.remove(file)
            dic = vars(detection_output[0])
            names = dic["names"]
            detected_class = dic["boxes"].cpu().numpy()
            things_present = [names[name] for name in detected_class.cls]
            logger.debug(f"The Detections are {things_present}")



            task,map = self.assign_current_task(things_present, sourceId, sessionId,manualId)
            if task is not None:
                document = self.monualCollection.find_one({"_id": int(manualId)})

                steps = {step["_id"]: step["text"] for step in document["steps"][:-1]}

                task_manager = TaskManager(steps=steps)                

                response = task_manager.get_next_step(sessionId, sourceId, task, manualId, "image_bytes",things_present,map)

                if response !=0 and response != None:
                    self.add_lag(sourceId,sessionId,response)
                logger.debug(f"Response from graph: {response}")
                return things_present, response
            
            return things_present
                
        except Exception as e:
            logger.error(f"Error occurred: {e}")
            print(e)
            return e
 
    
    def send_first_instruction(self,sessionId,frame_bytes,manualId,sourceId):
                    # Connect to Kafka producer and send message
        
        # message = {"sessionId": sessionId, "image_byte": frame_bytes, "manualId": manualId}
        # try:
        #     self.producer.send(self.video_details_kafka_topic+sessionId, value=json.dumps(message).encode("utf-8"))
        # except Exception as e:
        #     logger.error(f"Error in writing to Kafka topic {self.video_details_kafka_topic+sessionId}: {e}")
        #     pass
        # Assign task based on detections
        data=self.sessionSteps.find_one({"sessionId":sessionId})
        if data==None:
            document = self.monualCollection.find_one({"_id": int(manualId)})
            steps = {step["_id"]: step["text"] for step in document["steps"][:-1]}
            task_manager = TaskManager(steps=steps)

            response = task_manager.get_next_step(sessionId, sourceId, 0, manualId, frame_bytes,[],{})
        

    def text_action_detector(self, file, sourceId, sessionId, manualId):
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
            header,encoded=file.split(",",1)
            image_bytes = base64.b64decode(encoded)
            file = np.frombuffer(image_bytes, dtype=np.uint8)
            file = cv2.imdecode(file, cv2.IMREAD_COLOR)
            image=file
            try:
                
                height, width = image.shape[:2]
 
                # Calculate the new dimensions (half of original)
                new_width = width // 2
                new_height = height // 2
                image=cv2.resize(image,(new_width,new_height))
                compressed_frame= zlib.compress(cv2.imencode(".jpg", image)[1])
                frame_bytes = base64.b64encode(compressed_frame).decode("utf-8")
                logger.debug("Finished drawing bounding boxes")
            except Exception as e:
                logger.error(f"Error in CV2 Operations: {e}")
                pass
                
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=1000) as executor:
                # Assign task based on detections
                executor.submit(self.send_first_instruction(sessionId,frame_bytes,manualId,sourceId))
                return



        except Exception as e:
            logger.error(f"Error occurred: {e}")
            return e
 


    def text_detector(self,file, sourceId, sessionId, manualId):

        try:
            
            answer=self.monualCollection.find_one({"_id":int(manualId)})
            # print(answer["steps"])
            print("======================")
            if len(answer["steps"])>1:
                data=self.sessionSteps.find_one({"sessionId":sessionId})
                current_question=data['steps'][-1]["stepId"]
                for i in answer["steps"]:
                    print(int(current_question),i["_id"])
                    response  = requests.post(config.text_compare_url, json={"sentence1" : i["answer"], "sentence2": file})
                    similarity = json.loads(response.content.decode("utf-8"))["similarity"]
                    
                    if int(current_question)==i["_id"]:
                        document = self.monualCollection.find_one({"_id": int(manualId)})
                        steps = {step["_id"]: step["text"] for step in document["steps"][:-1]}
                        task_manager = TaskManager(steps=steps)
                        if similarity>0.9:
                            
                            print("ssssstttttaaaarrrrttt")
                            response = task_manager.get_next_step(sessionId, sourceId, i["_id"], manualId, "frame_bytes",[],{})
                            return
                        else:

                            print("ffffaaaaiiilllleedddd")
                            response = task_manager.get_next_step(sessionId, sourceId, -1, manualId, "frame_bytes",["text_based_model"],{})
                            return
            else:
                context=self.contextCollection.find_one({"manualId":manualId})["context"]
                # context = ''' KFC offers a variety of chicken burgers including the Classic Chicken Burger, Tandoori Chicken Burger, Crispy Chicken Burger, and Chicken Tikka Burger, along with sides like fries, and beverages such as Mirinda, Pepsi, and 7Up.'''
                try:
                    "==========="
                    # qamodel = QuestionAnswerModel()
                    # response1 = qamodel.generate_answer(context = context, question = file)


                    print(file,"-"*19)

                    response1  = requests.post(config.context_based_question_answer, json={
                                                                            "context": context,
                                                                            "question": file
                                                                            })
                    response1 = json.loads(response1.content.decode("utf-8"))
                    print("Generated Answer:", response1["answer"])
                    # response1={}
                    # response1["answer"]="hello"
                    response  = requests.post(config.t2v_endpoint, json={"text" : response1["answer"], "gender": 0})
                    data = json.loads(response.content.decode("utf-8"))
                    message={
                        "sessionId": sessionId,
                        "videoUrl": "",
                        "audioUrl": data["file_path"],
                        "contextUrl": "emt",
                        "contextType": "emt",
                        "manualId": manualId,
                        "stepId": 1,
                        "step": response1["answer"],
                        "status": "failed",
                        "repetition": 0,
                        "feedback": "",
                        "feedbackUrl": "",
                        "startTime": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00"),
                        "endTime": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00"),
                        }
                    self.producer.send(config.video_instruction_kafka_topic,value=json.dumps(message).encode("utf-8"))
                    print("======")
                except Exception as e:
                    print(e)


        except Exception as e:
            print(e)

        
    def chair_action_detector(self, file, sourceId, sessionId, manualId):
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
            header,encoded=file.split(",",1)
            image_bytes = base64.b64decode(encoded)
            file = np.frombuffer(image_bytes, dtype=np.uint8)
            file = cv2.imdecode(file, cv2.IMREAD_COLOR)
            # if manualId!=str(4):
            detection_output = self.chairmodel.predict(source=file, conf=0.25, save=False)   
            dic = vars(detection_output[0])
            names = dic["names"]
            # print(names)
            detected_class = dic["boxes"].cpu().numpy()
            things_present = [names[name] for name in detected_class.cls]
            detected_things=things_present[:]
            print("=================",things_present)
            try:
                response  = requests.post(config.action_detection_api, json={"file" : frame_bytes, "sourceId":sourceId,"sessionId": sessionId,"manualId" :manualId})
                print(response)
                data = json.loads(response.content.decode("utf-8"))
                things_present+=data
                print(things_present)
            except Exception as e:
                print(e)
            logger.debug(f"The Detections are {things_present}")
            a = detection_output[0].boxes
            xyxy = a.xyxy.cpu().numpy()
        

 
            try:
                image = cv2_operations().draw_bounding_boxes(file, xyxy, detected_things, "1.jpg")
                height, width = image.shape[:2]
 
                # Calculate the new dimensions (half of original)
                new_width = width 
                new_height = height 
                image=cv2.resize(image,(new_width,new_height))
                compressed_frame= zlib.compress(cv2.imencode(".jpg", image)[1])
                frame_bytes = base64.b64encode(compressed_frame).decode("utf-8")
                logger.debug("Finished drawing bounding boxes")
            except Exception as e:
                logger.error(f"Error in CV2 Operations: {e}")
                pass
                
            
            # Connect to Kafka producer and send message
            try:
                producer = KafkaProducer(bootstrap_servers=self.kafka_url)
            except Exception as e:
                logger.error(f"Error in connecting to Kafka instance: {e}")
                pass
            message = {"sessionId": sessionId, "image_byte": frame_bytes, "manualId": manualId}
            try:
                producer.send(self.video_details_kafka_topic+sessionId, value=json.dumps(message).encode("utf-8"))
            except Exception as e:
                logger.error(f"Error in writing to Kafka topic {self.video_details_kafka_topic+sessionId}: {e}")
                pass
            # Assign task based on detections
            
            lag=self.get_lag(sourceId,sessionId)
            if lag<=0:

                task,map = self.assign_task(things_present, sourceId, sessionId, manualId)

                if task is not None:

                    document = self.monualCollection.find_one({"_id": int(manualId)})
                    steps = {step["_id"]: step["text"] for step in document["steps"][:-1]}
                    task_manager = TaskManager(steps=steps)                
                    print(f"The task number is: {task}") 
                    response = task_manager.get_next_step(sessionId, sourceId, task, manualId, frame_bytes,things_present,map)
                    logger.debug(f"Response from graph: {response}")


                    if response !=0 and response!=None:

                        self.add_lag(sourceId,sessionId,response)

                    logger.debug(f"Response from graph: {response}")
            else:

                self.reduce_lag(sourceId,sessionId)

            return 
                
        except Exception as e:
            logger.error(f"Error occurred: {e}")
            return e


    def send_every_instruction(self,sessionId,frame_bytes,manualId,sourceId,saved_detections,object_names,image_paths):

        # print("sending frames and instruction")
        # message = {"sessionId": sessionId, "image_byte": frame_bytes, "manualId": manualId}
        # try:
        #     self.producer.send(self.video_details_kafka_topic+sessionId, value=json.dumps(message).encode("utf-8"))
        # except Exception as e:
        #     print(f"Error in writing to Kafka topic {self.video_details_kafka_topic+sessionId}: {e}")
        #     pass
        try:
            data=self.sessionSteps.find_one({"sessionId":sessionId})
            if data==None:
                document = self.monualCollection.find_one({"_id": int(manualId)})
                steps = {step["_id"]: step["text"] for step in document["steps"][:-1]}
                task_manager = TaskManager(steps=steps)

                response = task_manager.get_next_step(sessionId, sourceId, 0, manualId, frame_bytes,[],{})

            if len(saved_detections) >= config.continuity and len(set(saved_detections)) == 1:
                response  = requests.post(config.t2v_endpoint, json={"text" : f"The object you picked is {object_names}", "gender": 0})
                data = json.loads(response.content.decode("utf-8"))
                message={
                        "sessionId": sessionId,
                        "videoUrl": "",
                        "audioUrl": data["file_path"],
                        "contextUrl": image_paths,
                        "contextType": "img",
                        "manualId": manualId,
                        "stepId": 1,
                        "step": f"The object you picked is {object_names}",
                        "status": "failed",
                        "repetition": 0,
                        "feedback": "",
                        "feedbackUrl": "",
                        "startTime": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00"),
                        "endTime": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00"),
                        }
                print(message)
                self.producer.send(config.video_instruction_kafka_topic,value=json.dumps(message).encode("utf-8"))
                self.remove_detection(sessionId) 
            elif len(set(saved_detections)) > 1:
                self.remove_detection(sessionId) 
        except Exception as e:
            print(e)
    def send_continues_system_updates(self,sessionId,manualId,result_apps,error_message):
        if error_message=="error":
            text_message="I think you are not sharing correct screen please check and share your system monitor screen"
        elif len(result_apps)==0:
            text_message="We are good to go everything is working fine, you can turn off your screenshare."
        else:
            apps_list=", ".join(result_apps)
            first_app=result_apps[0]
            text_message=f"{apps_list} are taking more memory please close those and try again." if len(result_apps)>1 else f"{first_app} is taking more memory please close it and try again."
        # response  = requests.post(config.t2v_endpoint, json={"text" : text_message, "gender": 0})
        # data = json.loads(response.content.decode("utf-8"))
        # message={
        #         "sessionId": sessionId,
        #         "videoUrl": "",
        #         "audioUrl": data["file_path"],
        #         "contextUrl": "",
        #         "contextType": "emt",
        #         "manualId": manualId,
        #         "stepId": 1,
        #         "step": text_message,
        #         "status": "failed",
        #         "repetition": 0,
        #         "feedback": "",
        #         "feedbackUrl": "",
        #         "startTime": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00"),
        #         "endTime": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00"),
        #         }
        agent_message={"responseMsg":text_message,"responseTo":"USER"}
        self.producer.send("frame-output-topic",key=sessionId.encode("utf-8"),value=json.dumps(agent_message).encode("utf-8"))

    def system_monitor_detection(self, file, sourceId, sessionId, manualId):
        try:
            print(sourceId, sessionId, manualId)
            self.store_detection("123", 0, sessionId)
            print(self.get_detection(sessionId),"_____________________continuety")
            if len(self.get_detection(sessionId))>3:
                self.remove_detection(sessionId) 
                return
            if len(self.get_detection(sessionId))!=1:
                return
            header,encoded=file.split(",",1)
            image_bytes = base64.b64decode(encoded)
            file = np.frombuffer(image_bytes, dtype=np.uint8)
            file = cv2.imdecode(file, cv2.IMREAD_COLOR)
            output = reader.readtext(file)

            # Extract relevant information
            result1 = [output[i][1] for i in range(len(output))]
            print(result1)
            apps = ["intellij idea","firefox", "chrome", "java", "teams","webpack","google chrome","postman","docker","terminal","brave browser","finder","code","microsoft teams","mysqlworkbench","Music"]
            app = ""
            memory_usage = ""
            error_message="error"
            result_apps=[]
            for i in range(len(result1)):
                for j in apps:
                    if j in result1[i].lower():
                        app=result1[i]
                        error_message="true"
                        break
                if app != "":
                    if result1[i] == "MB":
                        if "." in result1[i-1]:
                            if int(result1[i].split(".")[0])>400:
                                result_apps.append(app)
                        else:
                            if int(result1[i-1].split(" ")[0])>400:
                                result_apps.append(app)
                            
                        app=""
                    if result1[i][-2:]=="MB":
                        if "." in result1[i]:
                            if int(result1[i].split(".")[0])>400:
                                result_apps.append(app)
                        else:
                            if int(result1[i].split(" ")[0])>400:
                                result_apps.append(app)
                        app=""
                    if result1[i]=="GB" or result1[i][-2:]=="GB":
                        result_apps.append(app)
                        app=""
            result_apps=list(set(result_apps))
            with concurrent.futures.ThreadPoolExecutor(max_workers=1000) as executor:
                # Assign task based on detections
                executor.submit(self.send_continues_system_updates,sessionId,manualId,result_apps,error_message)
                return
        except Exception as e:
            print(e)



    def get_similar_image_detector(self, file, sourceId, sessionId, manualId):
        try:
            header,encoded=file.split(",",1)
            image_bytes = base64.b64decode(encoded)
            file = np.frombuffer(image_bytes, dtype=np.uint8)
            file = cv2.imdecode(file, cv2.IMREAD_COLOR)
            with torch.no_grad():
                inputs = self.processor(images=file, return_tensors="pt").to(self.device)
                outputs = self.similarmodel(**inputs)
        
            # print(sourceId)
            # Extract embeddings
            embeddings = outputs.last_hidden_state
            embeddings = embeddings.mean(dim=1)
            vector = embeddings.detach().cpu().numpy()
            vector = np.float32(vector)
            faiss.normalize_L2(vector)

            # Search the FAISS index
            index = faiss.read_index("vectordb/vector.index")
            # print(sessionId)
        
            d, i = index.search(vector, 1)
            # print(i)
            json_file_path = 'vectordb/images.json'

            # Load JSON data
            with open(json_file_path, 'r') as f:
                data = json.load(f)

            images=list(data.keys())
            # Retrieve image paths from the indices (assuming 'images' is a list of image paths)
            image_paths = images[i[0][0]]
            # Retrieve object names from the data dictionary
            object_names = data[image_paths]
            print(image_paths,object_names)
            if object_names!="No object":
                self.store_detection(sourceId, object_names, sessionId)
            saved_detections = self.get_detection(sessionId)
            
            compressed_frame= zlib.compress(cv2.imencode(".jpg", file)[1])
            frame_bytes = base64.b64encode(compressed_frame).decode("utf-8")
            print("starting thread")
            with concurrent.futures.ThreadPoolExecutor(max_workers=1000) as executor:
                # Assign task based on detections
                executor.submit(self.send_every_instruction,sessionId,frame_bytes,manualId,sourceId,saved_detections,object_names,image_paths)
                return
        
        except Exception as e:
            print("error is ",e)


    def assign_task(self, things_present, sourceId, sessionId,manualId):
        """Perform object detection on the provided image file."""
        try:
            
            # Load the YAML data from the file
            data=self.sessionSteps.find_one({"sessionId":sessionId})
            print(data)
            manual=self.monualCollection.find_one({"_id":int(manualId)})
            print(manual)
            print(things_present, sourceId, sessionId,manualId)
            map = {step['_id']: step['answer'] for step in manual['steps'] if 'answer' in step}
            if data==None:
                return 0,map
            # Define a function to create the mapping for a given source ID

            # Example usage:
              # Change this to the desired source ID
            map = {step['_id']: step['answer'] for step in manual['steps'] if 'answer' in step}
            print(map)


            things_present=list(set(things_present))
            print(things_present)


            matching_keys = filter(lambda key: map[key] == sorted(things_present), map)

            # Converting the filter object to a list and getting the first item
            task = next(matching_keys, -1)
            for i in matching_keys:
                print(i)
            print(f"======{things_present}========{matching_keys}=================={task}==========")
            # Store detections in MongoDB
            self.store_detection(sourceId, task, sessionId)
            # Retrieve detections from MongoDB
            saved_detections = self.get_detection(sessionId)
            print("1*"*10)

            if saved_detections:
                logger.debug(f"Retrieved detections from MongoDB: {saved_detections}")
            print("2*"*10)
            print(saved_detections,"-------------", config.continuity,"-------------",len(set(saved_detections)),sessionId)

            if len(saved_detections) == config.continuity and len(set(saved_detections)) == 1:
                print("in if cndition")
                self.remove_detection(sessionId)
                print("3*"*10)

                return task, map
            
            elif len(set(saved_detections)) > 1:
                print("in else cndition")

                self.remove_detection(sessionId)
                print("5*"*10)

                return None, map
            
            return None, map
 
        except Exception as e:
            print(e)
            traceback.print_exc()
            logger.error(f"Error occurred: {e}")
            return e
    def assign_current_task(self, things_present, sourceId, sessionId,manualId):
        """Perform object detection on the provided image file."""
        try:
            
            # Load the YAML data from the file
            data=self.sessionSteps.find_one({"sessionId":sessionId})

            manual=self.monualCollection.find_one({"_id":int(manualId)})

            map = {step['_id']: step['answer'] for step in manual['steps'] if 'answer' in step}
            if data==None:
                return 0,map
            # Define a function to create the mapping for a given source ID

            # Example usage:
              # Change this to the desired source ID
            map = {step['_id']: step['answer'] for step in manual['steps'] if 'answer' in step}
            # print(map)
            things_present=list(set(things_present))
            matching_keys = filter(lambda key: map[key] == sorted(things_present), map)
            # Converting the filter object to a list and getting the first item
            task = next(matching_keys, -1)

            return task,map
 
        except Exception as e:
            logger.error(f"Error occurred: {e}")
            return e


    def analyse_doc(self, file, sourceId, sessionId, manualId):
        try:
            self.store_detection(sourceId, 0, sessionId)
            if len(self.get_detection(sessionId))<=3:
                self.remove_detection(sessionId) 
                return
            header,encoded=file.split(",",1)
            image_bytes = base64.b64decode(encoded)
            file = np.frombuffer(image_bytes, dtype=np.uint8)
            file = cv2.imdecode(file, cv2.IMREAD_COLOR)
            output = reader.readtext(file)

            # Extract relevant information
            result1 = [output[i][1] for i in range(len(output))]
            print(result1)
            apps = ["intellij idea","firefox", "chrome", "java", "teams","webpack","google chrome","postman","docker","terminal","brave browser","finder","code","microsoft teams","musqlworkbench","Music"]
            app = ""
            memory_usage = ""
            result_apps=[]
            for i in range(len(result1)):
                if result1[i].lower() in apps:
                    app = result1[i]
                elif app != "":
                    if result1[i] == "MB":
                        if "." in result1[i-1]:
                            if int(result1[i].split(".")[0])>400:
                                result_apps.append(app)
                        else:
                            if int(result1[i-1].split(" ")[0])>400:
                                result_apps.append(app)
                            
                        app=""
                    if result1[i][-2:]=="MB":
                        if "." in result1[i]:
                            if int(result1[i].split(".")[0])>400:
                                result_apps.append(app)
                        else:
                            if int(result1[i].split(" ")[0])>400:
                                result_apps.append(app)
                        app=""
                    if result1[i]=="GB" or result1[i][-2:]=="GB":
                        result_apps.append(app)
                        app=""
            result_apps=list(set(result_apps))

            with concurrent.futures.ThreadPoolExecutor(max_workers=1000) as executor:
                # Assign task based on detections
                executor.submit(self.send_continues_system_updates,sessionId,manualId,result_apps)
                return
        except Exception as e:
            print(e)


