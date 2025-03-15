import cv2 #type: ignore
import argparse #type: ignore
import time
import traceback
import base64
import concurrent.futures
import zlib
import numpy as np
import requests
import json
import datetime
import pymongo
from kafka import KafkaProducer
import pandas as pd #type: ignore
from deepface import DeepFace #type: ignore
from Config.settings import Settings
from instruction.instructions_graph import TaskManager

import os
config = Settings()

class AgeGenderRecognition:
    def __init__(self):
        self.ages = ['(0-5)', '(6-10)', '(11-15)', '(16-22)', '(23-30)', '(31-48)', '(48-59)', '(60-100)']
        self.genders = ["Male", "Female"]
        self.modelMeanValues = (78.4263377603, 87.7689143744, 114.895847746)

        self.faceNet = cv2.dnn.readNet("./checkpoints/gender_model_checkpoints/face_detector/opencv_face_detector_uint8.pb",
                                           "./checkpoints/gender_model_checkpoints/face_detector/opencv_face_detector.pbtxt")
        self.ageNet = cv2.dnn.readNet("./checkpoints/gender_model_checkpoints/age_detector/age_net.caffemodel",
                                          "./checkpoints/gender_model_checkpoints/age_detector/age_deploy.prototxt")
        self.genderNet = cv2.dnn.readNet("./checkpoints/gender_model_checkpoints/gender_detector/gender_net.caffemodel",
                                             "./checkpoints/gender_model_checkpoints/gender_detector/gender_deploy.prototxt")

        # # Update your model loading in AgeGenderRecognition.__init__
        # self.faceNet = cv2.dnn.readNet("./checkpoints/gender_model_checkpoints/face_detector/opencv_face_detector_uint8.pb",
        #                             "./checkpoints/gender_model_checkpoints/face_detector/opencv_face_detector.pbtxt")
        # self.faceNet.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        # self.faceNet.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)

        # self.ageNet = cv2.dnn.readNet("./checkpoints/gender_model_checkpoints/age_detector/age_net.caffemodel",
        #                             "./checkpoints/gender_model_checkpoints/age_detector/age_deploy.prototxt")
        # self.ageNet.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        # self.ageNet.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)

        # self.genderNet = cv2.dnn.readNet("./checkpoints/gender_model_checkpoints/gender_detector/gender_net.caffemodel",
        #                             "./checkpoints/gender_model_checkpoints/gender_detector/gender_deploy.prototxt")
        # self.genderNet.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        # self.genderNet.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)

    def getFaceBox(self, frame, confThreshold=0.7):
        frameHeight, frameWidth = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(frame, 1.0, (300, 300), [104, 117, 123], swapRB=True, crop=False)
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
            self.genderNet.setInput(blob)
            gender = self.genders[self.genderNet.forward()[0].argmax()]

            self.ageNet.setInput(blob)
            age = self.ages[self.ageNet.forward()[0].argmax()]

            faceData.append(((x1, y1, x2, y2), gender, age))

        return frame, faceData

class EmotionDetection:
    def __init__(self):
        self.feelings = ['angry', 'disgust', 'fear', 'happy', 'sad', 'surprise', 'neutral']
        self.dfFaceEmotions = pd.DataFrame(columns=self.feelings)

    def detect(self, frame, bboxes):
        faceEmotions = []

        for x1, y1, x2, y2 in bboxes:
            bbox = (x1, y1, x2, y2)
            faceImg = frame[y1:y2, x1:x2]

            if faceImg.size == 0:
                faceEmotions.append((bbox, "No Face"))
                continue

            try:
                emo = DeepFace.analyze(faceImg, actions=['emotion'], silent=True, enforce_detection=False)[0]['emotion']
                # # In EmotionDetection.detect method
                # emo = DeepFace.analyze(faceImg, actions=['emotion'], silent=True, enforce_detection=False, 
                #        detector_backend='opencv', model_name='DeepFace')[0]['emotion']
                emotion = max(emo, key=emo.get)
                faceEmotions.append((bbox, emotion))
            except Exception as e:
                print(f"Error analyzing face: {e}")
                faceEmotions.append((bbox, "Error"))

        return faceEmotions



