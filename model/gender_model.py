import cv2
import time
import traceback
import base64
import concurrent.futures
import numpy as np
import json
import pymongo
from kafka import KafkaProducer
import pandas as pd
from deepface import DeepFace
from Config.settings import Settings
from instruction.instructions_graph import TaskManager
from utils.eizen_utils.logger_utils.logger_operations import LoggerOperations
import logging
import threading

config = Settings()
logger = LoggerOperations(logger_name='gender_model', log_level=logging.INFO, use_log_file=False)

class AgeGenderRecognition:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AgeGenderRecognition, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.ages = ['(0-5)', '(6-10)', '(11-15)', '(16-22)', '(23-30)', '(31-48)', '(48-59)', '(60-100)']
            self.genders = ["Male", "Female"]
            self.modelMeanValues = (78.4263377603, 87.7689143744, 114.895847746)

            self.faceNet = cv2.dnn.readNet("./checkpoints/gender_model_checkpoints/face_detector/opencv_face_detector_uint8.pb",
                                               "./checkpoints/gender_model_checkpoints/face_detector/opencv_face_detector.pbtxt")
            self.ageNet = cv2.dnn.readNet("./checkpoints/gender_model_checkpoints/age_detector/age_net.caffemodel",
                                              "./checkpoints/gender_model_checkpoints/age_detector/age_deploy.prototxt")
            self.genderNet = cv2.dnn.readNet("./checkpoints/gender_model_checkpoints/gender_detector/gender_net.caffemodel",
                                                 "./checkpoints/gender_model_checkpoints/gender_detector/gender_deploy.prototxt")

            # Thread safety: Lock for DNN model operations
            self._lock = threading.Lock()

            self._initialized = True
            

    def getFaceBox(self, frame, confThreshold=0.7):
        frameHeight, frameWidth = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(frame, 1.0, (300, 300), [104, 117, 123], swapRB=True, crop=False)

        # Thread-safe DNN operations
        with self._lock:
            self.faceNet.setInput(blob)
            detections = self.faceNet.forward()

        bboxes = [[int(detections[0, 0, i, 3] * frameWidth),
                   int(detections[0, 0, i, 4] * frameHeight),
                   int(detections[0, 0, i, 5] * frameWidth),
                   int(detections[0, 0, i, 6] * frameHeight)]
                  for i in range(detections.shape[2]) if detections[0, 0, i, 2] > confThreshold]

        return bboxes

    def predict(self, frame):
        faceData = []
        bboxes = self.getFaceBox(frame)

        if not bboxes:
            return frame, faceData

        for x1, y1, x2, y2 in bboxes:
            face = frame[max(0, y1 - 20):min(y2 + 20, frame.shape[0] - 1),
                         max(0, x1 - 20):min(x2 + 20, frame.shape[1] - 1)]

            blob = cv2.dnn.blobFromImage(face, 1.0, (227, 227), self.modelMeanValues, swapRB=False)

            # Thread-safe DNN operations
            with self._lock:
                self.genderNet.setInput(blob)
                gender = self.genders[self.genderNet.forward()[0].argmax()]

                self.ageNet.setInput(blob)
                age = self.ages[self.ageNet.forward()[0].argmax()]

            faceData.append(((x1, y1, x2, y2), gender, age))

        return frame, faceData

class EmotionDetection:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmotionDetection, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.feelings = ['angry', 'disgust', 'fear', 'happy', 'sad', 'surprise', 'neutral']
            self.dfFaceEmotions = pd.DataFrame(columns=self.feelings)

            # Thread safety: Lock for DeepFace operations
            self._lock = threading.Lock()

            self._initialized = True

    def detect(self, frame, bboxes):
        faceEmotions = []

        for x1, y1, x2, y2 in bboxes:
            bbox = (x1, y1, x2, y2)
            faceImg = frame[y1:y2, x1:x2]

            if faceImg.size == 0:
                faceEmotions.append((bbox, "No Face"))
                continue

            try:
                # Thread-safe DeepFace operations
                with self._lock:
                    emo = DeepFace.analyze(faceImg, actions=['emotion'], silent=True, enforce_detection=False)[0]['emotion']
                    emotion = max(emo, key=emo.get)
                faceEmotions.append((bbox, emotion))
            except Exception as e:
                print(f"Error analyzing face: {e}")
                faceEmotions.append((bbox, "Error"))

        return faceEmotions



