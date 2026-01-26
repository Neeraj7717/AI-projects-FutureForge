import base64
import datetime
import os
import json
import logging
import traceback
import faiss
import zlib
import numpy as np
import requests
import pymongo
import torch
import yaml
import easyocr
import redis
from kafka import KafkaProducer
from ultralytics import YOLO
from utils.cv2Operations import cv2_operations
from Config.settings import Settings
from instruction.instructions_graph import TaskManager
import cv2
import concurrent.futures
from transformers import AutoImageProcessor, AutoModel
from utils.eizen_utils.logger_utils.logger_operations import LoggerOperations
from utils.eizen_utils.dms_utils.file_operations import FileOperations
from utils.semantic_similarity import SentenceSimilarityCalculator
from model.sop_manager import sop_manager

config = Settings()
file_ops = FileOperations()

detection_logger = LoggerOperations(logger_name='Detections', log_level=logging.INFO, use_log_file=False)

reader = easyocr.Reader(['en'])

 
class Detections:
    """Class for performing object detection and assigning tasks based on detections."""
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Detections, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize object detection model and other necessary parameters."""
        if not self._initialized:
            detection_logger.info("Starting model initialization...")
            with open('Config/viaconfig.yaml', 'r') as file:
                self.data = yaml.safe_load(file)

            detection_logger.info("Loading YOLO base model...")
            self.model_path = config.path_of_model
            self.model = YOLO(self.model_path, "v8")
            self.frames_path = config.frames_path
            self.kafka_url = config.kafka_url
            
            detection_logger.info("Loading EKYC model...")
            self.ekycmodel=YOLO(config.path_of_ekyc_model, "v8")
            
            detection_logger.info("Loading Chair model...")
            self.chairmodel=YOLO(config.path_of_chair_model,"v8")
            self.video_details_kafka_topic = config.video_details_kafka_topic
            self.shared_path = config.shared_path
            self.client = pymongo.MongoClient(config.mongo_connection_string_stateless)  # Connect to MongoDB
            self.db1 = self.client["analytics_ldev"]
            self.monualCollection=self.db1["manual"]
            self.sessionSteps=self.db1["sessionSteps"]
            self.contextCollection=self.db1["contexts"]
            self.producer=KafkaProducer(bootstrap_servers=config.kafka_url)
            self.fps = config.fps
            detection_logger.info("Loading DINOv2 model...")
            self.device = torch.device('cuda' if torch.cuda.is_available() else "cpu")
            self.processor = AutoImageProcessor.from_pretrained('facebook/dinov2-small')
            self.similarmodel = AutoModel.from_pretrained('facebook/dinov2-small').to(self.device)

            detection_logger.info("Initializing TaskManager...")
            self.task_manager = TaskManager()

            detection_logger.info("Initializing Redis client...")
            self.redis_client = redis.Redis(host=config.redis_host, port=config.redis_port, db=config.redis_db)

            self._initialized = True
            detection_logger.info("All models loaded successfully!")
            self.semanticSimilarity = SentenceSimilarityCalculator()
        
    def get_manual_name(self,manual_id):
        for model in self.data['models']:
            for manual in model['manuals']:
                if manual_id in manual['ids']:
                    return manual['name']
        return None

    def store_detection(self, sourceId, task, sessionId, manualId):
        """Store or update detections in Redis."""
        key = f"via:{sessionId}:{manualId}:{sourceId}:detections"
        existing_tasks = self.redis_client.get(key)

        if existing_tasks:
            updated_tasks = json.loads(existing_tasks)
            if isinstance(updated_tasks, dict):
                updated_tasks = updated_tasks.get("tasks", [])
            elif not isinstance(updated_tasks, list):
                updated_tasks = []
            updated_tasks.append(task)
            self.redis_client.set(key, json.dumps({"tasks": updated_tasks}))
        else:
            data = {"tasks": [task]}
            self.redis_client.set(key, json.dumps(data))
            
    def reduce_lag(self, sessionId, manualId):
        """Reduce lag in Redis."""
        key = f"vip:{sessionId}:{manualId}:lag"
        if not self.redis_client.exists(key):
            self.redis_client.set(key, 0)
        else:
            value = int(self.redis_client.get(key))
            self.redis_client.set(key, max(0, value - 1))
            detection_logger.info(f"Lag: {value - 1} =====================================")

            
    def add_lag(self, sessionId, manualId, time):
        """Add lag in Redis."""
        key = f"vip:{sessionId}:{manualId}:lag"
        time = time * self.fps
        self.redis_client.set(key, time)

    def get_detection(self, sessionId, manualId, sourceId):
        """Retrieve tasks from Redis."""
        key = f"via:{sessionId}:{manualId}:{sourceId}:detections"
        existing_tasks = self.redis_client.get(key)
        if existing_tasks:
            return json.loads(existing_tasks)["tasks"]
        else:
            return None

    def get_lag(self, sessionId, manualId):
        """Retrieve lag from Redis."""
        key = f"vip:{sessionId}:{manualId}:lag"
        if self.redis_client.exists(key):
            return int(self.redis_client.get(key))
        else:
            self.redis_client.set(key, 0)
            return 0

    def remove_detection(self, sessionId, manualId, sourceId):
        """Remove detections from Redis."""
        key = f"via:{sessionId}:{manualId}:{sourceId}:detections"
        self.redis_client.delete(key)
    
    def send_instruction(self,xyxy,new_width,new_height,sourceId,sessionId,manualId,things_present):
        xyxy=xyxy.tolist()
        key_component=sessionId.encode('utf-8') 
        message = {"sessionId": sessionId, "classes": things_present, "coordinates": list(xyxy),"frameDimensions":[new_width,new_height]}
        try:
            self.producer.send("vip-bounding-box-details",key=key_component, value=json.dumps(message).encode("utf-8"))
            
        except Exception as e:
            detection_logger.error(f"Error sending message: {str(e)}")
            traceback.print_exc()
            pass
        
        log_data = {
            "sessionId": sessionId,
            "manualId": manualId,
            "sourceId": sourceId,
            "thingsPresent": things_present
        }
        detection_logger.info(f"Detection data: {json.dumps(log_data)}")
        detection_logger.info("Processing detections with Python implementation")

        lag = self.get_lag(sessionId, manualId)
        if lag <= 0:
            task, map = self.assign_task(things_present, sourceId, sessionId, manualId)

            if task is not None:
                document = self.monualCollection.find_one({"_id": int(manualId)})
                steps = {step["_id"]: step["text"] for step in document["steps"][:-1]}
                detection_logger.info(f"The task number is: {task}")
                response = self.task_manager.get_next_step(sessionId, sourceId, task, manualId, "", things_present, map, steps)
                detection_logger.debug(f"Response from graph: {response}")

                if response != 0 and response != None:
                    self.add_lag(sessionId, manualId, response)

                detection_logger.debug(f"Response from graph: {response}")
        else:
            self.reduce_lag(sessionId, manualId)

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
            try:
                _,encoded=file.split(",",1)
                image_bytes = base64.b64decode(encoded)
                file = np.frombuffer(image_bytes, dtype=np.uint8)
                file = cv2.imdecode(file, cv2.IMREAD_COLOR)
                detection_output = self.ekycmodel.predict(source=file, conf=0.25, save=False)   
            except Exception as e:
                detection_logger.info("ERROR",e)
                traceback.print_exc()
                
            dic = vars(detection_output[0])
            names = dic["names"]
            detection_logger.debug(f"Model class names: {names}")
            detected_class = dic["boxes"].cpu().numpy()
            things_present = [names[name] for name in detected_class.cls]
            detection_logger.debug(f"The Detections are {things_present}")
            a = detection_output[0].boxes
            xyxy = a.xyxy.cpu().numpy()
            new_height, new_width = file.shape[:2]

            with concurrent.futures.ThreadPoolExecutor(max_workers=1000) as executor:
                # Assign task based on detections
                executor.submit(self.send_instruction(xyxy,new_width,new_height,sourceId,sessionId,manualId,things_present))
                return

            
                
        except Exception as e:
            detection_logger.error(f"Error occurred: {e}")
            traceback.print_exc()
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
            detection_logger.info("ACTION DETECTOR")
            # Perform object detection
            _,encoded=file.split(",",1)
            image_bytes = base64.b64decode(encoded)
            file = np.frombuffer(image_bytes, dtype=np.uint8)
            # Decode the numpy array to an image
            file = cv2.imdecode(file, cv2.IMREAD_COLOR)
            detection_output = self.model.predict(source=file, conf=0.25, save=False)   
            dic = vars(detection_output[0])
            names = dic["names"]
            detected_class = dic["boxes"].cpu().numpy()
            things_present = [names[name] for name in detected_class.cls]
            detection_logger.debug(f"The Detections are {things_present}")
            a = detection_output[0].boxes
            xyxy = a.xyxy.cpu().numpy()
            cls_ids = a.cls.cpu().numpy()  # Get class IDs for each box
            new_height, new_width = file.shape[:2]
            detection_logger.info("Completed Detection")

            # Execute SOP after detections
            self._execute_sop_after_action_detection(
                sourceId, sessionId, manualId, xyxy, cls_ids, names, new_width, new_height
            )

            with concurrent.futures.ThreadPoolExecutor(max_workers=1000) as executor:
                # Assign task based on detections
                executor.submit(self.send_instruction(xyxy,new_width,new_height,sourceId,sessionId,manualId,things_present))
                return
                
        except Exception as e:
            detection_logger.info(f"Error: {str(e)}")
            detection_logger.error(f"Error occurred: {e}")
            traceback.print_exc()

            return e

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
        file_path = None
        try:
            local_store_path = file.split('/')[-1]
            file_path = file_ops.download_file(
                cloud_path=file,
                local_file_name=local_store_path,
                local_folder="temp"
            )
            detection_logger.info(f"Downloaded file: {file_path}")
            # Perform object detection
            modelname=self.get_manual_name(int(manualId))
            if modelname=="phone":
                detection_output = self.model.predict(source=file_path, conf=0.25, save=False)
            elif modelname=="ekyc":
                detection_output = self.ekycmodel.predict(source=file_path, conf=0.25, save=False)
            elif modelname=="chair":
                detection_output = self.chairmodel.predict(source=file_path, conf=0.25, save=False)
            elif modelname=="similar":
                image = cv2.imread(file_path)
                with torch.no_grad():
                    inputs = self.processor(images=image, return_tensors="pt").to(self.device)
                    outputs = self.similarmodel(**inputs)
                embeddings = outputs.last_hidden_state
                embeddings = embeddings.mean(dim=1)
                vector = embeddings.detach().cpu().numpy()
                vector = np.float32(vector)
                faiss.normalize_L2(vector)
            
                # Search the FAISS index
                if manualId!="16":
                    index = faiss.read_index("vectordb/vector.index")
                    _, i = index.search(vector, 1)
                    detection_logger.info(f"Found similar image at index: {i}")
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
                    _, i = index.search(vector, 1)
                    detection_logger.info(f"Found similar image at index: {i}")
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

                try:
                    task,map = self.assign_current_task([], sourceId, sessionId,manualId)
                except:
                    map={}
                response = self.task_manager.get_next_step(sessionId, sourceId, 0, manualId, "image_bytes",[],map, steps)
                return

            dic = vars(detection_output[0])
            names = dic["names"]
            detected_class = dic["boxes"].cpu().numpy()
            things_present = [names[name] for name in detected_class.cls]
            detection_logger.debug(f"The Detections are {things_present}")



            task,map = self.assign_current_task(things_present, sourceId, sessionId,manualId)
            if task is not None:
                document = self.monualCollection.find_one({"_id": int(manualId)})

                steps = {step["_id"]: step["text"] for step in document["steps"][:-1]}

                response = self.task_manager.get_next_step(sessionId, sourceId, task, manualId, "image_bytes",things_present,map, steps)

                if response !=0 and response != None:
                    self.add_lag(sessionId,manualId,response)
                detection_logger.debug(f"Response from graph: {response}")
                return things_present, response
            
            return things_present
                
        except Exception as e:
            detection_logger.error(f"Error occurred: {e}")
            traceback.print_exc()
            return e

        finally:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    detection_logger.info(f"Cleaned up downloaded file: {file_path}")
                except Exception as e:
                    detection_logger.error(f"Error removing file {file_path}: {e}") 
    
    def send_first_instruction(self,sessionId,frame_bytes,manualId,sourceId):
        # Assign task based on detections
        data=self.sessionSteps.find_one({"sessionId":sessionId})
        if data==None:
            document = self.monualCollection.find_one({"_id": int(manualId)})
            steps = {step["_id"]: step["text"] for step in document["steps"][:-1]}

            self.task_manager.get_next_step(sessionId, sourceId, 0, manualId, frame_bytes,[],{}, steps)
        

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
            _,encoded=file.split(",",1)
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
                detection_logger.debug("Finished drawing bounding boxes")
            except Exception as e:
                traceback.print_exc()
                detection_logger.error(f"Error in CV2 Operations: {e}")
                pass
                
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=1000) as executor:
                # Assign task based on detections
                executor.submit(self.send_first_instruction(sessionId,frame_bytes,manualId,sourceId))
                return



        except Exception as e:
            detection_logger.error(f"Error occurred: {e}")
            traceback.print_exc()
            return e
 


    def text_detector(self,file, sourceId, sessionId, manualId):

        try:
            answer=self.monualCollection.find_one({"_id":int(manualId)})
            detection_logger.info("======================")
            if len(answer["steps"])>1:
                print(sessionId)
                data=self.sessionSteps.find_one({"sessionId":sessionId})
                print(data)
                current_question=data['steps'][-1]["stepId"]
                for i in answer["steps"]:
                    detection_logger.info(f"Current question: {int(current_question)}, ID: {i['_id']}")
                    similarity, _ = self.semanticSimilarity.calculate_similarity(
                        i["answer"], file
                    )

                    if int(current_question)==i["_id"]:
                        document = self.monualCollection.find_one({"_id": int(manualId)})
                        steps = {step["_id"]: step["text"] for step in document["steps"][:-1]}
                        if similarity>0.9:

                            detection_logger.info("ssssstttttaaaarrrrttt")
                            response = self.task_manager.get_next_step(sessionId, sourceId, i["_id"], manualId, "frame_bytes",[],{}, steps)
                            return
                        else:

                            detection_logger.info("ffffaaaaiiilllleedddd")
                            response = self.task_manager.get_next_step(sessionId, sourceId, -1, manualId, "frame_bytes",["text_based_model"],{}, steps)
                            return
            else:
                context=self.contextCollection.find_one({"manualId":manualId})["context"]
                try:
                    response1  = requests.post(config.context_based_question_answer, json={
                                                                            "context": context,
                                                                            "question": file
                                                                            })
                    response1 = json.loads(response1.content.decode("utf-8"))
                    detection_logger.info("Generated Answer:", response1["answer"])
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
                    detection_logger.info("======")
                except Exception as e:
                    traceback.print_exc()
                    detection_logger.info(f"Error: {e}")


        except Exception as e:
            traceback.print_exc()
            detection_logger.info(f"Error: {e}")
            

        
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
            _,encoded=file.split(",",1)
            image_bytes = base64.b64decode(encoded)
            file = np.frombuffer(image_bytes, dtype=np.uint8)
            file = cv2.imdecode(file, cv2.IMREAD_COLOR)
            detection_output = self.chairmodel.predict(source=file, conf=0.25, save=False)   
            dic = vars(detection_output[0])
            names = dic["names"]
            detected_class = dic["boxes"].cpu().numpy()
            things_present = [names[name] for name in detected_class.cls]
            detected_things=things_present[:]
            detection_logger.info(f"================={things_present}")
            try:
                response  = requests.post(config.action_detection_api, json={"file" : frame_bytes, "sourceId":sourceId,"sessionId": sessionId,"manualId" :manualId})
                data = json.loads(response.content.decode("utf-8"))
                things_present+=data
            except Exception as e:
                detection_logger.info(f"Error: {e}")
                traceback.print_exc()

            detection_logger.debug(f"The Detections are {things_present}")
            a = detection_output[0].boxes
            xyxy = a.xyxy.cpu().numpy()
        

 
            try:
                image = cv2_operations().draw_bounding_boxes(file, xyxy, detected_things, "1.jpg")
                height, width = image.shape[:2]
                new_width = width 
                new_height = height 
                image=cv2.resize(image,(new_width,new_height))
                compressed_frame= zlib.compress(cv2.imencode(".jpg", image)[1])
                frame_bytes = base64.b64encode(compressed_frame).decode("utf-8")
                detection_logger.debug("Finished drawing bounding boxes")
            except Exception as e:
                traceback.print_exc()
                detection_logger.error(f"Error in CV2 Operations: {e}")
                pass
                
            
            # Send message using existing producer (avoid creating new producers)
            message = {"sessionId": sessionId, "image_byte": frame_bytes, "manualId": manualId}
            try:
                self.producer.send(self.video_details_kafka_topic+sessionId, value=json.dumps(message).encode("utf-8"))
            except Exception as e:
                traceback.print_exc()
                detection_logger.error(f"Error in writing to Kafka topic {self.video_details_kafka_topic+sessionId}: {e}")
                pass
            # Assign task based on detections

            lag=self.get_lag(sessionId,manualId)
            if lag<=0:

                task,map = self.assign_task(things_present, sourceId, sessionId,manualId)

                if task is not None:

                    document = self.monualCollection.find_one({"_id": int(manualId)})
                    steps = {step["_id"]: step["text"] for step in document["steps"][:-1]}
                    detection_logger.info(f"The task number is: {task}")
                    response = self.task_manager.get_next_step(sessionId, sourceId, task, manualId, frame_bytes,things_present,map, steps)
                    detection_logger.debug(f"Response from graph: {response}")


                    if response !=0 and response!=None:

                        self.add_lag(sessionId,manualId,response)

                    detection_logger.debug(f"Response from graph: {response}")
            else:

                self.reduce_lag(sessionId,manualId)

            return 
                
        except Exception as e:
            traceback.print_exc()
            detection_logger.error(f"Error occurred: {e}")
            return e


    def send_every_instruction(self,sessionId,frame_bytes,manualId,sourceId,saved_detections,object_names,image_paths):
        try:
            data=self.sessionSteps.find_one({"sessionId":sessionId})
            try:
                if data==None:
                    document = self.monualCollection.find_one({"_id": int(manualId)})
                    steps = {step["_id"]: step["text"] for step in document["steps"][:-1]}

                    response = self.task_manager.get_next_step(sessionId, sourceId, 0, manualId, frame_bytes,[],{}, steps)
            except Exception as e:
                detection_logger.info(f"error in sending first instruction: {e}")
                traceback.print_exc()

            if saved_detections and len(saved_detections) >= config.continuity and len(set(saved_detections)) == 1:
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
                self.producer.send(config.video_instruction_kafka_topic,value=json.dumps(message).encode("utf-8"))
                self.remove_detection(sessionId, manualId, sourceId)
            elif saved_detections and len(set(saved_detections)) > 1:
                self.remove_detection(sessionId, manualId, sourceId) 
        except Exception as e:
            detection_logger.info(f"Error: {e}")
            traceback.print_exc()
            return e
    def send_continues_system_updates(self,sessionId,_manualId,result_apps,error_message):
        if error_message=="error":
            text_message="I think you are not sharing correct screen please check and share your system monitor screen"
        elif len(result_apps)==0:
            text_message="We are good to go everything is working fine, you can turn off your screenshare."
        else:
            apps_list=", ".join(result_apps)
            first_app=result_apps[0]
            text_message=f"{apps_list} are taking more memory please close those and try again." if len(result_apps)>1 else f"{first_app} is taking more memory please close it and try again."
        agent_message={"responseMsg":text_message,"responseTo":"USER"}
        self.producer.send("frame-output-topic",key=sessionId.encode("utf-8"),value=json.dumps(agent_message).encode("utf-8"))

    def system_monitor_detection(self, file, _sourceId, sessionId, manualId):
        try:
            self.store_detection("123", 0, sessionId, manualId)
            detections = self.get_detection(sessionId, manualId, "123")
            if detections and len(detections)>3:
                self.remove_detection(sessionId, manualId, "123")
                return
            if not detections or len(detections)!=1:
                return
            _,encoded=file.split(",",1)
            image_bytes = base64.b64decode(encoded)
            file = np.frombuffer(image_bytes, dtype=np.uint8)
            file = cv2.imdecode(file, cv2.IMREAD_COLOR)
            output = reader.readtext(file)

            # Extract relevant information
            result1 = [output[i][1] for i in range(len(output))]
            apps = ["intellij idea","firefox", "chrome", "java", "teams","webpack","google chrome","postman","docker","terminal","brave browser","finder","code","microsoft teams","mysqlworkbench","Music"]
            app = ""
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
            detection_logger.info(f"Error: {e}")
            traceback.print_exc()
            return e



    def get_similar_image_detector(self, file, sourceId, sessionId, manualId):
        try:
            _,encoded=file.split(",",1)
            image_bytes = base64.b64decode(encoded)
            file = np.frombuffer(image_bytes, dtype=np.uint8)
            file = cv2.imdecode(file, cv2.IMREAD_COLOR)
            with torch.no_grad():
                inputs = self.processor(images=file, return_tensors="pt").to(self.device)
                outputs = self.similarmodel(**inputs)

            # Extract embeddings
            embeddings = outputs.last_hidden_state
            embeddings = embeddings.mean(dim=1)
            vector = embeddings.detach().cpu().numpy()
            vector = np.float32(vector)
            faiss.normalize_L2(vector)

            # Search the FAISS index
            index = faiss.read_index("vectordb/vector.index")


            _, i = index.search(vector, 1)
            json_file_path = 'vectordb/images.json'

            # Load JSON data
            with open(json_file_path, 'r') as f:
                data = json.load(f)

            images=list(data.keys())
            # Retrieve image paths from the indices (assuming 'images' is a list of image paths)
            image_paths = images[i[0][0]]
            # Retrieve object names from the data dictionary
            object_names = data[image_paths]
            if object_names!="No object":
                self.store_detection(sourceId, object_names, sessionId, manualId)
            saved_detections = self.get_detection(sessionId, manualId, sourceId)
            
            compressed_frame= zlib.compress(cv2.imencode(".jpg", file)[1])
            frame_bytes = base64.b64encode(compressed_frame).decode("utf-8")
            detection_logger.info("starting thread")
            with concurrent.futures.ThreadPoolExecutor(max_workers=1000) as executor:
                # Assign task based on detections
                executor.submit(self.send_every_instruction,sessionId,frame_bytes,manualId,sourceId,saved_detections,object_names,image_paths)
                return
        
        except Exception as e:
            traceback.print_exc()
            detection_logger.info("error is ",e)


    def assign_task(self, things_present, sourceId, sessionId,manualId):
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

            things_present=list(set(things_present))
            matching_keys = filter(lambda key: map[key] == sorted(things_present), map)
            # Converting the filter object to a list and getting the first item
            task = next(matching_keys, -1)

            # Store detections in Redis
            self.store_detection(sourceId, task, sessionId, manualId)
            # Retrieve detections from Redis
            saved_detections = self.get_detection(sessionId, manualId, sourceId)
            if saved_detections:
                detection_logger.debug(f"Retrieved detections from Redis: {saved_detections}")

                if len(saved_detections) == config.continuity and len(set(saved_detections)) == 1:
                    self.remove_detection(sessionId, manualId, sourceId)
                    return task, map
                elif len(set(saved_detections)) > 1:
                    self.remove_detection(sessionId, manualId, sourceId)
                    return None, None

            # Not enough detections yet, return None
            return None, None

        except Exception as e:
            traceback.print_exc()
            detection_logger.error(f"Error occurred: {e}")
            return None, None
    
    def _execute_sop_after_action_detection(self, sourceId, sessionId, manualId, xyxy, cls_ids, names, width, height):
        """
        Execute SOP unified executor after action detection.
        Converts YOLO detection results to SOP format.
        
        Args:
            sourceId: Source identifier
            manualId: Manual identifier
            xyxy: Bounding boxes from YOLO (numpy array) - shape: [N, 4]
            cls_ids: Class IDs for each box (numpy array) - shape: [N]
            names: Dictionary mapping class IDs to names
            width: Image width
            height: Image height
        """
        try:
            import time as time_module
            
            # Convert YOLO detections to SOP format
            # SOP expects: Dict[str, List[List[float]]] where each list is [x1, y1, x2, y2]
            detections = {}
            things_present = []
            
            if xyxy is not None and len(xyxy) > 0:
                # Group detections by class name
                for i, box in enumerate(xyxy):
                    # box is [x1, y1, x2, y2] in pixel coordinates
                    # Convert to list format
                    box_list = box.tolist() if hasattr(box, 'tolist') else list(box)
                    
                    # Get class name for this detection using class ID
                    if i < len(cls_ids):
                        cls_id = int(cls_ids[i])
                        class_name = names.get(cls_id, f"Class_{cls_id}")
                    else:
                        class_name = "Unknown"
                    
                    # Track unique classes
                    if class_name not in things_present:
                        things_present.append(class_name)
                    
                    # Add to detections dict
                    if class_name not in detections:
                        detections[class_name] = []
                    detections[class_name].append(box_list)
            
            # Execute SOP
            sop_result = sop_manager.execute_sop(
                sourceId=sourceId,
                manualId=str(manualId),
                detections=detections,
                frame_number=0,  # Frame number not available here, can be passed if needed
                timestamp=str(time_module.time()),
                additional_data={
                    "things_present": things_present,
                    "image_width": width,
                    "image_height": height,
                    "detected_classes": things_present,
                    "sessionId": sessionId
                }
            )
            
            if sop_result:
                detection_logger.debug(f"SOP executed: activity={sop_result.get('current_activity')}, "
                                    f"cycle={sop_result.get('cycle_count')}, "
                                    f"success={sop_result.get('success')}")
                
        except Exception as e:
            detection_logger.debug(f"SOP execution skipped or failed: {e}")
            # Don't raise - SOP is optional and shouldn't break detection flow
    def assign_current_task(self, things_present, _sourceId, sessionId,manualId):
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

            things_present=list(set(things_present))
            matching_keys = filter(lambda key: map[key] == sorted(things_present), map)
            # Converting the filter object to a list and getting the first item
            task = next(matching_keys, -1)

            return task, map

        except Exception as e:
            traceback.print_exc()
            detection_logger.error(f"Error occurred: {e}")
            return None, None


    def analyse_doc(self, file, sourceId, sessionId, manualId):
        try:
            self.store_detection(sourceId, 0, sessionId, manualId)
            detections = self.get_detection(sessionId, manualId, sourceId)
            if detections and len(detections)<=3:
                self.remove_detection(sessionId, manualId, sourceId)
                return
            _,encoded=file.split(",",1)
            image_bytes = base64.b64decode(encoded)
            file = np.frombuffer(image_bytes, dtype=np.uint8)
            file = cv2.imdecode(file, cv2.IMREAD_COLOR)
            output = reader.readtext(file)

            # Extract relevant information
            result1 = [output[i][1] for i in range(len(output))]

            apps = ["intellij idea","firefox", "chrome", "java", "teams","webpack","google chrome","postman","docker","terminal","brave browser","finder","code","microsoft teams","musqlworkbench","Music"]
            app = ""
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
            traceback.print_exc()
            detection_logger.info(f"Error: {e}")
            return e


