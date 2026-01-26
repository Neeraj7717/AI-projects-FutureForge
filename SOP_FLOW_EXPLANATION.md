# SOP System - Complete Flow Explanation

## Overview
The SOP (Standard Operating Procedure) system is a rule-based workflow engine that processes detections and executes activities based on configured rules. It replaces the legacy instruction graph system.

---

## 🔄 Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. DETECTION PHASE (Model Layer)                                │
│    - Pose Detection (MediaPipe)                                 │
│    - Object Detection (YOLO)                                    │
└──────────────────────┬────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. DETECTION CONVERSION                                         │
│    - Convert landmarks/boxes to SOP format                      │
│    - Format: Dict[str, List[List[float]]]                        │
│    - Example: {"Person": [[x1,y1,x2,y2]], "Gripper": [...]}    │
└──────────────────────┬────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. SOP MANAGER - Entry Point                                    │
│    sop_manager.execute_sop()                                    │
│    ├─ Resolve SOP ID from manualId                             │
│    ├─ Get/Create executor (cached)                              │
│    └─ Prepare input data                                        │
└──────────────────────┬────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. SOP EXECUTOR (Unified Interface)                             │
│    - Determines SOP type (node/cycle)                           │
│    - Routes to appropriate executor                              │
│    - NodeExecutor: Activity triggered by class match           │
│    - CycleExecutor: State machine with transitions              │
└──────────────────────┬────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. ACTIVITY EXECUTION                                           │
│    For each activity:                                           │
│    ├─ Check if activity should run (class match/state)          │
│    ├─ Evaluate activity_rules                                   │
│    ├─ Evaluate anomaly_rules                                    │
│    └─ Update derived_data                                       │
└──────────────────────┬────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. RULE EVALUATION                                              │
│    - Load rule function from sop_rule_functions.py              │
│    - Pass detections + predefined values                        │
│    - Check persistence (N consecutive frames)                      │
│    - Return decision + metadata                                 │
└──────────────────────┬────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. RESULT PROCESSING                                            │
│    - Activity results aggregated                                │
│    - Cycle state updated (if cycle type)                        │
│    - Analytics/KPI data updated                                 │
│    - Return ExecutionResult                                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📋 Step-by-Step Detailed Flow

### **STEP 1: Model Detection**

#### **A. Pose Detection Flow** (`model/pose_model.py`)

```python
# Entry: /detect-pose endpoint or Kafka consumer
pose_obj._process_pose_detection(landmarks, sourceId, sessionId, manualId, frame_no)
    ↓
# Detects: personPresent, hand positions
things_present = ["personPresent", "rightHandAbove90"]
    ↓
pose_obj.process_squat_analysis(sessionId, frame, things_present, ...)
    ↓
# Check if SOP is configured
sop_id = sop_manager.get_sop_id_for_manual(str(manualId), sourceId)
    ↓
if sop_id:
    pose_obj._execute_sop_after_detection(...)
```

#### **B. Object Detection Flow** (`model/detections.py`)

```python
# Entry: /detect endpoint or Kafka consumer
detector.action_detector(file, sourceId, sessionId, manualId)
    ↓
# YOLO detection
detection_output = self.model.predict(source=file, conf=0.25)
    ↓
# Extract boxes and classes
xyxy = boxes.xyxy.cpu().numpy()  # [[x1,y1,x2,y2], ...]
cls_ids = boxes.cls.cpu().numpy()
names = {id: "class_name"}
    ↓
# Execute SOP
self._execute_sop_after_action_detection(...)
```

---

### **STEP 2: Detection Format Conversion**

#### **Pose → SOP Format** (`pose_model.py:197-250`)

```python
def _execute_sop_after_detection(self, sourceId, manualId, results, ...):
    detections = {}
    
    # Convert MediaPipe landmarks to bounding box
    if results.pose_landmarks:
        x_coords = [lm.x * 1920 for lm in landmarks.landmark]
        y_coords = [lm.y * 1080 for lm in landmarks.landmark]
        x1, x2 = min(x_coords), max(x_coords)
        y1, y2 = min(y_coords), max(y_coords)
        detections["Person"] = [[x1, y1, x2, y2]]
    
    # Call SOP Manager
    sop_manager.execute_sop(
        sourceId=sourceId,
        manualId=str(manualId),
        detections=detections,  # {"Person": [[x1,y1,x2,y2]]}
        frame_number=frame_no,
        additional_data={"things_present": things_present, ...}
    )
```

