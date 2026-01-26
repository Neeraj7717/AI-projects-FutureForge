"""
ABB Rule Functions - Spatial logic functions for robotic pick and place

Each function takes bounding boxes (or lists of boxes) and returns a decision dict.
If lists of boxes are provided (multiple objects of same class), it checks if ANY combination satisfies the rule.
"""
from typing import List, Optional, Dict, Any


def _ensure_list_of_boxes(bbox_input: Any) -> List[List[float]]:
    """
    Normalize input to a list of bounding boxes.
    
    Args:
        bbox_input: Can be None, single box [x,y,x,y], or list of boxes [[x,y,x,y], ...]
    
    Returns:
        List of [x,y,x,y] lists. Returns [] if input is None/Empty.
    """
    if bbox_input is None:
        return []
    
    # Case: Empty list
    if isinstance(bbox_input, list) and len(bbox_input) == 0:
        return []

    # Case: List of lists (Standard YOLO output for multiple detections)
    # Check first element to see if it's a list
    if isinstance(bbox_input, list) and len(bbox_input) > 0 and isinstance(bbox_input[0], list):
        return bbox_input
    
    # Case: Single box [x1, y1, x2, y2]
    # Check if elements are numbers
    if isinstance(bbox_input, list) and len(bbox_input) == 4 and all(isinstance(x, (int, float)) for x in bbox_input):
        return [bbox_input]
    
    return []


def _get_reference_point(bbox: List[float]) -> tuple:
    """
    Internal helper for single box reference point.
    Matches legacy processor.py behavior: Bottom-Right Corner (x2, y2).
    Legacy code used: point = (int(p_box[2]), int(p_box[3]))
    """
    x1, y1, x2, y2 = bbox
    return (x2, y2)


