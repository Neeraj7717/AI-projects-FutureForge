from pymongo import MongoClient
from pymongo.collection import ReturnDocument
from instruction.instructions_llava import LlavaInference
from utils.mongo_operations import MongoDBConnector
from kafka import KafkaProducer
from config.settings import Settings
import json
import logging
 
# Load configurations
config = Settings()
 
# Configure the root logger to output logs to the terminal
logging.basicConfig(level=config.log_level, format='%(asctime)s - %(levelname)s - %(message)s')
 
# Get the root logger
logger = logging.getLogger()
 
# Add a StreamHandler to the logger to output logs to the terminal
console_handler = logging.StreamHandler()
logger.addHandler(console_handler)
 
kafka_url = config.kafka_url
video_instruction_kafka_topic = config.video_instruction_kafka_topic

class TaskGraph:
    def __init__(self, steps):
        self.graph = self.build_graph(steps)
 
    def build_graph(self, steps):
        graph = {}
        for i in range(1, len(steps) + 1):
            graph[i] = i + 1 if i < len(steps) else None
        return graph
 
    def get_next(self, current_step):
        return self.graph.get(current_step)
 
class TaskManager:
    def __init__(self, db_uri=config.mongo_connection_string_stateless, db_name=config.stateless_db, collection_name=config.stateless_collection_state, steps={}):
        self.client = MongoClient(db_uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]
        self.steps = steps
        self.task_graph = TaskGraph(steps)
        self.mongodb = MongoDBConnector()
        # Create a Kafka producer
        self.producer = KafkaProducer(bootstrap_servers=kafka_url)
        self.llava = LlavaInference(steps=self.steps)
 
    def get_current_step(self, sessionId, sourceId):
        document = self.collection.find_one({"sessionId": sessionId, "sourceId": sourceId})
        if document:
            # Check if 'current_step' field exists; if not, add it with a value of 1
            if 'current_step' not in document:
                self.collection.update_one(
                    {"_id": document["_id"]},
                    {"$set": {"current_step": 1}}
                )
                return 1
            else:
                return document['current_step']
        else:
            # This condition might not be needed anymore, but kept for safety
            self.collection.insert_one({"sessionId": sessionId, "sourceId": sourceId, "current_step": 1})
            return 1
 
    def update_step(self, sessionId, step):
        # Updates the current_step. Assumes document exists, but handles the case where current_step might not.
        self.collection.update_one(
            {"sessionId": sessionId},
            {"$set": {"current_step": step}}
        )
 
    def reset_step(self, sessionId):
        self.update_step(sessionId, 1)
 
    def get_next_step(self, sessionId, sourceId, task, manualId, frame_bytes):
        manual = self.mongodb.get_document_by_id(document_id=int(manualId))
        current_step = self.get_current_step(sessionId, sourceId)
        total_steps = len(self.steps)
        next_step = self.task_graph.get_next(current_step)
        self.model = manual["model"]
 
        if current_step == total_steps and task == 0:
            if not self.model:
                self.reset_step(sessionId)
                self.mongodb.add_end_time(sessionId, next_step)
                step_details = manual["steps"][-1]
                logger.debug(step_details["text"])
                message = {
                    "id": step_details["url"],
                    "sessionId": sessionId,
                    "videoUrl": step_details["url"],
                    "manualId": manualId,
                    "step": step_details["text"],
                    "status": "inProgress",
                    "duration": "",
                    "repetition": "",
                    "feedback": "",
                    "feedbackUrl": "",
                    "startTime": ""
                }
                steps_mongo = {
                    "sessionId": sessionId,
                    "manualId": manualId,
                    "stepId": step_details["id"],
                    "step": step_details["text"],
                    "status": "inProgress",
                    "duration": "",
                    "repetition": "",
                    "feedback": "",
                    "videoUrl": step_details["url"],
                    "feedbackUrl": ""
                }
                self.mongodb.insert_or_update_data(session_id=sessionId, steps=steps_mongo)
                # self.mongodb.add_end_time(sessionId, step_details["id"])
                self.producer.send(
                    video_instruction_kafka_topic,
                    value=json.dumps(message).encode("utf-8"),
                )
                return self.steps[1]
            else:
                response = self.llava.verify(frame_bytes=frame_bytes)
                if response == "yes":
                    self.reset_step(sessionId)
                    step_details = manual["steps"][-1]
                    logger.debug(step_details["text"])
                    steps_mongo = {
                    "sessionId": sessionId,
                    "manualId": manualId,
                    "stepId": step_details["id"],
                    "step": step_details["text"],
                    "status": "inProgress",
                    "duration": "",
                    "repetition": "",
                    "feedback": "",
                    "videoUrl": step_details["url"],
                    "feedbackUrl": ""
                    }
                    self.mongodb.insert_or_update_data(session_id=sessionId, steps=steps_mongo)
                    message = {
                        "id": step_details["url"],
                        "sessionId": sessionId,
                        "videoUrl": step_details["url"],
                        "manualId": manualId,
                        "step": "",
                        "status": "inProgress",
                        "duration": "",
                        "repetition": "",
                        "feedback": "",
                        "feedbackUrl": "",
                        "startTime": ""
                    }
                    self.producer.send(
                        video_instruction_kafka_topic,
                        value=json.dumps(message).encode("utf-8"),
                    )
                    return self.steps[1]
                    
        elif task == 0 or task != current_step:
            if not self.model:
                step_details = manual["steps"][current_step - 1]
                logger.debug(step_details["text"])
                message = {
                    "id": step_details["url"],
                    "sessionId": sessionId,
                    "videoUrl": step_details["url"],
                    "manualId": manualId,
                    "step": "",
                    "status": "inProgress",
                    "duration": "",
                    "repetition": "",
                    "feedback": "",
                    "feedbackUrl": "",
                    "startTime": ""
                }
                self.producer.send(
                    video_instruction_kafka_topic,
                    value=json.dumps(message).encode("utf-8"),
                )
                steps_mongo = {
                    "sessionId": sessionId,
                    "manualId": manualId,
                    "stepId": step_details["id"],
                    "step": step_details["text"],
                    "status": "inProgress",
                    "duration": "",
                    "repetition": "",
                    "feedback": "",
                    "videoUrl": step_details["url"],
                    "feedbackUrl": ""
                }
                try:
                    self.mongodb.insert_or_update_data(session_id=sessionId, steps=steps_mongo)
                except Exception as e:
                    return e
                logger.debug(current_step)
                return self.steps[current_step]
            else:
                response = self.llava.verify(frame_bytes=frame_bytes)
                if response == "Yes":
                    step_details = manual["steps"][current_step - 1]
                    logger.debug(step_details["text"])
                    message = {
                        "id": step_details["url"],
                        "sessionId": sessionId,
                        "videoUrl": step_details["url"],
                        "manualId": manualId,
                        "step": "",
                        "status": "inProgress",
                        "duration": "",
                        "repetition": "",
                        "feedback": "",
                        "feedbackUrl": "",
                        "startTime": ""
                    }
                    steps_mongo = {
                    "sessionId": sessionId,
                    "manualId": manualId,
                    "stepId": step_details["id"],
                    "step": step_details["text"],
                    "status": "inProgress",
                    "duration": "",
                    "repetition": "",
                    "feedback": "",
                    "videoUrl": step_details["url"],
                    "feedbackUrl": ""
                    }
                    self.mongodb.insert_or_update_data(session_id=sessionId, steps=steps_mongo)
                    self.producer.send(
                        video_instruction_kafka_topic,
                        value=json.dumps(message).encode("utf-8"),
                    )
                    logger.debug(current_step)
                    return self.steps[current_step]
        elif task == current_step:
            logger.debug(next_step)
            if not self.model:
                if next_step is not None:
                    self.update_step(sessionId, next_step)
                    self.mongodb.add_end_time(sessionId, next_step)
                    step_details = manual["steps"][next_step - 1]
                    logger.debug(step_details["text"])
                    message = {
                        "id": step_details["url"],
                        "sessionId": sessionId,
                        "videoUrl": step_details["url"],
                        "manualId": manualId,
                        "step": "",
                        "status": "inProgress",
                        "duration": "",
                        "repetition": "",
                        "feedback": "",
                        "feedbackUrl": "",
                        "startTime": ""
                        }
                    steps_mongo = {
                    "sessionId": sessionId,
                    "manualId": manualId,
                    "stepId": step_details["id"],
                    "step": step_details["text"],
                    "status": "inProgress",
                    "duration": "",
                    "repetition": "",
                    "feedback": "",
                    "videoUrl": step_details["url"],
                    "feedbackUrl": ""
                    }
                    self.mongodb.insert_or_update_data(session_id=sessionId, steps=steps_mongo)
                    self.producer.send(
                        video_instruction_kafka_topic,
                        value=json.dumps(message).encode("utf-8"),
                    )
                    logger.debug(next_step)
                    return self.steps.get(next_step, "Please perform the next step.")
                else:
                    return "Well Done! Your task is completed. Please confirm to start over."
            else:
                response = self.llava.verify(frame_bytes=frame_bytes)
                if response == "yes" or response == "Yes":
                    if next_step is not None:
                        self.update_step(sessionId, next_step)
                        self.mongodb.add_end_time(sessionId, current_step)
                        step_details = manual["steps"][next_step - 1]
                        logger.debug(step_details["text"])
                        message = {
                            "id": step_details["url"],
                            "sessionId": sessionId,
                            "videoUrl": step_details["url"],
                            "manualId": manualId,
                            "step": "",
                            "status": "inProgress",
                            "duration": "",
                            "repetition": "",
                            "feedback": "",
                            "feedbackUrl": "",
                            "startTime": ""
                        }
                        steps_mongo = {
                            "sessionId": sessionId,
                            "manualId": manualId,
                            "stepId": step_details["id"],
                            "step": step_details["text"],
                            "status": "inProgress",
                            "duration": "",
                            "repetition": "",
                            "feedback": "",
                            "videoUrl": step_details["url"],
                            "feedbackUrl": ""
                        }
                        self.mongodb.insert_or_update_data(session_id=sessionId, steps=steps_mongo)
                        self.producer.send(
                            video_instruction_kafka_topic,
                            value=json.dumps(message).encode("utf-8"),
                        )
                        logger.debug(next_step)
                        return self.steps.get(next_step, "Please perform the next step.")
                    else:
                        return "Well Done! Your task is completed. Please confirm to start over."