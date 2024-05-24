import datetime
import json
import pymongo
from Config.settings import Settings
from pymongo.errors import PyMongoError
from kafka import KafkaProducer


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

    def insert_or_update_data(self, session_id, steps, total_steps,message):
        try:
            # Check if session_id exists
            existing_data = self.collection_insight.find_one({"sessionId": session_id})

            # Prepare data to be inserted or updated
            data_to_insert = {"sessionId": session_id, "steps": []}

            # If session_id exists, update the steps data
            if existing_data:
                data_to_insert = existing_data
                
                # Check if stepId already exists in the list of steps
                for step in data_to_insert["steps"]:
                    if step["stepId"] == steps["stepId"]:
                        # Update other details if anything is altered
                        for key, value in steps.items():
                            #print(key,value)
                            if key != "stepId" and key != "startTime" and key != "status" and key != "repetition":
                                step[key] = value
                        #print(data_to_insert["steps"])
                        #print("\n\n-------------------------------------")
                        break
                else:
                    
                    # Append new stepId to steps list
                    steps_with_time = dict(steps)
                    steps_with_time["startTime"] = datetime.datetime.now(datetime.timezone.utc)  # Adding start_time
                    message["startTime"]=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")
                    # if 'audioUrl' in message:
                    #     del message["audioUrl"]
                    # del message["contextUrl"]
                    # del message["contextType"]
                    self.producer.send(self.video_instruction_kafka_topic,value=json.dumps(message).encode("utf-8"))
                    if int(steps["stepId"]) == total_steps + 1:
                        steps_with_time["status"] = "completed"
                    data_to_insert["steps"].append(steps_with_time)
            else:
                
                # Insert new document
                steps_with_time = dict(steps)
                steps_with_time["startTime"] = datetime.datetime.now(datetime.timezone.utc) 
                steps_with_time["endTime"] = datetime.datetime.now(datetime.timezone.utc) 
                # Adding start_time
                message["startTime"]=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")
                message["audioUrl"] = ""
                # if 'audioUrl' in message:
                #     del message["audioUrl"]
                # del message["contextUrl"]
                # del message["contextType"]
                self.producer.send(self.video_instruction_kafka_topic,value=json.dumps(message).encode("utf-8"))
                if int(steps["stepId"]) == total_steps + 1:
                    steps_with_time["status"] = "completed"

                data_to_insert["steps"].append(steps_with_time)
            if 'audioUrl' in message and message["audioUrl"]!= "":
                steps_with_time = dict(steps)
                # message["videoUrl"]= ""
                message["status"]="failed"
                #print(data_to_insert["steps"])
                #print("\n\n")
                data_to_insert["steps"][-1]["repetition"]+=1
                #print(data_to_insert["steps"][-1])
                #print("\n\n")
                
                
                message["repetition"]=data_to_insert["steps"][-1]["repetition"]
                steps_with_time["startTime"] = data_to_insert["steps"][-1]["startTime"]  # Adding start_time
                steps_with_time["endTime"] = datetime.datetime.now(datetime.timezone.utc) 
                message["startTime"]=data_to_insert["steps"][-1]["startTime"].strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")
                # if 'audioUrl' in message:
                #     del message["audioUrl"]
                # del message["contextUrl"]
                # del message["contextType"]
                self.producer.send(self.video_instruction_kafka_topic,value=json.dumps(message).encode("utf-8"))
            # Update or insert the document
            self.collection_insight.update_one(
                {"sessionId": session_id},
                {"$set": data_to_insert},
                upsert=True
            )
            #print(data_to_insert)

        except PyMongoError as e:
            return f"An error occurred while inserting or updating data: {e}"
    def add_end_time(self, session_id, step_id,message):
        try:
            step_id = str(step_id)
            # Find the document with the given sessionId and stepId
            document = self.collection_insight.find_one({"sessionId": session_id})
            if document:
                for step in document["steps"]:
                    if step["stepId"] == step_id:
                        # Check if endTime already exists, if not, set current time
                        if "endTime" not in step:
                            step["endTime"] = datetime.datetime.now(datetime.timezone.utc)
                            message["startTime"]=step["startTime"].strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")
                            message["status"]="completed"
                            message["endTime"]=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")
                            # if 'audioUrl' in message:
                            #     del message["audioUrl"]
                            # if "contextUrl" in message:
                            #     del message["contextUrl"]
                            # if "contextType" in message:    
                            #     del message["contextType"]
                            # print(document)
                            message["repetition"]=document['steps'][-1]["repetition"]
                            self.producer.send(self.video_instruction_kafka_topic,value=json.dumps(message).encode("utf-8"))
                            # Update status to "completed"
                            if step["status"] != "completed":
                                step["status"] = "completed"
                        break
                # Update the document with the modified steps
                self.collection_insight.replace_one({"_id": document["_id"]}, document)
            else:
                return "Document not found for the given sessionId and stepId."

        except PyMongoError as e:
            return f"An error occurred while adding endTime: {e}"
