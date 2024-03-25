from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    kafka_url : str
    path_of_model : str
    frames_path : str
    video_details_kafka_topic : str
    video_instruction_kafka_topic : str
    mongo_connection_string_manual : str
    database_name : str
    collection_name : str
    root_path : str
    shared_path : str
    
    class Config:
        env_file = "./.env"