#### **YOLO → SOP Format** (`detections.py:872-930`)

```python
def _execute_sop_after_action_detection(self, sourceId, manualId, xyxy, cls_ids, names, ...):
    detections = {}
    things_present = []
    
    # Group by class name
    for i, box in enumerate(xyxy):
        cls_id = int(cls_ids[i])
        class_name = names.get(cls_id, f"Class_{cls_id}")
        
        if class_name not in detections:
            detections[class_name] = []
        detections[class_name].append(box.tolist())  # [x1,y1,x2,y2]
        things_present.append(class_name)
    
    # Call SOP Manager
    sop_manager.execute_sop(
        sourceId=sourceId,
        manualId=str(manualId),
        detections=detections,  # {"Gripper": [[x1,y1,x2,y2]], "Item": [[...]]}
        ...
    )
```

**SOP Detection Format:**
```python
{
    "Person": [[x1, y1, x2, y2]],           # Single person
    "Gripper": [[x1,y1,x2,y2], [x1,y1,x2,y2]],  # Multiple grippers
    "Item": [[x1,y1,x2,y2]]                 # Single item
}
```

---

### **STEP 3: SOP Manager - Entry Point** (`model/sop_manager.py`)

#### **3.1 Resolve SOP ID** (`sop_manager.py:57-165`)

```python
def get_sop_id_for_manual(self, manualId: str, sourceId: str) -> Optional[str]:
    # 1. Check cache
    if manualId in self.manual_to_sop:
        return self.manual_to_sop[manualId]
    
    # 2. Try MongoDB manual collection
    manual = db["manual"].find_one({"_id": int(manualId)})
    if manual and "sop_id" in manual:
        return manual["sop_id"]
    
    # 3. Try sop_activity_rule_map collection
    rule_map = db["sop_activity_rule_map"].find_one({"sop_id": f"EZA_SOP_{manualId}"})
    if rule_map:
        return rule_map["sop_id"]
    
    # 4. Try local JSON files (abbjsons/)
    # - pose_activity_rule_map.json
    # - abb_activity_rule_map.json
    
    # 5. Try common patterns (EZA_SOP_POSE, EZA_SOP_ABB, etc.)
    
    return None  # No SOP configured
```

#### **3.2 Get/Create Executor** (`sop_manager.py:167-218`)

```python
def get_executor(self, sourceId: str, manualId: str, sop_id: str = None):
    # Resolve sop_id if not provided
    if not sop_id:
        sop_id = self.get_sop_id_for_manual(manualId, sourceId)
    
    # Check cache
    cache_key = f"{sourceId}:{manualId}:{sop_id}"
    if cache_key in self.executors:
        return self.executors[cache_key]
    
    # Load SOP data
    sop_data = self._load_sop_data(sop_id)
    
    # Create executor
    executor = create_executor(
        sop_data=sop_data,
        sop_id=sop_id,
        source_type="mongodb",
        additional_predefined={}
    )
    
    # Cache executor
    self.executors[cache_key] = executor
    return executor
```

#### **3.3 Load SOP Data** (`sop_manager.py:220-266`)

```python
def _load_sop_data(self, sop_id: str) -> Optional[Dict]:
    # 1. Check cache
    if sop_id in self.sop_data_cache:
        return self.sop_data_cache[sop_id]
    
    # 2. Try local JSON files first
    sop_data = sop_loader.load_sop(
        source_type="local",
        sop_id=sop_id
    )
    
    # 3. Fallback to MongoDB
    if not sop_data or not sop_data.get("validation", {}).get("valid"):
        sop_data = sop_loader.load_sop(
            source_type="mongodb",
            sop_id=sop_id,
            mongo_uri=config.mongo_connection_string_stateless,
            database_name=config.database_name
        )
    
    # 4. Validate structure
    if sop_data and sop_data.get("validation", {}).get("valid"):
        self.sop_data_cache[sop_id] = sop_data
        return sop_data
    
    return None
```

#### **3.4 Execute SOP** (`sop_manager.py:268-344`)

