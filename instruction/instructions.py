from pymongo import MongoClient
from pymongo.collection import ReturnDocument
from utils.mongo_operations import MongoDBConnector
from kafka import KafkaProducer
from config.settings import Settings
import json

# Load configurations
config = Settings()
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
    def __init__(self, db_uri="mongodb://Eizen:Eizen123@183.82.116.237:27017/", db_name="testing", collection_name="state", steps={}):
        self.client = MongoClient(db_uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]
        self.steps = steps
        self.task_graph = TaskGraph(steps)
        self.mongodb = MongoDBConnector()
        # Create a Kafka producer
        self.producer = KafkaProducer(bootstrap_servers=kafka_url)

    def get_current_step(self, sessionId, sourceId):
        document = self.collection.find_one({"sessionId": sessionId, "sourceId": sourceId})
        if document:
            # Check if 'currentStep' field exists; if not, add it with a value of 1
            if 'currentStep' not in document:
                self.collection.update_one(
                    {"_id": document["_id"]},
                    {"$set": {"currentStep": 1}}
                )
                return 1
            else:
                return document['currentStep']
        else:
            # This condition might not be needed anymore, but kept for safety
            self.collection.insert_one({"sessionId": sessionId, "sourceId": sourceId, "currentStep": 1})
            return 1

    def update_step(self, sessionId, step):
        # Updates the currentStep. Assumes document exists, but handles the case where currentStep might not.
        self.collection.update_one(
            {"sessionId": sessionId},
            {"$set": {"currentStep": step}}
        )

    def reset_step(self, sessionId):
        self.update_step(sessionId, 1)

    def get_next_step(self, sessionId, sourceId, task, manualId):
        manual = self.mongodb.get_document_by_id(document_id=int(manualId))
        current_step = self.get_current_step(sessionId, sourceId)
        total_steps = len(self.steps)
        next_step = self.task_graph.get_next(current_step)

        if current_step == total_steps and task == 0:
            print("----------")
            print("Well Done! Your task is completed. Starting over.")
            self.reset_step(sessionId)
            step_details = manual["steps"][-1]
            print(step_details["text"])
            message = {
                "sessionId": sessionId,
                "instructionUrl": step_details["url"],
                "manualId": manualId
            }
            self.producer.send(
                video_instruction_kafka_topic,
                value=json.dumps(message).encode("utf-8"),
            )
            return self.steps[1]
        elif task == 0 or task != current_step:
            print("======")
            step_details = manual["steps"][current_step - 1]
            print(step_details["text"])
            message = {
                "sessionId": sessionId,
                "instructionUrl": step_details["url"],
                "manualId": manualId
            }
            self.producer.send(
                video_instruction_kafka_topic,
                value=json.dumps(message).encode("utf-8"),
            )
            print(current_step)
            return self.steps[current_step]
        elif task == current_step:
            print("++++++++")
            print(next_step)
            if next_step is not None:
                self.update_step(sessionId, next_step)
                step_details = manual["steps"][next_step - 1]
                print(step_details["text"])
                message = {
                    "sessionId": sessionId,
                    "instructionUrl": step_details["url"],
                    "manualId": manualId
                }
                self.producer.send(
                    video_instruction_kafka_topic,
                    value=json.dumps(message).encode("utf-8"),
                )
                print(next_step)
                return self.steps.get(next_step, "Please perform the next step.")
            else:
                return "Well Done! Your task is completed. Please confirm to start over."

# Example usage with dynamic steps and graph implementation
# steps = {
#     1: "Pick up the phone and its case.",
#     2: "Assemble the Case to phone.",
#     3: "Take the charger in your hand and connect it to phone.",
#     4: "Turn on the flashlight on your phone.",
#     5: "Turn off the flashlight and put your phone down"
# }

# task_manager = TaskManager(steps=steps)
# sessionId= 1  # Example identifiers

# # Simulate user actions
# print(task_manager.get_next_step(sessionId, 1, 0, 1))  # User does nothing, prompt for step 1
# # print(task_manager.get_next_step(sessionId, sourceId, 1))  # User completes step 1, prompt for step 2
# # Continue this pattern as needed
