"""
Activity Instruction Sender
==========================
Sends speech instructions to UI via Kafka when activities start.
Repeats instructions if activities are not completed correctly.
"""
import json
import logging
import requests
import traceback
import hashlib
from datetime import datetime
from typing import Dict, Optional
from kafka import KafkaProducer
from Config.settings import Settings
from utils.eizen_utils.logger_utils.logger_operations import LoggerOperations

instruction_sender_logger = LoggerOperations(
    logger_name='ActivityInstructionSender', 
    log_level=logging.INFO, 
    use_log_file=False
)

config = Settings()


class ActivityInstructionSender:
    """
    Sends activity-based speech instructions via Kafka.
    Maps activities to speech instructions and sends them when activities start.
    """
    
    def __init__(self):
        """Initialize the instruction sender with Kafka producer."""
        try:
            self.producer = KafkaProducer(bootstrap_servers=config.kafka_url)
            self.video_instruction_topic = config.video_instruction_kafka_topic
            self.t2v_endpoint = config.t2v_endpoint
            
            # Activity to instruction mapping
            self.activity_instructions = {
                # Pose detection activities
                "PERSON_PRESENT": "Please stand",
                "HAND_RAISED": "Please raise your right hand",
                "HANDS_DOWN": "Please lower your right hand",
                "LEFT_HAND_RAISED": "Please raise your left hand",
                "LEFT_HAND_DOWN": "Please lower your left hand",
                "BOTH_HANDS_RAISED": "Please raise both hands",
                "BOTH_HANDS_DOWN": "Please lower both hands",
                # Phone assembly activities
                "PHONE_BODY_PRESENT": "Show the phone body",
                "SCREEN_ATTACHED": "Show the display or screen",
                "COMPONENTS_PLACED": "Show the flash or camera",
                "ASSEMBLY_COMPLETE": "Show the complete phone",
            }
            
            # Wrong activity detection mapping (what was done wrong -> what should be done)
            # Matches instruction_graph style for better user guidance
            self.wrong_activity_messages = {
                ("HAND_RAISED", "leftHandAbove90"): "I see your left hand raised. Please raise your right hand instead.",
                ("HAND_RAISED", "leftHandBelow90"): "I see your left hand raised. Please raise your right hand instead.",
                ("HAND_RAISED", "leftBelowAbove90"): "I see your left hand raised. Please raise your right hand instead.",
                ("HAND_RAISED", "bothHandsAbove90"): "You are raising both hands. Please raise only your right hand.",
                ("HAND_RAISED", "bothHandsBelow90"): "You are raising both hands. Please raise only your right hand.",
                ("HAND_RAISED", "rightHandBelow90"): "Raise your right hand above your shoulders",
                ("LEFT_HAND_RAISED", "rightHandAbove90"): "I see your right hand raised. Please raise your left hand instead.",
                ("LEFT_HAND_RAISED", "rightHandBelow90"): "I see your right hand raised. Please raise your left hand instead.",
                ("LEFT_HAND_RAISED", "bothHandsAbove90"): "You are raising both hands. Please raise only your left hand.",
                ("LEFT_HAND_RAISED", "bothHandsBelow90"): "You are raising both hands. Please raise only your left hand.",
                ("LEFT_HAND_RAISED", "leftHandBelow90"): "Raise your left hand above your shoulders",
                ("HANDS_DOWN", "rightHandAbove90"): "I see your right hand raised. Please lower your right hand.",
                ("HANDS_DOWN", "rightHandBelow90"): "I see your right hand raised. Please lower your right hand.",
                ("HANDS_DOWN", "leftHandAbove90"): "I see your left hand raised. Please lower your left hand.",
                ("HANDS_DOWN", "leftBelowAbove90"): "I see your left hand raised. Please lower your left hand.",
                ("HANDS_DOWN", "bothHandsBelow90"): "You are raising both hands. Please lower your hands.",
                ("HANDS_DOWN", "bothHandsAbove90"): "You are raising both hands. Please lower your hands.",
                ("LEFT_HAND_DOWN", "leftHandAbove90"): "I see your left hand raised. Please lower your left hand.",
                ("LEFT_HAND_DOWN", "bothHandsAbove90"): "You are raising both hands. Please lower your hands.",
                ("LEFT_HAND_DOWN", "rightHandAbove90"): "I see your right hand raised. Please lower your left hand.",
            }
            
            # Messages for when no hand is detected (user not doing anything)
            # Matches instruction_graph messages exactly
            self.no_activity_messages = {
                "HAND_RAISED": "I don't see any hand raised. Please raise your right hand",
                "LEFT_HAND_RAISED": "I don't see any hand raised. Please raise your left hand",
                "BOTH_HANDS_RAISED": "You are not raising your hands. Please raise your both hands above the shoulders.",
            }
            
            # Messages for hand below shoulders (needs to raise higher)
            self.below_shoulder_messages = {
                "HAND_RAISED": "Raise your right hand above your shoulders",
                "LEFT_HAND_RAISED": "Raise your left hand above your shoulders",
                "BOTH_HANDS_RAISED": "Please raise your both hands above the shoulders.",
            }
            
            # Track last sent instruction per source to avoid duplicates
            self.last_instruction = {}  # source_id -> (activity, frame_number)
            
            # Track last sent anomaly message per source to avoid spam
            self.last_anomaly = {}  # f"{source_id}:{session_id}" -> (activity_id, frame_number)
            
            instruction_sender_logger.info("ActivityInstructionSender initialized")
        except Exception as e:
            instruction_sender_logger.error(f"Error initializing ActivityInstructionSender: {e}")
            self.producer = None
    
    def get_instruction_text(self, activity_id: str) -> str:
        """
        Get instruction text for an activity.
        
        Args:
            activity_id: Activity identifier (e.g., "PERSON_PRESENT", "HAND_RAISED")
            
        Returns:
            Instruction text to speak
        """
        # Default instruction if not found
        default = f"Please perform {activity_id.replace('_', ' ').lower()}"
        return self.activity_instructions.get(activity_id, default)

    def send_custom_instruction(
        self,
        *,
        step_text: str,
        source_id: str,
        session_id: str,
        manual_id: str,
        step_id: str,
        status: str = "inProgress",
        start_time: str = "",
        end_time: str = "",
        audio_url: str = "",
        gender: int = 1,
        repetition: int = 0,
        context_url: str = "",
        context_type: str = "",
        feedback: str = "",
        feedback_url: str = "",
        step_score: str = "",
        video_url: str = "",
    ) -> bool:
        """
        Send a UI/Speech instruction message with an explicit stepId/text/status.

        This is the generic primitive used by SOP/other flows to match the message
        schema expected by the UI consumer.
        """
        if not self.producer:
            instruction_sender_logger.warning("Kafka producer not available, skipping custom instruction")
            return False

        try:
            # Basic validation
            step_text = (step_text or "").strip()
            manual_id = str(manual_id) if manual_id is not None else ""
            step_id = str(step_id) if step_id is not None else ""

            # Timestamps
            now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")
            if status == "inProgress" and not start_time:
                start_time = now_iso
            if status in ["completed", "failed"] and not end_time:
                end_time = now_iso

            # Manual special-case (matches legacy instruction_graph)
            if manual_id and manual_id.isdigit() and int(manual_id) == 13 and status == "inProgress":
                audio_url = "https://cdn-dev.eizen.ai/0/via/pine_labs/audios-hindi/demohindi.mp3"

            # Generate audio if needed (only for inProgress by default)
            if not audio_url and step_text and status == "inProgress":
                try:
                    response = requests.post(
                        self.t2v_endpoint,
                        json={"text": step_text, "gender": gender},
                        timeout=5
                    )
                    if response.status_code == 200:
                        data = json.loads(response.content.decode("utf-8"))
                        audio_url = data.get("file_path", "") or ""
                    else:
                        instruction_sender_logger.warning(
                            f"T2V endpoint returned status {response.status_code} for custom instruction"
                        )
                except Exception as e:
                    instruction_sender_logger.warning(f"Error generating audio for custom instruction: {e}")

            message = {
                "stepId": step_id,
                "sessionId": session_id,
                "videoUrl": video_url,
                "manualId": manual_id,
                "step": step_text,
                "status": status,
                "startTime": start_time,
                "endTime": end_time,
                "audioUrl": audio_url,
                "contextUrl": context_url,
                "contextType": context_type,
                "repetition": repetition,
                "feedback": feedback,
                "feedbackUrl": feedback_url,
                "stepScore": step_score,
                # Helpful extra fields (UI can ignore)
                "sourceId": source_id,
            }

            key_component = session_id.encode("utf-8") if session_id else None
            message_json = json.dumps(message)
            self.producer.send(
                self.video_instruction_topic,
                key=key_component,
                value=message_json.encode("utf-8")
            )
            self.producer.flush()
            return True

        except Exception as e:
            instruction_sender_logger.error(f"Error sending custom instruction: {e}")
            traceback.print_exc()
            return False
    
    def send_activity_instruction(
        self,
        activity_id: str,
        source_id: str,
        session_id: str,
        manual_id: str,
        frame_number: int,
        cycle_count: int = 0,
        is_repeat: bool = False
    ) -> bool:
        """
        Send activity instruction via Kafka.
        
        Args:
            activity_id: Activity identifier
            source_id: Source identifier
            session_id: Session identifier
            manual_id: Manual identifier
            frame_number: Current frame number
            cycle_count: Current cycle number
            is_repeat: Whether this is a repeat instruction (activity not completed)
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.producer:
            instruction_sender_logger.warning("Kafka producer not available, skipping instruction")
            return False
        
        try:
            # Get instruction text
            instruction_text = self.get_instruction_text(activity_id)
            
            # Add repeat prefix if needed
            if is_repeat:
                instruction_text = f"Please try again. {instruction_text}"
            
            # Check if we already sent this instruction recently (avoid spam)
            cache_key = f"{source_id}:{session_id}"
            last_activity, last_frame = self.last_instruction.get(cache_key, (None, -1))
            
            # Only send if it's a new activity or repeat is requested
            if last_activity == activity_id and not is_repeat and (frame_number - last_frame) < 30:
                instruction_sender_logger.debug(
                    f"Skipping duplicate instruction for {activity_id} at frame {frame_number}"
                )
                return False
            
            # Generate audio URL using T2V endpoint
            audio_url = ""
            try:
                response = requests.post(
                    self.t2v_endpoint,
                    json={"text": instruction_text, "gender": 1},
                    timeout=5
                )
                if response.status_code == 200:
                    data = json.loads(response.content.decode("utf-8"))
                    audio_url = data.get("file_path", "")
                    instruction_sender_logger.info(
                        f"Generated audio for '{instruction_text}': {audio_url}"
                    )
                else:
                    instruction_sender_logger.warning(
                        f"T2V endpoint returned status {response.status_code}"
                    )
            except Exception as e:
                instruction_sender_logger.warning(f"Error generating audio: {e}")
                # Continue without audio URL - UI can use text-to-speech
            
            # Prepare Kafka message (matching format expected by UI)
            # Use datetime.utcnow() for compatibility (same as mongo_operations.py)
            current_time = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")
            
            # Use a numeric stepId that UI can recognize (use hash of activity_id for consistency)
            # UI might filter out non-numeric stepIds, so we'll use a consistent numeric ID
            step_id_hash = int(hashlib.md5(f"ACTIVITY_{activity_id}".encode()).hexdigest()[:8], 16) % 1000000
            step_id_str = str(step_id_hash)
            
            message = {
                "sessionId": session_id,
                "manualId": manual_id,
                "sourceId": source_id,
                "step": instruction_text,
                "stepId": step_id_str,  # Use numeric stepId for UI compatibility
                "status": "inProgress",
                "audioUrl": audio_url,
                "videoUrl": "",  # Not needed for activity instructions
                "activityId": activity_id,  # Keep activityId for our tracking
                "cycleCount": cycle_count,
                "frameNumber": frame_number,
                "isRepeat": is_repeat,
                "startTime": current_time,  # Set current time (UI might require this)
                "endTime": "",
                "stepScore": "",
                "repetition": 1 if is_repeat else 0,
                "contextUrl": "",
                "contextType": "",
                "feedback": "",
                "feedbackUrl": ""
            }
            
            # Send to Kafka
            key_component = session_id.encode('utf-8')
            message_json = json.dumps(message)
            
            # Send message
            future = self.producer.send(
                self.video_instruction_topic,
                key=key_component,
                value=message_json.encode("utf-8")
            )
            
            # Flush to ensure message is sent immediately
            self.producer.flush()
            
            # Log the full message for debugging
            instruction_sender_logger.debug(
                f"Kafka message sent to topic '{self.video_instruction_topic}': {message_json}"
            )
            
            # Update cache
            self.last_instruction[cache_key] = (activity_id, frame_number)
            
            repeat_msg = " (REPEAT)" if is_repeat else ""
            instruction_sender_logger.info(
                f"Sent instruction{repeat_msg}: '{instruction_text}' for activity {activity_id} "
                f"(Cycle {cycle_count}, Frame {frame_number}) | "
                f"Topic: {self.video_instruction_topic} | "
                f"Audio: {audio_url if audio_url else 'None'}"
            )
            
            return True
            
        except Exception as e:
            instruction_sender_logger.error(f"Error sending activity instruction: {e}")
            traceback.print_exc()
            return False
    
    def check_and_repeat_instruction(
        self,
        activity_id: str,
        source_id: str,
        session_id: str,
        manual_id: str,
        frame_number: int,
        cycle_count: int,
        activity_success: bool,
        consecutive_failures: int = 0,
        things_present: list = None
    ) -> bool:
        """
        Check if activity is completed correctly, repeat instruction if not.
        Sends specific corrective messages based on what's wrong (like instruction_graph).
        
        Args:
            activity_id: Current activity identifier
            source_id: Source identifier
            session_id: Session identifier
            manual_id: Manual identifier
            frame_number: Current frame number
            cycle_count: Current cycle number
            activity_success: Whether activity rules passed
            consecutive_failures: Number of consecutive failures
            things_present: List of detected things (optional, for better messages)
            
        Returns:
            True if instruction was sent, False otherwise
        """
        # Repeat instruction if activity is not completed correctly
        # Only repeat after a few consecutive failures to avoid spam
        if not activity_success and consecutive_failures >= 3:
            # Check if enough time has passed since last instruction
            cache_key = f"{source_id}:{session_id}"
            last_activity, last_frame = self.last_instruction.get(cache_key, (None, -1))
            
            # Repeat if it's been at least 60 frames since last instruction
            if (frame_number - last_frame) >= 60:
                # First, try to detect wrong activity and send specific message
                if things_present:
                    wrong_detected = self.detect_and_send_wrong_activity(
                        activity_id=activity_id,
                        things_present=things_present,
                        source_id=source_id,
                        session_id=session_id,
                        manual_id=manual_id,
                        frame_number=frame_number,
                        cycle_count=cycle_count
                    )
                    if wrong_detected:
                        # Wrong activity message sent, don't send generic repeat
                        return True
                
                # If no wrong activity detected, send generic repeat instruction
                instruction_sender_logger.warning(
                    f"Activity {activity_id} not completed correctly after {consecutive_failures} attempts. "
                    f"Repeating instruction at frame {frame_number}"
                )
                return self.send_activity_instruction(
                    activity_id=activity_id,
                    source_id=source_id,
                    session_id=session_id,
                    manual_id=manual_id,
                    frame_number=frame_number,
                    cycle_count=cycle_count,
                    is_repeat=True
                )
        
        return False
    
    def detect_and_send_wrong_activity(
        self,
        activity_id: str,
        things_present: list,
        source_id: str,
        session_id: str,
        manual_id: str,
        frame_number: int,
        cycle_count: int = 0
    ) -> bool:
        """
        Detect if wrong activity is performed and send anomaly message.
        
        Examples:
        - Expecting HAND_RAISED (right hand) but leftHandAbove90 detected
        - Expecting LEFT_HAND_RAISED but rightHandAbove90 detected
        
        Args:
            activity_id: Expected activity identifier
            things_present: List of detected things (e.g., ["personPresent", "leftHandAbove90"])
            source_id: Source identifier
            session_id: Session identifier
            manual_id: Manual identifier
            frame_number: Current frame number
            cycle_count: Current cycle number
            
        Returns:
            True if wrong activity detected and message sent, False otherwise
        """
        if not things_present or not isinstance(things_present, list):
            return False
        
        # Check for wrong hand positions
        wrong_hand_detected = None
        
        # Check what hand position is actually detected
        detected_hand = None
        for item in things_present:
            # Normalize item to string and check for hand-related keywords
            item_str = str(item).strip()
            if any(keyword in item_str for keyword in ["Hand", "hand", "Above90", "Below90"]):
                detected_hand = item_str
                break
        
        if not detected_hand:
            # Check if we should send a message for "no hand detected" scenario
            # This happens when user is not doing anything (just personPresent)
            # OR when hand is below shoulders (rightHandBelow90/leftHandBelow90)
            has_person = "personPresent" in things_present
            has_below_shoulder = any(item in things_present for item in ["rightHandBelow90", "leftHandBelow90", "bothHandsBelow90"])
            
            if has_person or has_below_shoulder:
                # Check if activity expects a hand to be raised
                if activity_id in self.no_activity_messages:
                    cache_key = f"{source_id}:{session_id}"
                    last_anomaly_activity, last_anomaly_frame = self.last_anomaly.get(cache_key, (None, -1))
                    
                    # Cooldown to avoid spamming repeated audio while user is stuck
                    if (last_anomaly_activity != "no_hand" or 
                        (frame_number - last_anomaly_frame) >= 60):
                        
                        no_hand_message = self.no_activity_messages[activity_id]
                        instruction_sender_logger.info(
                            f"No hand detected (or hand below shoulders) for {activity_id}. Sending: {no_hand_message}"
                        )
                        
                        sent = self.send_anomaly_instruction(
                            activity_id=activity_id,
                            anomaly_message=no_hand_message,
                            wrong_activity="no_hand",
                            source_id=source_id,
                            session_id=session_id,
                            manual_id=manual_id,
                            frame_number=frame_number,
                            cycle_count=cycle_count
                        )
                        
                        if sent:
                            self.last_anomaly[cache_key] = ("no_hand", frame_number)
                        
                        return sent
            
            instruction_sender_logger.debug(
                f"No hand detected in things_present={things_present} for activity {activity_id}"
            )
            return False  # No hand detected and no message sent
        
        instruction_sender_logger.debug(
            f"Detected hand: {detected_hand} for activity {activity_id}, things_present={things_present}"
        )
        
        # Check if wrong activity based on expected activity
        # Matches instruction_graph logic for better user guidance
        if activity_id == "HAND_RAISED":
            # Expecting right hand above shoulders
            if detected_hand in ["leftHandAbove90", "leftHandBelow90", "leftBelowAbove90"]:
                wrong_hand_detected = detected_hand
                instruction_sender_logger.info(
                    f"Wrong hand detected for HAND_RAISED: Expected rightHandAbove90, got {detected_hand}"
                )
            elif detected_hand in ["bothHandsBelow90", "bothHandsAbove90"]:
                wrong_hand_detected = detected_hand
                instruction_sender_logger.info(
                    f"Both hands detected for HAND_RAISED: Expected only right hand, got {detected_hand}"
                )
            elif detected_hand == "rightHandBelow90":
                # Hand is raised but below shoulders - needs to go higher
                wrong_hand_detected = detected_hand
                instruction_sender_logger.info(
                    f"Right hand below shoulders for HAND_RAISED: Needs to be above shoulders"
                )
        elif activity_id == "LEFT_HAND_RAISED":
            # Expecting left hand above shoulders
            if detected_hand in ["rightHandAbove90", "rightHandBelow90"]:
                wrong_hand_detected = detected_hand
                instruction_sender_logger.info(
                    f"Wrong hand detected for LEFT_HAND_RAISED: Expected leftHandAbove90, got {detected_hand}"
                )
            elif detected_hand in ["bothHandsBelow90", "bothHandsAbove90"]:
                wrong_hand_detected = detected_hand
                instruction_sender_logger.info(
                    f"Both hands detected for LEFT_HAND_RAISED: Expected only left hand, got {detected_hand}"
                )
            elif detected_hand in ["leftHandBelow90", "leftBelowAbove90"]:
                # Hand is raised but below shoulders - needs to go higher
                wrong_hand_detected = detected_hand
                instruction_sender_logger.info(
                    f"Left hand below shoulders for LEFT_HAND_RAISED: Needs to be above shoulders"
                )
        elif activity_id == "HANDS_DOWN":
            # Expecting hands down, but any hand raised
            if detected_hand in ["rightHandAbove90", "rightHandBelow90", "leftHandAbove90", "leftBelowAbove90", "bothHandsAbove90", "bothHandsBelow90"]:
                wrong_hand_detected = detected_hand
                instruction_sender_logger.info(
                    f"Hand still raised for HANDS_DOWN: Expected no hand raised, got {detected_hand}"
                )
        elif activity_id == "LEFT_HAND_DOWN":
            # Expecting left hand down, but left hand still raised
            if detected_hand in ["leftHandAbove90", "leftHandBelow90", "leftBelowAbove90", "bothHandsAbove90", "bothHandsBelow90"]:
                wrong_hand_detected = detected_hand
                instruction_sender_logger.info(
                    f"Left hand still raised for LEFT_HAND_DOWN: Expected left hand down, got {detected_hand}"
                )
        elif activity_id == "BOTH_HANDS_RAISED":
            # Expecting both hands, but only one or none
            if detected_hand in ["rightHandAbove90", "rightHandBelow90"]:
                wrong_hand_detected = detected_hand
                instruction_sender_logger.info(
                    f"Only right hand for BOTH_HANDS_RAISED: Expected both hands, got {detected_hand}"
                )
            elif detected_hand in ["leftHandAbove90", "leftHandBelow90", "leftBelowAbove90"]:
                wrong_hand_detected = detected_hand
                instruction_sender_logger.info(
                    f"Only left hand for BOTH_HANDS_RAISED: Expected both hands, got {detected_hand}"
                )
            elif detected_hand == "bothHandsBelow90":
                # Both hands raised but below shoulders
                wrong_hand_detected = detected_hand
                instruction_sender_logger.info(
                    f"Both hands below shoulders for BOTH_HANDS_RAISED: Needs to be above shoulders"
                )
        
        if wrong_hand_detected:
            # Send anomaly message continuously when wrong activity is detected
            # No cooldown - user needs continuous feedback until they correct the action
            cache_key = f"{source_id}:{session_id}"
            last_anomaly_activity, last_anomaly_frame = self.last_anomaly.get(cache_key, (None, -1))
            
            # Only send if it's a different wrong activity or at least 5 frames have passed (to avoid audio overlap)
            # Cooldown to avoid spamming repeated audio while user is stuck
            if (last_anomaly_activity != wrong_hand_detected or 
                (frame_number - last_anomaly_frame) >= 60):
                
                # Get the anomaly message - check for below shoulder case first
                anomaly_message = None
                
                # Check if hand is below shoulders (needs to raise higher)
                if wrong_hand_detected in ["rightHandBelow90", "leftHandBelow90", "leftBelowAbove90", "bothHandsBelow90"]:
                    if activity_id in self.below_shoulder_messages:
                        anomaly_message = self.below_shoulder_messages[activity_id]
                
                # If not below shoulder case, check wrong activity messages
                if not anomaly_message:
                    anomaly_key = (activity_id, wrong_hand_detected)
                    anomaly_message = self.wrong_activity_messages.get(
                        anomaly_key,
                        f"Please perform {activity_id.replace('_', ' ').lower()} correctly"
                    )
                
                # Send anomaly instruction
                instruction_sender_logger.warning(
                    f"Wrong activity detected: Expected {activity_id}, but {wrong_hand_detected} detected. "
                    f"Sending corrective message: {anomaly_message}"
                )
                
                sent = self.send_anomaly_instruction(
                    activity_id=activity_id,
                    anomaly_message=anomaly_message,
                    wrong_activity=wrong_hand_detected,
                    source_id=source_id,
                    session_id=session_id,
                    manual_id=manual_id,
                    frame_number=frame_number,
                    cycle_count=cycle_count
                )
                
                if sent:
                    # Update last anomaly sent
                    self.last_anomaly[cache_key] = (wrong_hand_detected, frame_number)
                
                return sent
        
        return False
    
    def send_anomaly_instruction(
        self,
        activity_id: str,
        anomaly_message: str,
        wrong_activity: str,
        source_id: str,
        session_id: str,
        manual_id: str,
        frame_number: int,
        cycle_count: int = 0
    ) -> bool:
        """
        Send anomaly instruction message via Kafka.
        
        Args:
            activity_id: Expected activity identifier
            anomaly_message: Message to send (e.g., "Please raise your right hand instead of left hand")
            wrong_activity: What was done wrong (e.g., "leftHandAbove90")
            source_id: Source identifier
            session_id: Session identifier
            manual_id: Manual identifier
            frame_number: Current frame number
            cycle_count: Current cycle number
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.producer:
            instruction_sender_logger.warning("Kafka producer not available, skipping anomaly instruction")
            return False
        
        try:
            # Generate audio for anomaly message
            audio_url = ""
            try:
                response = requests.post(
                    self.t2v_endpoint,
                    json={"text": anomaly_message, "gender": 1},
                    timeout=5
                )
                if response.status_code == 200:
                    data = json.loads(response.content.decode("utf-8"))
                    audio_url = data.get("file_path", "")
                    instruction_sender_logger.info(
                        f"Generated audio for anomaly message '{anomaly_message}': {audio_url}"
                    )
            except Exception as e:
                instruction_sender_logger.warning(f"Error generating audio for anomaly message: {e}")
            
            # Prepare Kafka message
            current_time = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")
            
            # Use numeric stepId for UI compatibility
            step_id_hash = int(hashlib.md5(f"ANOMALY_{activity_id}_{wrong_activity}".encode()).hexdigest()[:8], 16) % 1000000
            step_id_str = str(step_id_hash)
            
            message = {
                "sessionId": session_id,
                "manualId": manual_id,
                "sourceId": source_id,
                "step": anomaly_message,
                "stepId": step_id_str,
                "status": "failed",  # Anomaly = failed status
                "audioUrl": audio_url,
                "videoUrl": "",
                "activityId": activity_id,
                "cycleCount": cycle_count,
                "frameNumber": frame_number,
                "isRepeat": False,
                "isAnomaly": True,  # Mark as anomaly
                "wrongActivity": wrong_activity,  # What was done wrong
                "startTime": current_time,
                "endTime": "",
                "stepScore": "",
                "repetition": 0,
                "contextUrl": "",
                "contextType": "",
                "feedback": anomaly_message,  # Use anomaly message as feedback
                "feedbackUrl": ""
            }
            
            # Send to Kafka
            key_component = session_id.encode('utf-8')
            message_json = json.dumps(message)
            
            self.producer.send(
                self.video_instruction_topic,
                key=key_component,
                value=message_json.encode("utf-8")
            )
            
            self.producer.flush()
            
            instruction_sender_logger.info(
                f"Sent anomaly instruction: '{anomaly_message}' for activity {activity_id} "
                f"(wrong activity: {wrong_activity}) | "
                f"Topic: {self.video_instruction_topic} | "
                f"Audio: {audio_url if audio_url else 'None'}"
            )
            
            return True
            
        except Exception as e:
            instruction_sender_logger.error(f"Error sending anomaly instruction: {e}")
            traceback.print_exc()
            return False
    
    def clear_cache(self, source_id: str = None, session_id: str = None):
        """Clear instruction cache for a source/session."""
        if source_id and session_id:
            cache_key = f"{source_id}:{session_id}"
            if cache_key in self.last_instruction:
                del self.last_instruction[cache_key]
        else:
            self.last_instruction.clear()


# Global singleton instance
_instruction_sender = None

def get_instruction_sender() -> ActivityInstructionSender:
    """Get global ActivityInstructionSender instance."""
    global _instruction_sender
    if _instruction_sender is None:
        _instruction_sender = ActivityInstructionSender()
    return _instruction_sender
