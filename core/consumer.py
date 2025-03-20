import argparse
import asyncio
import datetime
import concurrent.futures
from model.detections_test_pose import Detections
from model.pose_test_redis2 import Pose
from model.gender_model import ProcessFrame
import traceback
from datetime import datetime
from pydantic import BaseModel
from typing import Optional
from Config.settings import Settings
import threading
from kafka import KafkaConsumer
import json

executor = concurrent.futures.ThreadPoolExecutor(max_workers=20)

detector = Detections()
pose_obj = Pose()
gender = ProcessFrame()

class GlobalState:
    def __init__(self):
        self.frame_no = 1
        self.lock = threading.Lock()

global_state = GlobalState()

config = Settings()

class Input(BaseModel):
    file: Optional[str] = None
    sourceId: Optional[str] = None
    sessionId: Optional[str] = None
    manualId: Optional[str] = None


# Initialize Kafka consumer with group 'vip'
consumer = KafkaConsumer(
    'vip-frame',
    bootstrap_servers=config.kafka_url,
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    auto_offset_reset='earliest',
    enable_auto_commit=True,
    group_id='vip'  # Adding group 'vip'
)

# Function to read messages from Kafka
async def read_kafka_messages():
    while True:
        for message in consumer:
            input_data = Input(**message.value)  # Store the consumer value into Input
            print(f"Received message: {input_data}")
            asyncio.create_task(handle_input_data(input_data))

async def handle_input_data(input_data: Input):
    if input_data.task_type == "pose":
        await detect_pose(input_data)
    elif input_data.task_type == "action":
        await detect_action(input_data)
    elif input_data.task_type == "gender":
        await detect_gender_function(input_data)
    elif input_data.task_type == "ekyc":
        await ekyc_detect_function(input_data)
    elif input_data.task_type == "text":
        await text_detect_function(input_data)
    elif input_data.task_type == "image_upload":
        await image_upload_function(input_data)
    elif input_data.task_type == "chair":
        await chair_detect_function(input_data)
    elif input_data.task_type == "similar_image":
        await similar_image_function(input_data)
    elif input_data.task_type == "system_monitor":
        await system_monitor_function(input_data)

# Start reading messages in a separate task
async def start_kafka_listener():
    asyncio.create_task(read_kafka_messages())

async def detect_pose(input_data: Input):
    print("Processing pose detection for:", input_data)
    # Dummy method call
    await asyncio.sleep(0)

async def detect_action(input_data: Input):
    print("Processing action detection for:", input_data)
    # Dummy method call
    await asyncio.sleep(0)

async def detect_gender_function(input_data: Input):
    print("Processing gender detection for:", input_data)
    # Dummy method call
    await asyncio.sleep(0)

async def ekyc_detect_function(input_data: Input):
    print("Processing EKYC detection for:", input_data)
    # Dummy method call
    await asyncio.sleep(0)

async def text_detect_function(input_data: Input):
    print("Processing text detection for:", input_data)
    # Dummy method call
    await asyncio.sleep(0)

async def image_upload_function(input_data: Input):
    print("Processing image upload for:", input_data)
    # Dummy method call
    await asyncio.sleep(0)

async def chair_detect_function(input_data: Input):
    print("Processing chair detection for:", input_data)
    # Dummy method call
    await asyncio.sleep(0)

async def similar_image_function(input_data: Input):
    print("Processing similar image detection for:", input_data)
    # Dummy method call
    await asyncio.sleep(0)

async def system_monitor_function(input_data: Input):
    print("Processing system monitor for:", input_data)
    # Dummy method call
    await asyncio.sleep(0)