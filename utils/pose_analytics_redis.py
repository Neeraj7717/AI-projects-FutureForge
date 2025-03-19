import cv2
import numpy as np
import mediapipe as mp
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import time
import os
import asyncio
import argparse
import logging
from matplotlib import animation
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from s3utils.generaloperations import upload_to_s3_bucket
import redis
pose_logger = logging.getLogger('pose_analytics')


# Connect to Redis
redis_client = redis.Redis(host='192.168.0.162', port=6379, db=0)


ENABLE_FILE_LOGGING = True
# Create a custom logger for this file only
pose_logger.setLevel(logging.INFO)

# Create handlers
console_handler = logging.StreamHandler()

# Create formatters and add it to handlers
log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(log_format)

# Add handlers to the logger
pose_logger.addHandler(console_handler)

if ENABLE_FILE_LOGGING:
    file_handler = logging.FileHandler('pose_analytics.log')
    file_handler.setFormatter(log_format)
    pose_logger.addHandler(file_handler)  # Add file handler only if enabled



# Prevent this logger from propagating to the root logger
pose_logger.propagate = False

# Initialize MediaPipe Pose
mp_pose = mp.solutions.pose

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



def is_good_squat(min_knee_angle):
    """
    Determine if a squat is performed with good form based on knee angle
    """
    # pose_logger.info(f"Checking squat quality with min knee angle: {min_knee_angle:.1f}")
    return min_knee_angle <= 80



# Global dictionary to store session data
session_data = {}

def init_session_data(session_id):
    """Initialize tracking data for a new session"""
    if session_id not in session_data:
        session_data[session_id] = {
            'knee_angles_left': [],
            'knee_angles_right': [], 
            # 'hip_angles_left': [],
            # 'hip_angles_right': [],
            # 'back_angles': [],
            # 'pose_3d_frames': [],
            'is_squatting': False,
            'good_squat_count': 0,
            'total_squat_count': 0,
            'bad_squat_count': 0,
            'min_knee_angle': 120,
            'feedback': "",
            'feedback_urls': ""  # Changed to string as per followup instructions
        }
    return session_data[session_id]

def get_final_summary(sessionId):
    """Get the final feedback summary for a session"""
    if sessionId not in session_data:
        return "", ""
    return session_data[sessionId]['feedback'], session_data[sessionId]['feedback_urls']


def set_if_not_exists(redis_client, sessionId, manualId, key, value):
    redis_key  = f"pose:{sessionId}:{manualId}:{key}"
    if not redis_client.exists(redis_key):  # Check if key exists
        redis_client.set(redis_key, value)
        pose_logger.info(f"Key '{redis_key}' was not present, so it was set with value: {value}")
        return value
    else:
        value = redis_client.get(redis_key)
        pose_logger.info(f"Key '{redis_key}' already exists. Value: {value.decode('utf-8')}")
        return value.decode('utf-8')


def update_value(redis_client, sessionId, manualId, key, new_value):
    redis_key  = f"pose:{sessionId}:{manualId}:{key}"
    if redis_client.exists(redis_key):
        redis_client.set(redis_key, new_value)
        pose_logger.info(f"Key '{redis_key}' updated with new value: {new_value}")
    else:
        pose_logger.info(f"Key '{redis_key}' does not exist. Cannot update.")

good_squrt_angle = 80
squart_start_angle = 120