```python
def execute_sop(self, sourceId, manualId, detections, frame_number, timestamp, additional_data):
    # Get executor
    executor = self.get_executor(sourceId, manualId)
    if not executor:
        return None
    
    # Prepare input data
    input_data = {
        "source_id": sourceId,
        "detections": detections,  # {"Person": [[x1,y1,x2,y2]]}
        "frame_number": frame_number,
        "frame_id": frame_number,
        "timestamp": timestamp,
        **additional_data  # things_present, pose_landmarks, etc.
    }
    
    # Execute
    executor.set_input_data(input_data)
    result = executor.execute_all()
    executor.reset()  # Clear temporary state
    
    # Convert result to dict
    return {
        "success": result.success,
        "activities_executed": result.activities_executed,
        "current_activity": result.current_activity,
        "cycle_active": result.cycle_active,
        "cycle_count": result.cycle_count,
        "derived_data": result.derived_data,
        "activity_results": {...}
    }
```

---

### **STEP 4: SOP Loader - Data Loading & Validation** (`sop_loader.py`)

#### **4.1 Load from MongoDB** (`sop_loader.py:222-290`)

```python
def _load_from_mongodb(mongo_uri, database_name, source_id, sop_id, collections):
    client = MongoClient(mongo_uri)
    db = client[database_name]
    
    # 1. Load sop_master
    sop_master = db[collections["sop_master"]].find_one({"sopId": sop_id})
    # Contains: sopId, type, activities, startActivity, endActivity
    
    # 2. Load sop_activity_rule_map
    activity_rule_map = db[collections["sop_activity_rule_map"]].find_one({"sop_id": sop_id})
    # Contains: rules_map [{activity_id, activity_rules, anomaly_rules, predefined_values}]
    
    # 3. Load sop_rule_master (all rule definitions)
    rules = list(db[collections["sop_rule_master"]].find({"sop_id": sop_id}))
    # Contains: rule_name, desc, input, output
    
    # 4. Load sop_analytics_template (optional)
    analytics = db[collections["sop_analytics_template"]].find_one({"sop_id": sop_id})
    
    return {
        "sop_master": sop_master,
        "sop_activity_rule_map": activity_rule_map,
        "sop_rules": rules,
        "sop_analytics_template": analytics
    }
```

#### **4.2 Validate Structure** (`sop_loader.py:78-176`)

```python
def validate_structure(data: Dict) -> Dict:
    errors = []
    
    # 1. Validate sop_master
    # - Check required fields: sopId, activities
    # - Validate each activity: activityId, model_class, etc.
    
    # 2. Validate sop_activity_rule_map
    # - Check rules_map structure
    # - Validate RuleMapping dataclass
    
    # 3. Validate sop_rules
    # - Check rule_name, input, output fields
    
    # 4. Cross-validation
    # - All activities in sop_master must have rules in rules_map
    # - All rules referenced in rules_map must exist in sop_rules
    
    return {"valid": len(errors) == 0, "errors": errors}
```

**Validation Checks:**
- ✅ All activities have corresponding rules
- ✅ All referenced rules exist
- ✅ Required fields present
- ✅ Data types correct
- ✅ Activity sequences valid

---

### **STEP 5: SOP Executor - Unified Interface** (`sop_unified_executor.py`)

#### **5.1 Initialize Executor** (`sop_unified_executor.py:168-209`)

```python
class SOPExecutor:
    def __init__(self, sop_data: Dict, additional_predefined: Dict = None):
        self.sop_data = sop_data
        self.additional_predefined = additional_predefined or {}
        
        # Extract SOP metadata
        sop_master = sop_data.get("sop_master", {})
        self.sop_id = sop_master.get("sopId", "unknown")
        self.sop_type = sop_master.get("type") or sop_master.get("sopType", "cycle")
        self.sop_type = self.sop_type.lower()  # "node" or "cycle"
        
        # Select executor based on type
        self._init_executor()
    
    def _init_executor(self):
        # Get executor class from registry
        executor_class = _EXECUTOR_REGISTRY.get(self.sop_type)
        
        # Create executor instance
        if self.sop_type == "cycle":
            self._executor = CycleExecutor(self.sop_data, self.additional_predefined)
        elif self.sop_type == "node":
            self._executor = NodeExecutor(self.sop_data, self.additional_predefined)
        else:
            raise ValueError(f"Unknown sop_type: {self.sop_type}")
```

#### **5.2 Set Input Data**

