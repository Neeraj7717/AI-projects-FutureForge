import json
import logging
import time
import traceback
import numpy as np
import pymongo
from datetime import datetime
import mediapipe as mp
import concurrent.futures
from kafka import KafkaProducer
from Config.settings import Settings
from instruction.instructions_graph_pose import TaskManager
import redis

pose = mp.solutions.pose

config = Settings()

pose_logger = logging.getLogger('pose_module')
pose_logger.setLevel(logging.INFO)
pose_logger.propagate = False

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
pose_logger.addHandler(console_handler)

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

    def send_instruction_pose(self, xyxy, new_width, new_height, sourceId, sessionId, manualId, things_present,timeStamp, keypoints=[]):
        try:
            xyxy = xyxy.tolist() if isinstance(xyxy, np.ndarray) else []
            key_component = sessionId.encode('utf-8')
            message = {"sessionId": sessionId, "classes": things_present, "coordinates": list(xyxy),
                       "frameDimensions": [new_width, new_height], "keyPoints": keypoints, "timeStamp": timeStamp}
            self.producer.send("vip-bounding-box-details", key=key_component,
                               value=json.dumps(message).encode("utf-8"))
        except Exception as e:
            pose_logger.error(f"Error sending message: {str(e)}")
            traceback.print_exc()

    def _handle_future_result(self, future):
        try:
            future.result()
        except Exception as e:
            pose_logger.error(f"Error in asynchronous task: {e}")
            traceback.print_exc()

    def pose_detector(self, file, sourceId, sessionId, manualId, frame_no):
        try:
            start_time = time.time()
            future_pose_processing = self.executor.submit(
                self._process_pose_detection, file, sourceId, sessionId, manualId
            )
            future_pose_processing.add_done_callback(self._handle_future_result)
            decode_time = time.time() - start_time
            return
        except Exception as e:
            pose_logger.error(f"Error submitting pose detection tasks: {e}")
            traceback.print_exc()
            return None

    def _process_pose_detection(self, landmarks, sourceId, sessionId, manualId, frame_no):
        try:
            start_time = time.time()
            frame_shape = (1080, 1920, 3)

            person_present = landmarks is not None
            things_present = []
            hand_status = None
            keypoint_data = {}

            if person_present:
                things_present.append("personPresent")
                hand_status = self.detect_raised_hands(landmarks, frame_shape)
                if hand_status is not None:
                    things_present.append(hand_status)
            print("Things Present", sorted(things_present))
            return frame_shape, landmarks, sorted(things_present), start_time

        except Exception as e:
            pose_logger.error(f"Error in _process_pose_detection: {e}")
            traceback.print_exc()
            return None, None, None, None

    def process_squat_analysis(self, sessionId, frame, things_present, sourceId, manualId, results, frame_no):
        try:
            overall_start_time = time.time()
            key = f"vip:{sessionId}:{manualId}:state"
            if self.redis_client.exists(key):
                current_step = int(self.redis_client.get(key))
                updated_things_present = things_present.copy()
                if current_step == 3:
                    print("In Step 3")
                    is_right_down = self.is_right_hand_down(results, (1080, 1920, 3))
                    print("is right Down", is_right_down)
                    if is_right_down is not None:
                        updated_things_present.append(is_right_down)
                    print("Updated Things Present", updated_things_present)
                    self.instruction_graph(sourceId, sessionId, manualId, frame, sorted(updated_things_present))
                elif current_step == 5:
                    print("In step 5")
                    is_left_down = self.is_left_hand_down(results, (1080, 1920, 3))
                    print("is left down", is_left_down)
                    if is_left_down is not None:
                        updated_things_present.append(is_left_down)
                    print("Updated Things Present", updated_things_present)
                    self.instruction_graph(sourceId, sessionId, manualId, frame, sorted(updated_things_present))
                elif current_step == 7:
                    print("In step 7")
                    updated_things_present.append("noHandRaised")
                    self.instruction_graph(sourceId, sessionId, manualId, frame, sorted(updated_things_present))

                else:
                    self.instruction_graph(sourceId, sessionId, manualId, frame, sorted(things_present))
            else:
                self.instruction_graph(sourceId, sessionId, manualId, frame, sorted(things_present))
        except Exception as e:
            print
            self.instruction_graph(sourceId, sessionId, manualId, frame, sorted(things_present))

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
        height, width, _ = frame_shape
        left_wrist_y = landmarks[pose.PoseLandmark.LEFT_WRIST.value]['y'] * height
        right_wrist_y = landmarks[pose.PoseLandmark.RIGHT_WRIST.value]['y'] * height
        left_shoulder_y = landmarks[pose.PoseLandmark.LEFT_SHOULDER.value]['y'] * height
        right_shoulder_y = landmarks[pose.PoseLandmark.RIGHT_SHOULDER.value]['y'] * height
        left_elbow_y = landmarks[pose.PoseLandmark.LEFT_ELBOW.value]['y'] * height
        right_elbow_y = landmarks[pose.PoseLandmark.RIGHT_ELBOW.value]['y'] * height
        hand_status = None

        if left_wrist_y < left_shoulder_y:
            hand_status = "leftHandAbove90" if left_elbow_y < left_shoulder_y else "leftHandBelow90"
        if right_wrist_y < right_shoulder_y:
            hand_status = "rightHandAbove90" if right_elbow_y < right_shoulder_y else "rightHandBelow90"
        if left_wrist_y < left_shoulder_y and right_wrist_y < right_shoulder_y:
            hand_status = "bothHandsAbove90" if left_elbow_y < left_shoulder_y and right_elbow_y < right_shoulder_y else "bothHandsBelow90"

        return hand_status

    def is_left_hand_down(self, landmarks, frame_shape):
        height, width, _ = frame_shape
        left_wrist_y = landmarks[pose.PoseLandmark.LEFT_WRIST.value]['y'] * height
        left_shoulder_y = landmarks[pose.PoseLandmark.LEFT_SHOULDER.value]['y'] * height
        left_hand_down = left_wrist_y > left_shoulder_y
        return "liftHandDown" if left_hand_down else None

    def is_right_hand_down(self, landmarks, frame_shape):
        height, width, _ = frame_shape
        right_wrist_y = landmarks[pose.PoseLandmark.RIGHT_WRIST.value]['y'] * height
        right_shoulder_y = landmarks[pose.PoseLandmark.RIGHT_SHOULDER.value]['y'] * height
        right_hand_down = right_wrist_y > right_shoulder_y
        print(right_hand_down)
        return "rightHandDown" if right_hand_down else None

    def draw_annotations(self, image, landmarks, sourceId, sessionId, manualId, start_time, frame_no, timeStamp):
        try:
            pose_logger.info(f"draw_annotations:start:---{frame_no}---:{datetime.now()}")

            if not landmarks:
                return

            landmarks_points = []
            new_height, new_width = image.shape[:2]

            skeleton_connections = [
                (pose.PoseLandmark.NOSE, pose.PoseLandmark.RIGHT_EYE_INNER),
                (pose.PoseLandmark.NOSE, pose.PoseLandmark.LEFT_EYE_INNER),
                (pose.PoseLandmark.LEFT_SHOULDER, pose.PoseLandmark.RIGHT_SHOULDER),
                (pose.PoseLandmark.RIGHT_SHOULDER, pose.PoseLandmark.RIGHT_ELBOW),
                (pose.PoseLandmark.RIGHT_ELBOW, pose.PoseLandmark.RIGHT_WRIST),
                (pose.PoseLandmark.LEFT_SHOULDER, pose.PoseLandmark.LEFT_ELBOW),
                (pose.PoseLandmark.LEFT_ELBOW, pose.PoseLandmark.LEFT_WRIST),
                (pose.PoseLandmark.LEFT_SHOULDER, pose.PoseLandmark.LEFT_HIP),
                (pose.PoseLandmark.RIGHT_SHOULDER, pose.PoseLandmark.RIGHT_HIP),
                (pose.PoseLandmark.LEFT_HIP, pose.PoseLandmark.RIGHT_HIP),
                (pose.PoseLandmark.RIGHT_HIP, pose.PoseLandmark.RIGHT_KNEE),
                (pose.PoseLandmark.RIGHT_KNEE, pose.PoseLandmark.RIGHT_ANKLE),
                (pose.PoseLandmark.LEFT_HIP, pose.PoseLandmark.LEFT_KNEE),
                (pose.PoseLandmark.LEFT_KNEE, pose.PoseLandmark.LEFT_ANKLE),
                (pose.PoseLandmark.RIGHT_ANKLE, pose.PoseLandmark.RIGHT_HEEL),
            ]

            visibility_threshold = 0.1

            for connection in skeleton_connections:
                start_point = landmarks[connection[0].value]
                end_point = landmarks[connection[1].value]

                if start_point['visibility'] > visibility_threshold and end_point['visibility'] > visibility_threshold:
                    start_x = int(start_point['x'] * image.shape[1])
                    start_y = int(start_point['y'] * image.shape[0])
                    end_x = int(end_point['x'] * image.shape[1])
                    end_y = int(end_point['y'] * image.shape[0])

                    landmarks_points.append([start_x, start_y, end_x, end_y])

            pose_logger.info(f"Total visible landmarks connections detected: {len(landmarks_points)}")
            self.send_instruction_pose([], new_width, new_height, sourceId, sessionId, manualId, [], timeStamp, landmarks_points)
            pose_logger.info(f"draw_annotations:end:---{frame_no}---:{datetime.now()}")

        except Exception as e:
            pose_logger.error(f"Error in draw_annotations: {e}")
            traceback.print_exc()