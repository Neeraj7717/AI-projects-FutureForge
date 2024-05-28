from pymongo import MongoClient
from pymongo.collection import ReturnDocument
import requests
from instruction.instructions_llava import LlavaInference
from utils.mongo_operations import MongoDBConnector
from kafka import KafkaProducer
from Config.settings import Settings
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
        for i in list(steps.keys()):
            graph[i] = i + 1 if i < list(steps.keys())[-1] else None
        return graph
    def get_graph(self):
        return self.graph
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
        document = self.collection.find_one({"sessionId": sessionId})
        start_step=list(self.task_graph.get_graph().keys())[0]
        if document:
            # Check if 'current_step' field exists; if not, add it with a value of 1
            if 'current_step' not in document:
                self.collection.update_one(
                    {"_id": document["_id"]},
                    {"$set": {"current_step": start_step}}
                )
                return start_step
            else:
                return document['current_step']
        else:
            # This condition might not be needed anymore, but kept for safety
            self.collection.insert_one({"sessionId": sessionId, "current_step": start_step})
            return start_step
 
    def update_step(self, sessionId, step):
        # Updates the current_step. Assumes document exists, but handles the case where current_step might not.
        self.collection.update_one(
            {"sessionId": sessionId},
            {"$set": {"current_step": step}}
        )
 
    def reset_step(self, sessionId):
        self.update_step(sessionId, 1)
 
    def get_next_step(self, sessionId, sourceId, task, manualId, frame_bytes,things_present,data):
        manual = self.mongodb.get_document_by_id(document_id=int(manualId))
        current_step = self.get_current_step(sessionId, sourceId)
        total_steps = len(self.steps)

        next_step = self.task_graph.get_next(current_step)
        self.model = manual["model"]
        print(current_step,manual["steps"][-2]["_id"],task)
        if current_step>manual["steps"][-2]["_id"]:
            return
        
        if current_step == manual["steps"][-2]["_id"] and (task == 0 or current_step==task):
            print("c\no\nr\nr\ne\nc\nt")
            if not self.model:
                self.update_step(sessionId,current_step+2)

                for step in manual["steps"]:
                    if step["_id"]==current_step:
                        step_details=step
                        break
                logger.debug(step_details["text"])
                message = {
                    "stepId": str(step_details["_id"]),
                    "sessionId": sessionId,
                    "videoUrl": step_details["url"],
                    "manualId": manualId,
                    "step": step_details["text"],
                    "status": "inProgress",
                    "endTime": "",
                    "audioUrl":"",
                    "contextUrl": step_details["contextUrl"],
                    "contextType":step_details["contextType"],
                    "repetition": 0,
                    "feedback": "",
                    "feedbackUrl": "",
                    "startTime": ""
                    }
                self.mongodb.add_end_time(sessionId, current_step,message)
                step_details = manual["steps"][-1]
                message = {
                    "stepId": str(step_details["_id"]),
                    "sessionId": sessionId,
                    "videoUrl": step_details["url"],
                    "manualId": manualId,
                    "step": step_details["text"],
                    "status": "inProgress",
                    "endTime": "",
                    "audioUrl":"",
                    "contextUrl": step_details["contextUrl"],
                    "contextType":step_details["contextType"],
                    "repetition": 0,
                    "feedback": "",
                    "feedbackUrl": "",
                    "startTime": ""
                }
                steps_mongo = {
                    "sessionId": sessionId,
                    "manualId": manualId,
                    "stepId": str(step_details["_id"]),
                    "step": step_details["text"],
                    "status": "inProgress",
                    "duration": "",
                    "repetition": 0,
                    "feedback": "",
                    "videoUrl": step_details["url"],
                    "feedbackUrl": ""
                }
                self.mongodb.insert_or_update_data(session_id=sessionId, steps=steps_mongo, total_steps=total_steps,message=message)
                message["status"]="completed"
                self.mongodb.add_end_time(sessionId, step_details["_id"],message)
                # self.producer.send(
                #     video_instruction_kafka_topic,
                #     value=json.dumps(message).encode("utf-8"),
                # )
                return step_details["time"]
            else:
                response = self.llava.verify(frame_bytes=frame_bytes)
                if response == "yes":
                    self.reset_step(sessionId)
                    step_details = manual["steps"][-1]
                    logger.debug(step_details["text"])
                    steps_mongo = {
                    "sessionId": sessionId,
                    "manualId": manualId,
                    "stepId": str(step_details["_id"]),
                    "step": step_details["text"],
                    "status": "inProgress",
                    "duration": "",
                    "repetition": 0,
                    "feedback": "",
                    "videoUrl": step_details["url"],
                    "feedbackUrl": ""
                    }

                    message = {
                        "stepId": str(step_details["_id"]),
                        "sessionId": sessionId,
                        "videoUrl": step_details["url"],
                        "manualId": manualId,
                        "step": step_details["text"],
                        "status": "inProgress",
                        "endTime": "",
                        "audioUrl":"",
                        "contextUrl": step_details["contextUrl"],
                        "contextType":step_details["contextType"],
                        "repetition": 0,
                        "feedback": "",
                        "feedbackUrl": "",
                        "startTime": ""
                    }
                    self.mongodb.insert_or_update_data(session_id=sessionId, steps=steps_mongo, total_steps=total_steps,message=message)
                    # self.producer.send(
                    #     video_instruction_kafka_topic,
                    #     value=json.dumps(message).encode("utf-8"),
                    # )
                    return self.steps[1]
                    
        elif task == 0 or task != current_step:
            if not self.model:
                for step in manual["steps"]:
                    if step["_id"]==current_step:
                        step_details=step
                        break

                # step_details = manual["steps"][current_step - 1]
                # self.mongodb.add_end_time(sessionId, next_step)
                logger.debug(step_details["text"])
                message = {
                    "stepId": str(step_details["_id"]),
                    "sessionId": sessionId,
                    "videoUrl": step_details["url"],
                    "manualId": manualId,
                    "step": step_details["text"],
                    "status": "inProgress",
                    "endTime": "",
                    "audioUrl":"",
                    "contextUrl": step_details["contextUrl"],
                    "contextType":step_details["contextType"],
                    "repetition": 0,
                    "feedback": "",
                    "feedbackUrl": "",
                    "startTime": ""
                }

                # self.producer.send(
                #     video_instruction_kafka_topic,
                #     value=json.dumps(message).encode("utf-8"),
                # )
                steps_mongo = {
                    "sessionId": sessionId,
                    "manualId": manualId,
                    "stepId": str(step_details["_id"]),
                    "step": step_details["text"],
                    "status": "inProgress",
                    "duration": "",
                    "repetition": 0,
                    "feedback": "",
                    "videoUrl": step_details["url"],
                    "feedbackUrl": ""
                }
                try:
                    def get_items(step_id, manual_id):
                        return data[step_id]
                    things_present=list(set(things_present))

                    if task!=0:
                        if "text_based_model" in things_present:
                            Text="Your answer is incorrect."
                        else:
                            true_items=get_items(int(current_step),int(manualId))[:]
                            if "Person" in true_items:
                                true_items.remove("Person")
                            if "Person" in things_present:
                                things_present.remove("Person")
                            text=step_details["text"]
                            
                            def format_items(items):
                                if len(items) > 1:
                                    return ', '.join(items[:-1]) + ' and ' + items[-1]
                                elif len(items) == 1:
                                    return items[0]
                                else:
                                    return 'nothing'
                            if len(things_present) == 0 and len(true_items) == 0:
                                Text = "You are holding nothing and you should hold nothing."
                            else:
                                items_text = format_items(things_present)
                                true_items_text = format_items(true_items)
                                Text = f"You are holding {items_text} but you have to hold {true_items_text}."
                                
                            if Text=="You are holding nothing and you should hold nothing.":
                                Text="Ensure you are having good lighting."
                        print(f"\n\n{Text}\n\n")    
                        response  = requests.post(config.t2v_endpoint, json={"text" : Text, "gender": 0})
                        data = json.loads(response.content.decode("utf-8"))
                        message["audioUrl"]= data["file_path"]
                        message["step"]=Text
                    self.mongodb.insert_or_update_data(session_id=sessionId, steps=steps_mongo, total_steps=total_steps,message=message)
                    if task==0:
                        return step_details["time"]
                except Exception as e:
                    print(e)
                    return e
                logger.debug(current_step)
                return 0
            else:
                response = self.llava.verify(frame_bytes=frame_bytes)
                if response == "Yes":
                    for step in manual["steps"]:
                        if step["_id"]==current_step:
                            step_details=step
                            break
                    logger.debug(step_details["text"])
                    message = {
                        "stepId": str(step_details["_id"]),
                        "sessionId": sessionId,
                        "videoUrl": step_details["url"],
                        "manualId": manualId,
                        "step": step_details["text"],
                        "status": "inProgress",
                        "endTime": "",
                        "audioUrl":"",
                        "contextUrl": step_details["contextUrl"],
                        "contextType":step_details["contextType"],
                        "repetition": 0,
                        "feedback": "",
                        "feedbackUrl": "",
                        "startTime": ""
                    }
                    steps_mongo = {
                    "sessionId": sessionId,
                    "manualId": manualId,
                    "stepId": str(step_details["_id"]),
                    "step": step_details["text"],
                    "status": "inProgress",
                    "duration": "",
                    "repetition": 0,
                    "feedback": "",
                    "videoUrl": step_details["url"],
                    "feedbackUrl": ""
                    }

                    self.mongodb.insert_or_update_data(session_id=sessionId, steps=steps_mongo, total_steps=total_steps,message=message)
                    # self.producer.send(
                    #     video_instruction_kafka_topic,
                    #     value=json.dumps(message).encode("utf-8"),
                    # )
                    logger.debug(current_step)
                    return self.steps[current_step]
        elif task == current_step:
            logger.debug(next_step)
            if not self.model:
                if next_step is not None:
                    self.update_step(sessionId, next_step)
                    for step in manual["steps"]:
                        if step["_id"]==current_step:
                            step_details=step
                            break
                    logger.debug(step_details["text"])
                    message = {
                        "stepId": str(step_details["_id"]),
                        "sessionId": sessionId,
                        "videoUrl": step_details["url"],
                        "manualId": manualId,
                        "step": step_details["text"],
                        "status": "inProgress",
                        "endTime": "",
                        "audioUrl":"",
                        "contextUrl": step_details["contextUrl"],
                        "contextType":step_details["contextType"],
                        "repetition": 0,
                        "feedback": "",
                        "feedbackUrl": "",
                        "startTime": ""
                        }
                    self.mongodb.add_end_time(sessionId, current_step,message)
                    for step in manual["steps"]:
                        if step["_id"]==next_step:
                            step_details=step
                            break
                    logger.debug(step_details["text"])
                    message = {
                        "stepId": str(step_details["_id"]),
                        "sessionId": sessionId,
                        "videoUrl": step_details["url"],
                        "manualId": manualId,
                        "step": step_details["text"],
                        "status": "inProgress",
                        "endTime": "",
                        "audioUrl":"",
                        "contextUrl": step_details["contextUrl"],
                        "contextType":step_details["contextType"],
                        "repetition": 0,
                        "feedback": "",
                        "feedbackUrl": "",
                        "startTime": ""
                        }
                    steps_mongo = {
                    "sessionId": sessionId,
                    "manualId": manualId,
                    "stepId": str(step_details["_id"]),
                    "step": step_details["text"],
                    "status": "inProgress",
                    "duration": "",
                    "repetition": 0,
                    "feedback": "",
                    "videoUrl": step_details["url"],
                    "feedbackUrl": ""
                    }

                    self.mongodb.insert_or_update_data(session_id=sessionId, steps=steps_mongo, total_steps=total_steps,message=message)
                    # self.producer.send(
                    #     video_instruction_kafka_topic,
                    #     value=json.dumps(message).encode("utf-8"),
                    # )
                    logger.debug(next_step)
                    return step_details["time"]
                else:
                    return "Well Done! Your task is completed. Please confirm to start over."
            else:
                response = self.llava.verify(frame_bytes=frame_bytes)
                if response == "yes" or response == "Yes":
                    if next_step is not None:
                        self.update_step(sessionId, next_step)
                        for step in manual["steps"]:
                            if step["_id"]==current_step:
                                step_details=step
                                break
                        message = {
                            "stepId": str(step_details["_id"]),
                            "sessionId": sessionId,
                            "videoUrl": step_details["url"],
                            "manualId": manualId,
                            "step": step_details["text"],
                            "status": "inProgress",
                            "endTime": "",
                            "audioUrl":"",
                            "contextUrl": step_details["contextUrl"],
                            "contextType":step_details["contextType"],
                            "repetition": 0,
                            "feedback": "",
                            "feedbackUrl": "",
                            "startTime": ""
                        }
                        self.mongodb.add_end_time(sessionId, current_step,message)
                        for step in manual["steps"]:
                            if step["_id"]==current_step:
                                step_details=step
                                break
                        message = {
                            "stepId": str(step_details["_id"]),
                            "sessionId": sessionId,
                            "videoUrl": step_details["url"],
                            "manualId": manualId,
                            "step": step_details["text"],
                            "status": "inProgress",
                            "endTime": "",
                            "audioUrl":"",
                            "contextUrl": step_details["contextUrl"],
                            "contextType":step_details["contextType"],
                            "repetition": 0,
                            "feedback": "",
                            "feedbackUrl": "",
                            "startTime": ""
                        }
                        for step in manual["steps"]:
                            if step["_id"]==next_step:
                                step_details=step
                                break
                        logger.debug(step_details["text"])
                        message = {
                            "stepId": str(step_details["_id"]),
                            "sessionId": sessionId,
                            "videoUrl": step_details["url"],
                            "manualId": manualId,
                            "step": step_details["text"],
                            "status": "inProgress",
                            "endTime": "",
                            "audioUrl":"",
                            "contextUrl": step_details["contextUrl"],
                            "contextType":step_details["contextType"],
                            "repetition": 0,
                            "feedback": "",
                            "feedbackUrl": "",
                            "startTime": ""
                        }
                        steps_mongo = {
                            "sessionId": sessionId,
                            "manualId": manualId,
                            "stepId": str(step_details["_id"]),
                            "step": step_details["text"],
                            "status": "inProgress",
                            "duration": "",
                            "repetition": 0,
                            "feedback": "",
                            "videoUrl": step_details["url"],
                            "feedbackUrl": ""
                        }

                        self.mongodb.insert_or_update_data(session_id=sessionId, steps=steps_mongo, total_steps=total_steps,message=message)
                        # self.producer.send(
                        #     video_instruction_kafka_topic,
                        #     value=json.dumps(message).encode("utf-8"),
                        # )
                        logger.debug(next_step)
                        return self.steps.get(next_step, "Please perform the next step.")
                    else:
                        return "Well Done! Your task is completed. Please confirm to start over."