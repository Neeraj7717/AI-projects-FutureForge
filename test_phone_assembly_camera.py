"""
Test script for Phone Assembly SOP using laptop camera.
Uses the unified interface: set_input_data() + execute_all()
"""
import json
import os
import sys
import cv2
import time
import warnings
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

# Use laptop camera (0 is usually the default camera)
CAMERA_INDEX = 0

# Model path - using yolov8n.pt from root directory
MODEL_PATH = os.path.join(BASE_DIR, "yolov8n.pt")
SOURCE_ID = "phone_assembly_camera_test"

# Phone assembly SOP file paths
PHONE_ASSEMBLY_DIR = os.path.join(BASE_DIR, "phone_assembly")
SOP_MASTER_PATH = os.path.join(PHONE_ASSEMBLY_DIR, "sop_master.json")
SOP_ACTIVITY_RULE_MAP_PATH = os.path.join(PHONE_ASSEMBLY_DIR, "sop_activity_rule_mapper.json")
SOP_RULE_MASTER_PATH = os.path.join(PHONE_ASSEMBLY_DIR, "sop_rule_master.json")

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

def load_sop_from_local_files():
    """Load SOP data from local JSON files in phone_assembly directory."""
    try:
        # Load sop_master
        with open(SOP_MASTER_PATH, 'r') as f:
            sop_master = json.load(f)
        
        # Remove MongoDB _id field if present
        if "_id" in sop_master:
            sop_master.pop("_id")
        
        # Normalize type field (sopType -> type)
        if "sopType" in sop_master and "type" not in sop_master:
            sop_master["type"] = sop_master.pop("sopType")
        
        # Filter activities to only include fields expected by Activity dataclass
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
        with open(SOP_ACTIVITY_RULE_MAP_PATH, 'r') as f:
            rule_map = json.load(f)
        
        # Remove MongoDB _id field if present
        if "_id" in rule_map:
            rule_map.pop("_id")
        
        # Load sop_rule_master (array of rules)
        with open(SOP_RULE_MASTER_PATH, 'r') as f:
            sop_rules = json.load(f)
        
        # Remove _id fields from rules and filter to expected fields
        filtered_rules = []
        for rule in sop_rules:
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
        
        # Validate structure (using sop_loader's validation)
        from sop_loader import validate_structure
        data["validation"] = validate_structure(data)
        
        sop_id = sop_master.get("sopId", "unknown")
        print(f"[load_sop_from_local] Loaded: {sop_id} ({len(sop_rules)} rules)")
        
        return data
        
    except FileNotFoundError as e:
        print(f"[load_sop_from_local] File not found: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"[load_sop_from_local] JSON decode error: {e}")
        return None
    except Exception as e:
        print(f"[load_sop_from_local] Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def process_detections(results):
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
            # Normalize class name (YOLO uses 'cell phone' but we'll use it as-is)
            if class_name not in detections:
                detections[class_name] = []
            detections[class_name].append(box.tolist())
    
    return detections

def draw_detections(frame, detections, triggered_activities=None):
    """Draw bounding boxes and labels on frame."""
    # Color map for different classes
    colors = {
        'cell phone': (0, 255, 0),      # Green
        'phone': (0, 255, 0),           # Green (alternative)
        'person': (0, 0, 255),          # Red
        'hand': (255, 0, 0),            # Blue
        'keyboard': (255, 165, 0),      # Orange
        'mouse': (255, 192, 203),       # Pink
    }
    
    # Draw bounding boxes
    for class_name, boxes in detections.items():
        color = colors.get(class_name, (255, 255, 255))  # White for unknown classes
        
        for box in boxes:
            x1, y1, x2, y2 = map(int, box)
            # Draw rectangle
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            # Draw label
            label = f"{class_name}"
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            label_y = max(y1, label_size[1] + 10)
            cv2.rectangle(frame, (x1, label_y - label_size[1] - 10), 
                         (x1 + label_size[0], label_y), color, -1)
            cv2.putText(frame, label, (x1, label_y - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
    
    # Draw activity status at top of frame
    if triggered_activities:
        activity_text = f"Activities: {', '.join(triggered_activities)}"
        cv2.putText(frame, activity_text, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    
    return frame

def main():
    print("=" * 60)
    print("Testing Phone Assembly SOP with Laptop Camera")
    print("=" * 60)
    
    # Change to parent directory for relative paths
    os.chdir(parent_dir)
    
    # Load SOP configurations from local files
    print("\n[1] Loading Phone Assembly SOP from local files...")
    sop_data = load_sop_from_local_files()
    
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
    sop_id = sop_data.get("sop_master", {}).get("sopId", "unknown")
    print(f"    SOP: {sop_id} | Type: {sop_type}")
    
    # Create SOPExecutor using the unified interface
    print("\n[2] Creating SOPExecutor (unified)...")
    executor = SOPExecutor(sop_data, additional_predefined={})
    print(f"    Executor type: {executor.sop_type}")
    
    # Configure MongoDB for analytics saving (if available)
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
    
    # Open laptop camera
    print(f"\n[3] Opening laptop camera (index {CAMERA_INDEX})...")
    cap = cv2.VideoCapture(CAMERA_INDEX)
    
    if not cap.isOpened():
        print(f"Failed to open camera at index {CAMERA_INDEX}")
        print("    Check if camera is connected and not being used by another application")
        return
    
    # Set camera properties for better performance
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)
    
    # Get camera properties
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0
        print(f"    Using default FPS: {fps}")
    else:
        print(f"    FPS: {fps}")
    
    print(f"    Resolution: {width}x{height}")
    print("    Camera opened successfully!")
    print("    Processing live video... (Press Q to quit)")
    
    # Load detection model
    print("\n[4] Loading detection model...")
    model = load_detection_model(MODEL_PATH)
    if not model:
        print("Failed to load model")
        cap.release()
        return
    
    # Process video
    print(f"\n[5] Processing live camera feed...")
    start_time = time.time()
    frame_count = 0
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("    [Warning] Failed to read frame from camera")
                time.sleep(0.1)
                continue
            
            # Validate frame
            if frame is None or frame.size == 0:
                print("    [Warning] Received empty frame, skipping...")
                continue
            
            frame_number = frame_count + 1
            timestamp = datetime.now().isoformat()
            
            # Run detection
            results = model(frame, verbose=False)
            detections = process_detections(results)
            detected_classes = list(detections.keys())
            
            # Show first frame info
            if frame_count == 0:
                print(f"    [Frame {frame_number}] First frame processed | Detections: {detected_classes}")
            
            # === USE NEW UNIFIED INTERFACE ===
            # set_input_data + execute_all
            executor.set_input_data({
                "frame": frame,
                "frame_id": frame_number,
                "frame_number": frame_number,
                "timestamp": timestamp,
                "source_id": SOURCE_ID,
                "detections": detections,
                "detected_classes": detected_classes
            })
            
            result = executor.execute_all()
            
            # Get triggered activities for display
            triggered_activities = []
            if hasattr(result, 'activity_results'):
                triggered_activities = [
                    act_id for act_id, act_result in result.activity_results.items()
                    if act_result.triggered
                ]
            elif hasattr(result, 'current_activity') and result.current_activity:
                triggered_activities = [result.current_activity]
            
            # Draw detections on frame
            display_frame = draw_detections(frame.copy(), detections, triggered_activities)
            
            # Add frame info text
            info_text = f"Frame: {frame_number} | Detections: {len(detected_classes)}"
            cv2.putText(display_frame, info_text, (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            # Add current activity info
            if hasattr(result, 'current_activity') and result.current_activity:
                activity_text = f"Current Activity: {result.current_activity}"
                cv2.putText(display_frame, activity_text, (10, 90), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            
            # Add cycle info
            if hasattr(result, 'cycle_count') and result.cycle_count > 0:
                cycle_text = f"Cycle: {result.cycle_count} | Active: {'Yes' if hasattr(result, 'cycle_active') and result.cycle_active else 'No'}"
                cv2.putText(display_frame, cycle_text, (10, 120), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            
            # Add instruction text based on current activity
            instruction_map = {
                "PHONE_BODY_PRESENT": "Step 1: Show the phone body",
                "SCREEN_ATTACHED": "Step 2: Show the display/screen",
                "COMPONENTS_PLACED": "Step 3: Show the flash/camera",
                "ASSEMBLY_COMPLETE": "Step 4: Show complete phone"
            }
            if hasattr(result, 'current_activity') and result.current_activity:
                instruction = instruction_map.get(result.current_activity, "")
                if instruction:
                    cv2.putText(display_frame, instruction, (10, 150), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Show frame in window
            cv2.imshow('Phone Assembly SOP - Press Q to quit', display_frame)
            
            # Debug: Print activity results for first few frames with detections
            if frame_count < 5 and detected_classes:
                print(f"\n[DEBUG Frame {frame_number}] Detected: {detected_classes}")
                if hasattr(result, 'activity_results'):
                    for act_id, act_result in result.activity_results.items():
                        print(f"  Activity {act_id}: triggered={act_result.triggered}, success={act_result.success}")
                elif hasattr(result, 'current_activity'):
                    print(f"  Current Activity: {result.current_activity}")
            
            # Reset for next frame
            executor.reset()
            
            frame_count += 1
            
            # Check for 'q' key press to quit
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("\n    [User] Quit requested (Q key pressed)")
                break
            
            # Print progress every 30 frames
            if frame_count % 30 == 0:
                if hasattr(result, 'activity_results'):
                    triggered_activities = [
                        act_id for act_id, act_result in result.activity_results.items()
                        if act_result.triggered
                    ]
                    activity_str = ", ".join(triggered_activities) if triggered_activities else "None"
                    executed = result.activities_executed if hasattr(result, 'activities_executed') else 0
                    skipped = result.activities_skipped if hasattr(result, 'activities_skipped') else 0
                    print(f"    [Frame {frame_number}] Activities: {activity_str} | Executed: {executed} | Skipped: {skipped} | Detections: {detected_classes}")
                else:
                    activity = result.current_activity if hasattr(result, 'current_activity') else "N/A"
                    cycle_count = result.cycle_count if hasattr(result, 'cycle_count') else 0
                    print(f"    [Frame {frame_number}] Activity: {activity} | Cycle: {cycle_count} | Detections: {detected_classes}")
    
    except KeyboardInterrupt:
        print("\n\n[Interrupted] Stopping video processing...")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("    Camera released")
    
    # Shutdown
    print("\n[6] Shutting down...")
    executor.shutdown(SOURCE_ID)
    
    end_time = time.time()
    processing_time = end_time - start_time
    fps_actual = frame_count / processing_time if processing_time > 0 else 0
    
    print(f"\n" + "=" * 60)
    print(f"RESULTS")
    print("=" * 60)
    print(f"Processing time: {processing_time:.2f}s ({fps_actual:.1f} FPS)")
    print(f"Total frames processed: {frame_count}")
    
    # Get completed cycles (for cycle-based SOPs)
    try:
        completed_cycles = executor.get_completed_cycles(SOURCE_ID)
        if completed_cycles:
            print(f"\nCompleted Cycles: {len(completed_cycles)}")
            for cycle in completed_cycles:
                print(f"  Cycle {cycle['cycle_number']}: {cycle['status']}")
    except:
        print("\n[Note] Cycle tracking not available")
    
    # Print KPI data
    try:
        analytics = executor.get_analytics_data(SOURCE_ID)
        if analytics:
            kpi = analytics.get("resultData", {}).get("kpi", {})
            print(f"\n=== KPI DATA ===")
            print(json.dumps(kpi, indent=2))
            
            # Print cycle summary (for cycle-based SOPs)
            cycles = analytics.get("resultData", {}).get("cycles", [])
            if cycles:
                print(f"\n=== CYCLES ({len(cycles)}) ===")
                for c in cycles:
                    status = "SUCCESS" if c.get("completed") else "ANOMALY"
                    print(f"  Cycle {c['cycle_number']}: {status} | Frames {c['start_frame']}-{c['end_frame']} | {c['actual_time_sec']:.2f}s")
    except Exception as e:
        print(f"\n[Note] Analytics not available: {e}")
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)

if __name__ == "__main__":
    main()
