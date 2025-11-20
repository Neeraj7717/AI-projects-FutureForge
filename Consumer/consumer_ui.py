
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['GLOG_minloglevel'] = '3'

import asyncio
import concurrent.futures
import threading
import logging
import json
import traceback
import yaml
from pathlib import Path
from datetime import datetime
from kafka import KafkaConsumer
from Config.settings import Settings
from utils.eizen_utils.logger_utils.logger_operations import LoggerOperations

consumer_logger = LoggerOperations(logger_name='consumer_logger', log_level=logging.INFO, use_log_file=False)
# Load YAML Configuration
def load_consumer_config():
    """Load consumer configuration from YAML file"""
    config_path = Path(__file__).parent / "consumer_config.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

# Load configuration and create manual_id to function mapping
consumer_config = load_consumer_config()
routing_config = consumer_config.get('routing', {})

# Create a flat mapping of manual_id -> function_name
manual_id_to_function = {}
for function_name, manual_ids in routing_config.items():
    for manual_id in manual_ids:
        manual_id_to_function[manual_id] = function_name

consumer_logger.debug(f"Loaded routing config for {len(manual_id_to_function)} manual IDs")

# Lazy import of functions - only import when needed
_functions_cache = {}

def get_function(function_name):
    """Lazy load processing functions only when needed"""
    if function_name not in _functions_cache:
        from Consumer import main_functions
        _functions_cache[function_name] = getattr(main_functions, function_name)
    return _functions_cache[function_name]

# Optimized Thread Pool - reduced from 5000 to prevent RAM explosion
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
    Asynchronously processes a Kafka message using YAML-based routing.
    """
    try:
        with global_state.lock:
            current_frame_no = global_state.frame_no
            global_state.frame_no += 1

        manual_id = int(message.value.get("manualId"))

        # Lookup function from YAML config
        function_name = manual_id_to_function.get(manual_id)

        if function_name is None:
            consumer_logger.debug(f"Skipping message with unknown manualId: {manual_id}")
            return

        # Get the processing function (lazy loaded)
        process_func = get_function(function_name)

        # Determine data field based on function type
        data_field = "poseLandMarks" if function_name == "pose_detection" else "frameUri"

        consumer_logger.info(f"Processing frame {current_frame_no} for manualId {manual_id} using {function_name}")

        # Execute function in thread pool
        loop = asyncio.get_event_loop()
        loop.run_in_executor(
            executor,
            process_func,
            message.value.get(data_field),
            message.value.get("sourceId"),
            message.value.get("sessionId"),
            manual_id,
            current_frame_no,
            message.value.get("timeStamp")
        )

        consumer_logger.debug(f"Sent frame {current_frame_no} to {function_name}")

    except Exception as e:
        consumer_logger.error(f"Error processing Kafka message: {e}")
        traceback.print_exc()

async def kafka_listener():
    """
    Asynchronous Kafka consumer for reading frames from the stream.
    """
    consumer_logger.debug("Kafka consumer started for live stream processing.")
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
        consumer_logger.debug("Kafka consumer closed.")

def start_kafka_listener():
    """
    Starts the Kafka listener asynchronously.
    """
    consumer_logger.debug("Starting Kafka Listener...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(kafka_listener())

if __name__ == "__main__":
    consumer_logger.debug("Starting Live Stream Processing...")
    start_kafka_listener()