import json
import logging
import time
import traceback
import pymongo
import mediapipe as mp
import concurrent.futures
from kafka import KafkaProducer
from Config.settings import Settings
from instruction.instructions_graph import TaskManager
import redis
from utils.eizen_utils.logger_utils.logger_operations import LoggerOperations
from model.sop_manager import sop_manager


pose = mp.solutions.pose

config = Settings()

pose_logger = LoggerOperations(logger_name='PoseModel', log_level=logging.INFO, use_log_file=False)

class Pose:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Pose, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.client = pymongo.MongoClient(config.mongo_connection_string_stateless)
            self.db = self.client[config.stateless_db]
            self.db1 = self.client[config.database_name]
            self.collection = self.db[config.stateless_collection_detections]
            self.lagcollection = self.db["lag"]
            self.stepcollection = self.db["state"]
            self.sessionSteps = self.db1["sessionSteps"]
            self.monualCollection = self.db1["manual"]
            self.producer = KafkaProducer(bootstrap_servers=config.kafka_url)
            self.pose_model = pose.Pose(static_image_mode=False,
                                        model_complexity=1,
                                        smooth_landmarks=True,
                                        enable_segmentation=False,
                                        min_detection_confidence=0.4,
                                        min_tracking_confidence=0.2
                                    )
            self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
            self.fps = config.pose_fps
            self.task_manager = TaskManager()
            self.redis_client = redis.Redis(host=config.redis_host, port=config.redis_port, db=config.redis_db)
            self.manual_data_cache = {}
        self._initialized = True

    def close(self):
        self.client.close()
        self.executor.shutdown(wait=True)
        self.redis_client.close()
        self.task_manager.close()


    def reduce_lag_redis(self, sessionId, manualId):
        key = f"vip:{sessionId}:{manualId}:lag"
        if not self.redis_client.exists(key):
            self.redis_client.set(key, 0)
        else:
            value = int(self.redis_client.get(key))
            self.redis_client.set(key, max(0, value - 1))

    def add_lag_redis(self, sessionId, manualId, time):
        key = f"vip:{sessionId}:{manualId}:lag"
        time = time * self.fps
        self.redis_client.set(key, time)

    def get_lag_redis(self, sessionId, manualId):
        key = f"vip:{sessionId}:{manualId}:lag"
        if self.redis_client.exists(key):
            return int(self.redis_client.get(key))
        else:
            self.redis_client.set(key, 0)
            return 0

    def store_detection_redis(self, sourceId, task, sessionId, manualId):
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

    def get_detection_redis(self, sessionId, manualId, sourceId):
        key = f"via:{sessionId}:{manualId}:{sourceId}:detections"
        existing_tasks = self.redis_client.get(key)
        if existing_tasks:
            return json.loads(existing_tasks)["tasks"]
        else:
            return None

    def remove_detection_redis(self, sessionId, manualId, sourceId):
        key = f"via:{sessionId}:{manualId}:{sourceId}:detections"
        self.redis_client.delete(key)

    def assign_task(self, things_present, sourceId, sessionId, manualId):
        try:
            data = self.sessionSteps.find_one({"sessionId": sessionId})

            if manualId not in self.manual_data_cache:
                manual = self.monualCollection.find_one({"_id": int(manualId)})
                self.manual_data_cache[manualId] = manual

            manual = self.manual_data_cache[manualId]
            map = {step['_id']: step['answer'] for step in manual['steps'] if 'answer' in step}
            if data == None:
                return 0, map
            map = {step['_id']: step['answer'] for step in manual['steps'] if 'answer' in step}
            things_present = list(set(things_present))
            matching_keys = filter(lambda key: map[key] == sorted(things_present), map)

            task = next(matching_keys, -1)
            self.store_detection_redis(sourceId, task, sessionId, manualId)

            saved_detections = self.get_detection_redis(sessionId, manualId, sourceId)

            if saved_detections is None:
                return None, map

            if len(saved_detections) == config.pose_continuity and len(set(saved_detections)) == 1:
                self.remove_detection_redis(sessionId, manualId, sourceId)
                return task, map

            elif len(set(saved_detections)) > 1:
                self.remove_detection_redis(sessionId, manualId, sourceId)
                return None, map

            return None, map

        except Exception as e:
            traceback.print_exc()
            pose_logger.error(f"Error occurred: {e}")
            return None, None


    def _process_pose_detection(self, file, sourceId, sessionId, manualId, frame_no):
        """
        Process pose detection on an image file.
        
        Args:
            file: Base64 encoded image string or image file path
            sourceId: Source identifier
            sessionId: Session identifier
            manualId: Manual identifier
            frame_no: Frame number
            
        Returns:
            frame, results, things_present, start_time
        """
        try:
            import cv2
            import numpy as np
            import base64
            
            start_time = time.time()
            things_present = []
            
            # Decode base64 image if it's a string
            if isinstance(file, str):
                try:
                    if ',' in file:
                        # Base64 with data URL prefix (e.g., "data:image/jpeg;base64,...")
                        _, encoded = file.split(",", 1)
                        # Add padding if needed (base64 strings must be multiple of 4)
                        padding = len(encoded) % 4
                        if padding:
                            encoded += '=' * (4 - padding)
                        image_bytes = base64.b64decode(encoded, validate=True)
                    else:
                        # Assume it's already base64 without prefix
                        # Add padding if needed
                        encoded = file.strip()
                        padding = len(encoded) % 4
                        if padding:
                            encoded += '=' * (4 - padding)
                        image_bytes = base64.b64decode(encoded, validate=True)
                except Exception as decode_error:
                    pose_logger.error(f"Error decoding base64 image: {decode_error}")
                    pose_logger.debug(f"File type: {type(file)}, length: {len(file) if isinstance(file, str) else 'N/A'}")
                    return None, None, [], start_time
                
                # Convert to numpy array and decode image
                nparr = np.frombuffer(image_bytes, dtype=np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            else:
                # Assume it's already a frame (numpy array)
                frame = file
            
            if frame is None:
                pose_logger.warning("Could not decode image frame")
                return None, None, [], start_time
            
            frame_shape = frame.shape
            height, width = frame_shape[:2]
            
            # Process with MediaPipe
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.pose_model.process(rgb_frame)
            
            # Extract landmarks and detect hand positions
            if results.pose_landmarks:
                things_present.append("personPresent")
                hand_status = self.detect_raised_hands(results.pose_landmarks, frame_shape)
                if hand_status is not None:
                    things_present.append(hand_status)
            
            return frame, results, sorted(things_present), start_time

        except Exception as e:
            pose_logger.error(f"Error in _process_pose_detection: {e}")
            traceback.print_exc()
            return None, None, [], None


    def process_squat_analysis(self, sessionId, frame, things_present, sourceId, manualId, results, frame_no):
        try:
            overall_start_time = time.time()
            
            # Check if SOP is available for this manualId - use SOP as primary system
            sop_id = sop_manager.get_sop_id_for_manual(str(manualId), sourceId)
            if sop_id:
                # Use SOP unified executor instead of old instruction graph
                self._execute_sop_after_detection(sourceId, manualId, results, frame_no, things_present, sessionId)
                return  # Exit early - SOP handles everything
            
            # NO FALLBACK: If SOP is not configured, do nothing (don't run old instruction_graph)
            return
            
        except Exception as e:
            pose_logger.error(f"Error in process_squat_analysis: {e}")
            traceback.print_exc()
            # NO FALLBACK: Don't run old system on error
            return
    
    def _execute_sop_after_detection(self, sourceId, manualId, results, frame_no, things_present, sessionId=None):
        """
        Execute SOP unified executor after pose detection.
        This REPLACES the old instruction_graph system when SOP is configured.
        Converts pose landmarks to detection format for SOP.
        """
        try:
            # Convert pose landmarks to detection format for SOP
            # SOP expects: Dict[str, List[List[float]]] where each list is [x1, y1, x2, y2]
            detections = {}
            
            # Convert pose landmarks to bounding boxes if available
            # For pose detection, we can create a bounding box from keypoints
            if results is not None:
                # Try to extract bounding box from pose landmarks
                if isinstance(results, dict):
                    # MediaPipe landmarks format: dict with landmark indices
                    # Calculate bounding box from all visible landmarks
                    try:
                        pose_landmarks = results
                        
                        # Get all landmark positions
                        x_coords = []
                        y_coords = []
                        for landmark_idx in range(33):  # MediaPipe has 33 pose landmarks
                            if landmark_idx in pose_landmarks:
                                landmark = pose_landmarks[landmark_idx]
                                if isinstance(landmark, dict):
                                    x_coords.append(landmark.get('x', 0) * 1920)  # Convert normalized to pixels
                                    y_coords.append(landmark.get('y', 0) * 1080)
                        
                        if x_coords and y_coords:
                            # Create bounding box from min/max coordinates
                            x1, x2 = min(x_coords), max(x_coords)
                            y1, y2 = min(y_coords), max(y_coords)
                            detections["Person"] = [[x1, y1, x2, y2]]
                    except Exception as e:
                        pose_logger.debug(f"Could not extract bounding box from pose landmarks: {e}")
                        # Fallback: empty detections but pass things_present
                        detections["Person"] = []
                elif hasattr(results, 'pose_landmarks'):
                    # MediaPipe results object
                    try:
                        landmarks = results.pose_landmarks
                        if landmarks:
                            x_coords = [lm.x * 1920 for lm in landmarks.landmark]
                            y_coords = [lm.y * 1080 for lm in landmarks.landmark]
                            if x_coords and y_coords:
                                x1, x2 = min(x_coords), max(x_coords)
                                y1, y2 = min(y_coords), max(y_coords)
                                detections["Person"] = [[x1, y1, x2, y2]]
                    except Exception as e:
                        pose_logger.debug(f"Could not extract bounding box from MediaPipe results: {e}")
                        detections["Person"] = []
            
            # Execute SOP unified executor (REPLACES old instruction_graph)
            sop_result = sop_manager.execute_sop(
                sourceId=sourceId,
                manualId=str(manualId),
                detections=detections,
                frame_number=frame_no,
                timestamp=str(time.time()),
                additional_data={
                    "things_present": things_present,
                    "pose_landmarks": results,
                    "sessionId": sessionId
                }
            )
            
            if sop_result:
                current_activity = sop_result.get('current_activity', 'N/A')
                cycle_count = sop_result.get('cycle_count', 0)
                success = "✅" if sop_result.get('success') else "❌"
                pose_logger.info(f"[SOP] Activity: {current_activity} | Cycle: {cycle_count} | Status: {success}")
                
                # SOP handles instruction generation internally, so we don't need old instruction_graph
                # The SOP result contains all the activity/cycle information
            else:
                pose_logger.warning(f"SOP execution returned None for manualId {manualId} - no instruction processing")
                # NO FALLBACK: Don't run old instruction_graph if SOP fails
                
        except Exception as e:
            pose_logger.error(f"SOP execution failed: {e}")
            traceback.print_exc()
            # NO FALLBACK: Don't run old instruction_graph on error

    def instruction_graph(self, sourceId, sessionId, manualId, frame, things_present):
        try:
            instruction_start1 = time.time()
            lag = self.get_lag_redis(sessionId, manualId)
            if lag <= 0:
                pose_logger.info(things_present)
                task, map = self.assign_task(things_present, sourceId, sessionId, manualId)
                if task is not None:
                    manual = self.manual_data_cache[manualId]
                    steps = {step["_id"]: step["text"] for step in manual["steps"][:-1]}
                    response = self.task_manager.get_next_step(sessionId, sourceId, task, manualId, frame, things_present, map, steps)
                    if response != 0 and response is not None:
                        self.add_lag_redis(sessionId, manualId, response)
                instruction_time2 = time.time() - instruction_start1
                pose_logger.info(f"Instruction analysis completed in if {instruction_time2:.3f}s")
            else:
                self.reduce_lag_redis(sessionId, manualId)
                instruction_time2 = time.time() - instruction_start1
                pose_logger.info(f"Instruction analysis completed in else {instruction_time2:.3f}s")

        except Exception as e:
            pose_logger.error(f"Error in instruction_graph: {e}")
            traceback.print_exc()
    

    def detect_raised_hands(self, landmarks, frame_shape):
        """
        Detect raised hand positions from MediaPipe pose landmarks.
        
        Args:
            landmarks: MediaPipe pose_landmarks object (has .landmark attribute)
            frame_shape: Tuple of (height, width, channels)
            
        Returns:
            Hand status string or None
        """
        if landmarks is None or not hasattr(landmarks, 'landmark'):
            return None
            
        height, width = frame_shape[:2]
        
        # Access landmarks via .landmark list (MediaPipe format)
        landmark_list = landmarks.landmark
        
        # Get landmark indices
        left_wrist_idx = pose.PoseLandmark.LEFT_WRIST.value
        right_wrist_idx = pose.PoseLandmark.RIGHT_WRIST.value
        left_shoulder_idx = pose.PoseLandmark.LEFT_SHOULDER.value
        right_shoulder_idx = pose.PoseLandmark.RIGHT_SHOULDER.value
        left_elbow_idx = pose.PoseLandmark.LEFT_ELBOW.value
        right_elbow_idx = pose.PoseLandmark.RIGHT_ELBOW.value
        
        # Extract y coordinates (normalized 0-1, multiply by height for pixels)
        left_wrist_y = landmark_list[left_wrist_idx].y * height
        right_wrist_y = landmark_list[right_wrist_idx].y * height
        left_shoulder_y = landmark_list[left_shoulder_idx].y * height
        right_shoulder_y = landmark_list[right_shoulder_idx].y * height
        left_elbow_y = landmark_list[left_elbow_idx].y * height
        right_elbow_y = landmark_list[right_elbow_idx].y * height
        
        hand_status = None

        if left_wrist_y < left_shoulder_y:
            hand_status = "leftHandAbove90" if left_elbow_y < left_shoulder_y else "leftHandBelow90"
        if right_wrist_y < right_shoulder_y:
            hand_status = "rightHandAbove90" if right_elbow_y < right_shoulder_y else "rightHandBelow90"
        if left_wrist_y < left_shoulder_y and right_wrist_y < right_shoulder_y:
            hand_status = "bothHandsAbove90" if left_elbow_y < left_shoulder_y and right_elbow_y < right_shoulder_y else "bothHandsBelow90"

        return hand_status

    def is_left_hand_down(self, landmarks, frame_shape):
        if landmarks is None or not hasattr(landmarks, 'landmark'):
            return None
        height, width = frame_shape[:2]
        landmark_list = landmarks.landmark
        left_wrist_y = landmark_list[pose.PoseLandmark.LEFT_WRIST.value].y * height
        left_shoulder_y = landmark_list[pose.PoseLandmark.LEFT_SHOULDER.value].y * height
        left_hand_down = left_wrist_y > left_shoulder_y
        return "liftHandDown" if left_hand_down else None

    def is_right_hand_down(self, landmarks, frame_shape):
        if landmarks is None or not hasattr(landmarks, 'landmark'):
            return None
        height, width = frame_shape[:2]
        landmark_list = landmarks.landmark
        right_wrist_y = landmark_list[pose.PoseLandmark.RIGHT_WRIST.value].y * height
        right_shoulder_y = landmark_list[pose.PoseLandmark.RIGHT_SHOULDER.value].y * height
        right_hand_down = right_wrist_y > right_shoulder_y
        return "rightHandDown" if right_hand_down else None