from pymongo import MongoClient
from pymongo.collection import ReturnDocument
import requests
# from instruction.instructions_llava import LlavaInference
from utils.mongo_operations import MongoDBConnector
from kafka import KafkaProducer
from Config.settings import Settings
import json
import logging
import traceback
from utils.pose_analytics import get_final_summary
import redis


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
    def __init__(self, db_uri=config.mongo_connection_string_stateless, db_name=config.stateless_db, collection_name=config.stateless_collection_state):
        self.client = MongoClient(db_uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]
        self.mongodb = MongoDBConnector()
        self.producer = KafkaProducer(bootstrap_servers=kafka_url)
        # Connect to Redis
        self.redis_client = redis.Redis(host=config.redis_host, port=config.redis_port, db=config.redis_db)
 
    # def get_current_step(self, sessionId, sourceId):
    #     document = self.collection.find_one({"sessionId": sessionId})
    #     try:
    #         start_step=list(self.task_graph.get_graph().keys())[0]
    #     except:
    #         start_step=0
    #     if document:
    #         if 'current_step' not in document:
    #             self.collection.update_one(
    #                 {"_id": document["_id"]},
    #                 {"$set": {"current_step": start_step}}
    #             )
    #             return start_step
    #         else:
    #             return document['current_step']
    #     else:
    #         # This condition might not be needed anymore, but kept for safety
    #         self.collection.insert_one({"sessionId": sessionId, "current_step": start_step})
    #         return start_step
 



    def get_current_step_redis(self, sessionId, manualId,task_graph):
        key = f"vip:{sessionId}:{manualId}:state"
        try:
            start_step = list(task_graph.get_graph().keys())[0]
        except:
            start_step = 0
        # Check if the key exists in Redis
        if not self.redis_client.exists(key):
            # If not, set the initial step in Redis
            self.redis_client.set(key, start_step)
            return start_step
        else:
            # If the key exists, retrieve the current step
            current_step = int(self.redis_client.get(key))
            return current_step




    # def update_step(self, sessionId, step):
    #     # Updates the current_step. Assumes document exists, but handles the case where current_step might not.
    #     self.collection.update_one(
    #         {"sessionId": sessionId},
    #         {"$set": {"current_step": step}}
    #     )





    def update_step_redis(self, sessionId, manualId, step):
        key = f"vip:{sessionId}:{manualId}:state"
        # Updates the current_step in Redis
        self.redis_client.set(key, step)



    def reset_step_redis(self, sessionId, manualId):
        self.update_step_redis(sessionId, manualId, 1)
 


    # def reset_step(self, sessionId):
    #     self.update_step(sessionId, 1)
 


    def get_next_step(self, sessionId, sourceId, task, manualId, frame_bytes,things_present,data, steps):
        task_graph = TaskGraph(steps)
        manual = self.mongodb.get_document_by_id(document_id=int(manualId))

        # current_step = self.get_current_step(sessionId, sourceId)
        current_step = self.get_current_step_redis(sessionId, manualId, task_graph)

        total_steps = len(steps)

        next_step = task_graph.get_next(current_step)
        self.model = manual["model"]
        if len(manual["steps"])==1:
            step_details=manual["steps"][0]
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
            print(f"insert-1________________________")
            self.mongodb.insert_or_update_data(session_id=sessionId, steps=steps_mongo, total_steps=total_steps,message=message)
            message["status"]="completed"
            self.mongodb.add_end_time(sessionId, step_details["_id"],message)

        print(current_step,manual["steps"][-2]["_id"],task)
        if current_step>manual["steps"][-2]["_id"]:
            return
        
        if current_step == manual["steps"][-2]["_id"] and (task == 0 or current_step==task):
            print("c\no\nr\nr\ne\nc\nt")
            if not self.model:
                # self.update_step(sessionId,current_step+2)
                self.update_step_redis(sessionId, manualId, current_step+2)
                feedback = ""
                feedbackUrl = ""
                for step in manual["steps"]:
                    if step["_id"]==current_step:
                        step_details=step
                        break
                logger.debug(step_details["text"])
                # print(manualId, type(manualId))
                # print(step_details["_id"], type(step_details["_id"]))
                if int(manualId) == 19 and step_details["_id"]==4:
                    print("In manualId 19")
                    key = f"pose:{sessionId}:{manualId}:feedback"
                    feedback = (self.redis_client.get(key)).decode('utf-8')
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
                    "feedback": feedback,
                    "feedbackUrl": feedbackUrl,
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
                    "feedback": feedback,
                    "feedbackUrl": feedbackUrl,
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
                    "feedback": feedback,
                    "videoUrl": step_details["url"],
                    "feedbackUrl": feedbackUrl
                }
                print(f"insert-2________________________")
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
                    # self.reset_step(sessionId)
                    self.reset_step_redis(sessionId, manualId)
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
                    print(f"insert-3________________________")

                    self.mongodb.insert_or_update_data(session_id=sessionId, steps=steps_mongo, total_steps=total_steps,message=message)
                    # self.producer.send(
                    #     video_instruction_kafka_topic,
                    #     value=json.dumps(message).encode("utf-8"),
                    # )
                    return steps[1]
                    
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
                    true_items=get_items(int(current_step),int(manualId))[:]

                    if task!=0:
                        if "text_based_model" in things_present:
                            if step_details["contextType"]!="emt":
                                Text="For the more information please look into demo image."
                            else:
                                Text="The answer you provided is incorrect"
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
                        if manual["_id"] == 19:
                            if not things_present:
                                Text = "I am unable to see you. It might be dark, something could be blocking the camera, or you may not be in front of it. Please check and try again."
                            elif "rightHandRaised" in true_items and "leftHandRaised" in things_present:
                                Text = "I can see your left hand raised. Please raise your right hand instead."
                            elif "rightHandRaised" in true_items and "noHandsRaised" in things_present:
                                Text = "I don't see any hand raised. Please raise your right hand."
                            elif "squatInProcess" in things_present:
                                Text =  "Squats in process."
                            elif "leftHandRaised" in true_items and "rightHandRaised" in things_present:
                                Text = "I can see your right hand raised. Please raise your left hand instead."
                            elif "leftHandRaised" in true_items and "noHandsRaised" in things_present:
                                Text = "I don't see any hand raised. Please raise your left hand."
                            elif "rightHandRaised" in true_items:
                                Text = "Please raise your right hand."
                            elif "leftHandRaised" in true_items:
                                Text = "Please raise your left hand."
                        
                        print(f"\n\n{Text}\n\n")    
                        response  = requests.post(config.t2v_endpoint, json={"text" : Text, "gender": 0})
                        data = json.loads(response.content.decode("utf-8"))
                        message["audioUrl"]= data["file_path"]
                        if manual["_id"]== 13:
                            message["audioUrl"] = "https://cdn-dev.eizen.ai/0/via/pine_labs/audios-hindi/demohindi.mp3"
                        message["step"]=Text
                    print(f"insert-4________________________")

                    self.mongodb.insert_or_update_data(session_id=sessionId, steps=steps_mongo, total_steps=total_steps,message=message)
                    if task==0:
                        return step_details["time"]
                except Exception as e:
                    print(e)
                    traceback.print_exc()
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
                    print(f"insert-5________________________")

                    self.mongodb.insert_or_update_data(session_id=sessionId, steps=steps_mongo, total_steps=total_steps,message=message)
                    # self.producer.send(
                    #     video_instruction_kafka_topic,
                    #     value=json.dumps(message).encode("utf-8"),
                    # )
                    logger.debug(current_step)
                    return steps[current_step]
        elif task == current_step:
            logger.debug(next_step)
            if not self.model:
                if next_step is not None:
                    # self.update_step(sessionId, next_step)
                    self.update_step_redis(sessionId, manualId, next_step)
                    
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
                    print(f"insert-6________________________")

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
                        # self.update_step(sessionId, next_step)
                        self.update_step_redis(sessionId, manualId, next_step)

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
                        print(f"insert-7________________________")

                        self.mongodb.insert_or_update_data(session_id=sessionId, steps=steps_mongo, total_steps=total_steps,message=message)
                        # self.producer.send(
                        #     video_instruction_kafka_topic,
                        #     value=json.dumps(message).encode("utf-8"),
                        # )
                        logger.debug(next_step)
                        return steps.get(next_step, "Please perform the next step.")
                    else:
                        return "Well Done! Your task is completed. Please confirm to start over."

    def close(self):
        self.client.close()
        self.mongodb.close()
        self.redis_client.close()
        