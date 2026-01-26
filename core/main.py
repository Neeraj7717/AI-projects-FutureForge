import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['GLOG_minloglevel'] = '3'
import argparse
import asyncio
import datetime
import concurrent.futures
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import traceback
from pydantic import BaseModel
from typing import Optional
from Config.settings import Settings
import threading
from contextlib import asynccontextmanager
from Consumer.consumer_ui import start_kafka_listener
from model.model_manager import model_manager

# Global variable to track consumer thread
consumer_thread = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI.
    Loads models and starts Kafka consumer on startup.
    """
    global consumer_thread

    # Load configuration
    config = Settings()

    # Load models based on config
    if config.load_all_models_at_start:
        print("Loading all models at startup (load_all_models_at_start=True)...")
        model_manager.load_all_models()
    else:
        print("Models will load on-demand (load_all_models_at_start=False)")

    # Start Kafka consumer in background thread
    print("Starting Kafka consumer in background...")
    consumer_thread = threading.Thread(target=start_kafka_listener, daemon=True)
    consumer_thread.start()
    print("✓ Kafka consumer started successfully")

    yield

    # Shutdown: Clean up resources
    print("Shutting down services...")
    model_manager.close()
    print("✓ Services shut down successfully")

# Create the app with the lifespan context manager
app = FastAPI(lifespan=lifespan)

# Add CORS middleware to allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Thread pool for API endpoints
executor = concurrent.futures.ThreadPoolExecutor(max_workers=1000)

# Use shared models from model_manager (shared with Consumer)
def get_detector():
    """Get shared Detector model"""
    return model_manager.get_detector_model()

def get_pose():
    """Get shared Pose model"""
    return model_manager.get_pose_model()

def get_gender():
    """Get shared Gender model"""
    return model_manager.get_gender_model()


class GlobalState:
    def __init__(self):
        self.frame_no = 1
        self.lock = threading.Lock()

global_state = GlobalState()

# Load configurations from settings
config = Settings()

class Input(BaseModel):
    """
    Input data model for hand detection endpoint.
    """
    file: Optional[str] = None
    sourceId: Optional[str] = None
    sessionId: Optional[str] = None
    manualId: Optional[str] = None
    timeStamp: Optional[str] = None

@app.post("/detect-pose")
async def detect_pose_endpoint(input_data: Input):
    try:
        pose_obj = get_pose()
        if pose_obj is None:
            return {"error": "Pose model not ready, please try again"}

        with global_state.lock:
            current_frame_no = global_state.frame_no
            global_state.frame_no += 1
        print("detect_pose_endpoint:start",current_frame_no,":", datetime.datetime.now())
        print(input_data.timeStamp)
        # Run pose detection in a separate thread without blocking
        future_pose_processing = asyncio.create_task(
            asyncio.to_thread(pose_obj._process_pose_detection, input_data.file, input_data.sourceId, input_data.sessionId, input_data.manualId, current_frame_no)
        )

        async def process_followup_tasks():
            try:
                frame, results, things_present, start_time = await future_pose_processing  # Await the task completion
                # Process squat analysis (draw_annotations method doesn't exist, so we skip it)
                await asyncio.to_thread(pose_obj.process_squat_analysis, input_data.sessionId, frame, things_present, input_data.sourceId, input_data.manualId, results, current_frame_no)

            except Exception as e:
                print(f"Error processing pose detection result: {e}")
                traceback.print_exc()

        # Start the follow-up processing asynchronously without blocking response
        asyncio.create_task(process_followup_tasks())
        print("detect_pose_endpoint:end",current_frame_no,":", datetime.datetime.now())
        return {"message": "Pose detection tasks submitted."}  # API responds immediately

    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}

@app.post("/detect")
async def detect(input_data: Input):
    """
    Endpoint for performing detections.

    Args:
        input_data (Input): Input data containing file path, sourceId, sessionId, and manualId.

    Returns:
        dict: Dictionary containing the output of detection.
    """
    # Extract input data
    file = input_data.file
    sourceId = input_data.sourceId
    sessionId = input_data.sessionId
    manualId = input_data.manualId
    
    # Perform hand detection
    asyncio.create_task(detector_action_detector(file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId))

    # return {"output": []}

async def detector_action_detector(file, sourceId, sessionId, manualId):
    """
    Asynchronous function to perform hand detection.

    Args:
        file (str): File path.
        sourceId (str): Source ID.
        sessionId (str): Session ID.
        manualId (str): Manual ID.
    """
    detector = get_detector()
    if detector is None:
        print("Detector model not ready, skipping request")
        return

    # Perform hand detection (Replace with your actual implementation)
    await asyncio.sleep(0)  # Simulate some asynchronous task
    await detector.action_detector(file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId)


@app.post("/detect-gender")
async def detect(input_data: Input):
    """
    Endpoint for performing gender detections.

    Args:
        input_data (Input): Input data containing file path, sourceId, sessionId, and manualId.

    """
    # Extract input data
    file = input_data.file
    sourceId = input_data.sourceId
    sessionId = input_data.sessionId
    manualId = input_data.manualId
    
    # Perform hand detection
    asyncio.create_task(gender_detector(file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId))

    # return {"output": []}

async def gender_detector(file, sourceId, sessionId, manualId):
    """
    Asynchronous function to perform gender detection.

    Args:
        file (str): File path.
        sourceId (str): Source ID.
        sessionId (str): Session ID.
        manualId (str): Manual ID.
    """
    gender = get_gender()
    if gender is None:
        print("Gender model not ready, skipping request")
        return

    # Perform hand detection (Replace with your actual implementation)
    await asyncio.sleep(0)  # Simulate some asynchronous task
    await gender.gender_detector(file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId)
    
@app.post("/ekyc_detect")
async def ekyc_detect(input_data: Input):
    """
    Endpoint for performing detections.

    Args:
        input_data (Input): Input data containing file path, sourceId, sessionId, and manualId.

    Returns:
        dict: Dictionary containing the output of detection.
    """
    # Extract input data
    file = input_data.file
    sourceId = input_data.sourceId
    sessionId = input_data.sessionId
    manualId = input_data.manualId
    
    # Perform hand detection
    asyncio.create_task(ekyc_detector_action_detector(file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId))
    b=datetime.datetime.now()
    print('Processing time is', b-a)
    return {"output": []}

async def ekyc_detector_action_detector(file, sourceId, sessionId, manualId):
    """
    Asynchronous function to perform hand detection.
    
    Args:
        file (str): File path.
        sourceId (str): Source ID.
        sessionId (str): Session ID.
        manualId (str): Manual ID.
    """
    
    # Perform hand detection (Replace with your actual implementation)
    await asyncio.sleep(0)  # Simulate some asynchronous task
    detector = get_detector()
    if detector is None:
        print("Detector model not ready, skipping request")
        return

    await detector.ekyc_action_detector(file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId)

@app.post("/text_detect")
async def text_detect(input_data: Input):
    """
    Endpoint for performing detections.

    Args:
        input_data (Input): Input data containing file path, sourceId, sessionId, and manualId.

    Returns:
        dict: Dictionary containing the output of detection.
    """
    # Extract input data
    file = input_data.file
    sourceId = input_data.sourceId
    sessionId = input_data.sessionId
    manualId = input_data.manualId
    
    # Perform hand detection
    asyncio.create_task(text_detector_action_detector(file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId))

    # return {"output": []}

async def text_detector_action_detector(file, sourceId, sessionId, manualId):
    """
    Asynchronous function to perform hand detection.
    
    Args:
        file (str): File path.
        sourceId (str): Source ID.
        sessionId (str): Session ID.
        manualId (str): Manual ID.
    """
    
    # Perform hand detection (Replace with your actual implementation)
    await asyncio.sleep(0)  # Simulate some asynchronous task
    detector = get_detector()
    if detector is None:
        print("Detector model not ready, skipping request")
        return

    await detector.text_action_detector(file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId)

@app.post("/text_input")
async def text_input(input_data: Input):
    """
    Endpoint for performing detections.

    Args:
        input_data (Input): Input data containing file path, sourceId, sessionId, and manualId.

    Returns:
        dict: Dictionary containing the output of detection.
    """
    # Extract input data
    file = input_data.file
    sourceId = input_data.sourceId
    sessionId = input_data.sessionId
    manualId = input_data.manualId
    
    detector = get_detector()
    if detector is None:
        return {"error": "Detector model not ready"}

    # Perform hand detection
    detector.text_detector(file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId)
    
    return {"result":"success"}


@app.post("/chat_input")
async def chat_input(input_data: Input):
    """
    Endpoint for performing detections.

    Args:
        input_data (Input): Input data containing file path, sourceId, sessionId, and manualId.

    Returns:
        dict: Dictionary containing the output of detection.
    """
    # Extract input data
    file = input_data.file
    sourceId = input_data.sourceId
    sessionId = input_data.sessionId
    manualId = input_data.manualId

    detector = get_detector()
    if detector is None:
        return {"error": "Detector model not ready"}

    # Perform hand detection
    detector.chat_detector(file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId)

    return {"result":"success"}

@app.post("/image_input")
async def image_upload(input_data: Input):
    """
    Endpoint for performing detections.

    Args:
        input_data (Input): Input data containing file path, sourceId, sessionId, and manualId.

    Returns:
        dict: Dictionary containing the output of detection.
    """
    # Extract input data
    print(input_data)
    file = input_data.file
    sourceId = input_data.sourceId
    sessionId = input_data.sessionId
    manualId = input_data.manualId

    detector = get_detector()
    if detector is None:
        return {"error": "Detector model not ready"}

    # Perform hand detection
    detector.image_input(file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId)


@app.post("/chair_detect")
async def chair_detect(input_data: Input):
    """
    Endpoint for performing detections.

    Args:
        input_data (Input): Input data containing file path, sourceId, sessionId, and manualId.

    Returns:
        dict: Dictionary containing the output of detection.
    """
    # Extract input data
    file = input_data.file
    sourceId = input_data.sourceId
    sessionId = input_data.sessionId
    manualId = input_data.manualId
    
    # Perform hand detection
    asyncio.create_task(chair_detector_action_detector(file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId))

    # return {"output": []}

async def chair_detector_action_detector(file, sourceId, sessionId, manualId):
    """
    Asynchronous function to perform hand detection.
    
    Args:
        file (str): File path.
        sourceId (str): Source ID.
        sessionId (str): Session ID.
        manualId (str): Manual ID.
    """
    
    # Perform hand detection (Replace with your actual implementation)
    await asyncio.sleep(0)  # Simulate some asynchronous task
    detector = get_detector()
    if detector is None:
        print("Detector model not ready, skipping request")
        return

    await detector.chair_action_detector(file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId)


@app.post("/similar_image")
async def similar_image(input_data: Input):
    """
    Endpoint for performing detections.

    Args:
        input_data (Input): Input data containing file path, sourceId, sessionId, and manualId.

    Returns:
        dict: Dictionary containing the output of detection.
    """
    # Extract input data
    file = input_data.file
    sourceId = input_data.sourceId
    sessionId = input_data.sessionId
    manualId = input_data.manualId
    
    # Perform hand detection
    asyncio.create_task(similar_image_detector(file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId))

    # return {"output": []}

async def similar_image_detector(file, sourceId, sessionId, manualId):
    """
    Asynchronous function to perform hand detection.
    
    Args:
        file (str): File path.
        sourceId (str): Source ID.
        sessionId (str): Session ID.
        manualId (str): Manual ID.
    """
    
    # Perform hand detection (Replace with your actual implementation)
    await asyncio.sleep(0)  # Simulate some asynchronous task
    detector = get_detector()
    if detector is None:
        print("Detector model not ready, skipping request")
        return

    await detector.get_similar_image_detector(file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId)


@app.post("/system_monitor")
async def system_monitor(input_data: Input):
    """
    Endpoint for performing detections.

    Args:
        input_data (Input): Input data containing file path, sourceId, sessionId, and manualId.

    Returns:
        dict: Dictionary containing the output of detection.
    """
    # Extract input data
    file = input_data.file
    sourceId = input_data.sourceId
    sessionId = input_data.sessionId
    manualId = input_data.manualId
    
    # Perform hand detection
    asyncio.create_task(system_monitor_detector(file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId))

    # return {"output": []}

async def system_monitor_detector(file, sourceId, sessionId, manualId):
    """
    Asynchronous function to perform hand detection.
    
    Args:
        file (str): File path.
        sourceId (str): Source ID.
        sessionId (str): Session ID.
        manualId (str): Manual ID.
    """
    
    # Perform hand detection (Replace with your actual implementation)
    await asyncio.sleep(0)  # Simulate some asynchronous task
    detector = get_detector()
    if detector is None:
        print("Detector model not ready, skipping request")
        return

    await detector.system_monitor_detection(file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId)


# Run the FastAPI application
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run FastAPI server with custom port")
    parser.add_argument(
        "--port",
        type=int,
        default=int(config.port_number),
        help="Port number to run the server on (default: 8078)",
    )
    args = parser.parse_args()
    uvicorn.run(app, host="0.0.0.0", port=args.port)