def _calculate_iou_single(box1: List[float], box2: List[float]) -> float:
    """Internal helper for single box IOU."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    
    if x2 < x1 or y2 < y1:
        return 0.0
    
    intersection = (x2 - x1) * (y2 - y1)
    
    # Processor.py calculates Intersection / Area of Box A (Overlap Ratio)
    # NOT Standard IoU (Intersection / Union)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    
    return intersection / area1 if area1 > 0 else 0.0


# =============================================================================
# EXPORTED RULE FUNCTIONS
# =============================================================================

def get_center(bbox: Any) -> Optional[tuple]:
    """
    Get reference point. If multiple boxes, returns point of FIRST box.
    NOTE: Renamed behavior to match rule logic (Bottom-Right), but keeping name 'get_center' 
    for compatibility if called externally, though usually only internal rules call it.
    Actually, to be safe, let's keep get_center as CENTER for external callers, 
    but use _get_reference_point for is_point_inside_box.
    """
    boxes = _ensure_list_of_boxes(bbox)
    if not boxes:
        return None
    # Default get_center still returns actual center for other uses?
    # But if the user expects "get_center" to return the point used for checks...
    # Let's stick to strict legacy replication for the RULE.
    x1, y1, x2, y2 = boxes[0]
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def calculate_iou(box1: Any, box2: Any) -> float:
    """Calculate Max IOU between any box in list1 and any box in list2."""
    boxes1 = _ensure_list_of_boxes(box1)
    boxes2 = _ensure_list_of_boxes(box2)
    
    max_iou = 0.0
    for b1 in boxes1:
        for b2 in boxes2:
            iou = _calculate_iou_single(b1, b2)
            if iou > max_iou:
                max_iou = iou
    return max_iou


def is_point_inside_box(primary_box: Any, secondary_box: Any) -> Dict[str, Any]:
    """
    Check if the REFERENCE POINT (Bottom-Right) of ANY primary box is inside ANY secondary box.
    """
    primary_list = _ensure_list_of_boxes(primary_box)
    secondary_list = _ensure_list_of_boxes(secondary_box)

    if not primary_list or not secondary_list:
        return {"decision": False, "center": None, "inside": False}
    
    passed = False
    last_point = None
    
    for p_box in primary_list:
        # Use Bottom-Right corner (Legacy Behavior from processor.py)
        point = _get_reference_point(p_box)
        px, py = point
        
        for s_box in secondary_list:
            x1, y1, x2, y2 = s_box
            if x1 <= px <= x2 and y1 <= py <= y2:
                passed = True
                last_point = point
                break # Found a match for this p_box
        
        if passed:
            break # At least one primary box is inside a zone
    
    return {"decision": passed, "center": last_point, "inside": passed}


def is_not_carrying_item(primary_box: Any, 
                         secondary_box: Any, 
                         threshold: float = 0.1) -> Dict[str, Any]:
    """
    Check if gripper is NOT carrying item.
    PASS if:
    1. No primary box (Gripper) detected.
    2. No secondary box (Item) detected.
    3. Max IOU between any Gripper and any Item is < threshold.
    """
    primary_list = _ensure_list_of_boxes(primary_box)
    secondary_list = _ensure_list_of_boxes(secondary_box)
    
    # Condition 1: No gripper detected -> Not carrying
    if not primary_list:
        return {"decision": False, "iou": 0.0, "not_carrying": True}
    
    # Condition 2: No item detected -> Not carrying
    if not secondary_list:
        return {"decision": True, "iou": 0.0, "not_carrying": True}
    
    # Condition 3: Check IOU
    max_iou = 0.0
    for p in primary_list:
        for s in secondary_list:
            iou = _calculate_iou_single(p, s)
            if iou > max_iou:
                max_iou = iou
    
    not_carrying = max_iou < threshold
    return {"decision": not_carrying, "iou": max_iou, "not_carrying": not_carrying}


def is_carrying_item(primary_box: Any, 
                     secondary_box: Any, 
                     threshold: float = 0.1) -> Dict[str, Any]:
    """
    Check if gripper IS carrying item.
    PASS if ANY Gripper has IOU >= threshold with ANY Item.
    """
    primary_list = _ensure_list_of_boxes(primary_box)
    secondary_list = _ensure_list_of_boxes(secondary_box)
    
    if not primary_list or not secondary_list:
        return {"decision": False, "iou": 0.0, "carrying": False}
    
    max_iou = 0.0
    carrying = False
    
    for p in primary_list:
        for s in secondary_list:
            iou = _calculate_iou_single(p, s)
            if iou > max_iou:
                max_iou = iou
            if iou >= threshold:
                carrying = True
                # Optimization: Could break here, but let's find max_iou for reporting
    
    return {"decision": carrying, "iou": max_iou, "carrying": carrying}


def is_box_outside_box(primary_box: Any, 
                       secondary_box: Any, 
                       threshold: float = 0.1) -> Dict[str, Any]:
    """
    Check if box is outside another.
    PASS if Max IOU < threshold.
    """
    # Simply reuse logic: if "carrying" (high overlap) is false, then "outside" is true.
    # Note: is_carrying logic returns True if Any overlap > threshold
    # So we can calculate Max IOU manually.
    
    primary_list = _ensure_list_of_boxes(primary_box)
    secondary_list = _ensure_list_of_boxes(secondary_box)
    
    if not primary_list or not secondary_list:
        return {"decision": False, "iou": 0.0, "outside": False}

    max_iou = 0.0
    for p in primary_list:
        for s in secondary_list:
            iou = _calculate_iou_single(p, s)
            if iou > max_iou:
                max_iou = iou
                
    outside = max_iou < threshold
    return {"decision": outside, "iou": max_iou, "outside": outside}


def is_double_pick(primary_box: Any, 
                   secondary_box: Any, 
                   threshold: int = 7,
                   **kwargs) -> Dict[str, Any]:
    """Placeholder for double pick."""
    primary_list = _ensure_list_of_boxes(primary_box)
    secondary_list = _ensure_list_of_boxes(secondary_box)
    iou_thresh = kwargs.get("iou_threshold", 0.2)
    
    if not primary_list or not secondary_list:
        return {"decision": False, "detected": False}
    
    # Check overlaps with first gripper (Primary[0])
    gripper = primary_list[0]
    count = 0
    
    for item in secondary_list:
        # Processor.py checks: calculate_iou(item, gripper)
        # i.e. Intersection / Area(Item)
        iou = _calculate_iou_single(item, gripper)
        if iou > iou_thresh:
            count += 1
    
    decision = count > 1
    if decision:
        print(f"  [DEBUG-DOUBLE-PICK] Items overlapping gripper: {count} (threshold: >1, iou_thresh: {iou_thresh})")
    return {"decision": decision, "count": count, "threshold": threshold}


def is_item_misplaced_by_iou(primary_box: Any, 
                              secondary_box: Any, 
                              threshold: int = 10,
                              iou_threshold: float = 0.8,
                              confirm_frames: int = 5,
                              **kwargs) -> Dict[str, Any]:
    """
    Check if item is misplaced (not properly inside ANY zone).
    
    PASS (True) if MAX IOU with ALL zones < threshold (i.e., NOT in any zone).
    
    Supports multiple zones via:
    - secondary_box: Primary zone to check
    - zone_box_2, zone_box_3, etc in kwargs: Additional zones
    
    Uses MAX IoU across all zones, matching processor.py behavior.
    """
    primary_list = _ensure_list_of_boxes(primary_box)
    
    # Combine all zone boxes from secondary_box and any zone_box_N in kwargs
    all_zone_boxes = _ensure_list_of_boxes(secondary_box)
    
    # Check for additional zones in kwargs
    for key, value in kwargs.items():
        if key.startswith("zone_box") or key.startswith("secondary_box_"):
            all_zone_boxes.extend(_ensure_list_of_boxes(value))
    
    if not primary_list or not all_zone_boxes:
         return {"decision": False, "iou": 0.0, "misplaced": False}
    
    max_iou = 0.0
    
    # Find BEST overlap with ANY zone (matching processor.py logic)
    for p in primary_list:
        for z in all_zone_boxes:
            iou = _calculate_iou_single(p, z)
            if iou > max_iou:
                max_iou = iou
    
    misplaced = max_iou < iou_threshold
    
    # Debug: Show IoU calculation with ALL zone details
    if primary_list and all_zone_boxes:
        print(f"  [DEBUG-MISPLACED] Items={len(primary_list)} Zones={len(all_zone_boxes)} MaxIoU={max_iou:.3f} -> Misplaced={misplaced}")
    
    return {
        "decision": misplaced, 
        "iou": max_iou, 
        "misplaced": misplaced,
        "iou_threshold": iou_threshold,
        "confirm_frames": confirm_frames
    }


def is_item_correctly_placed_by_iou(primary_box: Any, 
                                    secondary_box: Any, 
                                    iou_threshold: float = 0.8,
                                    persistence: int = 5) -> Dict[str, Any]:
    """
    Check if ANY item is correctly placed.
    PASS if Max IOU >= threshold.
    """
    primary_list = _ensure_list_of_boxes(primary_box)
    secondary_list = _ensure_list_of_boxes(secondary_box)
    
    if not primary_list or not secondary_list:
        return {"decision": False, "iou": 0.0, "placed": False}
    
    max_iou = 0.0
    for p in primary_list:
        for s in secondary_list:
            iou = _calculate_iou_single(p, s)
            if iou > max_iou:
                max_iou = iou

    placed = max_iou >= iou_threshold
    
    return {
        "decision": placed,
        "iou": max_iou,
        "placed": placed,
        "iou_threshold": iou_threshold
    }


# =============================================================================
# POSE DETECTION RULE FUNCTIONS
# =============================================================================

def _get_things_present_from_input(things_present_input: Any) -> List[str]:
    """
    Helper to extract things_present list from various input formats.
    
    Args:
        things_present_input: Can be:
            - List of strings: ["personPresent", "leftHandAbove90"]
            - String (comma-separated): "personPresent,leftHandAbove90"
            - Dict with 'things_present' key
            - None or empty
    
    Returns:
        List of strings, normalized and sorted
    """
    if things_present_input is None:
        return []
    
    # If it's already a list of strings
    if isinstance(things_present_input, list):
        # Filter out non-string items and normalize
        result = [str(item).strip() for item in things_present_input if item]
        return sorted(result)
    
    # If it's a string (comma-separated)
    if isinstance(things_present_input, str):
        if not things_present_input.strip():
            return []
        items = [item.strip() for item in things_present_input.split(',') if item.strip()]
        return sorted(items)
    
    # If it's a dict, try to get 'things_present' key
    if isinstance(things_present_input, dict):
        if 'things_present' in things_present_input:
            return _get_things_present_from_input(things_present_input['things_present'])
        return []
    
    return []


def is_person_present(primary_box: Any = None, 
                     secondary_box: Any = None,
                     things_present: Any = None,
                     **kwargs) -> Dict[str, Any]:
    """
    Check if person is present in the frame.
    
    PASS (True) if:
    1. Person bounding box is detected (primary_box or Person in detections), OR
    2. "personPresent" is in things_present list
    
    Args:
        primary_box: Person bounding box(es) from detections
        secondary_box: Not used (for compatibility)
        things_present: List of detected things from pose model (can be list, string, or None)
        kwargs: Can contain executor_input_data for fallback extraction
    
    Returns:
        Dict with decision, person_detected, and details
    """
    # Check for Person bounding box
    person_boxes = _ensure_list_of_boxes(primary_box)
    person_detected_by_box = len(person_boxes) > 0
    
    # Get things_present - try direct parameter first, then kwargs fallback
    things_present_list = []
    if things_present is not None:
        things_present_list = _get_things_present_from_input(things_present)
    elif 'things_present' in kwargs:
        things_present_list = _get_things_present_from_input(kwargs['things_present'])
    elif 'executor_input_data' in kwargs:
        executor_data = kwargs['executor_input_data']
        if isinstance(executor_data, dict):
            things_present_list = _get_things_present_from_input(executor_data.get('things_present', []))
            # Also check additional_data
            if 'additional_data' in executor_data:
                additional = executor_data['additional_data']
                if isinstance(additional, dict) and 'things_present' in additional:
                    things_present_list = _get_things_present_from_input(additional['things_present'])
    
    person_detected_by_pose = "personPresent" in things_present_list
    
    # Person is present if detected by either method
    decision = person_detected_by_box or person_detected_by_pose
    
    return {
        "decision": decision,
        "person_detected": decision,
        "detected_by_box": person_detected_by_box,
        "detected_by_pose": person_detected_by_pose,
        "things_present": things_present_list,
        "person_boxes_count": len(person_boxes)
    }


def is_hand_position(primary_box: Any = None,
                     secondary_box: Any = None,
                     hand_position: str = None,
                     things_present: Any = None,
                     **kwargs) -> Dict[str, Any]:
    """
    Check if a specific hand position is detected.
    
    PASS (True) if the specified hand_position is in things_present.
    
    Supported hand positions:
    - "leftHandAbove90"
    - "leftHandBelow90"
    - "rightHandAbove90"
    - "rightHandBelow90"
    - "bothHandsAbove90"
    - "bothHandsBelow90"
    - "leftHandDown" (if supported)
    - "rightHandDown" (if supported)
    
    Args:
        primary_box: Not used (for compatibility)
        secondary_box: Not used (for compatibility)
        hand_position: String specifying which hand position to check
        things_present: List of detected things from pose model (can be list, string, or None)
        kwargs: Can contain executor_input_data for fallback extraction
    
    Returns:
        Dict with decision, hand_position_detected, and details
    """
    if not hand_position:
        return {
            "decision": False,
            "hand_position_detected": False,
            "error": "hand_position parameter is required"
        }
    
    # Normalize hand_position string
    hand_position = str(hand_position).strip()
    
    # Get things_present - try direct parameter first, then kwargs fallback
    things_present_list = []
    if things_present is not None:
        things_present_list = _get_things_present_from_input(things_present)
    elif 'things_present' in kwargs:
        things_present_list = _get_things_present_from_input(kwargs['things_present'])
    elif 'executor_input_data' in kwargs:
        executor_data = kwargs['executor_input_data']
        if isinstance(executor_data, dict):
            things_present_list = _get_things_present_from_input(executor_data.get('things_present', []))
            # Also check additional_data
            if 'additional_data' in executor_data:
                additional = executor_data['additional_data']
                if isinstance(additional, dict) and 'things_present' in additional:
                    things_present_list = _get_things_present_from_input(additional['things_present'])
    
    # Check if hand_position is in things_present
    decision = hand_position in things_present_list
    
    return {
        "decision": decision,
        "hand_position_detected": decision,
        "requested_position": hand_position,
        "detected_positions": [item for item in things_present_list if 'Hand' in item or 'hand' in item],
        "all_things_present": things_present_list
    }


def matches_pose_combination(primary_box: Any = None,
                              secondary_box: Any = None,
                              expected_combination: Any = None,
                              things_present: Any = None,
                              **kwargs) -> Dict[str, Any]:
    """
    Check if things_present matches an expected combination.
    
    This replicates the original pose detection logic where sorted(things_present)
    is matched against manual step answers.
    
    PASS (True) if sorted(things_present) matches sorted(expected_combination).
    
    Args:
        primary_box: Not used (for compatibility)
        secondary_box: Not used (for compatibility)
        expected_combination: Can be:
            - List of strings: ["personPresent", "leftHandAbove90"]
            - String (comma-separated): "personPresent,leftHandAbove90"
            - String (JSON array): '["personPresent", "leftHandAbove90"]'
        things_present: List of detected things from pose model (can be list, string, or None)
        kwargs: Can contain executor_input_data for fallback extraction
    
    Returns:
        Dict with decision, match_details, and comparison
    """
    # Get expected combination
    expected = _get_things_present_from_input(expected_combination)
    
    if not expected:
        return {
            "decision": False,
            "match": False,
            "error": "expected_combination parameter is required"
        }
    
    # Get actual things_present - try direct parameter first, then kwargs fallback
    things_present_list = []
    if things_present is not None:
        things_present_list = _get_things_present_from_input(things_present)
    elif 'things_present' in kwargs:
        things_present_list = _get_things_present_from_input(kwargs['things_present'])
    elif 'executor_input_data' in kwargs:
        executor_data = kwargs['executor_input_data']
        if isinstance(executor_data, dict):
            things_present_list = _get_things_present_from_input(executor_data.get('things_present', []))
            # Also check additional_data
            if 'additional_data' in executor_data:
                additional = executor_data['additional_data']
                if isinstance(additional, dict) and 'things_present' in additional:
                    things_present_list = _get_things_present_from_input(additional['things_present'])
    
    # Compare sorted lists (matching original pose logic)
    expected_sorted = sorted(expected)
    actual_sorted = sorted(things_present_list)
    
    decision = expected_sorted == actual_sorted
    
    return {
        "decision": decision,
        "match": decision,
        "expected": expected_sorted,
        "actual": actual_sorted,
        "expected_original": expected,
        "actual_original": things_present_list
    }


def has_any_hand_raised(primary_box: Any = None,
                       secondary_box: Any = None,
                       things_present: Any = None,
                       **kwargs) -> Dict[str, Any]:
    """
    Check if any hand is raised (any hand position detected).
    
    PASS (True) if any hand position string is in things_present.
    
    Args:
        primary_box: Not used (for compatibility)
        secondary_box: Not used (for compatibility)
        things_present: List of detected things from pose model (can be list, string, or None)
        kwargs: Can contain executor_input_data for fallback extraction
    
    Returns:
        Dict with decision, hand_raised, and detected positions
    """
    # Get things_present - try direct parameter first, then kwargs fallback
    things_present_list = []
    if things_present is not None:
        things_present_list = _get_things_present_from_input(things_present)
    elif 'things_present' in kwargs:
        things_present_list = _get_things_present_from_input(kwargs['things_present'])
    elif 'executor_input_data' in kwargs:
        executor_data = kwargs['executor_input_data']
        if isinstance(executor_data, dict):
            things_present_list = _get_things_present_from_input(executor_data.get('things_present', []))
            # Also check additional_data
            if 'additional_data' in executor_data:
                additional = executor_data['additional_data']
                if isinstance(additional, dict) and 'things_present' in additional:
                    things_present_list = _get_things_present_from_input(additional['things_present'])
    
    # Check for any hand position
    hand_positions = [
        "leftHandAbove90", "leftHandBelow90",
        "rightHandAbove90", "rightHandBelow90",
        "bothHandsAbove90", "bothHandsBelow90",
        "leftHandDown", "rightHandDown"
    ]
    
    detected_hands = [pos for pos in hand_positions if pos in things_present_list]
    decision = len(detected_hands) > 0
    
    return {
        "decision": decision,
        "hand_raised": decision,
        "detected_hand_positions": detected_hands,
        "all_things_present": things_present_list
    }


def is_person_not_present(primary_box: Any = None, 
                         secondary_box: Any = None,
                         things_present: Any = None,
                         **kwargs) -> Dict[str, Any]:
    """
    Check if person is NOT present in the frame.
    
    PASS (True) if person is NOT detected (opposite of is_person_present).
    Used for anomaly detection - triggers when person is lost.
    
    Args:
        primary_box: Person bounding box(es) from detections
        secondary_box: Not used (for compatibility)
        things_present: List of detected things from pose model (can be list, string, or None)
        kwargs: Can contain executor_input_data for fallback extraction
    
    Returns:
        Dict with decision, person_not_detected, and details
    """
    # Use is_person_present logic but invert the result
    person_result = is_person_present(
        primary_box=primary_box,
        secondary_box=secondary_box,
        things_present=things_present,
        **kwargs
    )
    
    # Invert the decision
    person_detected = person_result.get("person_detected", False)
    decision = not person_detected
    
    return {
        "decision": decision,
        "person_not_detected": decision,
        "person_detected": person_detected,
        "detected_by_box": person_result.get("detected_by_box", False),
        "detected_by_pose": person_result.get("detected_by_pose", False),
        "things_present": person_result.get("things_present", []),
        "person_boxes_count": person_result.get("person_boxes_count", 0)
    }


# =============================================================================
# GENDER DETECTION RULE FUNCTIONS
# =============================================================================

def _parse_gender_data_string(gender_string: str) -> Dict[str, str]:
    """
    Parse gender detection data string format.
    
    Format: "Male\nAge: (23-30)\nhappy" or "Female\nAge: (31-48)\nsad"
    
    Returns:
        Dict with 'gender', 'age', 'emotion' keys
    """
    if not gender_string or not isinstance(gender_string, str):
        return {"gender": None, "age": None, "emotion": None}
    
    lines = [line.strip() for line in gender_string.split('\n') if line.strip()]
    
    result = {"gender": None, "age": None, "emotion": None}
    
    # First line is usually gender
    if len(lines) > 0:
        first_line = lines[0]
        if first_line in ["Male", "Female"]:
            result["gender"] = first_line
        else:
            # Try to extract gender from first line
            if "Male" in first_line:
                result["gender"] = "Male"
            elif "Female" in first_line:
                result["gender"] = "Female"
    
    # Second line is usually age
    if len(lines) > 1:
        age_line = lines[1]
        if age_line.startswith("Age:"):
            age_value = age_line.replace("Age:", "").strip()
            result["age"] = age_value
        elif "Age:" in age_line:
            # Extract age from line containing "Age:"
            parts = age_line.split("Age:")
            if len(parts) > 1:
                result["age"] = parts[1].strip()
    
    # Third line or remaining is usually emotion
    if len(lines) > 2:
        result["emotion"] = lines[2]
    elif len(lines) == 2 and not lines[1].startswith("Age:"):
        # If only 2 lines and second doesn't start with "Age:", it might be emotion
        result["emotion"] = lines[1]
    
    return result


def _get_gender_things_present(things_present_input: Any) -> List[str]:
    """
    Helper to extract things_present list from gender detection format.
    
    Gender detection format: things_present contains strings like "Male\nAge: (23-30)\nhappy"
    
    Returns:
        List of gender data strings
    """
    if things_present_input is None:
        return []
    
    # If it's already a list
    if isinstance(things_present_input, list):
        return [str(item) for item in things_present_input if item]
    
    # If it's a string
    if isinstance(things_present_input, str):
        if not things_present_input.strip():
            return []
        # Check if it contains newlines (gender detection format)
        if '\n' in things_present_input:
            return [things_present_input.strip()]
        # Otherwise treat as comma-separated
        items = [item.strip() for item in things_present_input.split(',') if item.strip()]
        return items
    
    # If it's a dict, try to get 'things_present' key
    if isinstance(things_present_input, dict):
        if 'things_present' in things_present_input:
            return _get_gender_things_present(things_present_input['things_present'])
        return []
    
    return []


def is_face_detected(primary_box: Any = None,
                     secondary_box: Any = None,
                     things_present: Any = None,
                     **kwargs) -> Dict[str, Any]:
    """
    Check if face is detected in the frame.
    
    PASS (True) if:
    1. Face bounding box is detected (primary_box or Face in detections), OR
    2. Gender data string is in things_present (contains "Male" or "Female")
    
    Args:
        primary_box: Face bounding box(es) from detections
        secondary_box: Not used (for compatibility)
        things_present: List of gender data strings from gender model (format: "Male\nAge: (23-30)\nhappy")
        kwargs: Can contain executor_input_data for fallback extraction
    
    Returns:
        Dict with decision, face_detected, and details
    """
    # Check for Face bounding box
    face_boxes = _ensure_list_of_boxes(primary_box)
    face_detected_by_box = len(face_boxes) > 0
    
    # Get things_present - try direct parameter first, then kwargs fallback
    things_present_list = []
    if things_present is not None:
        things_present_list = _get_gender_things_present(things_present)
    elif 'things_present' in kwargs:
        things_present_list = _get_gender_things_present(kwargs['things_present'])
    elif 'executor_input_data' in kwargs:
        executor_data = kwargs['executor_input_data']
        if isinstance(executor_data, dict):
            things_present_list = _get_gender_things_present(executor_data.get('things_present', []))
            # Also check additional_data
            if 'additional_data' in executor_data:
                additional = executor_data['additional_data']
                if isinstance(additional, dict) and 'things_present' in additional:
                    things_present_list = _get_gender_things_present(additional['things_present'])
    
    # Check if any gender data string contains "Male" or "Female"
    face_detected_by_gender = False
    for item in things_present_list:
        if isinstance(item, str):
            parsed = _parse_gender_data_string(item)
            if parsed.get("gender") in ["Male", "Female"]:
                face_detected_by_gender = True
                break
    
    # Face is detected if detected by either method
    decision = face_detected_by_box or face_detected_by_gender
    
    return {
        "decision": decision,
        "face_detected": decision,
        "detected_by_box": face_detected_by_box,
        "detected_by_gender": face_detected_by_gender,
        "face_boxes_count": len(face_boxes),
        "things_present": things_present_list
    }


def is_gender_detected(primary_box: Any = None,
                       secondary_box: Any = None,
                       gender: str = None,
                       things_present: Any = None,
                       **kwargs) -> Dict[str, Any]:
    """
    Check if a specific gender (Male or Female) is detected.
    
    PASS (True) if the specified gender is found in things_present.
    
    Args:
        primary_box: Not used (for compatibility)
        secondary_box: Not used (for compatibility)
        gender: Gender to check for ("Male" or "Female")
        things_present: List of gender data strings from gender model (format: "Male\nAge: (23-30)\nhappy")
        kwargs: Can contain executor_input_data for fallback extraction
    
    Returns:
        Dict with decision, gender_detected, and detected gender info
    """
    if not gender:
        return {
            "decision": False,
            "gender_detected": False,
            "error": "gender parameter is required"
        }
    
    gender = str(gender).strip()
    if gender not in ["Male", "Female"]:
        return {
            "decision": False,
            "gender_detected": False,
            "error": f"gender must be 'Male' or 'Female', got: {gender}"
        }
    
    # Get things_present - try direct parameter first, then kwargs fallback
    things_present_list = []
    if things_present is not None:
        things_present_list = _get_gender_things_present(things_present)
    elif 'things_present' in kwargs:
        things_present_list = _get_gender_things_present(kwargs['things_present'])
    elif 'executor_input_data' in kwargs:
        executor_data = kwargs['executor_input_data']
        if isinstance(executor_data, dict):
            things_present_list = _get_gender_things_present(executor_data.get('things_present', []))
            # Also check additional_data
            if 'additional_data' in executor_data:
                additional = executor_data['additional_data']
                if isinstance(additional, dict) and 'things_present' in additional:
                    things_present_list = _get_gender_things_present(additional['things_present'])
    
    # Check if any gender data string contains the specified gender
    gender_detected = False
    detected_info = None
    
    for item in things_present_list:
        if isinstance(item, str):
            parsed = _parse_gender_data_string(item)
            if parsed.get("gender") == gender:
                gender_detected = True
                detected_info = parsed
                break
    
    return {
        "decision": gender_detected,
        "gender_detected": gender_detected,
        "expected_gender": gender,
        "detected_gender": detected_info.get("gender") if detected_info else None,
        "detected_age": detected_info.get("age") if detected_info else None,
        "detected_emotion": detected_info.get("emotion") if detected_info else None,
        "things_present": things_present_list
    }


def is_face_not_detected(primary_box: Any = None,
                         secondary_box: Any = None,
                         things_present: Any = None,
                         **kwargs) -> Dict[str, Any]:
    """
    Check if face is NOT detected in the frame.
    
    PASS (True) if face is NOT detected (opposite of is_face_detected).
    Used for anomaly detection - triggers when face is lost.
    
    Args:
        primary_box: Face bounding box(es) from detections
        secondary_box: Not used (for compatibility)
        things_present: List of gender data strings from gender model
        kwargs: Can contain executor_input_data for fallback extraction
    
    Returns:
        Dict with decision, face_not_detected, and details
    """
    # Use is_face_detected logic but invert the result
    face_result = is_face_detected(
        primary_box=primary_box,
        secondary_box=secondary_box,
        things_present=things_present,
        **kwargs
    )
    
    # Invert the decision
    face_detected = face_result.get("face_detected", False)
    decision = not face_detected
    
    return {
        "decision": decision,
        "face_not_detected": decision,
        "face_detected": face_detected,
        "detected_by_box": face_result.get("detected_by_box", False),
        "detected_by_gender": face_result.get("detected_by_gender", False),
        "things_present": face_result.get("things_present", []),
        "face_boxes_count": face_result.get("face_boxes_count", 0)
    }


def is_age_detected(primary_box: Any = None,
                    secondary_box: Any = None,
                    age_range: str = None,
                    things_present: Any = None,
                    **kwargs) -> Dict[str, Any]:
    """
    Check if a specific age range is detected (optional rule for future use).
    
    PASS (True) if the specified age range is found in things_present.
    
    Args:
        primary_box: Not used (for compatibility)
        secondary_box: Not used (for compatibility)
        age_range: Age range to check for (e.g., "(23-30)", "(31-48)")
        things_present: List of gender data strings from gender model
        kwargs: Can contain executor_input_data for fallback extraction
    
    Returns:
        Dict with decision, age_detected, and detected age info
    """
    if not age_range:
        return {
            "decision": False,
            "age_detected": False,
            "error": "age_range parameter is required"
        }
    
    age_range = str(age_range).strip()
    
    # Get things_present
    things_present_list = []
    if things_present is not None:
        things_present_list = _get_gender_things_present(things_present)
    elif 'things_present' in kwargs:
        things_present_list = _get_gender_things_present(kwargs['things_present'])
    elif 'executor_input_data' in kwargs:
        executor_data = kwargs['executor_input_data']
        if isinstance(executor_data, dict):
            things_present_list = _get_gender_things_present(executor_data.get('things_present', []))
            if 'additional_data' in executor_data:
                additional = executor_data['additional_data']
                if isinstance(additional, dict) and 'things_present' in additional:
                    things_present_list = _get_gender_things_present(additional['things_present'])
    
    # Check if any gender data string contains the specified age range
    age_detected = False
    detected_info = None
    
    for item in things_present_list:
        if isinstance(item, str):
            parsed = _parse_gender_data_string(item)
            if parsed.get("age") == age_range:
                age_detected = True
                detected_info = parsed
                break
    
    return {
        "decision": age_detected,
        "age_detected": age_detected,
        "expected_age": age_range,
        "detected_age": detected_info.get("age") if detected_info else None,
        "detected_gender": detected_info.get("gender") if detected_info else None,
        "things_present": things_present_list
    }


def is_emotion_detected(primary_box: Any = None,
                        secondary_box: Any = None,
                        emotion: str = None,
                        things_present: Any = None,
                        **kwargs) -> Dict[str, Any]:
    """
    Check if a specific emotion is detected (optional rule for future use).
    
    PASS (True) if the specified emotion is found in things_present.
    
    Args:
        primary_box: Not used (for compatibility)
        secondary_box: Not used (for compatibility)
        emotion: Emotion to check for (e.g., "happy", "sad", "neutral", "angry")
        things_present: List of gender data strings from gender model
        kwargs: Can contain executor_input_data for fallback extraction
    
    Returns:
        Dict with decision, emotion_detected, and detected emotion info
    """
    if not emotion:
        return {
            "decision": False,
            "emotion_detected": False,
            "error": "emotion parameter is required"
        }
    
    emotion = str(emotion).strip().lower()
    
    # Get things_present
    things_present_list = []
    if things_present is not None:
        things_present_list = _get_gender_things_present(things_present)
    elif 'things_present' in kwargs:
        things_present_list = _get_gender_things_present(kwargs['things_present'])
    elif 'executor_input_data' in kwargs:
        executor_data = kwargs['executor_input_data']
        if isinstance(executor_data, dict):
            things_present_list = _get_gender_things_present(executor_data.get('things_present', []))
            if 'additional_data' in executor_data:
                additional = executor_data['additional_data']
                if isinstance(additional, dict) and 'things_present' in additional:
                    things_present_list = _get_gender_things_present(additional['things_present'])
    
    # Check if any gender data string contains the specified emotion
    emotion_detected = False
    detected_info = None
    
    for item in things_present_list:
        if isinstance(item, str):
            parsed = _parse_gender_data_string(item)
            detected_emotion = parsed.get("emotion")
            if detected_emotion and detected_emotion.lower() == emotion:
                emotion_detected = True
                detected_info = parsed
                break
    
    return {
        "decision": emotion_detected,
        "emotion_detected": emotion_detected,
        "expected_emotion": emotion,
        "detected_emotion": detected_info.get("emotion") if detected_info else None,
        "detected_gender": detected_info.get("gender") if detected_info else None,
        "detected_age": detected_info.get("age") if detected_info else None,
        "things_present": things_present_list
    }