```python
def set_input_data(self, data: Dict[str, Any]):
    """
    Set input data for current frame.
    
    data = {
        "source_id": "source1",
        "detections": {"Person": [[x1,y1,x2,y2]]},
        "frame_number": 123,
        "frame_id": 123,
        "timestamp": "1234567890",
        "things_present": ["personPresent", "rightHandAbove90"],
        "pose_landmarks": {...},
        "sessionId": "session123"
    }
    """
    self._executor.set_input_data(data)
```

#### **5.3 Execute All Activities**

```python
def execute_all(self) -> ExecutionResult:
    """
    Execute all activities and return result.
    Delegates to underlying executor (NodeExecutor or CycleExecutor).
    """
    return self._executor.execute_all()
```

---

### **STEP 6: Node Executor - Class-Based Triggering** (`node_executor.py`)

#### **6.1 Activity Sequence Building**

```python
def _build_activity_sequence(self) -> List[str]:
    """
    Build activity sequence from sop_master.activities.
    
    Logic:
    1. If activities have prevAct/nextAct links → Build graph
    2. Otherwise → Use array order
    """
    activities = self.sop_data.get("sop_master", {}).get("activities", [])
    
    # Example activities:
    # [
    #   {"activityId": "A1", "model_class": ["Gripper", "Item"]},
    #   {"activityId": "A2", "model_class": ["Person"]},
    #   {"activityId": "A3", "prevAct": ["A1"], "nextAct": ["A2"]}
    # ]
    
    return ["A1", "A2", "A3"]  # Activity IDs in order
```

#### **6.2 Execute All Activities**

```python
def execute_all(self) -> ExecutionResult:
    """
    For each activity:
    1. Check if detected_classes match activity.model_class
    2. If match → Execute activity_rules and anomaly_rules
    3. If no match → Skip activity
    """
    result = ExecutionResult()
    result.executor_input_data = self.executor_input_data.copy()
    result.predefined_data = self.predefined_data.copy()
    
    # Get detected classes from input
    detected_classes = self.executor_input_data.get("detected_classes", [])
    # OR extract from detections dict keys
    detected_classes = list(self.executor_input_data.get("detections", {}).keys())
    
    # Process each activity
    for activity_id in self.activity_sequence:
        activity = self._get_activity(activity_id)
        
        # Check if activity should trigger
        should_trigger = self._should_trigger_activity(activity, detected_classes)
        
        if should_trigger:
            # Execute activity
            activity_result = self.execute_activity(activity_id)
            result.activity_results[activity_id] = activity_result
            result.activities_executed += 1
        else:
            # Skip activity
            result.activity_results[activity_id] = ActivityResult(
                activity_id=activity_id,
                success=False,
                triggered=False
            )
            result.activities_skipped += 1
    
    result.derived_data = self.derived_data.copy()
    return result

def _should_trigger_activity(self, activity, detected_classes):
    """
    Check if activity should trigger based on model_class match.
    
    Activity has: model_class = ["Gripper", "Item"]
    Detected: ["Gripper", "Item", "Person"]
    
    Returns True if all model_class items are in detected_classes.
    """
    required_classes = activity.get("model_class", [])
    if not required_classes:
        return True  # No requirement, always trigger
    
    return all(cls in detected_classes for cls in required_classes)
```

#### **6.3 Execute Single Activity**

```python
def execute_activity(self, activity_id: str) -> ActivityResult:
    """
    Execute rules for a single activity.
    """
    activity_result = ActivityResult(activity_id=activity_id)
    
    # Get rules for this activity
    rules_config = self._activity_rules_map.get(activity_id, {})
    
    # Set up rule evaluator with data sources
    self.rule_evaluator.set_data_sources(
        executor_input_data=self.executor_input_data,
        predefined_data=self.predefined_data,
        derived_data=self.derived_data
    )
    
    # 1. Execute activity_rules
    activity_rules = rules_config.get("activity_rules", [])
    if activity_rules:
        success, results, rule_details = self.rule_evaluator.evaluate_rules(activity_rules)
        activity_result.success = success
        activity_result.results = results
        activity_result.rule_details = rule_details
    
    # 2. Execute anomaly_rules
    anomaly_rules = rules_config.get("anomaly_rules", [])
    if anomaly_rules:
        success, results, rule_details = self.rule_evaluator.evaluate_rules(anomaly_rules)
        activity_result.anomaly_results = results
    
    # 3. Update derived_data (from rule outputs)
    self.derived_data.update(activity_result.results)
    
    return activity_result
```

