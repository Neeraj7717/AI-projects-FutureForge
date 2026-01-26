# How Models Identify and Trigger SOPs

## Overview
This document explains how the system identifies which model to use and how it triggers the corresponding SOP (Standard Operating Procedure).

---

## 🔄 Complete Flow: Model → SOP Triggering

```
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: Model Detection (Automatic)                            │
│                                                                 │
│ Models run independently based on incoming video frames:       │
│ • Pose Model (MediaPipe) → Detects person, hand positions      │
│ • Detection Model (YOLO) → Detects objects (cell phone, etc.)  │
│ • Gender Model → Detects gender/age                             │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: Model Calls SOP Manager                                │
│                                                                 │
│ After detection, each model checks if SOP is configured:       │
│                                                                 │
│ pose_model.py:                                                 │
│   sop_id = sop_manager.get_sop_id_for_manual(manualId, sourceId)│
│   if sop_id:                                                    │
│       _execute_sop_after_detection(...)                         │
│                                                                 │
│ detections.py:                                                 │
│   sop_id = sop_manager.get_sop_id_for_manual(manualId, sourceId)│
│   if sop_id:                                                    │
│       _execute_sop_after_action_detection(...)                  │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: SOP Manager Resolves SOP ID                            │
│                                                                 │
│ sop_manager.get_sop_id_for_manual(manualId, sourceId):       │
│                                                                 │
│ 1. Check cache (manualId → sop_id mapping)                     │
│ 2. Query MongoDB "manual" collection:                          │
│    manual = db["manual"].find_one({"_id": manualId})           │
│    if "sop_id" in manual: return manual["sop_id"]             │
│ 3. Query "sop_activity_rule_map" collection:                  │
│    rule_map = db["sop_activity_rule_map"].find_one(...)        │
│    if found: return rule_map["sop_id"]                         │
│ 4. Try local JSON files:                                        │
│    - pose_activity_rule_map.json (for pose SOP)                 │
│    - phone_assembly/sop_activity_rule_mapper.json               │
│    - gender_detection/gender_activity_rule_map.json             │
│ 5. Try common patterns:                                        │
│    - EZA_SOP_POSE, EZA_SOP_PHONE_ASSEMBLY, etc.                │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: SOP Manager Loads SOP Configuration                    │
│                                                                 │
│ sop_manager._load_sop_data(sop_id):                             │
│                                                                 │
│ 1. Try local JSON files first (for testing):                     │
│    - phone_assembly/sop_master.json                             │
│    - pose_detection/pose_sop_master.json                        │
│    - gender_detection/gender_sop_master.json                     │
│                                                                 │
│ 2. Fallback to MongoDB:                                        │
│    - sop_master collection                                      │
│    - sop_activity_rule_map collection                           │
│    - sop_rule_master collection                                 │
│                                                                 │
│ Returns:                                                        │
│ {                                                               │
│   "sop_master": {...},                                          │
│   "sop_activity_rule_map": {...},                              │
│   "sop_rules": [...]                                            │
│ }                                                               │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 5: SOP Executor Created                                   │
│                                                                 │
│ sop_manager.get_executor(sourceId, manualId, sop_id):          │
│                                                                 │
│ 1. Create cache key: f"{sourceId}:{manualId}:{sop_id}"         │
│ 2. Check if executor already exists (cached)                    │
│ 3. If not, create new executor:                                 │
│    executor = create_executor(sop_data, sop_id, ...)           │
│ 4. Executor determines SOP type from sop_master:                │
│    - "type": "node" → NodeExecutor                              │
│    - "type": "cycle" → CycleExecutor                            │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 6: Model Detection Data Converted to SOP Format            │
│                                                                 │
│ Each model converts its detections to standard format:          │
│                                                                 │
│ Pose Model:                                                     │
│   things_present = ["personPresent", "rightHandAbove90"]       │
│   → additional_data = {"things_present": things_present}       │
│                                                                 │
│ YOLO Detection Model:                                           │
│   detections = {                                                │
│     "cell phone": [[x1, y1, x2, y2]],                          │
│     "Gripper": [[x1, y1, x2, y2], [x1, y1, x2, y2]]           │
│   }                                                             │
│                                                                 │
│ Input to executor:                                              │
│ {                                                               │
│   "detections": detections,                                     │
│   "frame_number": frame_no,                                     │
│   "source_id": sourceId,                                        │
│   "manualId": manualId,                                         │
│   ...additional_data                                            │
│ }                                                               │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 7: Activity Triggering Based on model_class               │
│                                                                 │
│ The SOP configuration contains activities with model_class:    │
│                                                                 │
│ Example from phone_assembly/sop_master.json:                   │
│ {                                                               │
│   "activityId": "PHONE_BODY_PRESENT",                          │
│   "model_class": ["cell phone"],  ← This identifies the model! │
│   "model_id": "yolov8n",          ← Specific model version     │
│   "activity_rules": [...],                                       │
│   "nextAct": ["SCREEN_ATTACHED"]                                │
│ }                                                               │
│                                                                 │
│ How activities are triggered:                                   │
│                                                                 │
│ A. Node Executor (node type SOP):                               │
│    - Checks if detected classes match activity.model_class      │
│    - If "cell phone" detected AND activity has model_class:    │
│      ["cell phone"] → Activity triggers                         │
│                                                                 │
│ B. Cycle Executor (cycle type SOP):                             │
│    - Uses state machine (prevAct → current → nextAct)          │
│    - Evaluates activity_rules (which may check model_class)     │
│    - Transitions based on rule evaluation                      │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 8: Rule Evaluation                                         │
│                                                                 │
│ For each triggered activity:                                    │
│                                                                 │
│ 1. Execute activity_rules:                                      │
│    - Rules check detections against predefined values           │
│    - Example: "check_cell_phone_present" rule                   │
│                                                                 │
│ 2. Execute anomaly_rules:                                      │
│    - Check for violations                                       │
│    - Example: "check_phone_missing" rule                        │
│                                                                 │
│ 3. Update derived_data:                                         │
│    - Store results for next activities                         │
│    - Update analytics/KPI data                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔑 Key Concepts

### 1. **Model Identification via `model_class`**

The `model_class` field in each activity tells the system **which type of detections** are needed for that activity:

```json
{
  "activityId": "PHONE_BODY_PRESENT",
  "model_class": ["cell phone"],  // ← Needs "cell phone" detection
  "model_id": "yolov8n"           // ← Uses YOLO v8n model
}
```

**How it works:**
- When YOLO detects "cell phone" → The detection dict contains `{"cell phone": [[x1,y1,x2,y2]]}`
- The executor checks: Does `"cell phone"` exist in `detected_classes`?
- If yes → Activity can trigger (if other conditions are met)

### 2. **SOP Selection via `manualId`**

The system uses `manualId` to find the correct SOP:

```python
# In pose_model.py or detections.py:
sop_id = sop_manager.get_sop_id_for_manual(str(manualId), sourceId)
```

**Resolution order:**
1. **Cache** - Check if `manualId → sop_id` mapping exists
2. **MongoDB manual collection** - `manual.sop_id` field
3. **MongoDB sop_activity_rule_map** - Search by `sop_id` patterns
4. **Local JSON files** - Based on SOP type (pose, phone_assembly, gender)
5. **Common patterns** - Try `EZA_SOP_POSE`, `EZA_SOP_PHONE_ASSEMBLY`, etc.

### 3. **Model Execution Flow**

**Pose Model:**
```python
# model/pose_model.py
def process_squat_analysis(self, sessionId, frame, things_present, sourceId, manualId, ...):
    # Check if SOP is configured
    sop_id = sop_manager.get_sop_id_for_manual(str(manualId), sourceId)
    if sop_id:
        # Execute SOP with pose detections
        self._execute_sop_after_detection(
            sourceId, manualId, results, frame_no, 
            things_present, sessionId
        )
