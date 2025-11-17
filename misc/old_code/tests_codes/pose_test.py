import base64
import json
import logging
import time
import traceback
import numpy as np
import pymongo
import cv2
from datetime import datetime
import mediapipe as mp
import concurrent.futures
from kafka import KafkaProducer
from Config.settings import Settings
from utils.pose_analytics import analyze_live_squat
from instruction.instructions_graph import TaskManager


pose = mp.solutions.pose

# Load configurations from settings
config = Settings()

# Create a unique logger for pose module
pose_logger = logging.getLogger('pose_module')
pose_logger.setLevel(logging.INFO)
pose_logger.propagate = False  # Prevent propagation to root logger

# Create formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Add a StreamHandler to the logger to output logs to the terminal
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
pose_logger.addHandler(console_handler)

class Pose:
    """Class for performing pose detection."""
 
    def __init__(self):
        """Initialize pose detection model."""
        self.client = pymongo.MongoClient(config.mongo_connection_string_stateless)  # Connect to MongoDB
        self.db = self.client[config.stateless_db]  # Use or create a database
        self.db1 = self.client[config.database_name]
        self.collection = self.db[config.stateless_collection_detections]
        self.lagcollection = self.db["lag"]
        self.stepcollection = self.db["state"]
        self.sessionSteps=self.db1["sessionSteps"]
        self.monualCollection=self.db1["manual"]
        self.producer = KafkaProducer(bootstrap_servers=config.kafka_url)
        self.pose_model = pose.Pose(static_image_mode=True, min_detection_confidence=0.5)
        # Create a single thread pool executor that can be reused
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=100)

    def reduce_lag(self, sourceId, sessionId):
        """Store or update detections in MongoDB."""
        # Check if the document with the given sourceId already exists
        existing_document = self.lagcollection.find_one({"sessionId": sessionId})
        
        pose_logger.info(f"{existing_document['lag']}=====================================")
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

    def add_lag(self, sourceId, sessionId, time):
        """Store or update detections in MongoDB."""
        # Check if the document with the given sourceId already exists
        existing_document = self.lagcollection.find_one({"sessionId": sessionId})
        pose_logger.info(f"{time}, {type(time)}")
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

    def get_lag(self, sourceId,sessionId):
        """Retrieve tasks from MongoDB."""
        data = self.lagcollection.find_one({"sessionId": sessionId})
        if data:
            return data["lag"]
        else:
            data = self.lagcollection.insert_one({"sessionId": sessionId,"lag":0})
            return 0


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


    def get_detection(self, sessionId):
        """Retrieve tasks from MongoDB."""
        data = self.collection.find_one({"sessionId": sessionId})
        if data:
            return data["tasks"]
        else:
            return None
        
    def remove_detection(self, sessionId):
        """Remove detections from MongoDB."""
        self.collection.delete_one({"sessionId": sessionId})
    


    def assign_task(self, things_present, sourceId, sessionId, manualId):
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
            pose_logger.info(f"{sourceId}, {sessionId}, {manualId}")
            things_present=list(set(things_present))
            pose_logger.info(map)
            matching_keys = filter(lambda key: map[key] == sorted(things_present), map)

            # Converting the filter object to a list and getting the first item
            task = next(matching_keys, -1)
            pose_logger.info(task)
            # Store detections in MongoDB
            self.store_detection(sourceId, task, sessionId)
            # Retrieve detections from MongoDB
            saved_detections = self.get_detection(sessionId)

            pose_logger.info(f"{len(saved_detections)}, {saved_detections}")

            if saved_detections:
                pose_logger.debug(f"Retrieved detections from MongoDB: {saved_detections}")


            if len(saved_detections) == config.pose_continuity and len(set(saved_detections)) == 1:
                self.remove_detection(sessionId)
                return task, map
            
            elif len(set(saved_detections)) > 1:
                self.remove_detection(sessionId)
                return None, map
            
            return None, map
 
        except Exception as e:
            traceback.print_exc()
            pose_logger.error(f"Error occurred: {e}")
            return e

    def send_instruction_pose(self, xyxy, new_width, new_height, sourceId, sessionId, manualId, things_present, keypoints=[]):
        try:
            xyxy = xyxy.tolist() if isinstance(xyxy, np.ndarray) else []
            key_component=sessionId.encode('utf-8') 
            message = {"sessionId": sessionId, "classes": things_present, "coordinates": list(xyxy), "frameDimensions":[new_width,new_height], "keyPoints":keypoints}
            pose_logger.debug(message)
            self.producer.send("vip-bounding-box-details", key=key_component, value=json.dumps(message).encode("utf-8"))
            pose_logger.info("Message Sent from instruction")
        except Exception as e:
            pose_logger.error(f"Error sending message: {str(e)}")
            traceback.print_exc()


    # def pose_detector(self, file, sourceId, sessionId, manualId):
    #     try:
    #         start_time = time.time()
    #         pose_logger.info("Starting pose detection...")
            
    #         # Decode base64 image
    #         decode_start = time.time()
    #         header, encoded = file.split(",", 1)
    #         image_bytes = base64.b64decode(encoded)
    #         np_arr = np.frombuffer(image_bytes, dtype=np.uint8)
    #         if np_arr is None or np_arr.size == 0:
    #             pose_logger.info("Empty image buffer")
    #             return None
    #         frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    #         decode_time = time.time() - decode_start
    #         pose_logger.info(f"Image decoded in {decode_time:.3f}s, shape: {frame.shape}")

    #         # Convert image to RGB for MediaPipe
    #         rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    #         results = self.pose_model.process(rgb_image)

    #         # Check if person is present
    #         person_present = results.pose_landmarks is not None

    #         things_present = []
    #         hand_status = "noHandsRaised"
    #         keypoint_data = {}

    #         if person_present:
    #             things_present.append("personPresent")
    #             hand_status, keypoint_data = self.detect_raised_hands(results.pose_landmarks, frame.shape)
    #             things_present.append(hand_status)

    #             # Submit draw_annotations to run asynchronously
    #             self.executor.submit(
    #                 self.draw_annotations, 
    #                 frame, 
    #                 results.pose_landmarks, 
    #                 sourceId, 
    #                 sessionId, 
    #                 manualId
    #             )

    #         squat_start = time.time()
    #         try:
    #             pose_logger.info("---------------------------------In document Getting")
    #             document = self.stepcollection.find_one({"sessionId": sessionId})
    #             pose_logger.info(document)
    #             if document:
    #                 # Check if 'current_step' field exists; if not, add it with a value of 1
    #                 if 'current_step' in document:
    #                     pose_logger.info(f"{document['current_step']}----------------------------------------------------------current step")
    #                     if document['current_step'] > 2 and document['current_step'] < 6:
    #                         squats_result = analyze_live_squat(sessionId, frame)
    #                         squat_time = time.time() - squat_start
    #                         pose_logger.info(f"Squat analysis completed in {squat_time:.3f}s")
    #                         pose_logger.info(squats_result)
    #                         things_present.append(squats_result)
    #         except Exception as e:
    #             pose_logger.error(f"{e}--------------------------------------------------------------------------------test Error")

    #         # Submit instruction_graph to run asynchronously
    #         self.executor.submit(
    #             self.instruction_graph, 
    #             sourceId, 
    #             sessionId, 
    #             manualId, 
    #             frame, 
    #             things_present
    #         )
            
    #         total_time = time.time() - start_time
    #         pose_logger.info(f"Total pose detection pipeline completed in {total_time:.3f}s---------------------------------Final Time")

    #     except Exception as e:
    #         pose_logger.error(f"Error occurred: {e}")
    #         traceback.print_exc()

    def pose_detector(self, file, sourceId, sessionId, manualId):
        try:
            print(datetime.now())
            start_time = time.time()
            pose_logger.info("Starting pose detection...")
            
            # Decode base64 image
            decode_start = time.time()
            header, encoded = file.split(",", 1)
            image_bytes = base64.b64decode(encoded)
            np_arr = np.frombuffer(image_bytes, dtype=np.uint8)
            if np_arr is None or np_arr.size == 0:
                pose_logger.info("Empty image buffer")
                return None
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            decode_time = time.time() - decode_start
            pose_logger.info(f"Image decoded in {decode_time:.3f}s, shape: {frame.shape}")

            # Convert image to RGB for MediaPipe
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
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

                # Submit draw_annotations to run asynchronously
                self.executor.submit(
                    self.draw_annotations, 
                    frame, 
                    results.pose_landmarks, 
                    sourceId, 
                    sessionId, 
                    manualId,
                    start_time
                )
            pose_results = results
            # Submit squat analysis to run asynchronously
            self.executor.submit(
                self.process_squat_analysis,
                sessionId,
                frame,
                things_present,
                sourceId,
                pose_results,
                manualId
            )
            
            total_time = time.time() - start_time
            pose_logger.info(f"Main pose detection pipeline completed in {total_time:.3f}s -------------------------------------------------------------------Final Time")

        except Exception as e:
            pose_logger.error(f"Error occurred: {e}")
            traceback.print_exc()

    def process_squat_analysis(self, sessionId, frame, things_present, sourceId, results, manualId):
        """Handle squat analysis in a separate thread"""        
        try:
            document = self.stepcollection.find_one({"sessionId": sessionId})
            if document and 'current_step' in document:
                current_step = document['current_step']
                pose_logger.info(f"{current_step}----------------------------------------------------------current step")
                pose_logger.info(f"{things_present}----------------------------------------------------------Things Present")
                
                if current_step > 2 and current_step < 6:
                    # Time the squat analysis
                    squat_start_time = time.time()
                    pose_logger.info(f"Starting analyze_live_squat at {squat_start_time}")
                    
                    squats_result = analyze_live_squat(sessionId, frame, results)
                    
                    squat_end_time = time.time()
                    squat_duration = squat_end_time - squat_start_time
                    pose_logger.info(f"analyze_live_squat completed in {squat_duration:.3f}s")
                    pose_logger.info(f"Result from squat analysis: {squats_result}")
                    
                    # Create a copy of things_present to avoid race conditions
                    updated_things_present = things_present.copy()
                    updated_things_present.append(squats_result)
                    pose_logger.info(f"{updated_things_present}----------------------------------------------------------Things Present")
                    
                    # Time the instruction graph execution
                   
                    
                    self.instruction_graph(sourceId, sessionId, manualId, frame, updated_things_present)
                
                else:
                    # If not in squat step range, time only instruction_graph
                    self.instruction_graph(sourceId, sessionId, manualId, frame, things_present)
            else:
                # If no document or current_step, time only instruction_graph
                self.instruction_graph(sourceId, sessionId, manualId, frame, things_present)
                
               
        
        except Exception as e:
            pose_logger.error(f"{e}--------------------------------------------------------------------------------Squat Analysis Error")
            traceback.print_exc()
            self.instruction_graph(sourceId, sessionId, manualId, frame, things_present)

        
        overall_end_time = time.time()
        overall_duration = overall_end_time - overall_start_time
        pose_logger.info(f"Overall process_squat_analysis completed in {overall_duration:.3f}s")

    def instruction_graph(self, sourceId, sessionId, manualId, frame, things_present):
        try:
            instruction_start = time.time()

            pose_logger.info(f"--------------------------------------------In side Graph Function 1")
            
            lag = self.get_lag(sourceId, sessionId)
            if lag <= 0:
                pose_logger.info(f"-----------{lag}---------------------------------In side Graph Function 1")

                pose_logger.info(things_present)
                task, map = self.assign_task(things_present, sourceId, sessionId, manualId)
                pose_logger.info(f"{task}------------------------------Task")
                if task is not None:
                    document = self.monualCollection.find_one({"_id": int(manualId)})
                    steps = {step["_id"]: step["text"] for step in document["steps"][:-1]}
                    task_manager = TaskManager(steps=steps)
                    pose_logger.info(f"The task number is: {task}")
                    response = task_manager.get_next_step(sessionId, sourceId, task, manualId, frame, things_present, map)
                    pose_logger.info(f"{response}0----------------------------------------------")
                    pose_logger.info(f"Response from graph: {response}")

                    if response != 0 and response is not None:
                        self.add_lag(sourceId, sessionId, response)

                    pose_logger.info(f"Response from graph: {response}")
                instruction_time1 = time.time() - instruction_start
                pose_logger.info(f"Instruction analysis completed in {instruction_time1:.3f}s ---------------if")
            else:
                self.reduce_lag(sourceId, sessionId)                
                instruction_time1 = time.time() - instruction_start
                pose_logger.info(f"Instruction analysis completed in {instruction_time1:.3f}s ---------------else")
                
        except Exception as e:
            pose_logger.error(f"Error in instruction_graph: {e}")
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



    def draw_annotations(self, image, landmarks, sourceId, sessionId, manualId, start_time):
        try:
            if not landmarks:
                return
            
            landmarks_points = []
            new_height, new_width = image.shape[:2]
            
            # Define connections for full body skeleton
            skeleton_connections = [
                # Face
                (pose.PoseLandmark.NOSE, pose.PoseLandmark.RIGHT_EYE_INNER),
                (pose.PoseLandmark.RIGHT_EYE_INNER, pose.PoseLandmark.RIGHT_EYE),
                (pose.PoseLandmark.RIGHT_EYE, pose.PoseLandmark.RIGHT_EYE_OUTER),
                (pose.PoseLandmark.NOSE, pose.PoseLandmark.LEFT_EYE_INNER),
                (pose.PoseLandmark.LEFT_EYE_INNER, pose.PoseLandmark.LEFT_EYE),
                (pose.PoseLandmark.LEFT_EYE, pose.PoseLandmark.LEFT_EYE_OUTER),
                (pose.PoseLandmark.RIGHT_EYE_OUTER, pose.PoseLandmark.RIGHT_EAR),
                (pose.PoseLandmark.LEFT_EYE_OUTER, pose.PoseLandmark.LEFT_EAR),
                (pose.PoseLandmark.MOUTH_RIGHT, pose.PoseLandmark.MOUTH_LEFT),

                # Upper body
                (pose.PoseLandmark.LEFT_SHOULDER, pose.PoseLandmark.RIGHT_SHOULDER),
                (pose.PoseLandmark.RIGHT_SHOULDER, pose.PoseLandmark.RIGHT_ELBOW),
                (pose.PoseLandmark.RIGHT_ELBOW, pose.PoseLandmark.RIGHT_WRIST),
                (pose.PoseLandmark.LEFT_SHOULDER, pose.PoseLandmark.LEFT_ELBOW),
                (pose.PoseLandmark.LEFT_ELBOW, pose.PoseLandmark.LEFT_WRIST),
                (pose.PoseLandmark.RIGHT_WRIST, pose.PoseLandmark.RIGHT_PINKY),
                (pose.PoseLandmark.RIGHT_WRIST, pose.PoseLandmark.RIGHT_INDEX),
                (pose.PoseLandmark.RIGHT_WRIST, pose.PoseLandmark.RIGHT_THUMB),
                (pose.PoseLandmark.LEFT_WRIST, pose.PoseLandmark.LEFT_PINKY),
                (pose.PoseLandmark.LEFT_WRIST, pose.PoseLandmark.LEFT_INDEX),
                (pose.PoseLandmark.LEFT_WRIST, pose.PoseLandmark.LEFT_THUMB),

                # Torso
                (pose.PoseLandmark.LEFT_SHOULDER, pose.PoseLandmark.LEFT_HIP),
                (pose.PoseLandmark.RIGHT_SHOULDER, pose.PoseLandmark.RIGHT_HIP),
                (pose.PoseLandmark.LEFT_HIP, pose.PoseLandmark.RIGHT_HIP),

                # Lower body
                (pose.PoseLandmark.RIGHT_HIP, pose.PoseLandmark.RIGHT_KNEE),
                (pose.PoseLandmark.RIGHT_KNEE, pose.PoseLandmark.RIGHT_ANKLE),
                (pose.PoseLandmark.LEFT_HIP, pose.PoseLandmark.LEFT_KNEE),
                (pose.PoseLandmark.LEFT_KNEE, pose.PoseLandmark.LEFT_ANKLE),
                (pose.PoseLandmark.RIGHT_ANKLE, pose.PoseLandmark.RIGHT_HEEL),
                (pose.PoseLandmark.RIGHT_HEEL, pose.PoseLandmark.RIGHT_FOOT_INDEX),
                (pose.PoseLandmark.LEFT_ANKLE, pose.PoseLandmark.LEFT_HEEL),
                (pose.PoseLandmark.LEFT_HEEL, pose.PoseLandmark.LEFT_FOOT_INDEX)
            ]

            pose_logger.info("Sending skeleton connections...")
            for connection in skeleton_connections:
                start_point = landmarks.landmark[connection[0]]
                end_point = landmarks.landmark[connection[1]]
                
                # Convert normalized coordinates to pixel coordinates
                start_x = int(start_point.x * image.shape[1])
                start_y = int(start_point.y * image.shape[0])
                end_x = int(end_point.x * image.shape[1])
                end_y = int(end_point.y * image.shape[0])

                landmarks_points.append([start_x, start_y, end_x, end_y])

            pose_logger.info(f"Total landmarks detected: {len(landmarks_points)}")
            
            # Send the instruction pose directly - no need for extra threading here
            self.send_instruction_pose([], new_width, new_height, sourceId, sessionId, manualId, [], landmarks_points)
            total_time = time.time() - start_time
            print(datetime.now(),"---2")

            pose_logger.info(f"Pose Keypoints Sent successfully completed in {total_time:.3f}s -------------------------------------------------------------------Final Time")
        
        except Exception as e:
            pose_logger.error(f"Error in draw_annotations: {e}")
            traceback.print_exc()