class ProcessFrame:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ProcessFrame, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.ageGenderModel = AgeGenderRecognition()
            self.emotionModel = EmotionDetection()
            self.kafka_url = config.kafka_url
            self.client = pymongo.MongoClient(config.mongo_connection_string_stateless)
            self.db = self.client[config.database_name]
            self.monualCollection=self.db["manual"]
            self.sessionSteps=self.db["sessionSteps"]
            self.producer=KafkaProducer(bootstrap_servers=config.kafka_url)
            self.task_manager = TaskManager()
            self._initialized = True

    def processFrame(self, frame, ageGenderModel, emotionModel):
        faceData = ageGenderModel.predict(frame)[1] if ageGenderModel else []
        bboxes = [bbox[0] for bbox in faceData]
        faceEmotions = emotionModel.detect(frame, bboxes) if emotionModel else []

        faceInfo = {}
        for bbox, gender, age in faceData:
            faceInfo[bbox] = {'gender': gender, 'age': age}

        for bbox, emotion in faceEmotions:
            if bbox in faceInfo:
                faceInfo[bbox]['emotion'] = emotion
            else:
                faceInfo[bbox] = {'emotion': emotion}

        # Prepare the JSON output
        things_present = []
        xyxy = []

        for bbox, info in faceInfo.items():
            x1, y1, x2, y2 = bbox

            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)

            font = cv2.FONT_HERSHEY_SIMPLEX
            fontScale = 0.5
            fontColor = (255, 255, 255)
            fontThickness = 1

            boxHeight = 30
            startX = x2 + 10

            def drawInfoBox(x, y, text, color):
                (textWidth, textHeight) = cv2.getTextSize(text, font, fontScale, fontThickness)[0]
                boxWidth = textWidth + 10

                cv2.rectangle(frame, (x, y), (x + boxWidth, y + boxHeight), color, -1)

                textX = x + 5
                textY = y + int((boxHeight + textHeight) / 2) + 4

                cv2.putText(frame, text, (textX, textY), font, fontScale, fontColor, fontThickness)

            startY = y2 - (3 * (boxHeight+5)) + 10

            yGender = startY
            drawInfoBox(startX, yGender, f"Gender: {info.get('gender', 'N/A')}", (0, 0, 0))

            yAge = yGender + boxHeight + 5
            drawInfoBox(startX, yAge, f"Age: {info.get('age', 'N/A')}", (0, 0, 0))

            yEmotion = yAge + boxHeight + 5
            drawInfoBox(startX, yEmotion, f"Emotion: {info.get('emotion', 'N/A')}", (0, 0, 0))

            gender_data_string = f"{info.get('gender', 'N/A')}\nAge: {info.get('age', 'N/A')}\n{info.get('emotion', 'N/A')}"
            coord = [x1,y1,x2,y2]
            things_present.append(gender_data_string)
            xyxy.append(coord)

            
        return frame, things_present, xyxy 

    def send_instruction_pose(self,xyxy,new_width,new_height,sourceId,sessionId,manualId,things_present,keypoints=[]):
        key_component=sessionId.encode('utf-8') 
        message = {"sessionId": sessionId, "classes": things_present, "coordinates": list(xyxy),"frameDimensions":[new_width,new_height],"keyPoints":keypoints}
        logger.info(f"Sending gender detection {message} to Kafka topic 'vip-bounding-box-details'") 
        try:
            
            self.producer.send("vip-bounding-box-details",key=key_component, value=json.dumps(message).encode("utf-8"))            
        except Exception as e:
            traceback.print_exc()
            pass
        return


    def gender_detector(self, file, sourceId, sessionId, manualId):
        try:
            logger.info(f"Processing gender detection for sessionId: {sessionId}")
            start_time = time.time()
            _, encoded = file.split(",", 1)
            image_bytes = base64.b64decode(encoded)
            np_arr = np.frombuffer(image_bytes, dtype=np.uint8)
            if np_arr is None or np_arr.size == 0:
                end_time = time.time()
                logger.error(f"Decoded image array is empty. Time taken: {end_time - start_time:.2f} seconds")
                return None
            
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            frame, gender_data, xyxy = self.processFrame(frame, self.ageGenderModel, self.emotionModel)
            data=self.sessionSteps.find_one({"sessionId":sessionId})

            if data==None:
                document = self.monualCollection.find_one({"_id": int(manualId)})
                steps = {step["_id"]: step["text"] for step in document["steps"][:-1]}
                response = self.task_manager.get_next_step(sessionId, sourceId, 0, manualId, frame, [], {}, steps)

            new_height, new_width = frame.shape[:2]
            with concurrent.futures.ThreadPoolExecutor(max_workers=1000) as executor:
                self.send_instruction_pose(xyxy, new_width, new_height, sourceId, sessionId, manualId, gender_data, [])
                end_time = time.time()
                logger.info(f"Completed gender detection. Time taken: {end_time - start_time:.2f} seconds")
                return None
        
        except Exception as e:
            logger.error(f"Error in gender detection: {e}")
            traceback.print_exc()
            return None