```

**YOLO Detection Model:**
```python
# model/detections.py
def _execute_sop_after_action_detection(self, sourceId, sessionId, manualId, xyxy, cls_ids, names, ...):
    # Convert YOLO detections to SOP format
    detections = {}
    for i, box in enumerate(xyxy):
        cls_id = int(cls_ids[i])
        class_name = names.get(cls_id, f"Class_{cls_id}")
        detections[class_name] = detections.get(class_name, []) + [box.tolist()]
    
    # Execute SOP
    sop_manager.execute_sop(
        sourceId=sourceId,
        manualId=str(manualId),
        detections=detections,  # {"cell phone": [[x1,y1,x2,y2]], ...}
        frame_number=frame_no,
        ...
    )
```

### 4. **Activity Triggering Logic**

**Node Executor** (for node-type SOPs):
```python
# node_executor.py
def _should_trigger_activity(self, activity_id: str) -> bool:
    activity_config = self._activity_rules_map.get(activity_id, {})
    model_classes = activity_config.get("model_class", [])
    
    # If no model_class defined, activity always runs
    if not model_classes:
        return True
    
    # Get detected classes from input data
    detected_classes = list(self.executor_input_data.get("detections", {}).keys())
    
    # Check if any detected class matches
    for detected in detected_classes:
        if detected in model_classes:
            return True
    
    return False
