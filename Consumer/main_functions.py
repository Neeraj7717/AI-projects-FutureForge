# Suppress TensorFlow/MediaPipe internal logs BEFORE any imports
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Suppress TensorFlow logs
os.environ['GLOG_minloglevel'] = '3'  # Suppress MediaPipe/Google logs

import logging
import concurrent.futures
import traceback
from utils.eizen_utils.logger_utils.logger_operations import LoggerOperations
from model.model_manager import model_manager

function_logger = LoggerOperations(logger_name='function_logger', log_level=logging.INFO, use_log_file=False)
executor = concurrent.futures.ThreadPoolExecutor(max_workers=5000)

# Use global model manager (shared with API) - avoids duplicate model loading
def get_pose_model():
    """Get shared Pose model from global model manager"""
    return model_manager.get_pose_model()

def get_detector_model():
    """Get shared Detector model from global model manager"""
    return model_manager.get_detector_model()

def get_gender_model():
    """Get shared Gender model from global model manager"""
    return model_manager.get_gender_model()

 
def pose_detection(file, sourceId, sessionId, manualId, frame_no, timeStamp):
    """
    Handles the frame processing asynchronously.
    """
    try:
        pose_obj = get_pose_model()

        # Skip frame if model is not ready (loading or failed)
        if pose_obj is None:
            function_logger.debug(f"Skipping pose frame {frame_no} - model not ready")
            return

        function_logger.debug(f"Processing pose frame {frame_no}...")

        # Pose detection (preferably on GPU)
        frame, results, things_present, start_time = pose_obj._process_pose_detection(
            file, sourceId, sessionId, manualId, frame_no
        )
        executor.submit(pose_obj.process_squat_analysis, sessionId, frame, things_present, sourceId, manualId, results, frame_no)

        function_logger.debug(f"Frame {frame_no} processing completed.")

    except Exception as e:
        function_logger.error(f"Error processing frame {frame_no}: {e}")
        traceback.print_exc()
        
def action_detection(file, sourceId, sessionId, manualId, frame_no, timeStamp):
    """
    Handles the frame processing asynchronously.
    """
    try:
        detector = get_detector_model()
        if detector is None:
            function_logger.debug(f"Skipping action frame {frame_no} - model not ready")
            return

        function_logger.debug(f"Processing action frame {frame_no}...")
        executor.submit(detector.action_detector, file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId)
        function_logger.debug(f"Frame {frame_no} processing completed.")

    except Exception as e:
        function_logger.error(f"Error processing frame {frame_no}: {e}")
        traceback.print_exc()

def gender_detection(file, sourceId, sessionId, manualId, frame_no, timeStamp):
    """
    Handles the frame processing asynchronously.
    """
    try:
        gender = get_gender_model()
        if gender is None:
            function_logger.debug(f"Skipping gender frame {frame_no} - model not ready")
            return

        function_logger.debug(f"Processing gender frame {frame_no}...")
        executor.submit(gender.gender_detector, file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId, frame_no=frame_no)
        function_logger.debug(f"Frame {frame_no} processing completed.")

    except Exception as e:
        function_logger.error(f"Error processing frame {frame_no}: {e}")
        traceback.print_exc()

def ekyc_detect(file, sourceId, sessionId, manualId, frame_no, timeStamp):
    """
    Handles the frame processing asynchronously.
    """
    try:
        detector = get_detector_model()
        if detector is None:
            function_logger.debug(f"Skipping ekyc frame {frame_no} - model not ready")
            return

        function_logger.debug(f"Processing ekyc frame {frame_no}...")
        executor.submit(detector.ekyc_action_detector, file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId)
        function_logger.debug(f"Frame {frame_no} processing completed.")

    except Exception as e:
        function_logger.error(f"Error processing frame {frame_no}: {e}")
        traceback.print_exc()

def text_detect(file, sourceId, sessionId, manualId, frame_no, timeStamp):
    """
    Handles the frame processing asynchronously.
    """
    try:
        detector = get_detector_model()
        if detector is None:
            function_logger.debug(f"Skipping text frame {frame_no} - model not ready")
            return

        function_logger.debug(f"Processing text frame {frame_no}...")
        executor.submit(detector.text_action_detector, file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId)
        function_logger.debug(f"Frame {frame_no} processing completed.")

    except Exception as e:
        function_logger.error(f"Error processing frame {frame_no}: {e}")
        traceback.print_exc()

def chair_detect(file, sourceId, sessionId, manualId, frame_no, timeStamp):
    """
    Handles the frame processing asynchronously.
    """
    try:
        detector = get_detector_model()
        if detector is None:
            function_logger.debug(f"Skipping chair frame {frame_no} - model not ready")
            return

        function_logger.debug(f"Processing chair frame {frame_no}...")
        executor.submit(detector.chair_action_detector, file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId)
        function_logger.debug(f"Frame {frame_no} processing completed.")

    except Exception as e:
        function_logger.error(f"Error processing frame {frame_no}: {e}")
        traceback.print_exc()

def similar_image(file, sourceId, sessionId, manualId, frame_no, timeStamp):
    """
    Handles the frame processing asynchronously.
    """
    try:
        detector = get_detector_model()
        if detector is None:
            function_logger.debug(f"Skipping similar_image frame {frame_no} - model not ready")
            return

        function_logger.debug(f"Processing similar_image frame {frame_no}...")
        executor.submit(detector.get_similar_image_detector, file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId)
        function_logger.debug(f"Frame {frame_no} processing completed.")

    except Exception as e:
        function_logger.error(f"Error processing frame {frame_no}: {e}")
        traceback.print_exc()

def system_monitor(file, sourceId, sessionId, manualId, frame_no, timeStamp):
    """
    Handles the frame processing asynchronously.
    """
    try:
        detector = get_detector_model()
        if detector is None:
            function_logger.debug(f"Skipping system_monitor frame {frame_no} - model not ready")
            return

        function_logger.debug(f"Processing system_monitor frame {frame_no}...")
        executor.submit(detector.system_monitor_detection, file=file, sourceId=sourceId, sessionId=sessionId, manualId=manualId)
        function_logger.debug(f"Frame {frame_no} processing completed.")

    except Exception as e:
        function_logger.error(f"Error processing frame {frame_no}: {e}")
        traceback.print_exc()


