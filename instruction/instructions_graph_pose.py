from pymongo import MongoClient
from pymongo.collection import ReturnDocument
import requests
from utils.mongo_operations import MongoDBConnector
from kafka import KafkaProducer
from Config.settings import Settings
import json
import traceback
import redis
from utils.logger_utils import setup_logger

config = Settings()

instruction_logger = setup_logger(name='instruction_graph_pose')

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
        self.redis_client = redis.Redis(host=config.redis_host, port=config.redis_port, db=config.redis_db)
 
    def get_current_step_redis(self, sessionId, manualId,task_graph):
        key = f"vip:{sessionId}:{manualId}:state"
        try:
            start_step = list(task_graph.get_graph().keys())[0]
        except:
            start_step = 0
        if not self.redis_client.exists(key):
            self.redis_client.set(key, start_step)
            return start_step
        else:
            current_step = int(self.redis_client.get(key))
            return current_step

    def update_step_redis(self, sessionId, manualId, step):
        key = f"vip:{sessionId}:{manualId}:state"
        self.redis_client.set(key, step)

    def reset_step_redis(self, sessionId, manualId):
        self.update_step_redis(sessionId, manualId, 1)
 
    def get_next_step(self, sessionId, sourceId, task, manualId, frame_bytes,things_present,data, steps):
        
        task_graph = TaskGraph(steps)
        manual = self.mongodb.get_document_by_id(document_id=int(manualId))

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
                    "startTime": "",
                    "stepScore":""
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
                    "feedbackUrl": "",
                    "stepScore":100.0
                }
            
            instruction_logger.debug("insert-1________________________")
            self.mongodb.insert_or_update_data(session_id=sessionId, steps=steps_mongo, total_steps=total_steps,message=message, things_present=things_present, manual_id=manualId)
            message["status"]="completed"
            self.mongodb.add_end_time(sessionId, step_details["_id"],message)

        instruction_logger.debug(f"current_step: {current_step}, last_step: {manual['steps'][-2]['_id']}, task: {task}")
        if current_step>manual["steps"][-2]["_id"]:
            return
        
        if current_step == manual["steps"][-2]["_id"] and (task == 0 or current_step==task):
            instruction_logger.debug("c\no\nr\nr\ne\nc\nt")
            if not self.model:
                self.update_step_redis(sessionId, manualId, current_step+2)
                feedback = ""
                feedbackUrl = ""
                for step in manual["steps"]:
                    if step["_id"]==current_step:
                        step_details=step
                        break
                instruction_logger.debug(f"{step_details['text']}")
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
                    "startTime": "",
                    "stepScore":""
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
                    "startTime": "",
                    "stepScore":""
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
                    "feedbackUrl": feedbackUrl,
                    "stepScore":100.0
                }
                instruction_logger.debug(f"insert-2________________________")
                self.mongodb.insert_or_update_data(session_id=sessionId, steps=steps_mongo, total_steps=total_steps,message=message, things_present=things_present, manual_id=manualId)

                message["status"]="completed"
                self.mongodb.add_end_time(sessionId, step_details["_id"],message)
                return step_details["time"]
            else:
                response = self.llava.verify(frame_bytes=frame_bytes)
                if response == "yes":
                    self.reset_step_redis(sessionId, manualId)
                    step_details = manual["steps"][-1]
                    instruction_logger.debug(f"{step_details['text']}")
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
                    "feedbackUrl": "",
                    "stepScore":100.0
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
                        "startTime": "",
                        "stepScore":""
                    }
                    instruction_logger.info(f"insert-3________________________")

                    self.mongodb.insert_or_update_data(session_id=sessionId, steps=steps_mongo, total_steps=total_steps,message=message, things_present=things_present, manual_id=manualId)
                    return steps[1]
                    
        elif task == 0 or task != current_step:
            if not self.model:
                for step in manual["steps"]:
                    if step["_id"] == current_step:
                        step_details = step
                        break
                instruction_logger.debug(f"{step_details['text']}")
                message = {
                    "stepId": str(step_details["_id"]),
                    "sessionId": sessionId,
                    "videoUrl": step_details["url"],
                    "manualId": manualId,
                    "step": step_details["text"],
                    "status": "inProgress",
                    "endTime": "",
                    "audioUrl": "",
                    "contextUrl": step_details["contextUrl"],
                    "contextType": step_details["contextType"],
                    "repetition": 0,
                    "feedback": "",
                    "feedbackUrl": "",
                    "startTime": "",
                    "stepScore":""
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
                    "feedbackUrl": "",
                    "stepScore":100.0
                }
                try:
                    def get_items(step_id, manual_id):
                        return data[step_id]
                    things_present = list(set(things_present))
                    true_items = get_items(int(current_step), int(manualId))[:]

                    if task != 0:
                        if "text_based_model" in things_present:
                            if step_details["contextType"] != "emt":
                                Text = "For the more information please look into demo image."
                            else:
                                Text = "The answer you provided is incorrect"

                        else:
                            true_items = get_items(int(current_step), int(manualId))[:]
                            if "Person" in true_items:
                                true_items.remove("Person")
                            if "Person" in things_present:
                                things_present.remove("Person")
                            text = step_details["text"]

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

                            if Text == "You are holding nothing and you should hold nothing.":
                                Text = "Ensure you are having good lighting."


                        if manual["_id"] in {19, 23}:
                            instruction_logger.info(f"thingsPresent: {things_present}---- true_items: {true_items}")
                            if not things_present:
                                Text = "I can't see you. Please stand in front of the camera."
                            elif sorted(["personPresent"]) == sorted(true_items):
                                if "personPresent" in things_present:
                                    message["status"] = "completed"
                                    self.mongodb.add_end_time(sessionId, step_details["_id"],message)
                                    return
                                
                            elif sorted(["personPresent","rightHandAbove90"]) == sorted(true_items):
                                if "rightHandBelow90" in things_present:
                                    Text = "Raise your right hand above your shoulders"
                                elif "leftHandAbove90" in things_present or "leftBelowAbove90" in things_present:
                                    Text = "I see your left hand raised. Please raise your right hand instead."
                                elif "bothHandsBelow90" in things_present or "bothHandsAbove90" in things_present:
                                    Text = "Your are raising both hands. Please raise only your right hand."
                                elif "personPresent" in things_present:
                                    Text = "I don't see any hand raised. Please raise your right hand"
                                else:
                                    return
                            
                            elif sorted(["personPresent","leftHandAbove90"]) == sorted(true_items):
                                if "leftHandBelow90" in things_present:
                                    Text = "Raise your left hand above your shoulders"
                                elif "rightHandAbove90" in things_present or "rightHandBelow90" in things_present:
                                    Text = "I see your right hand raised. Please raise your left hand instead."
                                elif "bothHandsBelow90" in things_present or "bothHandsAbove90" in things_present:
                                    Text = "Your are raising both hands. Please raise only your left hand."
                                elif "personPresent" in things_present:
                                    Text = "I don't see any hand raised. Please raise your left hand"
                                else:
                                    return
                                
                            elif sorted(["personPresent", "liftHandDown"]) == sorted(true_items):
                                if "rightHandAbove90" in things_present or "rightHandBelow90" in things_present:
                                    Text = "I see your right hand raised. Please lower your right hand."
                                elif "leftHandAbove90" in things_present or "leftBelowAbove90" in things_present:
                                    Text = "I see your left hand raised. Please lower your left hand"
                                elif "bothHandsBelow90" in things_present or "bothHandsAbove90" in things_present:
                                    Text = "Your are raising both hands. Please lower your hands."
                                else:
                                    return

                            elif sorted(["personPresent", "rightHandDown"]) == sorted(true_items):
                                if "rightHandAbove90" in things_present or "rightHandBelow90" in things_present:
                                    Text = "I see your right hand raised. Please lower your right hand."
                                elif "leftHandAbove90" in things_present or "leftBelowAbove90" in things_present:
                                    Text = "I see your left hand raised. Please lower your left hand"
                                elif "bothHandsBelow90" in things_present or "bothHandsAbove90" in things_present:
                                    Text = "Your are raising both hands. Please lower your hands."
                                else:
                                    return
                            
                            elif sorted(["personPresent", "bothHandsAbove90"]) == sorted(true_items):
                                if "bothHandsBelow90" in things_present:
                                    Text = "Please raise your both hands above the shoulders."
                                elif "rightHandAbove90" in things_present or "rightHandBelow90" in things_present:
                                    Text = "I see your right hand raised. Please raise your both hands above the shoulders."
                                elif "leftHandAbove90" in things_present or "leftBelowAbove90" in things_present:
                                    Text = "I see your left hand raised. Please raise your both hands above the shoulders."
                                elif "personPresent" in things_present:
                                    Text = "You are not raising your hands. Please raise your both hands above the shoulders."
                                else:
                                    return
                            
                            elif sorted(["personPresent", "noHandRaised"]) == sorted(true_items):
                                if "bothHandsBelow90" in things_present or "bothHandsAbove90" in things_present:
                                    Text = "Your are raising both hands. Please lower your hands."
                                elif "rightHandAbove90" in things_present or "rightHandBelow90" in things_present:
                                    Text = "I see your right hand raised. Please lower your right hand."
                                elif "leftHandAbove90" in things_present or "leftBelowAbove90" in things_present:
                                    Text = "I see your left hand raised. Please lower your left hand."
                                else:
                                    return
                        

                        instruction_logger.info(f"\n\n{Text}\n\n")
                        response = requests.post(config.t2v_endpoint, json={"text": Text, "gender": 0})
                        data = json.loads(response.content.decode("utf-8"))
                        message["audioUrl"] = data["file_path"]
                        if manual["_id"] == 13:
                            message["audioUrl"] = "https://cdn-dev.eizen.ai/0/via/pine_labs/audios-hindi/demohindi.mp3"
                        message["step"] = Text
                    instruction_logger.info(f"insert-4________________________")

                    self.mongodb.insert_or_update_data(session_id=sessionId, steps=steps_mongo, total_steps=total_steps, message=message, things_present=things_present, manual_id=manualId)

                    if task == 0:
                        return step_details["time"]
                except Exception as e:
                    instruction_logger.info(f"Error Occured: {e}")
                    traceback.print_exc()
                    return e
                instruction_logger.info(f"current_step: {current_step}, last_step: {manual['steps'][-2]['_id']}, task: {task}")
                return 0
            else:
                response = self.llava.verify(frame_bytes=frame_bytes)
                if response == "Yes":
                    for step in manual["steps"]:
                        if step["_id"]==current_step:
                            step_details=step
                            break
                    instruction_logger.debug(f"{step_details['text']}")
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
                        "startTime": "",
                        "stepScore":""
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
                    "feedbackUrl": "",
                    "stepScore":100.0
                    }
                    instruction_logger.debug(f"insert-5________________________")

                    self.mongodb.insert_or_update_data(session_id=sessionId, steps=steps_mongo, total_steps=total_steps,message=message, things_present=things_present, manual_id=manualId)

                    instruction_logger.debug(f"{current_step}")
                    return steps[current_step]
        elif task == current_step:
            instruction_logger.debug(f"{next_step}")
            if not self.model:
                if next_step is not None:
                    self.update_step_redis(sessionId, manualId, next_step)
                    
                    for step in manual["steps"]:
                        if step["_id"]==current_step:
                            step_details=step
                            break
                    instruction_logger.debug(f"{step_details['text']}")
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
                        "startTime": "",
                        "stepScore":""
                        }
                    self.mongodb.add_end_time(sessionId, current_step,message)
                    for step in manual["steps"]:
                        if step["_id"]==next_step:
                            step_details=step
                            break
                    instruction_logger.debug(f"{step_details['text']}")
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
                        "startTime": "",
                        "stepScore":""
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
                    "feedbackUrl": "",
                    "stepScore":100.0
                    }
                    instruction_logger.info(f"insert-6________________________")

                    self.mongodb.insert_or_update_data(session_id=sessionId, steps=steps_mongo, total_steps=total_steps,message=message, things_present=things_present, manual_id=manualId)

                    instruction_logger.debug(f"{next_step}")
                    return step_details["time"]
                else:
                    return "Well Done! Your task is completed. Please confirm to start over."
            else:
                response = self.llava.verify(frame_bytes=frame_bytes)
                if response == "yes" or response == "Yes":
                    if next_step is not None:
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
                            "startTime": "",
                            "stepScore":""
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
                            "startTime": "",
                            "stepScore":""
                        }
                        for step in manual["steps"]:
                            if step["_id"]==next_step:
                                step_details=step
                                break
                        instruction_logger.debug(f"{step_details['text']}")
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
                            "startTime": "",
                            "stepScore":""
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
                            "feedbackUrl": "",
                            "stepScore":100.0
                        }
                        instruction_logger.debug(f"insert-7________________________")
                        self.mongodb.insert_or_update_data(session_id=sessionId, steps=steps_mongo, total_steps=total_steps,message=message, things_present=things_present, manual_id=manualId)
                        instruction_logger.debug(f"{next_step}")
                        return steps.get(next_step, "Please perform the next step.")
                    else:
                        return "Well Done! Your task is completed. Please confirm to start over."

    def close(self):
        self.client.close()
        self.mongodb.close()
        self.redis_client.close()