```

**Cycle Executor** (for cycle-type SOPs):
- Uses state machine transitions (prevAct → current → nextAct)
- Activities trigger based on rule evaluation, not direct class matching
- `model_class` is used indirectly in rules (e.g., "check_cell_phone_present" rule)

---

## 📋 Example: Phone Assembly SOP

### Configuration (`phone_assembly/sop_master.json`):

```json
{
  "sopId": "EZA_SOP_PHONE_ASSEMBLY",
  "type": "cycle",
  "startActivity": ["PHONE_BODY_PRESENT"],
  "activities": [
    {
      "activityId": "PHONE_BODY_PRESENT",
      "model_class": ["cell phone"],  // ← Needs "cell phone" detection
      "model_id": "yolov8n",          // ← Uses YOLO model
      "nextAct": ["SCREEN_ATTACHED"]
    },
    {
      "activityId": "SCREEN_ATTACHED",
      "model_class": ["cell phone"],  // ← Also needs "cell phone"
      "model_id": "yolov8n",
      "prevAct": ["PHONE_BODY_PRESENT"],
      "nextAct": ["COMPONENTS_PLACED"]
    }
  ]
}
```

### Execution Flow:

1. **YOLO Model** detects "cell phone" in frame
2. **detections.py** calls `sop_manager.execute_sop()` with:
   ```python
   detections = {"cell phone": [[x1, y1, x2, y2]]}
   ```
3. **SOP Manager** resolves `sop_id = "EZA_SOP_PHONE_ASSEMBLY"` from `manualId`
4. **Cycle Executor** checks if `startActivity` ("PHONE_BODY_PRESENT") rules pass
5. **Rule Evaluation** checks if "cell phone" is present (matches `model_class`)
6. **Activity Triggers** → Cycle starts
7. **State Machine** progresses: PHONE_BODY_PRESENT → SCREEN_ATTACHED → ...

---

## 🎯 Summary

**To execute an SOP, you need:**

1. **Model Detection** - A model (Pose, YOLO, Gender) must detect something
2. **SOP Configuration** - The `manualId` must map to a `sop_id` 
3. **Activity Configuration** - Activities must have `model_class` matching detected classes
4. **Rule Evaluation** - Activity rules must pass for the activity to trigger

**The system identifies which model to use by:**
- `model_class` field in activities → Tells which detections are needed
- `model_id` field → Specifies the exact model (e.g., "yolov8n")
- Detection results → Must contain classes matching `model_class`

**The system triggers the SOP by:**
- `manualId` → Resolves to `sop_id` via SOP Manager
- `sop_id` → Loads SOP configuration (sop_master, rules, etc.)
- Detections → Match against `model_class` in activities
- Rules → Evaluate to determine activity transitions
