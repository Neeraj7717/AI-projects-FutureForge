import asyncio
import concurrent.futures
import threading
import json
import traceback
from kafka import KafkaConsumer
from model.pose_model_test_1 import Pose
from Config.settings import Settings
from utils.logger_utils import setup_logger
executor = concurrent.futures.ThreadPoolExecutor(max_workers=2000)

logger = setup_logger(name='consumer_ui')

pose_obj = Pose()

class GlobalState:
    def __init__(self):
        self.frame_no = 1
        self.lock = threading.Lock()

global_state = GlobalState()

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
    try:
        with global_state.lock:
            current_frame_no = global_state.frame_no
            global_state.frame_no += 1

        manual_id = message.value.get("manualId")
        if int(manual_id) in {19, 23}:
            logger.debug(f"Recivied frame {current_frame_no} for manualId {manual_id}")
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
            logger.debug(f"Skipping message with manualId: {manual_id}")

    except Exception as e:
        logger.error(f"Error processing Kafka message: {e}")
        traceback.print_exc()

async def kafka_listener():
    logger.debug("Kafka consumer started for live stream processing.")
    try:
        while True:
            raw_messages = consumer.poll(timeout_ms=10)
            if raw_messages:
                tasks = [process_kafka_message(msg) for tp, messages in raw_messages.items() for msg in messages]
                await asyncio.gather(*tasks)
    except Exception as e:
        logger.error(f"Error in Kafka consumer: {e}")
        traceback.print_exc()
    finally:
        consumer.close()
        logger.debug("Kafka consumer closed.")

def handle_input_data(file, sourceId, sessionId, manualId, frame_no, timeStamp):
    try:
        frame, results, things_present, start_time = pose_obj._process_pose_detection(
            file, sourceId, sessionId, manualId, frame_no
        )
        executor.submit(pose_obj.process_squat_analysis, sessionId, frame, things_present, sourceId, manualId, results, frame_no)

        logger.debug(f"Frame {frame_no} processing completed.")

    except Exception as e:
        logger.error(f"Error processing frame {frame_no}: {e}")
        traceback.print_exc()

def start_kafka_listener():
    logger.info("Starting Kafka Listener...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(kafka_listener())

if __name__ == "__main__":
    logger.info("Starting Live Stream Processing...")
    start_kafka_listener() 