---

### **STEP 7: Cycle Executor - State Machine** (`sop_cycle_executor.py`)

#### **7.1 State Machine Building**

```python
def _build_state_machine(self):
    """
    Build state machine from activities with prevAct/nextAct links.
    
    Example:
    Activities:
    - A1: startActivity, nextAct: ["A2"]
    - A2: prevAct: ["A1"], nextAct: ["A3"]
    - A3: prevAct: ["A2"], endActivity, nextAct: ["A1"]  # Cycle back
    
    State Machine:
    {
        "A1": {"next": ["A2"], "is_start": True},
        "A2": {"prev": ["A1"], "next": ["A3"]},
        "A3": {"prev": ["A2"], "next": ["A1"], "is_end": True}
    }
    """
    # Build transitions from prevAct/nextAct
    # Track start/end activities
```

#### **7.2 Cycle Execution Flow**

```python
def execute_all(self) -> ExecutionResult:
    """
    Cycle-based execution:
    1. Check if cycle should start (start_activity conditions met)
    2. If cycle active → Check current activity rules
    3. If rules pass → Transition to next activity
    4. If end_activity reached and start_activity detected → Complete cycle
    """
    source_id = self.executor_input_data.get("source_id", "default")
    source_state = self.sources.get(source_id, SourceState(source_id=source_id))
    
    frame_number = self.executor_input_data.get("frame_number", 0)
    
    # 1. Check if cycle should start
    if not source_state.cycle_state.is_active:
        if self._check_start_activity(source_state):
            # Start cycle
            source_state.cycle_state.is_active = True
            source_state.cycle_state.current_activity = self.start_activity
            source_state.cycle_state.cycle_count += 1
            source_state.cycle_state.cycle_start_frame = frame_number
    
    # 2. If cycle active, process current activity
    if source_state.cycle_state.is_active:
        current_activity = source_state.cycle_state.current_activity
        
        # Execute activity rules
        activity_result = self._execute_activity_rules(current_activity, source_state)
        
        # Check if rules passed (with persistence)
        if activity_result.success:
            # Transition to next activity
            next_activity = self._get_next_activity(current_activity)
            
            if next_activity:
                # Check if we reached end activity
                if next_activity == self.end_activity:
                    # Check if start activity is detected again (cycle complete)
                    if self._check_start_activity(source_state):
                        # Complete cycle
                        self._complete_cycle(source_state, frame_number)
                        # Restart cycle
                        source_state.cycle_state.current_activity = self.start_activity
                else:
                    # Transition to next
                    source_state.cycle_state.current_activity = next_activity
    
    # Build result
    result = ExecutionResult()
    result.current_activity = source_state.cycle_state.current_activity
    result.cycle_active = source_state.cycle_state.is_active
    result.cycle_count = source_state.cycle_state.cycle_count
    result.derived_data = source_state.derived_data.copy()
    
    return result
```

#### **7.3 Rule Persistence** (`sop_cycle_executor.py:34-71`)

```python
class RuleStateTracker:
    """
    Tracks rule persistence (N consecutive frames).
    Prevents false positives from single-frame detections.
    """
    def __init__(self):
        # Maps rule_id -> (consecutive_success_count, last_frame)
        self.persistence_state: Dict[str, Tuple[int, int]] = {}
    
    def update_rule_state(self, rule_id: str, is_passing: bool, current_frame: int):
        """Update tracking state."""
        current_count, last_frame = self.persistence_state.get(rule_id, (0, -1))
        
        if is_passing:
            self.persistence_state[rule_id] = (current_count + 1, current_frame)
        else:
            self.persistence_state[rule_id] = (0, current_frame)
    
    def is_rule_confirmed(self, rule_id: str, required_frames: int) -> bool:
        """
        Check if rule has been passing for required number of frames.
        
        Example:
        - required_frames = 5
        - Rule passed in frames: 1, 2, 3, 4, 5
        - Returns True after frame 5
        """
        current_count, _ = self.persistence_state.get(rule_id, (0, 0))
        return current_count >= required_frames
```

---

### **STEP 8: Rule Evaluation** (`sop_rule_functions.py`)

#### **8.1 Rule Function Structure**

