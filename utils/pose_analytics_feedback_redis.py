import cv2
import numpy as np
import mediapipe as mp
import asyncio
import logging
import os
import redis
from s3utils.generaloperations import upload_to_s3_bucket

# Configuration (load from .env file or command-line args)
REDIS_HOST = '192.168.0.162'
REDIS_PORT = 6379
REDIS_DB = 0
S3_BUCKET = 'eizen-dev'

GOOD_SQUAT_ANGLE = 80
SQUAT_START_ANGLE = 120



# Logging setup (as you have it)
pose_logger = logging.getLogger('pose_analytics')
pose_logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(log_format)
pose_logger.addHandler(console_handler)

ENABLE_FILE_LOGGING = False
if ENABLE_FILE_LOGGING:
    file_handler = logging.FileHandler('pose_analytics.log')
    file_handler.setFormatter(log_format)
    pose_logger.addHandler(file_handler)
pose_logger.propagate = False

# Redis connection
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)

# MediaPipe Pose
mp_pose = mp.solutions.pose


import os

if not os.path.exists('/tmp'):
    try:
        os.makedirs('/tmp')
        pose_logger.info("Created /tmp directory")
    except OSError as e:
        pose_logger.error(f"Failed to create /tmp directory: {e}")

def calculate_angle(a, b, c):
    """
    Calculate angle between three points in 2D
    """
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)
    
    radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
    angle = np.abs(radians*180.0/np.pi)
    
    if angle > 180.0:
        angle = 360-angle
        
    return angle

# async def upload_bad_squat_frame(session_id, frame):
#     try:
#         frame_filename = f"bad_squat_{session_id}.jpg"
#         local_path = f"/tmp/{frame_filename}"
#         cv2.imwrite(local_path, frame)

#         cloud_path = f"feedback_frames/"
#         url = upload_to_s3_bucket(S3_BUCKET, local_path, cloud_path, frame_filename)
#         os.remove(local_path)
#         return url
#     except Exception as e:
#         pose_logger.error(f"Error uploading bad squat frame: {str(e)}")
#         return None

async def upload_bad_squat_frame(session_id, manual_id,frame):
    try:
        frame_filename = f"bad_squat_{session_id}.jpg"
        os.makedirs("/tmp", exist_ok=True)
        local_path = f"/tmp/{frame_filename}"

        success = cv2.imwrite(local_path, frame)  # Capture the return value
        if not success:
            pose_logger.error(f"cv2.imwrite failed to write image to {local_path}")
            return None
        
        cloud_path = f"feedback_frames/"
        url = upload_to_s3_bucket(S3_BUCKET, local_path, cloud_path, frame_filename)
        update_value(redis_client, session_id, manual_id, "feedbackUrl", url)
    finally:
        # Ensure the temporary file is removed
        if os.path.exists(local_path):
            os.remove(local_path)
    
    return url

def set_if_not_exists(redis_client, sessionId, manualId, key, value):
    redis_key  = f"pose:{sessionId}:{manualId}:{key}"
    if not redis_client.exists(redis_key):  # Check if key exists
        redis_client.set(redis_key, value)
        # pose_logger.info(f"Key '{redis_key}' was not present, so it was set with value: {value}")
        return value
    else:
        value = redis_client.get(redis_key)
        # pose_logger.info(f"Key '{redis_key}' already exists. Value: {value.decode('utf-8')}")
        return value.decode('utf-8')

def update_value(redis_client, sessionId, manualId, key, new_value):
    redis_key  = f"pose:{sessionId}:{manualId}:{key}"
    if redis_client.exists(redis_key):
        redis_client.set(redis_key, new_value)
        # pose_logger.info(f"Key '{redis_key}' updated with new value: {new_value}")
    else:
        pose_logger.info(f"Key '{redis_key}' does not exist. Cannot update.")

