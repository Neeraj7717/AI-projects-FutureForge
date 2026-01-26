"""
Generic test script for any SOP using laptop camera.
Supports object detection (YOLO), pose detection, and gender detection.

Usage:
    # Test phone assembly SOP
    python test_sop_camera.py --sop-id EZA_SOP_PHONE_ASSEMBLY
    
    # Test pose SOP
    python test_sop_camera.py --sop-id EZA_SOP_POSE --use-pose
    
    # Test gender detection SOP
    python test_sop_camera.py --sop-id EZA_SOP_GENDER --use-gender
    
    # Test with custom directory
    python test_sop_camera.py --sop-dir phone_assembly
    
    # Use pose detection instead of YOLO
    python test_sop_camera.py --sop-id EZA_SOP_POSE --use-pose
"""
import json
import os
import sys
import cv2
import time
import warnings
import argparse
from datetime import datetime

# Suppress OpenCV warnings
warnings.filterwarnings('ignore')
os.environ['OPENCV_FFMPEG_LOGLEVEL'] = '-8'

# Add parent directory for imports
parent_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, parent_dir)

from sop_loader import load_sop, DEFAULT_MONGO_URI, DEFAULT_DATABASE_NAME
from sop_unified_executor import SOPExecutor

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Default camera index
DEFAULT_CAMERA_INDEX = 0

# Default model path
DEFAULT_MODEL_PATH = os.path.join(BASE_DIR, "yolov8n.pt")

# SOP directory mapping
SOP_DIRECTORIES = {
    "EZA_SOP_PHONE_ASSEMBLY": "phone_assembly",
    "EZA_SOP_POSE": "pose_detection",  # Pose SOP files are in pose_detection
    "EZA_SOP_ABB": "abbjsons",
    "EZA_SOP_MOTORCYCLE": "ABB/bike_dection",
    "EZA_SOP_GENDER": "gender_detection"
}