def analyze_live_squat(session_id, manual_id, frame, results, target_reps=1):

    """
    Process live video feed, analyze squat form, count good squats, and stop after reaching target
    """
    pose_logger.info("----------------------((((((((((((((((((((((((( In squat )))))))))))))))))))))))))--------------------------------")
    
    # Get or initialize session data
    current_session = init_session_data(session_id)
    
    is_squatting = current_session['is_squatting']
    good_squat_count = current_session['good_squat_count']
    total_squat_count = current_session['total_squat_count']
    bad_squat_count = current_session['bad_squat_count']
    min_knee_angle = current_session['min_knee_angle']
    feedback = current_session['feedback']
    feedback_urls = current_session['feedback_urls']


    redis_is_sqt = set_if_not_exists(redis_client, session_id, manual_id, "isSqt", 0)
    redis_is_good_sqt = set_if_not_exists(redis_client, session_id, manual_id, "isGoodSqt", 0)
    redis_total_sqt  = set_if_not_exists(redis_client, session_id, manual_id, "totalSqt", 0)
    redis_good_sqt_count  = set_if_not_exists(redis_client, session_id, manual_id, "goodSqtCount", 0)
    redis_feedback = set_if_not_exists(redis_client,session_id,manual_id,"feedback","")
    redis_feedback_url = set_if_not_exists(redis_client,session_id,manual_id,"feedbackUrl","")
    
    # pose_logger.info("redis is_sqt------------------------------------------- %s", redis_is_sqt)
    # pose_logger.info("redis is_good_sqt------------------------------------------- %s", redis_is_good_sqt)
    # pose_logger.info("redis total_sqt------------------------------------------- %s", redis_total_sqt)
    # pose_logger.info("redis good_sqt_count------------------------------------------- %s", redis_good_sqt_count)
    # pose_logger.info("redis feedback------------------------------------------- %s", redis_feedback)
    # pose_logger.info("redis feedbackUrl------------------------------------------- %s", redis_feedback_url)



        
    pose_logger.info(f"Starting squat analysis. Target: {target_reps} good squats")
    pose_logger.info(f"Stand in view of the camera and prepare to begin...{session_id}")
    frame_height, frame_width = frame.shape[:2]
    annotated_image = frame.copy()
    # pose_logger.info(f"Debug------------------------------------------------------------------1")
    if results.pose_landmarks:
        # pose_logger.info(f"Debug------------------------------------------------------------------2")

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
        pose_logger.info(f"Current knee angle: {current_knee_angle:.1f}, Is squatting: {is_squatting}")
        
        if current_knee_angle <= squart_start_angle and int(redis_is_sqt) == 0:
            new_redis_total_sqt = int(redis_total_sqt) + 1
            update_value(redis_client, session_id, manual_id, "isSqt", 1)
            update_value(redis_client, session_id, manual_id, "totalSqt", new_redis_total_sqt)

        if current_knee_angle > squart_start_angle and int(redis_is_sqt) == 1:
            update_value(redis_client, session_id, manual_id, "isSqt", 0)

        if current_knee_angle <= good_squrt_angle and int(redis_is_good_sqt) == 0:
            new_redis_good_sqt_count = int(redis_good_sqt_count) + 1
            update_value(redis_client, session_id, manual_id, "isGoodSqt", 1)
            update_value(redis_client, session_id, manual_id, "goodSqtCount", new_redis_good_sqt_count)
        
        if current_knee_angle > good_squrt_angle and int(redis_is_good_sqt) ==1:
            update_value(redis_client, session_id, manual_id, "isGoodSqt", 0)

        redis_is_sqt = set_if_not_exists(redis_client, session_id, manual_id, "isSqt", 0)
        redis_is_good_sqt = set_if_not_exists(redis_client, session_id, manual_id, "isGoodSqt", 0)
        redis_total_sqt  = set_if_not_exists(redis_client, session_id, manual_id, "totalSqt", 0)
        redis_good_sqt_count  = set_if_not_exists(redis_client, session_id, manual_id, "goodSqtCount", 0)


        pose_logger.info("redis is_sqt------------------------------------------- %s", redis_is_sqt)
        pose_logger.info("redis is_good_sqt------------------------------------------- %s", redis_is_good_sqt)
        pose_logger.info("redis total_sqt------------------------------------------- %s", redis_total_sqt)
        pose_logger.info("redis good_sqt_count------------------------------------------- %s", redis_good_sqt_count)



        # Check if we're entering a squat
        if current_knee_angle < 120 and not is_squatting:
            is_squatting = True
            min_knee_angle = 120  # Reset min_knee_angle when starting new squat
            pose_logger.info("Squat started")
        
        # Update minimum knee angle during squat
        if is_squatting and current_knee_angle < min_knee_angle:
            min_knee_angle = current_knee_angle
            pose_logger.info(f"New minimum knee angle: {min_knee_angle:.1f}")
        
        # Check if we're exiting a squat
        if current_knee_angle > 120 and is_squatting:
            is_squatting = False
            total_squat_count += 1
            pose_logger.info(f"Squat completed. Min knee angle reached: {min_knee_angle:.1f}")
            
            # Determine if it was a good squat
            if min_knee_angle <= 80:
                good_squat_count += 1
                pose_logger.info(f"Good squat detected! Count: {good_squat_count}/{target_reps}")
            else:
                bad_squat_count += 1
                pose_logger.info(f"Bad squat detected - not deep enough! Count: {bad_squat_count}")
                
                # Only upload if we don't already have a feedback URL
                if 'feedback_urls' not in current_session or not current_session['feedback_urls']:
                    # Save bad squat frame to S3 asynchronously
                    async def upload_bad_squat_frame():
                        try:
                            frame_filename = f"bad_squat_{session_id}_{bad_squat_count}.jpg"
                            local_path = f"/tmp/{frame_filename}"
                            cv2.imwrite(local_path, frame)
                            
                            cloud_path = f"feedback_frames/"
                            url = upload_to_s3_bucket("eizen-dev", local_path, cloud_path, frame_filename)
                            update_value(redis_client, session_id, manual_id, "feedbackUrl", url)
                            current_session['feedback_urls'] += url   # Append URL to the string
                            
                            # Cleanup temporary file
                            os.remove(local_path)
                        except Exception as e:
                            pose_logger.error(f"Error uploading bad squat frame: {str(e)}")
                    
                    # Start async upload without waiting
                    
                    asyncio.create_task(upload_bad_squat_frame())
            
            # Reset min_knee_angle to default
            success_rate = f"{(good_squat_count/total_squat_count * 100):.1f}%" if total_squat_count > 0 else "0%"
            feedback = f"good_squats were {good_squat_count} and bad_squats were {bad_squat_count} and total_attempts:{total_squat_count} and success_rate:{success_rate}|suggestion were "

            if total_squat_count > 0:
                if (bad_squat_count/total_squat_count) > 0.5:
                    feedback += "Most of your squats need improvement. Focus on going deeper by bending your knees more."
                elif (bad_squat_count/total_squat_count) > 0.3:
                    feedback += "You're doing okay, but try to achieve greater depth in your squats for better results."
                elif bad_squat_count > 0:
                    feedback += "Good job! Just a few squats need more depth. Keep up the good work!"
                else:
                    feedback += "Excellent form! All your squats achieved proper depth."
            else:
                feedback += "No squats performed yet."
            min_knee_angle = 120



    # Build the feedback string with all stats and suggestions

    pose_logger.info(f"S3 feedback URLs: {current_session.get('feedback_urls', '')}")
    pose_logger.info(f"Good squats completed: {good_squat_count}/{target_reps}")
    pose_logger.info(f"Total squat attempts: {total_squat_count}")
    pose_logger.info(f"Bad squat attempts: {bad_squat_count}")
    pose_logger.info(f"the feedback was: {feedback}")
    update_value(redis_client, session_id, manual_id, "feedback", feedback)
    redis_feedback = set_if_not_exists(redis_client,session_id,manual_id,"feedback","")
    redis_feedback_url = set_if_not_exists(redis_client,session_id,manual_id,"feedbackUrl","")
    pose_logger.info("redis feedback------------------------------------------- %s", redis_feedback)
    pose_logger.info("redis feedbackUrl------------------------------------------- %s", redis_feedback_url)
    


    pose_logger.info("----------------------((((((((((((((((((((((((( Out squat )))))))))))))))))))))))))--------------------------------")

    current_session['is_squatting'] = is_squatting
    current_session['good_squat_count'] = good_squat_count
    current_session['total_squat_count'] = total_squat_count
    current_session['bad_squat_count'] = bad_squat_count
    current_session['min_knee_angle'] = min_knee_angle
    current_session['feedback']=feedback
    
    # Update main dictionary
    session_data[session_id] = current_session

    
    if good_squat_count < target_reps:
        return "squatInProcess"
    else:
        return "squatCompleted"
    
    