def analyze_live_squat(session_id, manual_id, frame, results, target_reps=1):
    pose_logger.info("----------------------((((((((((((((((((((((((( In squat )))))))))))))))))))))))))--------------------------------")

    # Retrieve Redis values at the beginning
    redis_is_sqt = int(set_if_not_exists(redis_client, session_id, manual_id, "isSqt", 0))
    redis_is_good_sqt = int(set_if_not_exists(redis_client, session_id, manual_id, "isGoodSqt", 0))
    redis_total_sqt  = int(set_if_not_exists(redis_client, session_id, manual_id, "totalSqt", 0))
    redis_good_sqt_count  = int(set_if_not_exists(redis_client, session_id, manual_id, "goodSqtCount", 0))
    redis_feedback = set_if_not_exists(redis_client, session_id, manual_id, "feedback", "")
    redis_feedback_url = set_if_not_exists(redis_client, session_id, manual_id, "feedbackUrl", "")

    # pose_logger.info("redis is_sqt------------------------------------------- %s", redis_is_sqt)
    # pose_logger.info("redis is_good_sqt------------------------------------------- %s", redis_is_good_sqt)
    # pose_logger.info("redis total_sqt------------------------------------------- %s", redis_total_sqt)
    # pose_logger.info("redis good_sqt_count------------------------------------------- %s", redis_good_sqt_count)
    # pose_logger.info("redis feedback------------------------------------------- %s", redis_feedback)
    # pose_logger.info("redis feedbackUrl------------------------------------------- %s", redis_feedback_url)

    if results.pose_landmarks:
        landmarks = results.pose_landmarks.landmark

        left_hip = [landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].x,
                    landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].y]
        left_knee = [landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].x,
                        landmarks[mp_pose.PoseLandmark.LEFT_KNEE.value].y]
        left_ankle = [landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].x,
                        landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].y]

        left_knee_angle = calculate_angle(left_hip, left_knee, left_ankle)

        right_hip = [landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].x,
                        landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].y]
        right_knee = [landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].x,
                        landmarks[mp_pose.PoseLandmark.RIGHT_KNEE.value].y]
        right_ankle = [landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].x,
                        landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].y]

        right_knee_angle = calculate_angle(right_hip, right_knee, right_ankle)

        current_knee_angle = min(left_knee_angle, right_knee_angle)
        # pose_logger.info(f"Current knee angle: {current_knee_angle:.1f}")

        if current_knee_angle <= SQUAT_START_ANGLE and redis_is_sqt == 0:
            new_redis_total_sqt = redis_total_sqt + 1
            update_value(redis_client, session_id, manual_id, "isSqt", 1)
            update_value(redis_client, session_id, manual_id, "totalSqt", new_redis_total_sqt)

        if current_knee_angle > SQUAT_START_ANGLE and redis_is_sqt == 1:
            update_value(redis_client, session_id, manual_id, "isSqt", 0)

        if current_knee_angle <= GOOD_SQUAT_ANGLE and redis_is_good_sqt == 0:
            new_redis_good_sqt_count = redis_good_sqt_count + 1
            update_value(redis_client, session_id, manual_id, "isGoodSqt", 1)
            update_value(redis_client, session_id, manual_id, "goodSqtCount", new_redis_good_sqt_count)

        if current_knee_angle > GOOD_SQUAT_ANGLE and redis_is_good_sqt == 1:
            update_value(redis_client, session_id, manual_id, "isGoodSqt", 0)

        # Retrieve Redis values again to check if they have been updated
        redis_is_sqt = int(set_if_not_exists(redis_client, session_id, manual_id, "isSqt", 0))
        redis_is_good_sqt = int(set_if_not_exists(redis_client, session_id, manual_id, "isGoodSqt", 0))
        redis_total_sqt  = int(set_if_not_exists(redis_client, session_id, manual_id, "totalSqt", 0))
        redis_good_sqt_count  = int(set_if_not_exists(redis_client, session_id, manual_id, "goodSqtCount", 0))

        # pose_logger.info("redis is_sqt------------------------------------------- %s", redis_is_sqt)
        # pose_logger.info("redis is_good_sqt------------------------------------------- %s", redis_is_good_sqt)
        # pose_logger.info("redis total_sqt------------------------------------------- %s", redis_total_sqt)
        # pose_logger.info("redis good_sqt_count------------------------------------------- %s", redis_good_sqt_count)
        
        # Upload frame for the first bad squat
        if redis_total_sqt - redis_good_sqt_count == 1 and redis_feedback_url == "":
            # Use the existing event loop to run the async function
            loop = asyncio.get_event_loop()
            loop.run_until_complete(upload_bad_squat_frame(session_id, manual_id,frame))

        if redis_total_sqt > 0:
            redis_bad_squat_count = redis_total_sqt - redis_good_sqt_count
            feedback = ""
            if (redis_bad_squat_count / redis_total_sqt) > 0.5:
                feedback += "Most of your squats need improvement. Focus on going deeper by bending your knees more."
            elif (redis_bad_squat_count / redis_total_sqt) > 0.3:
                feedback += "You're doing okay, but try to achieve greater depth in your squats for better results."
            elif redis_bad_squat_count > 0:
                feedback += "Good job! Just a few squats need more depth. Keep up the good work!"
            else:
                feedback += "Excellent form! All your squats achieved proper depth."
        else:
            feedback = "No squats performed yet."
        update_value(redis_client, session_id, manual_id, "feedback", feedback)

        redis_feedback = set_if_not_exists(redis_client, session_id, manual_id, "feedback", "")
        redis_feedback_url = set_if_not_exists(redis_client, session_id, manual_id, "feedbackUrl", "")
        
    pose_logger.info("redis feedback------------------------------------------- %s", redis_feedback)
    pose_logger.info("redis feedbackUrl------------------------------------------- %s", redis_feedback_url)

    pose_logger.info("----------------------((((((((((((((((((((((((( Out squat )))))))))))))))))))))))))--------------------------------")

    if redis_total_sqt < target_reps:
        return "squatInProcess"
    else:
        return "squatCompleted"

def close_redis_connection_pose_utils():
    """
    Close the Redis connection.
    """
    redis_client.close()
    pose_logger.info("Redis connection closed.")