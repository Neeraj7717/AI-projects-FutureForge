import asyncio
import concurrent.futures
import threading
import logging
import json
import traceback
from datetime import datetime
from kafka import KafkaConsumer
from model.pose_test_redis_ui import Pose
from Config.settings import Settings
import multiprocessing
import gc
import psutil
# Logging Setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
 
# Optimized Thread Pool
executor = concurrent.futures.ThreadPoolExecutor(max_workers=multiprocessing.cpu_count() * 2)
 
# Pose Detection Model
pose_obj = Pose()
 
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
    auto_offset_reset='latest',  # Process latest frames only
    enable_auto_commit=True,  # Commit offsets automatically
    group_id='vip-consumer-test',
    fetch_max_bytes=1048576,  # Fetch max 1MB data at once
    max_partition_fetch_bytes=524288,  # Fetch max 512KB per partition
    session_timeout_ms=30000  # Session timeout for consumer group
    # linger_ms is not a configuration in this context
)
 
async def process_kafka_message(message):
    """
    Asynchronously processes a Kafka message.
    """
    try:

        with global_state.lock:
            current_frame_no = global_state.frame_no
            global_state.frame_no += 1
        # print("UI Time Stamp:", current_frame_no, ":", message.value.get("timeStamp"))
        # print("Producer Time Stamp:", current_frame_no, ":", message.value.get("prodRecvTimeStamp"))

        # print("Message In Consumer:start", current_frame_no, ":", datetime.now())
        manual_id = message.value.get("manualId")
        if int(manual_id) in {19, 23}:   # Process only relevant messages
            logging.info(f"Processing frame {current_frame_no} for manualId {manual_id}")
            # print(message.value)
            # Submit tasks asynchronously
            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                executor,
                handle_input_data,
                message.value.get("poseLandMarks"),
                message.value.get("sourceId"),
                message.value.get("sessionId"),
                manual_id,
                current_frame_no,
                message.value.get("timeStamp")
            )
        else:
            logging.info(f"Skipping message with manualId: {manual_id}")
 
    except Exception as e:
        logging.error(f"Error processing Kafka message: {e}")
        traceback.print_exc()
 
async def kafka_listener():
    """
    Asynchronous Kafka consumer for reading frames from the stream.
    """
    logging.info("Kafka consumer started for live stream processing.")
    try:
        while True:
            raw_messages = consumer.poll(timeout_ms=10)  # Poll messages quickly
            if raw_messages:
                tasks = [process_kafka_message(msg) for tp, messages in raw_messages.items() for msg in messages]
                await asyncio.gather(*tasks)
    except Exception as e:
        logging.error(f"Error in Kafka consumer: {e}")
        traceback.print_exc()
    finally:
        consumer.close()
        logging.info("Kafka consumer closed.")
 
def handle_input_data(file, sourceId, sessionId, manualId, frame_no, timeStamp):
    """
    Handles the frame processing asynchronously.
    """
    try:
        logging.info(f"Processing frame {frame_no}...")
 
        # Pose detection (preferably on GPU)
        frame, results, things_present, start_time = pose_obj._process_pose_detection(
            file, sourceId, sessionId, manualId, frame_no
        )
        print(things_present)
        # # Run Annotation & Squat Analysis in Parallel
        # executor.submit(pose_obj.draw_annotations, frame, results, sourceId, sessionId, manualId, start_time, frame_no, timeStamp)
        executor.submit(pose_obj.process_squat_analysis, sessionId, frame, things_present, sourceId, manualId, results, frame_no)
 
        logging.info(f"Frame {frame_no} processing completed.")
        memory_usage = psutil.virtual_memory().percent
        if memory_usage > 60:
            logging.info(f"Memory usage is high: {memory_usage}%. Calling gc.collect()...")
            gc.collect() 
 
    except Exception as e:
        logging.error(f"Error processing frame {frame_no}: {e}")
        logging.error(f"Current memory usage: {psutil.virtual_memory().percent}%")
        gc.collect()
        traceback.print_exc()
 
def start_kafka_listener():
    """
    Starts the Kafka listener asynchronously.
    """
    logging.info("Starting Kafka Listener...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(kafka_listener())
 
if __name__ == "__main__":
    logging.info("Starting Live Stream Processing...")
    start_kafka_listener()