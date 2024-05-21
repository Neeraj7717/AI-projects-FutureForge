from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    kafka_url : str
    path_of_model : str
    frames_path : str
    path_of_ekyc_model : str
    video_details_kafka_topic : str
    video_instruction_kafka_topic : str
    mongo_connection_string_manual : str
    database_name : str
    collection_name : str
    root_path : str
    shared_path : str
    mongo_connection_string_stateless : str
    stateless_db : str
    stateless_collection_detections : str
    stateless_collection_state : str
    continuity : int
    log_level : str
    llava_endpoint: str
    t2v_endpoint : str
    insights_collection: str
    port_number: str
    text_compare_url: str
    class Config:
        env_file = "./.env"