import asyncio
import datetime
import concurrent.futures
from model.pose_test_redis import Pose
import traceback
from datetime import datetime
from Config.settings import Settings
import threading
from kafka import KafkaConsumer
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

executor = concurrent.futures.ThreadPoolExecutor(max_workers=2000)

pose_obj = Pose()

class GlobalState:
    def __init__(self):
        self.frame_no = 1
        self.lock = threading.Lock()

global_state = GlobalState()

config = Settings()

# consumer = KafkaConsumer(
#     'via-frame',
#     bootstrap_servers=config.kafka_url,
#     value_deserializer=lambda m: json.loads(m.decode('utf-8')),
#     auto_offset_reset='latest',
#     enable_auto_commit=True,
#     group_id='vip-consumer-test'
# )



# def read_kafka_messages():
#     print("Kafka consumer started.")
#     try:
#         for message in consumer:
#             print("Kafka consumer started.")

#             with global_state.lock:
#                 current_frame_no = global_state.frame_no
#                 global_state.frame_no += 1
#             print("UI Time Stamp:", current_frame_no, ":", message.value.get("timeStamp"))
#             print("Message In Consumer:start", current_frame_no, ":", datetime.now())
            
#             manual_id = message.value.get("manualId")
#             if int(manual_id) == 19:
#                 print(f"Processing message with manualId: {manual_id}")
#                 try:
#                     executor.submit(handle_input_data,
#                         file=message.value.get("frameUri"),
#                         sourceId=message.value.get("sourceId"),
#                         sessionId=message.value.get("sessionId"),
#                         manualId=manual_id,
#                         frame_no=current_frame_no,
#                         timeStamp=message.value.get("timeStamp")
#                     )
#                 except Exception as e:
#                     logging.exception(f"Error submitting handle_input_data task for manualId {manual_id}:")
#                     print(f"Error submitting handle_input_data task: {e}")
#                     traceback.print_exc()

#             else:
#                 print(f"Skipping message with manualId: {manual_id}")
#             print("Message In Consumer:end", current_frame_no, ":", datetime.now())

#     except Exception as e:
#         logging.exception("Error in Kafka consumer:")
#         print(f"Error in Kafka consumer: {e}")
#         traceback.print_exc()
#     finally:
#         consumer.close()
#         print("Kafka consumer closed.")

consumer = KafkaConsumer(
    'via-frame',
    bootstrap_servers=config.kafka_url,
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    auto_offset_reset='latest',    # 'earliest' for reprocessing, 'latest' for real-time
    enable_auto_commit=False,      # Manual offset commit for performance
    group_id='vip-consumer-test',
    max_poll_records=500,          # Higher batch size for better throughput
    fetch_min_bytes=10240,         # Minimum data Kafka fetches in a poll (10KB)
    fetch_max_wait_ms=100,         # Reduce wait time for quicker polling
    session_timeout_ms=30000,      # Prevents frequent consumer rebalancing
    heartbeat_interval_ms=5000,    # Keep-alive mechanism
    queued_max_messages_kbytes=1048576  # Larger queue size (1GB)
)
 

async def read_kafka_messages():
    while True:
        print("Kafka consumer started.")
        try:
            messages = consumer.poll(timeout_ms=1000)
            for message in consumer:


                with global_state.lock:
                    current_frame_no = global_state.frame_no
                    global_state.frame_no += 1
                print("UI Time Stamp:", current_frame_no, ":", message.value.get("timeStamp"))
                print("Producer Time Stamp:", current_frame_no, ":", message.value.get("prodRecvTimeStamp"))
                print("Message In Consumer:start", current_frame_no, ":", datetime.now())
                
                manual_id = message.value.get("manualId")
                if int(manual_id) == 19:
                    print(f"Processing message with manualId: {manual_id}")
                    try:
                        executor.submit(handle_input_data,
                            file=message.value.get("frameUri"),
                            sourceId=message.value.get("sourceId"),
                            sessionId=message.value.get("sessionId"),
                            manualId=manual_id,
                            frame_no=current_frame_no,
                            timeStamp=message.value.get("timeStamp")
                        )
                    except Exception as e:
                        logging.exception(f"Error submitting handle_input_data task for manualId {manual_id}:")
                        print(f"Error submitting handle_input_data task: {e}")
                        traceback.print_exc()

                else:
                    print(f"Skipping message with manualId: {manual_id}")
                print("Message In Consumer:end", current_frame_no, ":", datetime.now())

        except Exception as e:
            logging.exception("Error in Kafka consumer:")
            print(f"Error in Kafka consumer: {e}")
            traceback.print_exc()
        finally:
            consumer.close()
            print("Kafka consumer closed.")


def handle_input_data(file, sourceId, sessionId, manualId, frame_no, timeStamp):
    try:
        print("handle_input_data:start:", frame_no, ":", datetime.now())

        try:
            frame, results, things_present, start_time = pose_obj._process_pose_detection(file, sourceId, sessionId, manualId, frame_no)

            # Submit draw_annotations and process_squat_analysis to the thread pool
            future_draw = executor.submit(pose_obj.draw_annotations, frame, results, sourceId, sessionId, manualId, start_time, frame_no, timeStamp)
            future_squat = executor.submit(pose_obj.process_squat_analysis, sessionId, frame, things_present, sourceId, manualId, results, frame_no)

            print("handle_input_data:end:", frame_no, ":", datetime.now())
            

        except Exception as e:
            logging.exception(f"Error in handle_input_data's subtasks for manualId {manualId}:")
            print(f"Error in handle_input_data's subtasks: {e}")
            traceback.print_exc()

    except Exception as e:
        logging.exception(f"Error in handle_input_data for manualId {manualId}:")
        print(f"Error in handle_input_data: {e}")
        traceback.print_exc()


def start_kafka_listener():
    print("Starting Kafka listener...")
    read_kafka_messages()

if __name__ == "__main__":
    print("Starting the application...")
    start_kafka_listener()