```python
# Example rule function
def is_point_inside_box(primary_box: Any, secondary_box: Any) -> Dict[str, Any]:
    """
    Check if reference point of primary box is inside secondary box.
    
    Args:
        primary_box: Can be [x1,y1,x2,y2] or [[x1,y1,x2,y2], ...]
        secondary_box: Same format
    
    Returns:
        {"decision": bool, "center": (x,y), "inside": bool}
    """
    primary_list = _ensure_list_of_boxes(primary_box)
    secondary_list = _ensure_list_of_boxes(secondary_box)
    
    # Check if any primary box's bottom-right corner is inside any secondary box
    for p_box in primary_list:
        point = _get_reference_point(p_box)  # (x2, y2)
        for s_box in secondary_list:
            x1, y1, x2, y2 = s_box
            if x1 <= point[0] <= x2 and y1 <= point[1] <= y2:
                return {"decision": True, "center": point, "inside": True}
    
    return {"decision": False, "center": None, "inside": False}
```

#### **8.2 Rule Execution**

```python
# Rule definition in MongoDB:
{
    "rule_name": "is_point_inside_box",
    "desc": "Check if gripper is inside zone",
    "input": ["primary_box", "secondary_box"],
    "output": ["decision", "center"]
}

# Rule mapping in activity:
{
    "activity_id": "PickItem",
    "activity_rules": [
        {
            "is_point_inside_box": {
                "primary_box": "detections.Gripper",
                "secondary_box": "predefined.Zone1"
            }
        }
    ]
}

# Execution:
# 1. Resolve inputs:
primary_box = executor_input_data["detections"]["Gripper"]  # [[x1,y1,x2,y2]]
secondary_box = predefined_data["Zone1"]  # [[x1,y1,x2,y2]]

# 2. Call function:
result = is_point_inside_box(primary_box, secondary_box)
# Returns: {"decision": True, "center": (500, 300), "inside": True}

# 3. Store outputs:
derived_data["decision"] = True
derived_data["center"] = (500, 300)
```

#### **8.3 Available Rule Functions** (`sop_rule_functions.py`)

```python
# Spatial Rules:
- is_point_inside_box(primary_box, secondary_box)
- is_carrying_item(primary_box, secondary_box, threshold=0.1)
- is_not_carrying_item(primary_box, secondary_box, threshold=0.1)
- is_box_outside_box(primary_box, secondary_box, threshold=0.1)
- calculate_iou(box1, box2)
- get_center(bbox)

# Logic Rules:
- AND/OR groups for multiple rules
- Persistence checks (N consecutive frames)
```

---

### **STEP 9: Data Flow**

#### **9.1 Data Sources**

```python
# 1. executor_input_data (Live, per frame)
{
    "source_id": "source1",
    "detections": {"Person": [[x1,y1,x2,y2]]},
    "frame_number": 123,
    "things_present": ["personPresent"],
    "pose_landmarks": {...}
}

# 2. predefined_data (Static, loaded once)
{
    "Zone1": [[x1,y1,x2,y2]],
    "Zone2": [[x1,y1,x2,y2]],
    "threshold": 0.1,
    "models": {...}
}

# 3. derived_data (Computed, updated by rules)
{
    "decision": True,
    "center": (500, 300),
    "iou": 0.85,
    "carrying": True
}
```

#### **9.2 Rule Input Resolution**

```python
# Rule input: "detections.Gripper"
# Resolves to: executor_input_data["detections"]["Gripper"]

# Rule input: "predefined.Zone1"
# Resolves to: predefined_data["Zone1"]

# Rule input: "derived_data.decision"
# Resolves to: derived_data["decision"]
```

---

## 🔍 Validation Process

### **1. Structure Validation** (`sop_loader.py:78-176`)

```python
✅ sop_master exists and has required fields
✅ All activities have activityId
✅ sop_activity_rule_map exists
✅ All activities in sop_master have rules in rules_map
✅ All rules referenced exist in sop_rules
✅ Rule inputs/outputs are valid
```

### **2. Runtime Validation**

```python
✅ Detections format correct: Dict[str, List[List[float]]]
✅ Bounding boxes valid: [x1, y1, x2, y2] where x2 > x1, y2 > y1
✅ Activity sequence valid (no circular dependencies)
✅ State machine transitions valid
```

---

