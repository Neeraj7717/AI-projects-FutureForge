from Consumer.main_functions import *
import asyncio
import concurrent.futures
import threading
import logging
import json
import traceback
from datetime import datetime
from kafka import KafkaConsumer
from Config.settings import Settings
import multiprocessing


# Consumer Logger Setup
consumer_logger = logging.getLogger('consumer_logger')
consumer_logger.setLevel(logging.INFO)
consumer_logger.propagate = False  # Prevent propagation to root logger

# Create console handler with formatting
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - Consumer - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)

# Add handler to consumer logger
consumer_logger.addHandler(console_handler)

# Optimized Thread Pool
executor = concurrent.futures.ThreadPoolExecutor(max_workers=5000)

# Global State for Frame Tracking
class GlobalState:
    def __init__(self):
        self.frame_no = 1
        self.lock = threading.Lock()

global_state = GlobalState()

# Kafka Consumer Configurations (Optimized for Live Stream Processing)
config = Settings()
consumer = KafkaConsumer(
    'via-frame',
    bootstrap_servers=config.kafka_url,
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    auto_offset_reset='latest',
    enable_auto_commit=True,
    group_id='vip-consumer-test',
    fetch_max_bytes=1048576,
    max_partition_fetch_bytes=524288,
    session_timeout_ms=30000
)

async def process_kafka_message(message):
    """
    Asynchronously processes a Kafka message.
    """
    try:
        with global_state.lock:
            current_frame_no = global_state.frame_no
            global_state.frame_no += 1
        manual_id = message.value.get("manualId")

        if int(manual_id) in {19, 23}:
            consumer_logger.info(f"Processing frame {current_frame_no} for manualId {manual_id} Step 1")
            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                executor,
                pose_detection,
                message.value.get("poseLandMarks"),
                message.value.get("sourceId"),
                message.value.get("sessionId"),
                manual_id,
                current_frame_no,
                message.value.get("timeStamp")
            )
            consumer_logger.info(f"Sent Process frame {current_frame_no} for manualId {manual_id} Step 1")
        
        elif int(manual_id) in {1, 2, 3, 5, 7}:
            consumer_logger.info(f"Processing frame {current_frame_no} for manualId {manual_id} Step 2")
            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                executor,
                action_detection,
                message.value.get("frameUri"),
                message.value.get("sourceId"),
                message.value.get("sessionId"),
                manual_id,
                current_frame_no,
                message.value.get("timeStamp")
            )
            consumer_logger.info(f"Sent Process frame {current_frame_no} for manualId {manual_id} Step 2")

        elif int(manual_id) in {20, 22}:
            consumer_logger.info(f"Processing frame {current_frame_no} for manualId {manual_id} Step 3")
            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                executor,
                gender_detection,
                message.value.get("frameUri"),
                message.value.get("sourceId"),
                message.value.get("sessionId"),
                manual_id,
                current_frame_no,
                message.value.get("timeStamp")
            )
            consumer_logger.info(f"Sent Process frame {current_frame_no} for manualId {manual_id} Step 3")

        elif int(manual_id) in {4, 6, 8}:
            consumer_logger.info(f"Processing frame {current_frame_no} for manualId {manual_id} Step 4")
            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                executor,
                ekyc_detect,
                message.value.get("frameUri"),
                message.value.get("sourceId"),
                message.value.get("sessionId"),
                manual_id,
                current_frame_no,
                message.value.get("timeStamp")
            )
            consumer_logger.info(f"Sent Process frame {current_frame_no} for manualId {manual_id} Step 4")

        elif int(manual_id) in {9, 10, 12, 13, 14, 16, 18}:
            consumer_logger.info(f"Processing frame {current_frame_no} for manualId {manual_id} Step 5")
            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                executor,
                text_detect,
                message.value.get("frameUri"),
                message.value.get("sourceId"),
                message.value.get("sessionId"),
                manual_id,
                current_frame_no,
                message.value.get("timeStamp")
            )
            consumer_logger.info(f"Sent Process frame {current_frame_no} for manualId {manual_id} Step 5")

        elif int(manual_id) in {11}:
            consumer_logger.info(f"Processing frame {current_frame_no} for manualId {manual_id} Step 6")
            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                executor,
                chair_detect,
                message.value.get("frameUri"),
                message.value.get("sourceId"),
                message.value.get("sessionId"),
                manual_id,
                current_frame_no,
                message.value.get("timeStamp")
            )
            consumer_logger.info(f"Sent Process frame {current_frame_no} for manualId {manual_id} Step 6")
        
        elif int(manual_id) in {15}:
            consumer_logger.info(f"Processing frame {current_frame_no} for manualId {manual_id} Step 7")
            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                executor,
                similar_image,
                message.value.get("frameUri"),
                message.value.get("sourceId"),
                message.value.get("sessionId"),
                manual_id,
                current_frame_no,
                message.value.get("timeStamp")
            )
            consumer_logger.info(f"Sent Process frame {current_frame_no} for manualId {manual_id} Step 7")

        elif int(manual_id) in {17}:
            consumer_logger.info(f"Processing frame {current_frame_no} for manualId {manual_id} Step 8")
            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                executor,
                system_monitor,
                message.value.get("frameUri"),
                message.value.get("sourceId"),
                message.value.get("sessionId"),
                manual_id,
                current_frame_no,
                message.value.get("timeStamp")
            )
            consumer_logger.info(f"Sent Process frame {current_frame_no} for manualId {manual_id} Step 8")

        else:
            consumer_logger.info(f"Skipping message with manualId: {manual_id}")

    except Exception as e:
        consumer_logger.error(f"Error processing Kafka message: {e}")
        traceback.print_exc()

async def kafka_listener():
    """
    Asynchronous Kafka consumer for reading frames from the stream.
    """
    consumer_logger.info("Kafka consumer started for live stream processing.")
    try:
        while True:
            raw_messages = consumer.poll(timeout_ms=10)  # Poll messages quickly
            if raw_messages:
                tasks = [process_kafka_message(msg) for tp, messages in raw_messages.items() for msg in messages]
                await asyncio.gather(*tasks)
    except Exception as e:
        consumer_logger.error(f"Error in Kafka consumer: {e}")
        traceback.print_exc()
    finally:
        consumer.close()
        consumer_logger.info("Kafka consumer closed.")

def start_kafka_listener():
    """
    Starts the Kafka listener asynchronously.
    """
    consumer_logger.info("Starting Kafka Listener...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(kafka_listener())

if __name__ == "__main__":
    consumer_logger.info("Starting Live Stream Processing...")
    start_kafka_listener()