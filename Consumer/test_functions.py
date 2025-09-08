import logging
import gc
import psutil
import concurrent.futures
import traceback
from model.detections import Detections
from model.gender_model import ProcessFrame
from model.pose_model import Pose

# Function Logger Setup
function_logger = logging.getLogger('function_logger')
function_logger.setLevel(logging.INFO)
function_logger.propagate = False  # Prevent propagation to root logger

# Create console handler with formatting
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - Function - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)

# Add handler to function logger
function_logger.addHandler(console_handler)

# Remove the basic config since we're using custom loggers
# logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Pose Detection Model
pose_obj = Pose()
detector = Detections()
gender = ProcessFrame()

executor = concurrent.futures.ThreadPoolExecutor(max_workers=5000)
 
def pose_detection(file, sourceId, sessionId, manualId, frame_no, timeStamp):
    """
    Handles the frame processing asynchronously.
    """
    try:
        function_logger.info(f"Processing frame {frame_no}...")
 
        # Pose detection (preferably on GPU)
        frame, results, things_present, start_time = pose_obj._process_pose_detection(
            file, sourceId, sessionId, manualId, frame_no
        )
        print(things_present)
        executor.submit(pose_obj.process_squat_analysis, sessionId, frame, things_present, sourceId, manualId, results, frame_no)
 
        function_logger.info(f"Frame {frame_no} processing completed.")
        memory_usage = psutil.virtual_memory().percent
        if memory_usage > 60:
            function_logger.info(f"Memory usage is high: {memory_usage}%. Calling gc.collect()...")
            gc.collect() 
 
    except Exception as e:
        function_logger.error(f"Error processing frame {frame_no}: {e}")
        function_logger.error(f"Current memory usage: {psutil.virtual_memory().percent}%")
        gc.collect()
        traceback.print_exc()
        
def action_detection(file, sourceId, sessionId, manualId, frame_no, timeStamp):
    """
    Handles the frame processing asynchronously.
    """
    try:
        function_logger.info(f"Processing frame {frame_no}...action_detection")
        
        executor.submit(detector.action_detector, file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId)
 
        function_logger.info(f"Frame {frame_no} processing completed.")
        memory_usage = psutil.virtual_memory().percent
        if memory_usage > 60:
            function_logger.info(f"Memory usage is high: {memory_usage}%. Calling gc.collect()...")
            gc.collect() 
 
    except Exception as e:
        function_logger.error(f"Error processing frame {frame_no}: {e}")
        function_logger.error(f"Current memory usage: {psutil.virtual_memory().percent}%")
        gc.collect()
        traceback.print_exc()
        
def gender_detection(file, sourceId, sessionId, manualId, frame_no, timeStamp):
    """
    Handles the frame processing asynchronously.
    """
    try:
        function_logger.info(f"Processing frame {frame_no}...gender_detection")
        
        executor.submit(gender.gender_detector, file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId)

        function_logger.info(f"Frame {frame_no} processing completed.")
        memory_usage = psutil.virtual_memory().percent
        if memory_usage > 60:
            function_logger.info(f"Memory usage is high: {memory_usage}%. Calling gc.collect()...")
            gc.collect() 
 
    except Exception as e:
        function_logger.error(f"Error processing frame {frame_no}: {e}")
        function_logger.error(f"Current memory usage: {psutil.virtual_memory().percent}%")
        gc.collect()
        traceback.print_exc()

def ekyc_detect(file, sourceId, sessionId, manualId, frame_no, timeStamp):
    """
    Handles the frame processing asynchronously.
    """
    try:
        function_logger.info(f"Processing frame {frame_no}...ekyc_detect")
        
        executor.submit(detector.ekyc_action_detector, file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId)

        function_logger.info(f"Frame {frame_no} processing completed.")
        memory_usage = psutil.virtual_memory().percent
        if memory_usage > 60:
            function_logger.info(f"Memory usage is high: {memory_usage}%. Calling gc.collect()...")
            gc.collect() 
 
    except Exception as e:
        function_logger.error(f"Error processing frame {frame_no}: {e}")
        function_logger.error(f"Current memory usage: {psutil.virtual_memory().percent}%")
        gc.collect()
        traceback.print_exc()

def text_detect(file, sourceId, sessionId, manualId, frame_no, timeStamp):
    """
    Handles the frame processing asynchronously.
    """
    try:
        function_logger.info(f"Processing frame {frame_no}...ekyc_detect")
        
        executor.submit(detector.text_action_detector, file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId)
        function_logger.info(f"Frame {frame_no} processing completed.")
        memory_usage = psutil.virtual_memory().percent
        if memory_usage > 60:
            function_logger.info(f"Memory usage is high: {memory_usage}%. Calling gc.collect()...")
            gc.collect() 
 
    except Exception as e:
        function_logger.error(f"Error processing frame {frame_no}: {e}")
        function_logger.error(f"Current memory usage: {psutil.virtual_memory().percent}%")
        gc.collect()
        traceback.print_exc()

def chair_detect(file, sourceId, sessionId, manualId, frame_no, timeStamp):
    """
    Handles the frame processing asynchronously.
    """
    try:
        function_logger.info(f"Processing frame {frame_no}...ekyc_detect")
        
        executor.submit(detector.chair_action_detector, file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId)
        function_logger.info(f"Frame {frame_no} processing completed.")
        memory_usage = psutil.virtual_memory().percent
        if memory_usage > 60:
            function_logger.info(f"Memory usage is high: {memory_usage}%. Calling gc.collect()...")
            gc.collect() 
 
    except Exception as e:
        function_logger.error(f"Error processing frame {frame_no}: {e}")
        function_logger.error(f"Current memory usage: {psutil.virtual_memory().percent}%")
        gc.collect()
        traceback.print_exc()

def similar_image(file, sourceId, sessionId, manualId, frame_no, timeStamp):
    """
    Handles the frame processing asynchronously.
    """
    try:
        function_logger.info(f"Processing frame {frame_no}...ekyc_detect")
        
        executor.submit(detector.get_similar_image_detector, file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId)
        function_logger.info(f"Frame {frame_no} processing completed.")
        memory_usage = psutil.virtual_memory().percent
        if memory_usage > 60:
            function_logger.info(f"Memory usage is high: {memory_usage}%. Calling gc.collect()...")
            gc.collect() 
 
    except Exception as e:
        function_logger.error(f"Error processing frame {frame_no}: {e}")
        function_logger.error(f"Current memory usage: {psutil.virtual_memory().percent}%")
        gc.collect()
        traceback.print_exc()

def system_monitor(file, sourceId, sessionId, manualId, frame_no, timeStamp):
    """
    Handles the frame processing asynchronously.
    """
    try:
        function_logger.info(f"Processing frame {frame_no}...ekyc_detect")
        
        executor.submit(detector.system_monitor_detection, file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId)
        function_logger.info(f"Frame {frame_no} processing completed.")
        memory_usage = psutil.virtual_memory().percent
        if memory_usage > 60:
            function_logger.info(f"Memory usage is high: {memory_usage}%. Calling gc.collect()...")
            gc.collect() 
 
    except Exception as e:
        function_logger.error(f"Error processing frame {frame_no}: {e}")
        function_logger.error(f"Current memory usage: {psutil.virtual_memory().percent}%")
        gc.collect()
        traceback.print_exc()