class ProcessFrame:
    def __init__(self):
        self.ageGenderModel = AgeGenderRecognition()   
        self.emotionModel = EmotionDetection()
        self.kafka_url = config.kafka_url
        self.client = pymongo.MongoClient(config.mongo_connection_string_stateless) 
        self.db = self.client[config.database_name]
        self.monualCollection=self.db["manual"]
        self.sessionSteps=self.db["sessionSteps"]
        self.producer=KafkaProducer(bootstrap_servers=config.kafka_url)


    def processFrame(self, frame, ageGenderModel, emotionModel):
        print("Processing Frame for Gender detect")
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

    # def send_every_instruction(self,sessionId,frame_bytes,manualId,sourceId,saved_detections,object_names,image_paths):
    #     try:
    #         data=self.sessionSteps.find_one({"sessionId":sessionId})
    #         if data==None:
    #             document = self.monualCollection.find_one({"_id": int(manualId)})
    #             steps = {step["_id"]: step["text"] for step in document["steps"][:-1]}
    #             task_manager = TaskManager(steps=steps)

    #             response = task_manager.get_next_step(sessionId, sourceId, 0, manualId, frame_bytes,[],{})

    #         if len(saved_detections) >= config.continuity and len(set(saved_detections)) == 1:
    #             response  = requests.post(config.t2v_endpoint, json={"text" : f"The object you picked is {object_names}", "gender": 0})
    #             data = json.loads(response.content.decode("utf-8"))
    #             message={
    #                     "sessionId": sessionId,
    #                     "videoUrl": "",
    #                     "audioUrl": data["file_path"],
    #                     "contextUrl": image_paths,
    #                     "contextType": "img",
    #                     "manualId": manualId,
    #                     "stepId": 1,
    #                     "step": f"The object you picked is {object_names}",
    #                     "status": "failed",
    #                     "repetition": 0,
    #                     "feedback": "",
    #                     "feedbackUrl": "",
    #                     "startTime": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00"),
    #                     "endTime": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00"),
    #                     }
    #             print(message)
    #             self.producer.send(config.video_instruction_kafka_topic,value=json.dumps(message).encode("utf-8"))
    #             self.remove_detection(sessionId) 
    #         elif len(set(saved_detections)) > 1:
    #             self.remove_detection(sessionId) 
    #     except Exception as e:
    #         print(e)


    def send_instruction_pose(self,xyxy,new_width,new_height,sourceId,sessionId,manualId,things_present,keypoints=[]):
        key_component=sessionId.encode('utf-8') 
        message = {"sessionId": sessionId, "classes": things_present, "coordinates": list(xyxy),"frameDimensions":[new_width,new_height],"keyPoints":keypoints}
        try:
            
            self.producer.send("vip-bounding-box-details",key=key_component, value=json.dumps(message).encode("utf-8"))
            print("sent to kafka")
            
        except Exception as e:
            traceback.print_exc()
            pass
        return


    def gender_detector(self, file, sourceId, sessionId, manualId):
        try:
            start_time = time.time()
            header, encoded = file.split(",", 1)
            image_bytes = base64.b64decode(encoded)
            np_arr = np.frombuffer(image_bytes, dtype=np.uint8)
            if np_arr is None or np_arr.size == 0:
                return None
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            frame, gender_data, xyxy = self.processFrame(frame, self.ageGenderModel, self.emotionModel)

            # gender_data_string = f"Gender: {gender_data['gender']}, Age: {gender_data['age']}, emotion: {gender_data['emotion']}."

            data=self.sessionSteps.find_one({"sessionId":sessionId})
            if data==None:
                document = self.monualCollection.find_one({"_id": int(manualId)})
                steps = {step["_id"]: step["text"] for step in document["steps"][:-1]}
                task_manager = TaskManager(steps=steps)
                response = task_manager.get_next_step(sessionId, sourceId, 0, manualId, frame, [], {})

            new_height, new_width = frame.shape[:2]
            print(xyxy)
            print(gender_data)
            print(new_width,new_height,)
            with concurrent.futures.ThreadPoolExecutor(max_workers=1000) as executor:
                # Assign task based on detections
                self.send_instruction_pose(xyxy, new_width, new_height, sourceId, sessionId, manualId, gender_data, [])
                return
        
        except Exception as e:
            print("error is ",e)


# def main():
#     parser = argparse.ArgumentParser(description='Age, Gender, and Emotion Recognition')
#     parser.add_argument('-i', '--input', type=str, help='Path to input image/video (default: camera)')
#     parser.add_argument('--no_age_gender', action='store_true', help='Disable age and gender recognition')
#     parser.add_argument('--no_emotion', action='store_true', help='Disable emotion recognition')

#     args = parser.parse_args()

#     showAgeGender = not args.no_age_gender
#     showEmotion = not args.no_emotion



#     inputPath = args.input

#     inputSource = "camera"
#     if inputPath:
#         try:
#             img = cv2.imread(inputPath)
#             if img is not None:
#                 inputSource = "image"
#             else:
#                 cap = cv2.VideoCapture(inputPath)
#                 if cap.isOpened():
#                     inputSource = "video"
#                     cap.release()
#                 else:
#                     print(f"Warning: Could not open {inputPath} as either image or video.  Falling back to camera.")
#                     inputSource = "camera"

#         except Exception as e:
#             print(f"Error checking input path: {e}.  Falling back to camera.")
#             inputSource = "camera"


#     if inputSource == "image":
#         try:
#             frame = cv2.imread(inputPath)
#             if frame is None:
#                 raise ValueError(f"Could not read image from {inputPath}")

#             processedFrame = processFrame(frame, ageGenderModel, emotionModel)
#             cv2.imshow('Age, Gender & Emotion Detection - Image', processedFrame)
#             cv2.waitKey(0)
#             cv2.destroyAllWindows()

#         except ValueError as e:
#             print(f"Error processing image: {e}")
#         except Exception as e:
#             print(f"An unexpected error occurred: {e}")

#     elif inputSource == "video":
#         cap = cv2.VideoCapture(inputPath)
#         if not cap.isOpened():
#             print(f"Error: Could not open video file at {inputPath}")
#             return

#         while cap.isOpened():
#             ret, frame = cap.read()
#             if not ret:
#                 break

#             processedFrame = processFrame(frame, ageGenderModel, emotionModel)
#             cv2.imshow('Age, Gender & Emotion Detection - Video', processedFrame)

#             if cv2.waitKey(1) & 0xFF == ord('q'):
#                 break

#         cap.release()
#         cv2.destroyAllWindows()

#     else:
#         cap = cv2.VideoCapture(0)
#         if not cap.isOpened():
#             print("Error: Could not access camera.  Please check camera connection.")
#             return

#         while cap.isOpened():
#             ret, frame = cap.read()
#             if not ret:
#                 print("Error: Could not read frame from camera.  Exiting.")
#                 break

#             processedFrame = processFrame(frame, ageGenderModel, emotionModel)
#             cv2.imshow('Age, Gender & Emotion Detection - Camera', processedFrame)

#             if cv2.waitKey(1) & 0xFF == ord('q'):
#                 break

#         cap.release()
#         cv2.destroyAllWindows()

# if __name__ == "__main__":
#     main()