####################################################################### Not Using Any more ############################################################

def generate_squat_report(knee_angles_left, knee_angles_right, back_angles, good_squat_count, total_squat_count):
    """
    Generate a summary report of the squat analysis
    """
    # Calculate metrics
    min_left_knee = min(knee_angles_left) if knee_angles_left else 0
    min_right_knee = min(knee_angles_right) if knee_angles_right else 0
    avg_back_angle = sum(back_angles) / len(back_angles) if back_angles else 0
    
    # Check for asymmetry
    knee_asymmetry = abs(min_left_knee - min_right_knee)
    
    # Generate feedback
    feedback = []
    
    # Squat depth
    if min_left_knee > 110 or min_right_knee > 110:
        feedback.append("- Insufficient squat depth. Try to go deeper for better muscle engagement.")
    elif min_left_knee < 70 or min_right_knee < 70:
        feedback.append("- Very deep squat. Be careful with your knees if you experience any pain.")
    else:
        feedback.append("- Good squat depth achieved.")
    
    # Asymmetry
    if knee_asymmetry > 15:
        feedback.append(f"- Significant asymmetry detected between left and right knee angles ({knee_asymmetry:.1f}°). Try to distribute weight evenly.")
    
    # Back angle
    if avg_back_angle > 45:
        feedback.append("- Significant forward lean. Focus on maintaining a more upright torso position.")
    else:
        feedback.append("- Good back posture maintained during squats.")
    
    # Success rate
    success_rate = (good_squat_count / total_squat_count * 100) if total_squat_count > 0 else 0
    
    # Generate report
    pose_logger.info("\n======== SQUAT ANALYSIS REPORT ========")
    pose_logger.info(f"Good squats completed: {good_squat_count}")
    pose_logger.info(f"Total squat attempts: {total_squat_count}")
    pose_logger.info(f"Success rate: {success_rate:.1f}%")
    pose_logger.info(f"Minimum knee angle (left): {min_left_knee:.1f}°")
    pose_logger.info(f"Minimum knee angle (right): {min_right_knee:.1f}°")
    pose_logger.info(f"Knee angle asymmetry: {knee_asymmetry:.1f}°")
    pose_logger.info(f"Average back angle: {avg_back_angle:.1f}°")
    pose_logger.info("\nForm Assessment:")
    for item in feedback:
        pose_logger.info(item)
    pose_logger.info("=======================================")
    
    # Save report to file
    with open("live_squat_analysis_report.txt", "w") as f:
        f.write("======== SQUAT ANALYSIS REPORT ========\n")
        f.write(f"Good squats completed: {good_squat_count}\n")
        f.write(f"Total squat attempts: {total_squat_count}\n")
        f.write(f"Success rate: {success_rate:.1f}%\n")
        f.write(f"Minimum knee angle (left): {min_left_knee:.1f}°\n")
        f.write(f"Minimum knee angle (right): {min_right_knee:.1f}°\n")
        f.write(f"Knee angle asymmetry: {knee_asymmetry:.1f}°\n")
        f.write(f"Average back angle: {avg_back_angle:.1f}°\n")
        f.write("\nForm Assessment:\n")
        for item in feedback:
            f.write(f"{item}\n")
        f.write("=======================================\n")
    
    pose_logger.info("Report saved to 'live_squat_analysis_report.txt'")
