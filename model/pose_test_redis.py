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
from utils.pose_analytics_feedback_redis import analyze_live_squat
from instruction.instructions_graph_redis import TaskManager
import redis

# Connect to Redis
redis_client = redis.Redis(host='192.168.0.162', port=6379, db=0)

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
        self.sessionSteps = self.db1["sessionSteps"]
        self.monualCollection = self.db1["manual"]
        self.producer = KafkaProducer(bootstrap_servers=config.kafka_url)
        self.pose_model = pose.Pose(static_image_mode=True, min_detection_confidence=0.5)
        # Create a thread pool executor
        # Important: Adjust max_workers based on your CPU cores and workload.  Too many can hurt performance.
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=4) # Example: 4 workers
        self.fps = config.fps
        # Store manual data in a dictionary
        self.manual_data_cache = {}

    def reduce_lag_redis(self, sessionId, manualId):
        """Reduce lag in Redis by decrementing the value."""
        key = f"vip:{sessionId}:{manualId}:lag"
        if not redis_client.exists(key):  # Check if key exists
            redis_client.set(key, 0)  # Initialize lag to 0 if it doesn't exist
        else:
            value = int(redis_client.get(key))  # Ensure value is an integer
            redis_client.set(key, max(0, value - 1))  # Decrement lag but ensure it doesn't go below 0

    def add_lag_redis(self, sessionId, manualId, time):
        """Add lag in Redis."""
        key = f"vip:{sessionId}:{manualId}:lag"
        time = time * self.fps
        redis_client.set(key, time)  # Set the lag value directly

    def get_lag_redis(self, sessionId, manualId):
        """Retrieve lag from Redis."""
        key = f"vip:{sessionId}:{manualId}:lag"
        if redis_client.exists(key):
            return int(redis_client.get(key))  # Ensure the returned value is an integer
        else:
            redis_client.set(key, 0)  # Initialize lag to 0 if it doesn't exist
            return 0

    def store_detection_redis(self, sourceId, task, sessionId, manualId):
        """Store or update detections in Redis."""
        key = f"via:{sessionId}:{manualId}:{sourceId}:detections"
        existing_tasks = redis_client.get(key)

        if existing_tasks:
            # If tasks exist, append the new task
            updated_tasks = json.loads(existing_tasks)  # Load existing tasks from Redis
            if isinstance(updated_tasks, dict):
                updated_tasks = updated_tasks.get("tasks", [])  # Ensure it's a list
            elif not isinstance(updated_tasks, list):
                updated_tasks = []  # Initialize as an empty list if it's not a list
            updated_tasks.append(task)  # Append the new task
            redis_client.set(key, json.dumps({"tasks": updated_tasks}))  # Update the tasks in Redis
        else:
            # If no tasks exist, create a new list with the task
            data = {"tasks": [task]}
            redis_client.set(key, json.dumps(data))  # Store the new data in Redis

    def get_detection_redis(self, sessionId, manualId, sourceId):
        """Retrieve tasks from Redis."""
        key = f"via:{sessionId}:{manualId}:{sourceId}:detections"

        existing_tasks = redis_client.get(key)
        if existing_tasks:
            return json.loads(existing_tasks)["tasks"]
        else:
            return None

    def remove_detection_redis(self, sessionId, manualId, sourceId):
        """Remove detections from Redis."""
        key = f"via:{sessionId}:{manualId}:{sourceId}:detections"
        redis_client.delete(key)

    def assign_task(self, things_present, sourceId, sessionId, manualId):
        """Perform object detection on the provided image file."""
        try:
            # Load the YAML data from the file
            data = self.sessionSteps.find_one({"sessionId": sessionId})

            # Check if manual data is already cached
            if manualId not in self.manual_data_cache:
                manual = self.monualCollection.find_one({"_id": int(manualId)})
                self.manual_data_cache[manualId] = manual  # Cache the manual data

            manual = self.manual_data_cache[manualId]
            map = {step['_id']: step['answer'] for step in manual['steps'] if 'answer' in step}
            if data == None:
                return 0, map
            # Define a function to create the mapping for a given source ID
            # Example usage:
            # Change this to the desired source ID
            map = {step['_id']: step['answer'] for step in manual['steps'] if 'answer' in step}
            pose_logger.info(f"{sourceId}, {sessionId}, {manualId}")
            things_present = list(set(things_present))
            pose_logger.info(map)
            matching_keys = filter(lambda key: map[key] == sorted(things_present), map)

            # Converting the filter object to a list and getting the first item
            task = next(matching_keys, -1)
            pose_logger.info(task)
            # Store detections in MongoDB
            # self.store_detection(sourceId, task, sessionId)
            self.store_detection_redis(sourceId, task, sessionId, manualId)

            # Retrieve detections from MongoDB
            # saved_detections = self.get_detection(sessionId)
            saved_detections = self.get_detection_redis(sessionId, manualId, sourceId)
            pose_logger.info(f"-----------------{len(saved_detections)}, {saved_detections}--------------Detections")

            if saved_detections:
                pose_logger.debug(f"Retrieved detections from MongoDB: {saved_detections}")

            if len(saved_detections) == config.continuity and len(set(saved_detections)) == 1:
                # self.remove_detection(sessionId)
                self.remove_detection_redis(sessionId, manualId, sourceId)
                return task, map

            elif len(set(saved_detections)) > 1:
                self.remove_detection_redis(sessionId, manualId, sourceId)
                # self.remove_detection(sessionId)
                return None, map

            return None, map

        except Exception as e:
            traceback.print_exc()
            pose_logger.error(f"Error occurred: {e}")
            return None, None  # Return a tuple to avoid unpacking issues

    def send_instruction_pose(self, xyxy, new_width, new_height, sourceId, sessionId, manualId, things_present, keypoints=[]):
        try:
            xyxy = xyxy.tolist() if isinstance(xyxy, np.ndarray) else []
            key_component = sessionId.encode('utf-8')
            message = {"sessionId": sessionId, "classes": things_present, "coordinates": list(xyxy),
                       "frameDimensions": [new_width, new_height], "keyPoints": keypoints}
            pose_logger.debug(message)
            self.producer.send("vip-bounding-box-details", key=key_component,
                               value=json.dumps(message).encode("utf-8"))
            pose_logger.info("Message Sent from instruction")
        except Exception as e:
            pose_logger.error(f"Error sending message: {str(e)}")
            traceback.print_exc()

    # Handler for future results to avoid blocking
    def _handle_future_result(self, future):
        """Handle the result of a completed future."""
        try:
            # This retrieves the result and will raise any exceptions that occurred
            # during execution of the future
            future.result()
        except Exception as e:
            pose_logger.error(f"Error in asynchronous task: {e}")
            traceback.print_exc()

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
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            decode_time = time.time() - decode_start
            pose_logger.info(f"Image decoded in {decode_time:.3f}s")

            model_start = time.time()
            # Convert image to RGB for MediaPipe
            results = self.pose_model.process(rgb_image)
            model_finel_time = time.time() - model_start
            pose_logger.info(f"Model Process Time {model_finel_time:.3f}s")

            # Check if person is present
            person_present = results.pose_landmarks is not None

            things_present = []
            hand_status = "noHandsRaised"
            keypoint_data = {}

            if person_present:
                things_present.append("personPresent")
                hand_status, keypoint_data = self.detect_raised_hands(results.pose_landmarks, frame.shape)
                things_present.append(hand_status)

            futures = []  # List to hold future objects

            # Submit draw_annotations to run asynchronously
            future_draw = self.executor.submit(
                self.draw_annotations,
                frame,
                results.pose_landmarks,
                sourceId,
                sessionId,
                manualId,
                start_time
            )
            futures.append(future_draw)
            future_draw.add_done_callback(self._handle_future_result)

            # Submit instruction graph processing to run asynchronously
            future_process_squat_analysis = self.executor.submit(
                self.process_squat_analysis,
                sessionId,
                frame,
                things_present,
                sourceId,
                manualId,
                results
            )
            futures.append(future_process_squat_analysis)
            future_process_squat_analysis.add_done_callback(self._handle_future_result)

            # Wait for all futures to complete (optional, but good practice - REMOVE for true parallelism)
            # concurrent.futures.wait(futures)

            total_time = time.time() - start_time
            pose_logger.info(f"Main pose detection pipeline submitted tasks in {total_time:.3f}s.  Asynchronous tasks running...")

            # Return immediately without waiting for futures to complete
            return None

        except Exception as e:
            pose_logger.error(f"Error occurred in pose_detector: {e}")
            traceback.print_exc()
            return None

    def process_squat_analysis(self, sessionId, frame, things_present, sourceId, manualId, results):
        """Handle squat analysis in a separate thread"""
        try:
            overall_start_time = time.time()
            # document = self.stepcollection.find_one({"sessionId": sessionId})
            key = f"vip:{sessionId}:{manualId}:state"
            if redis_client.exists(key):
                # if document and 'current_step' in document:
                current_step = int(redis_client.get(key))

                pose_logger.info(f"{current_step}----------------------------------------------------------current step")
                pose_logger.info(f"{things_present}----------------------------------------------------------Things Present")

                if current_step > 2 and current_step < 6:

                    squat_start_time = time.time()
                    pose_logger.info(f"Starting analyze_live_squat at {squat_start_time}")

                    squats_result = analyze_live_squat(sessionId, manualId, frame, results)

                    squat_end_time = time.time()
                    squat_duration = squat_end_time - squat_start_time
                    pose_logger.info(f"analyze_live_squat completed in {squat_duration:.3f}s")
                    pose_logger.info(f"Result from squat analysis: {squats_result}")
                    # Create a copy of things_present to avoid race conditions
                    updated_things_present = things_present.copy()
                    updated_things_present.append(squats_result)
                    pose_logger.info(f"{updated_things_present}----------------------------------------------------------Things Present")
                    # Process the instruction graph with the updated things_present
                    self.instruction_graph(sourceId, sessionId, manualId, frame, updated_things_present)
                else:
                    # If not in squat step range, process with original things_present
                    self.instruction_graph(sourceId, sessionId, manualId, frame, things_present)
            else:
                # If no document or current_step, process with original things_present
                self.instruction_graph(sourceId, sessionId, manualId, frame, things_present)
        except Exception as e:
            pose_logger.error(f"{e}--------------------------------------------------------------------------------Squat Analysis Error")
            # Even if squat analysis fails, still process the frame
            self.instruction_graph(sourceId, sessionId, manualId, frame, things_present)

        overall_end_time = time.time()
        overall_duration = overall_end_time - overall_start_time
        pose_logger.info(f"Overall process_squat_analysis completed in {overall_duration:.3f}s")

    def instruction_graph(self, sourceId, sessionId, manualId, frame, things_present):
        try:
            instruction_start1 = time.time()

            # pose_logger.info(f"--------------------------------------------In side Graph Function 1")

            # lag = self.get_lag(sourceId, sessionId)
            lag = self.get_lag_redis(sessionId, manualId)
            if lag <= 0:
                pose_logger.info(f"-----------{lag}---------------{type(lag)}----------------Instruction Graph Function")
                pose_logger.info(things_present)
                task, map = self.assign_task(things_present, sourceId, sessionId, manualId)
                pose_logger.info(f"{task}------------------------------Task")
                instruction_time1 = time.time() - instruction_start1
                pose_logger.info(f"Analysis Task completed in {instruction_time1:.3f}s ---------------else")
                if task is not None:
                    # Use cached manual data
                    instruction_start2 = time.time()

                    manual = self.manual_data_cache[manualId]
                    steps = {step["_id"]: step["text"] for step in manual["steps"][:-1]}
                    task_manager = TaskManager(steps=steps)
                    pose_logger.info(f"The task number is: {task}")
                    response = task_manager.get_next_step(sessionId, sourceId, task, manualId, frame, things_present, map)
                    pose_logger.info(f"Response from graph: {response}---------{type(response)}")

                    if response != 0 and response is not None:
                        # self.add_lag(sourceId, sessionId)
                        self.add_lag_redis(sessionId, manualId, response)
                    instruction_time2 = time.time() - instruction_start2
                    pose_logger.info(f"Instruction analysis completed in {instruction_time2:.3f}s ---------------if")
            else:
                # self.reduce_lag(sourceId, sessionId)
                self.reduce_lag_redis(sessionId, manualId)

                instruction_time2 = time.time() - instruction_start1
                pose_logger.info(f"Instruction analysis completed in {instruction_time2:.3f}s ---------------else")

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
            draw_time = time.time()
            if not landmarks:
                return

            landmarks_points = []
            new_height, new_width = image.shape[:2]

            # Define connections for full body skeleton
            skeleton_connections = [
                # Face
                 (pose.PoseLandmark.LEFT_SHOULDER, pose.PoseLandmark.RIGHT_SHOULDER),
                (pose.PoseLandmark.RIGHT_SHOULDER, pose.PoseLandmark.RIGHT_ELBOW),
                (pose.PoseLandmark.RIGHT_ELBOW, pose.PoseLandmark.RIGHT_WRIST),
                (pose.PoseLandmark.LEFT_SHOULDER, pose.PoseLandmark.LEFT_ELBOW),
                (pose.PoseLandmark.LEFT_ELBOW, pose.PoseLandmark.LEFT_WRIST),
                
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
                (pose.PoseLandmark.LEFT_ANKLE, pose.PoseLandmark.LEFT_HEEL),
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
            final_draw_time = time.time() - draw_time
            total_time = time.time() - start_time
            print(datetime.now(), "---2")
            pose_logger.info(f"Pose Keypoints draw completed in {final_draw_time:.3f}s ------------------------------Final Time")
            pose_logger.info(f"Pose Keypoints Sent successfully completed in {total_time:.3f}s -------------------------------------------------------------------Final Time")

        except Exception as e:
            pose_logger.error(f"Error in draw_annotations: {e}")
            traceback.print_exc()