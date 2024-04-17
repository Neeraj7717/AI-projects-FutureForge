import json
from config.settings import Settings
import logging
from utils.mongo_operations import MongoDBConnector
from kafka import KafkaProducer

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

class LlavaInference:
    def __init__(self, steps = {}):
        self.steps = steps
        self.mongodb = MongoDBConnector()
        self.producer = KafkaProducer(bootstrap_servers=kafka_url)
        
    def verify(self, sessionId, sourceId, task, manualId):
        manual = self.mongodb.get_document_by_id(document_id=int(manualId))
        step_details = manual["steps"][-1]
        if task is not None:
            data = {
                "file": "https://campaigntool.s3.ap-south-1.amazonaws.com/edusecase/1.jpeg",
                "question": "Is the Chemical Equation shown in the image correct or not? Give me one word answer, Yes or No"
            }
            response_string = self.api_client.call_api(data)
            if response_string["output"] == "Yes":
                message = {
                    "sessionId": sessionId,
                    "instructionUrl": step_details["url"],
                    "manualId": manualId
                }
                self.producer.send(
                    video_instruction_kafka_topic,
                    value=json.dumps(message).encode("utf-8"),
                )
                