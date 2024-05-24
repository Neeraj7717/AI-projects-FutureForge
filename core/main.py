import argparse
import asyncio
import datetime
from fastapi import FastAPI, File, UploadFile
from model.detections import Detections
import uvicorn
from pydantic import BaseModel
from typing import Optional
from Config.settings import Settings

# Create FastAPI app instance
app = FastAPI()

# Initialize detection model
detector = Detections()

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
    a=datetime.datetime.now()
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
    
    # Perform hand detection (Replace with your actual implementation)
    await asyncio.sleep(0)  # Simulate some asynchronous task
    await detector.action_detector(file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId)
    
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
    a=datetime.datetime.now()
    file = input_data.file
    sourceId = input_data.sourceId
    sessionId = input_data.sessionId
    manualId = input_data.manualId
    
    # Perform hand detection
    asyncio.create_task(ekyc_detector_action_detector(file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId))

    # return {"output": []}

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
    a=datetime.datetime.now()
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
    a=datetime.datetime.now()
    file = input_data.file
    sourceId = input_data.sourceId
    sessionId = input_data.sessionId
    manualId = input_data.manualId
    
    # Perform hand detection
    detector.text_detector(file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId)
    
    return {"result":"success"}



# Run the FastAPI application
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run FastAPI server with custom port")
    parser.add_argument(
        "--port",
        type=int,
        default=8108,
        help="Port number to run the server on (default: 8078)",
    )
    args = parser.parse_args()
    uvicorn.run(app, host="0.0.0.0", port=int(config.port_number))
