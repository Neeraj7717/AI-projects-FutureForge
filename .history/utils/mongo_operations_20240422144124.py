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
    
def insert_or_update_data(self, session_id, steps):
        try:
            # Check if session_id exists
            existing_data = self.collection_insight.find_one({"sessionId": session_id})

            if existing_data:
                # Update existing document
                self.collection_insight.update_one(
                    {"sessionId": session_id},
                    {"$set": {"steps": steps}}
                )
            else:
                # Insert new document
                self.collection_insight.insert_one({"sessionId": session_id, "steps": steps})
        except PyMongoError as e:
            print(f"An error occurred while inserting or updating data: {e}")
            
ins = MongoDBConnector()

ins.insert_or_update_data("1", ["Hehe", "Huhu"])
