import argparse
import asyncio
import datetime
import concurrent.futures
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware  # Import CORSMiddleware
from model.detections_test_pose import Detections
from model.pose_test_redis2 import Pose
from model.gender_model import ProcessFrame
import uvicorn
import traceback
from datetime import datetime
from pydantic import BaseModel
from typing import Optional
from Config.settings import Settings
import threading
# Create FastAPI app instance
app = FastAPI()

# Add CORS middleware to allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Initialize detection model
detector = Detections()
executor = concurrent.futures.ThreadPoolExecutor(max_workers=20)
pose_obj = Pose()
gender = ProcessFrame()


global_frame_no = 1
frame_no_lock = threading.Lock()
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


@app.post("/detect-pose")
async def detect_pose_endpoint(input_data: Input):
    try:
        file = input_data.file
        sourceId = input_data.sourceId
        sessionId = input_data.sessionId
        manualId = input_data.manualId
 
        global global_frame_no
        with frame_no_lock:
            current_frame_no = global_frame_no  # Get current value
            global_frame_no += 1
        print("detect_pose_endpoint:start",current_frame_no,":", datetime.now())
        
        # Run pose detection in a separate thread without blocking
        future_pose_processing = asyncio.create_task(
            asyncio.to_thread(pose_obj._process_pose_detection, file, sourceId, sessionId, manualId, current_frame_no)
        )
 
        async def process_followup_tasks():
            try:
                frame, results, things_present, start_time = await future_pose_processing  # Await the task completion
                # Run the next two tasks in parallel using asyncio.gather
                await asyncio.gather(
                    asyncio.to_thread(pose_obj.draw_annotations, frame, results, sourceId, sessionId, manualId, start_time, current_frame_no),
                    asyncio.to_thread(pose_obj.process_squat_analysis, sessionId, frame, things_present, sourceId, manualId, results, current_frame_no)
                )
 
            except Exception as e:
                print(f"Error processing pose detection result: {e}")
                traceback.print_exc()
 
        # Start the follow-up processing asynchronously without blocking response
        asyncio.create_task(process_followup_tasks())
        print("detect_pose_endpoint:end",current_frame_no,":", datetime.now())
        return {"message": "Pose detection tasks submitted."}  # API responds immediately

    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}

# @app.post("/detect-pose")
# async def detect(input_data: Input):
#     """
#     Endpoint for performing pose detections.

#     Args:
#         input_data (Input): Input data containing file path, sourceId, sessionId, and manualId.

#     """
#     # Extract input data
#     a=datetime.datetime.now()
#     file = input_data.file
#     sourceId = input_data.sourceId
#     sessionId = input_data.sessionId
#     manualId = input_data.manualId
    
#     # Perform hand detection
#     asyncio.create_task(pose_detector(file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId))

#     # return {"output": []}

# async def pose_detector(file, sourceId, sessionId, manualId):
#     """
#     Asynchronous function to perform pose detection.
    
#     Args:
#         file (str): File path.
#         sourceId (str): Source ID.
#         sessionId (str): Session ID.
#         manualId (str): Manual ID.
#     """
    
#     # Perform hand detection (Replace with your actual implementation)
#     await asyncio.sleep(0)  # Simulate some asynchronous task
#     await pose.pose_detector(file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId)


# @app.post("/detect-pose")

# async def detect_pose_endpoint(request: Input):

#     try:

#         data = await request.json()  # Assuming data is sent as JSON

#         file = data.get("file")

#         sourceId = data.get("sourceId")

#         sessionId = data.get("sessionId")

#         manualId = data.get("manualId")
 
#         # Submit pose detection asynchronously

#         future_pose_processing = pose_obj.executor.submit(

#             pose_obj.pose_detector, file, sourceId, sessionId, manualId

#         )
 
#         def process_followup_tasks(future):

#             try:

#                 frame, results, things_present, start_time = future.result()  # Extract results after completion

#                 # Now submit the two functions asynchronously

#                 future_draw = pose_obj.executor.submit(

#                     pose_obj.draw_annotations, frame, results, sourceId, sessionId, manualId, start_time

#                 )

#                 future_draw.add_done_callback(pose_obj._handle_future_result)
 
#                 future_process_squat = pose_obj.executor.submit(

#                     pose_obj.process_squat_analysis, sessionId, frame, things_present, sourceId, manualId, results

#                 )

#                 future_process_squat.add_done_callback(pose_obj._handle_future_result)
 
#             except Exception as e:

#                 print(f"Error processing pose detection result: {e}")
 
#         # Add callback to execute follow-up tasks after pose detection completes

#         future_pose_processing.add_done_callback(process_followup_tasks)
 
#         return {"message": "Pose detection tasks submitted."}  # Immediate response
 
#     except Exception as e:

#         traceback.print_exc()

#         return {"error": str(e)}

 

# @app.post("/detect-pose")
# async def detect_pose_endpoint(request: Input):
#     try:
#         data = await request.json()  # Assuming data is sent as JSON
#         file = data.get("file")
#         sourceId = data.get("sourceId")
#         sessionId = data.get("sessionId")
#         manualId = data.get("manualId")

#         # Submit ALL tasks to the thread pool DIRECTLY from the API endpoint
#         future_pose_processing = pose_obj.executor.submit( # This ensures main def pose_detector does not wait for other functions
#             pose_obj.pose_detector, file, sourceId, sessionId, manualId
#         )

#         frame, results, things_present, start_time = future_pose_processing.result() #This will make sure _process_pose_detection runs to the end

#         future_draw =  pose_obj.executor.submit( # draw_annotations runs parallaly with _process_pose_detection function since it is called from api
#                 pose_obj.draw_annotations,
#                 frame,
#                 results,
#                 sourceId,
#                 sessionId,
#                 manualId,
#                 start_time
#             )
#         future_draw.add_done_callback(pose_obj._handle_future_result) #Added this too

#         future_process_squat = pose_obj.executor.submit( #process_squat_analysis runs parallaly with _process_pose_detection function since it is called from api
#             pose_obj.process_squat_analysis,
#             sessionId,
#             frame,
#             things_present,
#             sourceId,
#             manualId,
#             results
#         )

#         future_process_squat.add_done_callback(pose_obj._handle_future_result)

#         return {"message": "Pose detection tasks submitted."}  # Immediate response

#     except Exception as e:
#         traceback.print_exc()
#         return {"error": str(e)}

@app.post("/detect-gender")
async def detect(input_data: Input):
    """
    Endpoint for performing gender detections.

    Args:
        input_data (Input): Input data containing file path, sourceId, sessionId, and manualId.

    """
    # Extract input data
    a=datetime.datetime.now()
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
    a=datetime.datetime.now()
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
    a=datetime.datetime.now()
    file = input_data.file
    sourceId = input_data.sourceId
    sessionId = input_data.sessionId
    manualId = input_data.manualId
    
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
    a=datetime.datetime.now()
    file = input_data.file
    sourceId = input_data.sourceId
    sessionId = input_data.sessionId
    manualId = input_data.manualId
    
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
    a=datetime.datetime.now()
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
    a=datetime.datetime.now()
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
    a=datetime.datetime.now()
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
