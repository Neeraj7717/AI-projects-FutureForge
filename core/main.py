from fastapi import FastAPI, File, UploadFile
from model.detections import Detections
import uvicorn
from pydantic import BaseModel
from typing import Optional

# Create FastAPI app instance
app = FastAPI()

# Initialize detection model
detector = Detections()

class Input(BaseModel):
    """
    Input data model for hand detection endpoint.
    """
    file: Optional[str] = None
    sourceId: Optional[str] = None
    sessionId: Optional[str] = None
    manualId: Optional[str] = None

@app.post("/detect")
async def detect_hand(input_data: Input):
    """
    Endpoint for performing hand detection.

    Args:
        input_data (Input): Input data containing file path, sourceId, sessionId, and manualId.

    Returns:
        dict: Dictionary containing the output of hand detection.
    """
    # Extract input data
    file = input_data.file
    sourceId = input_data.sourceId
    sessionId = input_data.sessionId
    manualId = input_data.manualId
    
    # Perform hand detection
    output = detector.action_detector(file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId)

    return {"output": output}

# Run the FastAPI application
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8108)
