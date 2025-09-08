import datetime
import json
import pymongo
from Config.settings import Settings
from pymongo.errors import PyMongoError
from kafka import KafkaProducer
import redis
import traceback
import logging
import time
from utils.logger_utils import setup_logger

mongo_logger = setup_logger(name='mongo_operations')

config = Settings()

class MongoDBConnector:
    def __init__(self):
        self.connection_string = config.mongo_connection_string_manual
        self.database_name = config.database_name
        self.collection_name = config.collection_name
        self.insights_collection = config.insights_collection
        self.client = None
        self.db = None
        self.collection = None
        self.client_insight = None
        self.db_insight = None
        self.collection_insight = None
        self.producer=KafkaProducer(bootstrap_servers=config.kafka_url)
        self.video_instruction_kafka_topic=config.video_instruction_kafka_topic
        self.redis_client = redis.Redis(host=config.redis_host, port=config.redis_port, db=config.redis_db)

        self.connect()
        self.connect_insights()

    def connect(self):
        self.client = pymongo.MongoClient(self.connection_string)
        self.db = self.client[self.database_name]
        self.collection = self.db[self.collection_name]
    
    def connect_insights(self):
        self.client_insight = pymongo.MongoClient(self.connection_string)
        self.db_insight = self.client_insight[self.database_name]
        self.collection_insight = self.db_insight[self.insights_collection]

    def close(self):
        if self.client:
            self.client.close()

    def get_document_by_id(self, document_id):
        document = self.collection.find_one({"_id": document_id})
        return document

    def insert_or_update_data(self, session_id, steps, total_steps, message, things_present, manual_id):
        start1 = time.time()
        try:
            existing_data = self.collection_insight.find_one({"sessionId": session_id})
            data_to_insert = {"sessionId": session_id, "steps": []}

            if existing_data:
                data_to_insert = existing_data
                for step in data_to_insert["steps"]:
                    if step["stepId"] == steps["stepId"]:
                        for key, value in steps.items():
                            if key != "stepId" and key != "startTime" and key != "status" and key != "repetition":
                                step[key] = value
                        break
                else:
                    steps_with_time = dict(steps)
                    steps_with_time["startTime"] = datetime.datetime.now(datetime.timezone.utc)
                    steps_with_time["endTime"] = datetime.datetime.now(datetime.timezone.utc)
                    message["startTime"]=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")
                    self.producer.send(self.video_instruction_kafka_topic,value=json.dumps(message).encode("utf-8"))
                    data_to_insert["steps"].append(steps_with_time)
            else:
                steps_with_time = dict(steps)
                steps_with_time["startTime"] = datetime.datetime.now(datetime.timezone.utc)
                steps_with_time["endTime"] = datetime.datetime.now(datetime.timezone.utc)
                message["startTime"]=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")
                message["audioUrl"] = ""
                self.producer.send(self.video_instruction_kafka_topic,value=json.dumps(message).encode("utf-8"))
                if int(steps["stepId"]) == total_steps + 1:
                    steps_with_time["status"] = "completed"
                data_to_insert["steps"].append(steps_with_time)
            if 'audioUrl' in message and message["audioUrl"]!= "":
                steps_with_time = dict(steps)
                message["status"]="failed"
                key = f"vip:{session_id}:{manual_id}:state"
                if self.redis_client.exists(key):
                    current_step = int(self.redis_client.get(key))
                else:
                    current_step = 1
                key = f"Pose:{session_id}:{manual_id}:{current_step}:thingsPresent"
                previous_things_present = self.redis_client.get(key)
                if previous_things_present is None:
                    self.redis_client.set(key, json.dumps(things_present))
                    data_to_insert["steps"][-1]["repetition"] += 1
                else:
                    previous_things_present = json.loads(previous_things_present)
                    if sorted(previous_things_present) != sorted(things_present):
                        self.redis_client.set(key, json.dumps(things_present))
                        data_to_insert["steps"][-1]["repetition"] += 1
                repetition = data_to_insert["steps"][-1]["repetition"]
                score = round((1 / (int(repetition) + 1)) * 100, 2)
                data_to_insert["steps"][-1]["stepScore"] = score
                message["repetition"]=data_to_insert["steps"][-1]["repetition"]
                steps_with_time["startTime"] = data_to_insert["steps"][-1]["startTime"]
                steps_with_time["endTime"] = datetime.datetime.now(datetime.timezone.utc)
                message["startTime"]=data_to_insert["steps"][-1]["startTime"].strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")
                self.producer.send(self.video_instruction_kafka_topic,value=json.dumps(message).encode("utf-8"))
            self.collection_insight.update_one(
                {"sessionId": session_id},
                {"$set": data_to_insert},
                upsert=True
            )
            end1 = time.time() - start1
            mongo_logger.info(f"Mongo Insert or Update Step {end1:.3f}s")
        except PyMongoError as e:
            traceback.print_exc()
            return f"An error occurred while inserting or updating data: {e}"
        
    def add_end_time(self, session_id, step_id,message):
        start1 = time.time()
        try:
            step_id = str(step_id)
            document = self.collection_insight.find_one({"sessionId": session_id})

            if document:
                for step in document["steps"]:
                    if step["stepId"] == step_id:
                        if step["status"]!="completed":
                            step["endTime"] = datetime.datetime.now(datetime.timezone.utc)
                            message["startTime"]=step["startTime"].strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")
                            message["status"]="completed"
                            message["endTime"]=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")
                            message["repetition"]=document['steps'][-1]["repetition"]
                            try:
                                message["stepScore"]=str(document['steps'][-1]["stepScore"])
                            except:
                                message["stepScore"]=str(0)
                            self.producer.send(self.video_instruction_kafka_topic,value=json.dumps(message).encode("utf-8"))
                            if step["status"] != "completed":
                                step["status"] = "completed"
                        break
                self.collection_insight.replace_one({"_id": document["_id"]}, document)
            else:
                return "Document not found for the given sessionId and stepId."
            end1 = time.time() - start1
            mongo_logger.info(f"Mongo Add End Time Step: {end1:.3f}s")
        except PyMongoError as e:
            return f"An error occurred while adding endTime: {e}"