## 📊 Example: Complete Flow

### **Scenario: Pose Detection → SOP Execution**

```
1. Frame arrives via Kafka
   ↓
2. Pose detection runs (MediaPipe)
   - Detects: personPresent, rightHandAbove90
   ↓
3. Convert to SOP format
   detections = {"Person": [[100, 200, 500, 800]]}
   ↓
4. SOP Manager resolves SOP ID
   manualId=23 → sop_id="EZA_SOP_POSE"
   ↓
5. Load SOP data from MongoDB
   - sop_master: {sopId: "EZA_SOP_POSE", type: "cycle", activities: [...]}
   - sop_activity_rule_map: {rules_map: [...]}
   - sop_rules: [{rule_name: "is_point_inside_box", ...}]
   ↓
6. Create CycleExecutor (sop_type="cycle")
   ↓
7. Execute cycle
   - Check start_activity conditions
   - Process current activity rules
   - Evaluate: is_point_inside_box(Person, Zone1)
   - Check persistence (5 consecutive frames)
   - Transition to next activity if rules pass
   ↓
8. Return result
   {
       "success": True,
       "current_activity": "RaiseRightHand",
       "cycle_active": True,
       "cycle_count": 1,
       "activities_executed": 1
   }
```

---

## 🎯 Key Points

1. **SOP replaces instruction_graph** - New code uses SOP, legacy system deprecated
2. **Two executor types** - Node (class-based) and Cycle (state machine)
3. **Rule persistence** - Requires N consecutive frames to prevent false positives
4. **Caching** - Executors and SOP data are cached per source/manual
5. **Validation** - Structure validated on load, runtime checks during execution
6. **Flexible rules** - Spatial logic, IOU calculations, custom functions
7. **Data sources** - executor_input_data (live), predefined_data (static), derived_data (computed)

---

## 🗣️ SOP → UI/Speech Instruction Flow (Kafka + TTS)  ✅ (Mirrors Instruction Graph)

The SOP path now sends **the same style of Kafka instruction messages** as the legacy instruction graph:

- **Topic**: `config.video_instruction_kafka_topic` (from `.env`)
- **Producer**: `kafka.KafkaProducer`
- **Payload**: JSON string encoded as UTF-8 bytes

### Message Schema (UI/Speech)

SOP emits the same keys the UI expects:

- **Required**: `stepId`, `sessionId`, `manualId`, `step`, `status`, `startTime`, `endTime`, `audioUrl`
- **Optional**: `contextUrl`, `contextType`, `repetition`, `feedback`, `feedbackUrl`, `stepScore`, `videoUrl`

### Where This Happens

- **TTS + Kafka message primitive**: `model/activity_instruction_sender.py` → `send_custom_instruction()`
- **SOP cycle step lifecycle hooks**: `sop_cycle_executor.py`
  - Sends `status="inProgress"` when an activity becomes the current/next SOP step
  - Sends `status="completed"` when the current activity is confirmed/ready
  - Sends `status="failed"` when an anomaly/confirmation anomaly resets the cycle
  - Updates Redis: `vip:{sessionId}:{manualId}:state` with numeric `stepId` (best-effort)

### How Step Completion Is Validated (SOP)

- The SOP cycle executor validates each activity via its configured `activity_rules` + persistence.
- For non-start activities, completion is defined by the executor’s confirmation gate:
  - `_is_activity_confirmed(source_id, activity_id)` must pass
- Once confirmed, SOP emits:
  1. **Completion message**: `status="completed"`
  2. **Next step message**: `status="inProgress"` (with TTS-generated `audioUrl`)

### Special Case (Manual 13)

- `manualId == 13` uses the hardcoded Hindi audio:
  - `https://cdn-dev.eizen.ai/0/via/pine_labs/audios-hindi/demohindi.mp3`

---

## 🔧 Configuration Files

### **Local JSON Files** (`abbjsons/`)
- `pose_sop_master.json` - SOP master configuration
- `pose_activity_rule_map.json` - Activity-to-rules mapping
- `pose_central_rules.json` - Rule definitions

### **MongoDB Collections**
- `sop_master` - SOP definitions
- `sop_activity_rule_map` - Activity rules
- `sop_rule_master` - Rule definitions
- `sop_analytics_template` - Analytics configuration

---

This completes the full SOP system flow! 🎉
