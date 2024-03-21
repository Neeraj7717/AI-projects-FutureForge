import json
from fastapi import FastAPI
from kafka import KafkaProducer
from utils.mongo_operations import MongoDBConnector
from config.var import Settings

# Initialize FastAPI app
app = FastAPI()

# Load configurations
config = Settings()
kafka_url = config.kafka_url
video_instruction_kafka_topic = config.video_instruction_kafka_topic

# Create a Kafka producer
producer = KafkaProducer(bootstrap_servers=kafka_url)

# Define Node class for graph
class Node:
    def __init__(self, val=0, neighbors=None):
        self.val = val
        self.neighbors = neighbors if neighbors is not None else []

# Define steps and build graph
steps = {
    0: "Greetings!",
    1: "Pick up the phone and its case.",
    2: "Assemble the Case to phone.",
    3: "Take the charger in your hand and connect it to phone.",
    4: "Turn on the flashlight on your phone.",
    5: "Turn off the flash light and place your phone down.",
    6: "Well Done! Your task is completed.",
}

def build_graph(steps):
    graph = {}
    for i in range(len(steps)):
        graph[i] = Node(i)
    # Define graph connections
    graph[0].neighbors = [graph[1]]
    graph[1].neighbors = [graph[2]]
    graph[2].neighbors = [graph[3]]
    graph[3].neighbors = [graph[4]]
    graph[4].neighbors = [graph[5]]
    graph[5].neighbors = [graph[6]]
    return graph

# Initialize graph
graph = build_graph(steps)

# Track completed tasks
task_completed = [False for i in range(len(steps)+1)]
start = {}
end = {}
prev_step = {}

# Define function to complete task
def complete_task(file):
    """Complete a task and send instruction to the user."""
    sourceId = file["sourceId"]
    task = file["task"]
    manualId = int(file["manualId"])
    sessionId = file["sessionId"]
    mongodb = MongoDBConnector()
    manual = mongodb.get_document_by_id(document_id=manualId)

    # Initialize task tracking for sourceId
    if sourceId not in prev_step:
        start[sourceId] = 0
        end[sourceId] = 5
        prev_step[sourceId] = [False for i in range(len(steps))]

    t = False
    
    # Check if task is in graph's neighbors
    for n in graph[start[sourceId]].neighbors:
        if n.val == task and not prev_step[sourceId][task]:
            t = True
            prev_step[sourceId][task] = True
            start[sourceId] = n.val

    if t:
        # Send instruction for the next task
        for n in graph[start[sourceId]].neighbors:
            step_details = manual["steps"][n.val - 1]
            message = {
                "sessionId": sessionId,
                "instructionUrl": step_details["url"],
                "manualId": manualId
            }
            producer.send(
                video_instruction_kafka_topic,
                value=json.dumps(message).encode("utf-8"),
            )
            return message

    elif start[sourceId] != end[sourceId]:
        # Send instruction for pending tasks
        for n in graph[start[sourceId]].neighbors:
            if not prev_step[sourceId][n.val]:
                step_details = manual["steps"][n.val - 1]
                message = {
                    "sessionId": sessionId,
                    "instructionUrl": step_details["url"],
                    "manualId": manualId
                }
                producer.send(
                    video_instruction_kafka_topic,
                    value=json.dumps(message).encode("utf-8"),
                )
                return message

    # If all tasks completed, reset and send completion message
    if start[sourceId] == end[sourceId]:
        start[sourceId] = 0
        prev_step[sourceId] = [False for i in range(len(steps))]
        step_details = manual["steps"][n.val - 1]
        message = {
            "sessionId": sessionId,
            "instructionUrl": step_details["url"],
            "manualId": manualId
        }
        producer.send(
            video_instruction_kafka_topic,
            value=str(json.dumps(message).encode("utf-8")),
        )
        return message
