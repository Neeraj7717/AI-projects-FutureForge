from kafka import KafkaConsumer
import json
import logging

# Configure logging
logging.basicConfig(filename='kafka_consumer.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Kafka configuration
kafka_broker = '192.168.0.162:9092'  # Your Kafka broker address
video_details_kafka_topic = "vip-user-video-detailing-web"
video_instruction_kafka_topic = "vip-elina-instruction-details"
topics = [video_details_kafka_topic, video_instruction_kafka_topic,"vip-bounding-box-details"]

def consume_kafka_messages():
    """
    Consumes messages from the specified Kafka topics and logs them to a file.
    """
    try:
        consumer = KafkaConsumer(
            *topics,  # Pass topics as separate arguments
            bootstrap_servers=[kafka_broker],
            auto_offset_reset='earliest',  # Start consuming from the beginning if no offset is stored
            enable_auto_commit=True,
            group_id='my-consumer-group',  # Important:  Use a group ID for fault tolerance and offset management
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))  # Assuming messages are JSON-encoded UTF-8
        )

        logging.info(f"Consumer started. Listening to topics: {topics}")

        for message in consumer:
            try:
                topic = message.topic
                partition = message.partition
                offset = message.offset
                value = message.value

                log_message = f"Topic: {topic}, Partition: {partition}, Offset: {offset}, Message: {value}"
                logging.info(log_message)
                print(log_message) # Optional: Print to console as well

            except Exception as e:
                logging.error(f"Error processing message: {e}", exc_info=True)  # Log the full traceback

    except Exception as e:
        logging.error(f"Error initializing Kafka consumer: {e}", exc_info=True)  # Log Kafka connection errors

if __name__ == "__main__":
    consume_kafka_messages()
