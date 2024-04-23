import pymongo
from config.settings import Settings
from pymongo.errors import PyMongoError


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
    

Sure, you can add the start_time key to the dictionary data only when a new stepId is inserted. Here's the updated function:

python
Copy code
from pymongo.errors import PyMongoError
from datetime import datetime

class YourClassName:
    def __init__(self, database_name, connection_string, insights_collection):
        self.database_name = database_name
        self.connection_string = connection_string
        self.insights_collection = insights_collection
        self.client = MongoClient(connection_string)
        self.db = self.client[database_name]
        self.collection_insight = self.db[insights_collection]

    def insert_or_update_data(self, session_id, steps):
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
                            if key != "stepId" and key != "start_time":
                                step[key] = value
                        break
                else:
                    # Append new stepId to steps list
                    steps_with_time = dict(steps)
                    steps_with_time["start_time"] = datetime.now()  # Adding start_time
                    data_to_insert["steps"].append(steps_with_time)
            else:
                # Insert new document
                steps_with_time = dict(steps)
                steps_with_time["start_time"] = datetime.now()  # Adding start_time
                data_to_insert["steps"].append(steps_with_time)

            # Update or insert the document
            self.collection_insight.update_one(
                {"sessionId": session_id},
                {"$set": data_to_insert},
                upsert=True
            )

        except PyMongoError as e:
            print(f"An error occurred while inserting or updating data: {e}")
            
ins = MongoDBConnector()
steps_mongo = {
    "sessionId": "1",
    "manualId": "",
    "stepId": "1",
    "step": "",
    "status": "inStatus",
    "duration": "",
    "repetition": "",
    "feedback": "",
    "videoUrl": "",
    "feedbackUrl": "",
}
ins.insert_or_update_data("1", steps_mongo)