def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generic SOP test script with camera",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test phone assembly
  python test_sop_camera.py --sop-id EZA_SOP_PHONE_ASSEMBLY
  
  # Test pose SOP
  python test_sop_camera.py --sop-id EZA_SOP_POSE --use-pose
  
  # Test gender detection SOP
  python test_sop_camera.py --sop-id EZA_SOP_GENDER --use-gender
  
  # Custom directory
  python test_sop_camera.py --sop-dir phone_assembly
  
  # Custom camera
  python test_sop_camera.py --sop-id EZA_SOP_PHONE_ASSEMBLY --camera 1
        """
    )
    
    parser.add_argument(
        "--sop-id",
        type=str,
        help="SOP ID (e.g., EZA_SOP_PHONE_ASSEMBLY, EZA_SOP_POSE)"
    )
    
    parser.add_argument(
        "--sop-dir",
        type=str,
        help="Directory containing SOP files (overrides sop-id mapping)"
    )
    
    parser.add_argument(
        "--use-pose",
        action="store_true",
        help="Use pose detection instead of YOLO object detection"
    )
    
    parser.add_argument(
        "--use-gender",
        action="store_true",
        help="Use gender detection instead of YOLO object detection"
    )
    
    parser.add_argument(
        "--camera",
        type=int,
        default=DEFAULT_CAMERA_INDEX,
        help=f"Camera index (default: {DEFAULT_CAMERA_INDEX})"
    )
    
    parser.add_argument(
        "--model-path",
        type=str,
        default=DEFAULT_MODEL_PATH,
        help=f"Path to YOLO model (default: {DEFAULT_MODEL_PATH})"
    )
    
    parser.add_argument(
        "--source-id",
        type=str,
        help="Source ID for tracking (default: auto-generated from SOP ID)"
    )
    
    return parser.parse_args()

def find_sop_directory(sop_id=None, sop_dir=None):
    """Find the directory containing SOP files."""
    if sop_dir:
        return sop_dir
    
    if sop_id and sop_id in SOP_DIRECTORIES:
        return SOP_DIRECTORIES[sop_id]
    
    # Try common directories
    common_dirs = ["phone_assembly", "gender_detection", "pose_detection", "abbjsons", "ABB/bike_dection"]
    for dir_name in common_dirs:
        dir_path = os.path.join(BASE_DIR, dir_name)
        if os.path.exists(dir_path):
            # Check for various SOP master file names
            possible_masters = [
                "sop_master.json",
                "pose_sop_master.json",
                "abb_sop_master.json",
                "gender_sop_master.json"
            ]
            for master_file in possible_masters:
                sop_master_path = os.path.join(dir_path, master_file)
                if os.path.exists(sop_master_path):
                    return dir_name
    
    return None

def find_sop_files(sop_dir):
    """Find SOP JSON files in the directory."""
    base_path = os.path.join(BASE_DIR, sop_dir)
    
    # Try different file naming conventions
    file_patterns = [
        ("sop_master.json", "sop_activity_rule_mapper.json", "sop_rule_master.json"),
        ("sop_master.json", "sop_activity_rule_map.json", "sop_rule_master.json"),
        ("pose_sop_master.json", "pose_activity_rule_map.json", "pose_central_rules.json"),
        ("abb_sop_master.json", "abb_activity_rule_map.json", "abb_central_rules.json"),
        ("gender_sop_master.json", "gender_activity_rule_map.json", "gender_central_rules.json"),
    ]
    
    for master_name, rule_map_name, rule_master_name in file_patterns:
        master_path = os.path.join(base_path, master_name)
        rule_map_path = os.path.join(base_path, rule_map_name)
        rule_master_path = os.path.join(base_path, rule_master_name)
        
        if os.path.exists(master_path) and os.path.exists(rule_map_path):
            return master_path, rule_map_path, rule_master_path if os.path.exists(rule_master_path) else None
    
    return None, None, None

def load_detection_model(model_path):
    """Load YOLO detection model."""
    try:
        from ultralytics import YOLO
        model = YOLO(model_path)
        print(f"[Model] Loaded: {model_path}")
        return model
    except Exception as e:
        print(f"[Model] Error loading: {e}")
        return None

def load_pose_model():
    """Load MediaPipe pose model."""
    try:
        import mediapipe as mp
        pose = mp.solutions.pose
        model = pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            smooth_landmarks=True,
            enable_segmentation=False,
            min_detection_confidence=0.4,
            min_tracking_confidence=0.2
        )
        print(f"[Model] Loaded: MediaPipe Pose")
        return model
    except Exception as e:
        print(f"[Model] Error loading pose model: {e}")
        return None

def load_gender_model():
    """Load gender detection model (ProcessFrame)."""
    try:
        from model.gender_model import ProcessFrame
        model = ProcessFrame()
        print(f"[Model] Loaded: Gender Detection (ProcessFrame)")
        return model
    except Exception as e:
        print(f"[Model] Error loading gender model: {e}")
        import traceback
        traceback.print_exc()
        return None

def process_gender_detection(gender_model, frame):
    """Process frame with gender detection and return detections and things_present.
    Matches the logic from model/gender_model.py processFrame().
    """
    try:
        detections = {}
        things_present = []
        
        # Process frame using gender model
        frame, gender_data, xyxy = gender_model.processFrame(
            frame, 
            gender_model.ageGenderModel, 
            gender_model.emotionModel
        )
        
        # Convert xyxy to detections format
        if xyxy and len(xyxy) > 0:
            # Ensure all boxes are in correct format [x1, y1, x2, y2]
            face_boxes = []
            for box in xyxy:
                if isinstance(box, list) and len(box) == 4:
                    face_boxes.append([float(box[0]), float(box[1]), float(box[2]), float(box[3])])
            detections["Face"] = face_boxes
        
        # things_present contains gender data strings like "Male\nAge: (23-30)\nhappy"
        things_present = gender_data if gender_data else []
        
        return detections, things_present, frame
    except Exception as e:
        print(f"[Gender] Error processing: {e}")
        import traceback
        traceback.print_exc()
        return {}, [], frame

def process_pose_detection(pose_model, frame):
    """Process frame with pose detection and return things_present.
    Matches the logic from model/pose_model.py detect_raised_hands().
    """
    try:
        import mediapipe as mp
        pose_landmarks = mp.solutions.pose.PoseLandmark
        
        results = pose_model.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        
        things_present = []
        detections = {}
        
        if results.pose_landmarks:
            things_present.append("personPresent")
            
            # Extract bounding box from landmarks
            landmarks = results.pose_landmarks.landmark
            h, w = frame.shape[:2]
            x_coords = [lm.x * w for lm in landmarks]
            y_coords = [lm.y * h for lm in landmarks]
            
            if x_coords and y_coords:
                x1, x2 = min(x_coords), max(x_coords)
                y1, y2 = min(y_coords), max(y_coords)
                detections["Person"] = [[x1, y1, x2, y2]]
            
            # Detect hand positions using same logic as pose_model.py
            if landmarks:
                # Get key points using MediaPipe PoseLandmark indices
                height, width, _ = frame.shape
                
                # Left side indices
                left_wrist_idx = pose_landmarks.LEFT_WRIST.value
                left_elbow_idx = pose_landmarks.LEFT_ELBOW.value
                left_shoulder_idx = pose_landmarks.LEFT_SHOULDER.value
                
                # Right side indices
                right_wrist_idx = pose_landmarks.RIGHT_WRIST.value
                right_elbow_idx = pose_landmarks.RIGHT_ELBOW.value
                right_shoulder_idx = pose_landmarks.RIGHT_SHOULDER.value
                
                # Get Y coordinates (in pixels) - MediaPipe landmarks are normalized [0,1]
                left_wrist_y = landmarks[left_wrist_idx].y * height
                right_wrist_y = landmarks[right_wrist_idx].y * height
                left_shoulder_y = landmarks[left_shoulder_idx].y * height
                right_shoulder_y = landmarks[right_shoulder_idx].y * height
                left_elbow_y = landmarks[left_elbow_idx].y * height
                right_elbow_y = landmarks[right_elbow_idx].y * height
                
                # Detect hand status (matching pose_model.py detect_raised_hands logic exactly)
                # Note: The original logic checks left, then right, then both (last one wins)
                hand_status = None
                
                # Check left hand
                if left_wrist_y < left_shoulder_y:
                    hand_status = "leftHandAbove90" if left_elbow_y < left_shoulder_y else "leftHandBelow90"
                
                # Check right hand (may overwrite left)
                if right_wrist_y < right_shoulder_y:
                    hand_status = "rightHandAbove90" if right_elbow_y < right_shoulder_y else "rightHandBelow90"
                
                # Check both hands (overwrites individual hand status)
                if left_wrist_y < left_shoulder_y and right_wrist_y < right_shoulder_y:
                    hand_status = "bothHandsAbove90" if (left_elbow_y < left_shoulder_y and right_elbow_y < right_shoulder_y) else "bothHandsBelow90"
                
                # Add hand status if detected
                if hand_status:
                    things_present.append(hand_status)
                
                # Also check for hands down (separate detection)
                if left_wrist_y > left_shoulder_y:
                    things_present.append("leftHandDown")
                if right_wrist_y > right_shoulder_y:
                    things_present.append("rightHandDown")
        
        return detections, things_present, results
    except Exception as e:
        print(f"[Pose] Error processing: {e}")
        import traceback
        traceback.print_exc()
        return {}, [], None

def process_yolo_detections(results):
    """Convert YOLO results to detection dict."""
    detections = {}
    
    for result in results:
        if result.boxes is None:
            continue
            
        boxes = result.boxes.xyxy.cpu().numpy()
        classes = result.boxes.cls.cpu().numpy().astype(int)
        names = result.names
        
        for i, (box, cls) in enumerate(zip(boxes, classes)):
            class_name = names[cls]
            if class_name not in detections:
                detections[class_name] = []
            detections[class_name].append(box.tolist())
    
    return detections

def load_sop_from_local_files(sop_dir):
    """Load SOP data from local JSON files."""
    master_path, rule_map_path, rule_master_path = find_sop_files(sop_dir)
    
    if not master_path or not rule_map_path:
        print(f"[Error] Could not find SOP files in directory: {sop_dir}")
        return None
    
    try:
        # Load sop_master
        with open(master_path, 'r') as f:
            sop_master = json.load(f)
        
        # Handle array format (some SOPs are stored as arrays)
        if isinstance(sop_master, list) and len(sop_master) > 0:
            sop_master = sop_master[0]
        
        # Remove MongoDB _id field if present
        if "_id" in sop_master:
            sop_master.pop("_id")
        
        # Normalize type field
        if "sopType" in sop_master and "type" not in sop_master:
            sop_master["type"] = sop_master.pop("sopType")
        
        # Filter activities
        if "activities" in sop_master:
            filtered_activities = []
            for activity in sop_master["activities"]:
                filtered_activity = {
                    "activityId": activity.get("activityId") or activity.get("activity_id"),
                    "prevAct": activity.get("prevAct", []) or activity.get("prev_act", []),
                    "nextAct": activity.get("nextAct", []) or activity.get("next_act", []),
                    "model_class": activity.get("model_class", []),
                    "model_id": activity.get("model_id"),
                    "function": activity.get("function"),
                    "expectedTime": activity.get("expectedTime") or activity.get("expected_time")
                }
                filtered_activities.append(filtered_activity)
            sop_master["activities"] = filtered_activities
        
        # Load sop_activity_rule_map
        with open(rule_map_path, 'r') as f:
            rule_map = json.load(f)
        
        # Handle array format
        if isinstance(rule_map, list) and len(rule_map) > 0:
            rule_map = rule_map[0]
        
        # Remove MongoDB _id field if present
        if "_id" in rule_map:
            rule_map.pop("_id")
        
        # Load sop_rule_master (optional)
        sop_rules = []
        if rule_master_path and os.path.exists(rule_master_path):
            with open(rule_master_path, 'r') as f:
                sop_rules = json.load(f)
        
        # Filter rules
        filtered_rules = []
        for rule in sop_rules:
            if isinstance(rule, dict):
                filtered_rule = {
                    "rule_name": rule.get("rule_name"),
                    "desc": rule.get("desc", ""),
                    "input": rule.get("input", []),
                    "output": rule.get("output", [])
                }
                filtered_rules.append(filtered_rule)
        sop_rules = filtered_rules
        
        # Build data structure
        data = {
            "sop_master": sop_master,
            "sop_activity_rule_map": rule_map,
            "sop_rules": sop_rules
        }
        
        # Validate structure
        from sop_loader import validate_structure
        data["validation"] = validate_structure(data)
        
        sop_id = sop_master.get("sopId") or sop_master.get("sop_id", "unknown")
        print(f"[load_sop_from_local] Loaded: {sop_id} ({len(sop_rules)} rules)")
        
        return data
        
    except Exception as e:
        print(f"[load_sop_from_local] Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_instruction_map(sop_id):
    """Get instruction map for different SOPs."""
    if "PHONE_ASSEMBLY" in sop_id:
        return {
            "PHONE_BODY_PRESENT": "Step 1: Show the phone body",
            "SCREEN_ATTACHED": "Step 2: Show the display/screen",
            "COMPONENTS_PLACED": "Step 3: Show the flash/camera",
            "ASSEMBLY_COMPLETE": "Step 4: Show complete phone"
        }
    elif "POSE" in sop_id:
        return {
            "PERSON_PRESENT": "Step 1: Please stand in front of camera",
            "HAND_RAISED": "Step 2: Please raise your right hand",
            "HANDS_DOWN": "Step 3: Please lower your hands"
        }
    elif "GENDER" in sop_id:
        return {
            "FACE_DETECTED": "Step 1: Face detected - looking for gender",
            "GENDER_IDENTIFIED": "Step 2: Gender identified successfully!"
        }
    else:
        # Generic fallback
        return {}

def draw_detections(frame, detections, triggered_activities=None, pose_results=None):
    """Draw bounding boxes and labels on frame."""
    # Color map for different classes
    colors = {
        'cell phone': (0, 255, 0),
        'person': (0, 0, 255),
        'Person': (0, 0, 255),
        'Face': (0, 255, 255),  # Cyan for face detection
    }
    
    # Draw YOLO bounding boxes
    for class_name, boxes in detections.items():
        color = colors.get(class_name, (255, 255, 255))
        for box in boxes:
            x1, y1, x2, y2 = map(int, box)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            label = f"{class_name}"
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            label_y = max(y1, label_size[1] + 10)
            cv2.rectangle(frame, (x1, label_y - label_size[1] - 10), 
                         (x1 + label_size[0], label_y), color, -1)
            cv2.putText(frame, label, (x1, label_y - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
    
    # Draw pose landmarks if available
    if pose_results and pose_results.pose_landmarks:
        import mediapipe as mp
        mp_drawing = mp.solutions.drawing_utils
        mp_drawing.draw_landmarks(
            frame, pose_results.pose_landmarks, mp.solutions.pose.POSE_CONNECTIONS
        )
    
    # Draw activity status
    if triggered_activities:
        activity_text = f"Activities: {', '.join(triggered_activities)}"
        cv2.putText(frame, activity_text, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    
    return frame

def main():
    args = parse_arguments()
    
    # Determine SOP directory
    sop_dir = find_sop_directory(args.sop_id, args.sop_dir)
    if not sop_dir:
        print("[Error] Could not find SOP directory. Please specify --sop-id or --sop-dir")
        return
    
    print("=" * 60)
    print("Generic SOP Test with Camera")
    print("=" * 60)
    print(f"SOP Directory: {sop_dir}")
    if args.sop_id:
        print(f"SOP ID: {args.sop_id}")
    detection_type = "Gender" if args.use_gender else ("Pose" if args.use_pose else "YOLO")
    print(f"Detection Type: {detection_type}")
    print("=" * 60)
    
    # Change to parent directory
    os.chdir(parent_dir)
    
    # Load SOP configurations
    print("\n[1] Loading SOP from local files...")
    sop_data = load_sop_from_local_files(sop_dir)
    
    if not sop_data:
        print("Failed to load SOP data!")
        return
    
    # Check validation
    validation = sop_data.get("validation", {})
    if not validation.get("valid", False):
        print(f"    ⚠️  Validation errors:")
        for error in validation.get("errors", []):
            print(f"      - {error}")
    else:
        print("    ✓ Validation passed")
    
    sop_type = sop_data.get("sop_master", {}).get("type", "unknown")
    sop_id = sop_data.get("sop_master", {}).get("sopId") or sop_data.get("sop_master", {}).get("sop_id", "unknown")
    print(f"    SOP: {sop_id} | Type: {sop_type}")
    
    # Create SOPExecutor
    print("\n[2] Creating SOPExecutor (unified)...")
    executor = SOPExecutor(sop_data, additional_predefined={})
    print(f"    Executor type: {executor.sop_type}")
    
    # Configure MongoDB
    try:
        if hasattr(executor.executor, '_cycle_executor'):
            executor.executor._cycle_executor.set_mongo_config(
                uri=DEFAULT_MONGO_URI,
                db_name=DEFAULT_DATABASE_NAME,
                collection_name="derived_analytics"
            )
            print("    MongoDB configured for analytics")
    except Exception as e:
        print(f"    MongoDB config skipped: {e}")
    
    # Open camera
    print(f"\n[3] Opening camera (index {args.camera})...")
    cap = cv2.VideoCapture(args.camera)
    
    if not cap.isOpened():
        print(f"Failed to open camera at index {args.camera}")
        return
    
    # Set camera properties
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)
    
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    print(f"    Resolution: {width}x{height} | FPS: {fps}")
    print("    Camera opened successfully!")
    
    # Load detection model
    print(f"\n[4] Loading {detection_type.lower()} model...")
    if args.use_gender:
        model = load_gender_model()
    elif args.use_pose:
        model = load_pose_model()
    else:
        model = load_detection_model(args.model_path)
    
    if not model:
        print("Failed to load model")
        cap.release()
        return
    
    # Generate source ID
    source_id = args.source_id or f"{sop_id.lower().replace('_', '_')}_camera_test"
    
    # Process video
    print(f"\n[5] Processing live camera feed...")
    print("    Press Q to quit")
    start_time = time.time()
    frame_count = 0
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                continue
            
            if frame is None or frame.size == 0:
                continue
            
            frame_number = frame_count + 1
            timestamp = datetime.now().isoformat()
            
            # Run detection
            if args.use_gender:
                detections, things_present, processed_frame = process_gender_detection(model, frame)
                detected_classes = list(detections.keys())
                pose_results = None
                # Use processed frame (with annotations) for display
                frame = processed_frame
            elif args.use_pose:
                detections, things_present, pose_results = process_pose_detection(model, frame)
                detected_classes = list(detections.keys())
            else:
                results = model(frame, verbose=False)
                detections = process_yolo_detections(results)
                detected_classes = list(detections.keys())
                things_present = detected_classes
                pose_results = None
            
            if frame_count == 0:
                if args.use_gender or args.use_pose:
                    print(f"    [Frame {frame_number}] First frame processed | Things Present: {things_present}")
                else:
                    print(f"    [Frame {frame_number}] First frame processed | Detections: {detected_classes}")
            
            # Prepare input data
            input_data = {
                "frame": frame,
                "frame_id": frame_number,
                "frame_number": frame_number,
                "timestamp": timestamp,
                "source_id": source_id,
                "detections": detections,
                "detected_classes": detected_classes
            }
            
            # Add detection-specific data
            if args.use_gender:
                # For gender detection, things_present contains gender data strings
                input_data["things_present"] = things_present
                input_data["additional_data"] = {
                    "things_present": things_present,
                    "face_boxes": [detections.get("Face", [])]
                }
            elif args.use_pose:
                # For pose detection, things_present is critical
                input_data["things_present"] = things_present
                input_data["additional_data"] = {
                    "things_present": things_present,
                    "pose_landmarks": pose_results
                }
            else:
                # For YOLO, things_present is same as detected_classes
                input_data["things_present"] = detected_classes
            
            # Execute SOP
            executor.set_input_data(input_data)
            result = executor.execute_all()
            
            # Get triggered activities
            triggered_activities = []
            if hasattr(result, 'activity_results'):
                triggered_activities = [
                    act_id for act_id, act_result in result.activity_results.items()
                    if act_result.triggered
                ]
            elif hasattr(result, 'current_activity') and result.current_activity:
                triggered_activities = [result.current_activity]
            
            # Draw on frame
            display_frame = draw_detections(frame.copy(), detections, triggered_activities, pose_results)
            
            # Add info text
            if args.use_gender or args.use_pose:
                things_text = ", ".join(things_present[:2]) if things_present else "None"  # Show first 2 items
                if len(things_present) > 2:
                    things_text += f" (+{len(things_present)-2} more)"
                info_text = f"Frame: {frame_number} | Things: {things_text}"
            else:
                info_text = f"Frame: {frame_number} | Detections: {len(detected_classes)}"
            cv2.putText(display_frame, info_text, (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            if hasattr(result, 'current_activity') and result.current_activity:
                activity_text = f"Activity: {result.current_activity}"
                cv2.putText(display_frame, activity_text, (10, 90), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            
            if hasattr(result, 'cycle_count') and result.cycle_count > 0:
                cycle_text = f"Cycle: {result.cycle_count}"
                cv2.putText(display_frame, cycle_text, (10, 120), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            
            # Add instruction text based on current activity and SOP type
            if hasattr(result, 'current_activity') and result.current_activity:
                instruction_map = get_instruction_map(sop_id)
                instruction = instruction_map.get(result.current_activity, "")
                if instruction:
                    cv2.putText(display_frame, instruction, (10, 150), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Show frame
            window_title = f"{sop_id} - Press Q to quit"
            cv2.imshow(window_title, display_frame)
            
            executor.reset()
            frame_count += 1
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("\n    [User] Quit requested")
                break
            
            # Print progress
            if frame_count % 30 == 0:
                activity = result.current_activity if hasattr(result, 'current_activity') else "N/A"
                cycle_count = result.cycle_count if hasattr(result, 'cycle_count') else 0
                if args.use_gender or args.use_pose:
                    things_str = ", ".join(things_present[:2]) if things_present else "None"
                    if len(things_present) > 2:
                        things_str += f" (+{len(things_present)-2} more)"
                    print(f"    [Frame {frame_number}] Activity: {activity} | Cycle: {cycle_count} | Things: {things_str}")
                else:
                    print(f"    [Frame {frame_number}] Activity: {activity} | Cycle: {cycle_count} | Detections: {detected_classes}")
    
    except KeyboardInterrupt:
        print("\n\n[Interrupted] Stopping...")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("    Camera released")
    
    # Shutdown
    print("\n[6] Shutting down...")
    executor.shutdown(source_id)
    
    end_time = time.time()
    processing_time = end_time - start_time
    fps_actual = frame_count / processing_time if processing_time > 0 else 0
    
    print(f"\n" + "=" * 60)
    print(f"RESULTS")
    print("=" * 60)
    print(f"Processing time: {processing_time:.2f}s ({fps_actual:.1f} FPS)")
    print(f"Total frames: {frame_count}")
    
    # Print analytics
    try:
        analytics = executor.get_analytics_data(source_id)
        if analytics:
            kpi = analytics.get("resultData", {}).get("kpi", {})
            print(f"\n=== KPI DATA ===")
            print(json.dumps(kpi, indent=2))
    except Exception as e:
        print(f"\n[Note] Analytics not available: {e}")
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)

if __name__ == "__main__":
    main()
