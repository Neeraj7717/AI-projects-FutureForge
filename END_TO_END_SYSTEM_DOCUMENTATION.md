# Videos in Action (VIA) - End-to-End System Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture Components](#architecture-components)
3. [Entry Points](#entry-points)
4. [Model Detection Layer](#model-detection-layer)
5. [SOP System Flow](#sop-system-flow)
6. [Instruction & UI Communication](#instruction--ui-communication)
7. [Data Flow](#data-flow)
8. [Configuration](#configuration)
9. [Example Flows](#example-flows)

---

## System Overview

**Videos in Action (VIA)** is a real-time video analysis system that:
- Receives video frames via Kafka or REST API
- Performs AI/ML model detections (Pose, Gender/Age/Emotion)
- Executes Standard Operating Procedures (SOPs) based on detections
- Loads all SOP configurations from MongoDB
- Sends real-time instructions and feedback to users via Kafka
- Tracks activity completion and generates analytics

**Important Notes**:
- **YOLO Object Detection Model**: Was used only for testing SOP functionality and has been removed from the application
- **SOP Configuration**: All SOPs are loaded from MongoDB as the primary and only data source (local JSON files are legacy and not used)

### Key Features
- **Multi-Model Support**: Pose detection (MediaPipe), Gender/Age detection
- **SOP-Based Workflows**: Rule-based activity execution with two types:
  - **Node Executor**: Activities triggered by detected object classes
  - **Cycle Executor**: State machine-based sequential activities
- **Real-Time Communication**: Kafka-based messaging for instructions and feedback
- **Model Management**: Centralized model loading and caching
- **Scalable Architecture**: Thread pool-based processing for high throughput
- **MongoDB-Based SOP Configuration**: All SOPs are loaded from MongoDB as the primary data source

---

## Architecture Components

### 1. **Entry Layer**
- **Kafka Consumer** (`Consumer/consumer_ui.py`): Listens to `via-frame` topic
- **REST API** (`core/main.py`): FastAPI endpoints for direct frame submission

### 2. **Model Layer**
- **Model Manager** (`model/model_manager.py`): Singleton for managing all ML models
- **Pose Model** (`model/pose_model.py`): MediaPipe-based pose detection
- **Gender Model** (`model/gender_model.py`): Age/Gender/Emotion detection
- **Note**: YOLO detection model was used only for testing SOP functionality and has been removed from production

### 3. **SOP Layer**
- **SOP Manager** (`model/sop_manager.py`): Central coordinator for SOP execution
- **SOP Loader** (`sop_loader.py`): Loads SOP configurations from MongoDB/JSON
- **SOP Executor** (`sop_unified_executor.py`): Unified interface for all SOP types
- **Node Executor** (`node_executor.py`): Class-based activity triggering
- **Cycle Executor** (`sop_cycle_executor.py`): State machine-based execution
- **Rule Functions** (`sop_rule_functions.py`): Spatial and logic rule implementations

### 4. **Communication Layer**
- **Activity Instruction Sender** (`model/activity_instruction_sender.py`): Sends instructions via Kafka
- **T2V Service**: Text-to-Voice audio generation
- **Kafka Producer**: Publishes to `video_instruction_kafka_topic`

### 5. **Data Layer**
- **MongoDB**: Primary source for SOP configurations, session data, analytics
- **Redis**: Caches session state
- **Local JSON Files**: Legacy/testing configurations (not used in production)

---

## Entry Points

### 1. Kafka Consumer (Primary Entry Point)

**Location**: `Consumer/consumer_ui.py`

**Flow**:
```
Kafka Topic: 'via-frame'
    ↓
Consumer polls messages (timeout: 10ms)
    ↓
Message contains: {manualId, sourceId, sessionId, frameUri/poseLandMarks, timeStamp}
    ↓
Lookup function from consumer_config.yaml based on manualId
    ↓
Route to appropriate detection function:
    - pose_detection → Pose Model
    - gender_detection → Gender Model
    - Note: action_detection (YOLO) was removed after SOP testing
    ↓
Execute in ThreadPoolExecutor (max_workers: 5000)
```

**Configuration** (`Consumer/consumer_config.yaml`):
```yaml
routing:
  pose_detection: [23, 24, ...]
  gender_detection: [5, 6, ...]
  # Note: action_detection (YOLO) removed after SOP testing
```

**Key Functions**:
- `start_kafka_listener()`: Starts async Kafka consumer
- `process_kafka_message()`: Routes messages to detection functions
- `kafka_listener()`: Main polling loop

### 2. REST API (Alternative Entry Point)

**Location**: `core/main.py`

**Endpoints**:
- `POST /detect-pose`: Pose detection
- `POST /detect-gender`: Gender detection
- `POST /ekyc_detect`: EKYC detection
- `POST /text_detect`: Text detection
- `POST /chair_detect`: Chair detection
- `POST /similar_image`: Similar image search
- `POST /system_monitor`: System monitoring
- **Note**: `/detect` endpoint (YOLO object detection) was removed after SOP testing

**Request Format**:
```json
{
  "file": "base64_encoded_image",
  "sourceId": "source1",
  "sessionId": "session123",
  "manualId": "23",
  "timeStamp": "2024-01-01T00:00:00"
}
```

**Response**: Immediate acknowledgment (processing happens asynchronously)

---

## Model Detection Layer

### 1. Model Manager

**Location**: `model/model_manager.py`

**Purpose**: Centralized singleton for managing all ML models

**Features**:
- Lazy loading: Models load on first use
- Thread-safe: Prevents duplicate loading
- Shared instance: API and Consumer share same models
- Pre-loading option: `load_all_models_at_start=True` in config

**Methods**:
- `get_pose_model()`: Returns Pose model instance
- `get_gender_model()`: Returns Gender model instance
- `load_all_models()`: Pre-loads all models at startup
- **Note**: `get_detector_model()` (YOLO) was removed after SOP testing

### 2. Pose Detection Model

**Location**: `model/pose_model.py`

**Technology**: MediaPipe Pose

**Detection Output**:
```python
things_present = [
    "personPresent",
    "rightHandAbove90",
    "leftHandAbove90",
    "bothHandsAbove90",
    ...
]
```

**Flow**:
```
Input: Base64 image or pose landmarks
    ↓
MediaPipe Pose Detection
    ↓
Extract landmarks (33 keypoints)
    ↓
Calculate hand positions relative to shoulders
    ↓
Generate things_present list
    ↓
Check if SOP configured for manualId
    ↓
If SOP exists → Execute SOP
    ↓
Convert to SOP format: {"Person": [[x1,y1,x2,y2]]}
```

**SOP Integration**:
```python
sop_id = sop_manager.get_sop_id_for_manual(str(manualId), sourceId)
if sop_id:
    self._execute_sop_after_detection(
        sourceId, manualId, results, frame_no,
        things_present, sessionId
    )
```

### 3. Gender Detection Model

**Location**: `model/gender_model.py`

**Technology**: Custom CNN models for age/gender/emotion

**Detection Output**:
```python
gender_data = {
    "age": 25,
    "gender": "male",
    "emotion": "happy",
    ...
}
```

**Flow**: Similar to Pose/Detection models, with SOP integration

---

## SOP System Flow

### Overview

The SOP (Standard Operating Procedure) system is a rule-based workflow engine that:
1. Receives detections from models
2. Matches detections to activities based on `model_class`
3. Evaluates rules (spatial, logic, persistence)
4. Triggers activity transitions
5. Sends instructions to users
6. Tracks completion and generates analytics

### SOP Manager

**Location**: `model/sop_manager.py`

**Responsibilities**:
1. **Resolve SOP ID** from `manualId`
2. **Load SOP Configuration** from MongoDB (primary source)
3. **Create/Cache Executors** per source/manual combination
4. **Execute SOP** with detection data

**SOP ID Resolution Order**:
```
1. Check cache (manualId → sop_id mapping)
2. Query MongoDB "manual" collection: manual.sop_id
3. Query "sop_activity_rule_map" collection
4. Try common patterns (EZA_SOP_POSE, EZA_SOP_PHONE_ASSEMBLY, etc.)
```

**Note**: Local JSON files are no longer used. All SOPs are loaded from MongoDB as the primary and only source in production.

**Executor Caching**:
```python
cache_key = f"{sourceId}:{manualId}:{sop_id}"
if cache_key in self.executors:
    return self.executors[cache_key]  # Reuse existing executor
```

### SOP Loader

**Location**: `sop_loader.py`

**Data Source**: **MongoDB** (Primary and only source in production)

**MongoDB Collections**:
- `sop_master`: SOP definitions (contains sopId, type, activities, startActivity, endActivity)
- `sop_activity_rule_map`: Activity-to-rules mapping (contains rules_map with activity_rules, anomaly_rules, predefined_values)
- `sop_rule_master`: Rule definitions (contains rule_name, desc, input, output)
- `sop_analytics_template`: Analytics configuration

**Note**: Local JSON files are legacy and no longer used. All SOP configurations are stored and loaded from MongoDB.

**SOP Data Structure**:
```python
{
    "sop_master": {
        "sopId": "EZA_SOP_POSE",
        "type": "cycle",  # or "node"
        "activities": [
            {
                "activityId": "PERSON_PRESENT",
                "model_class": ["Person"],
                "model_id": "mediapipe",
                "prevAct": [],
                "nextAct": ["HAND_RAISED"]
            },
            ...
        ],
        "startActivity": ["PERSON_PRESENT"],
        "endActivity": ["HANDS_DOWN"]
    },
    "sop_activity_rule_map": {
        "rules_map": [
            {
                "activity_id": "PERSON_PRESENT",
                "activity_rules": [...],
                "anomaly_rules": [...],
                "predefined_values": {...}
            },
            ...
        ]
    },
    "sop_rules": [
        {
            "rule_name": "is_point_inside_box",
            "desc": "Check if point is inside box",
            "input": ["primary_box", "secondary_box"],
            "output": ["decision", "center"]
        },
        ...
    ]
}
```

### SOP Executor (Unified Interface)

**Location**: `sop_unified_executor.py`

**Purpose**: Provides unified interface for both Node and Cycle executors

**Flow**:
```
SOPExecutor.__init__(sop_data)
    ↓
Extract sop_type from sop_master.type
    ↓
Select executor:
    - "node" → NodeExecutor
    - "cycle" → CycleExecutor
    ↓
Initialize executor with sop_data
```

**Methods**:
- `set_input_data(data)`: Set frame data
- `execute_all()`: Execute all activities
- `reset()`: Clear temporary state
- `reset_state()`: Full reset between sessions

### Node Executor

**Location**: `node_executor.py`

**Triggering Logic**: Activities trigger when detected classes match `model_class`

**Flow**:
```
For each activity in sequence:
    ↓
Check if detected_classes match activity.model_class
    ↓
If match:
    ↓
    Load predefined_values for activity
    ↓
    Execute activity_rules
    ↓
    Execute anomaly_rules
    ↓
    Update derived_data
    ↓
If no match:
    ↓
    Skip activity
```

**Example**:
```python
# Activity config
{
    "activityId": "PHONE_BODY_PRESENT",
    "model_class": ["cell phone"]
}

# Detections
detections = {"cell phone": [[x1,y1,x2,y2]]}

# Result: Activity triggers because "cell phone" in detected_classes
```

### Cycle Executor

**Location**: `sop_cycle_executor.py`

**Triggering Logic**: State machine with sequential transitions

**Flow**:
```
Check if cycle should start (start_activity conditions)
    ↓
If cycle not active:
    ↓
    Check start_activity rules
    ↓
    If rules pass (with persistence):
        ↓
        Start cycle
        ↓
        Set current_activity = start_activity
        ↓
If cycle active:
    ↓
    Execute current_activity rules
    ↓
    If rules pass (with persistence):
        ↓
        Transition to next_activity
        ↓
        If next_activity == end_activity:
            ↓
            Check if start_activity detected again
            ↓
            If yes: Complete cycle, restart
```

**Persistence**: Rules must pass for N consecutive frames before transition

**Example**:
```python
# Activity sequence
startActivity: "PERSON_PRESENT"
    ↓
nextAct: "HAND_RAISED"
    ↓
nextAct: "HANDS_DOWN"
    ↓
endActivity: "HANDS_DOWN"
    ↓
(next cycle starts when PERSON_PRESENT detected again)
```

### Rule Evaluation

**Location**: `sop_rule_functions.py`

**Rule Types**:

1. **Spatial Rules**:
   - `is_point_inside_box(primary_box, secondary_box)`: Check if point is inside box
   - `is_carrying_item(primary_box, secondary_box, threshold)`: Check if carrying item
   - `calculate_iou(box1, box2)`: Calculate Intersection over Union
   - `get_center(bbox)`: Get center point of bounding box

2. **Logic Rules**:
   - AND/OR groups for multiple rules
   - Persistence checks (N consecutive frames)

**Rule Input Resolution**:
```python
# Rule input: "detections.Gripper"
# Resolves to: executor_input_data["detections"]["Gripper"]

# Rule input: "predefined.Zone1"
# Resolves to: predefined_data["Zone1"]

# Rule input: "derived_data.decision"
# Resolves to: derived_data["decision"]
```

**Rule Execution**:
```python
# Rule definition
{
    "is_point_inside_box": {
        "primary_box": "detections.Gripper",
        "secondary_box": "predefined.Zone1"
    }
}

# Execution
primary_box = executor_input_data["detections"]["Gripper"]
secondary_box = predefined_data["Zone1"]
result = is_point_inside_box(primary_box, secondary_box)
# Returns: {"decision": True, "center": (500, 300), "inside": True}
```

---

## Instruction & UI Communication

### Activity Instruction Sender

**Location**: `model/activity_instruction_sender.py`

**Purpose**: Sends real-time instructions to UI via Kafka

**Kafka Topic**: `video_instruction_kafka_topic` (from config)

**Message Format**:
```json
{
    "stepId": "123456",
    "sessionId": "session123",
    "manualId": "23",
    "sourceId": "source1",
    "step": "Please raise your right hand",
    "status": "inProgress",  // or "completed", "failed"
    "audioUrl": "https://cdn-dev.eizen.ai/.../audio.mp3",
    "videoUrl": "",
    "startTime": "2024-01-01T00:00:00.000000+00:00",
    "endTime": "",
    "stepScore": "",
    "repetition": 0,
    "contextUrl": "",
    "contextType": "",
    "feedback": "",
    "feedbackUrl": "",
    "activityId": "HAND_RAISED",
    "cycleCount": 1,
    "frameNumber": 123
}
```

### Instruction Flow

**When Activity Starts**:
```
Activity becomes current_activity
    ↓
Get instruction text from activity_instructions mapping
    ↓
Generate audio via T2V endpoint
    ↓
Send Kafka message with status="inProgress"
```

**When Activity Completes**:
```
Activity rules pass (with persistence)
    ↓
Send completion message: status="completed"
    ↓
Send next activity message: status="inProgress"
```

**When Activity Fails**:
```
Anomaly detected or wrong activity performed
    ↓
Send anomaly message: status="failed"
    ↓
Include corrective feedback
```

### Activity Instruction Mapping

**Default Instructions**:
```python
{
    "PERSON_PRESENT": "Please stand",
    "HAND_RAISED": "Please raise your right hand",
    "LEFT_HAND_RAISED": "Please raise your left hand",
    "HANDS_DOWN": "Please lower your right hand",
    "PHONE_BODY_PRESENT": "Show the phone body",
    "SCREEN_ATTACHED": "Show the display or screen",
    ...
}
```

**Wrong Activity Messages**:
```python
{
    ("HAND_RAISED", "leftHandAbove90"): "I see your left hand raised. Please raise your right hand instead.",
    ("HAND_RAISED", "bothHandsAbove90"): "You are raising both hands. Please raise only your right hand.",
    ...
}
```

### T2V (Text-to-Voice) Integration

**Endpoint**: `config.t2v_endpoint`

**Request**:
```json
{
    "text": "Please raise your right hand",
    "gender": 1
}
```

**Response**:
```json
{
    "file_path": "https://cdn-dev.eizen.ai/.../audio.mp3"
}
```

**Special Case**: Manual ID 13 uses hardcoded Hindi audio:
```
https://cdn-dev.eizen.ai/0/via/pine_labs/audios-hindi/demohindi.mp3
```

---

## Data Flow

### Complete End-to-End Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. FRAME RECEPTION                                              │
│                                                                 │
│ Option A: Kafka Consumer                                       │
│   Topic: 'via-frame'                                            │
│   Message: {manualId, sourceId, sessionId, frameUri, ...}     │
│                                                                 │
│ Option B: REST API                                              │
│   POST /detect-pose, /detect, /detect-gender                   │
│   Body: {file, sourceId, sessionId, manualId, ...}            │
└──────────────────────┬────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. ROUTING                                                      │
│                                                                 │
│ consumer_config.yaml: manualId → function_name                │
│   - pose_detection → Pose Model                                 │
│   - action_detection → Detection Model                         │
│   - gender_detection → Gender Model                            │
└──────────────────────┬────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. MODEL DETECTION                                              │
│                                                                 │
│ Model Manager (Singleton):                                     │
│   - Lazy loads models on first use                             │
│   - Thread-safe loading                                        │
│   - Shared between API and Consumer                            │
│                                                                 │
│ Detection Models:                                              │
│   - Pose: MediaPipe → things_present list                      │
│   - Gender: CNN → age/gender/emotion                            │
│   - Note: YOLO detection was removed after SOP testing        │
└──────────────────────┬────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. DETECTION FORMAT CONVERSION                                  │
│                                                                 │
│ Pose → SOP Format:                                             │
│   things_present = ["personPresent", "rightHandAbove90"]      │
│   detections = {"Person": [[x1,y1,x2,y2]]}                    │
│                                                                 │
│ Gender → SOP Format:                                           │
│   gender_data = {"age": 25, "gender": "male", ...}           │
│   Additional data passed to SOP executor                       │
└──────────────────────┬────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. SOP MANAGER                                                  │
│                                                                 │
│ get_sop_id_for_manual(manualId, sourceId):                   │
│   1. Check cache                                                │
│   2. Query MongoDB "manual" collection: manual.sop_id        │
│   3. Query "sop_activity_rule_map" collection                 │
│   4. Try common patterns (EZA_SOP_POSE, etc.)                 │
│                                                                 │
│ get_executor(sourceId, manualId, sop_id):                     │
│   1. Check executor cache                                      │
│   2. Load SOP data from MongoDB (primary source)             │
│   3. Create executor (NodeExecutor or CycleExecutor)           │
│   4. Cache executor                                            │
└──────────────────────┬────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. SOP EXECUTION                                                │
│                                                                 │
│ executor.set_input_data({                                      │
│   "detections": {...},                                          │
│   "frame_number": 123,                                          │
│   "source_id": "source1",                                      │
│   "things_present": [...]                                       │
│ })                                                              │
│                                                                 │
│ result = executor.execute_all()                                │
│                                                                 │
│ Node Executor:                                                  │
│   - Check model_class match                                     │
│   - Execute matching activities                                 │
│                                                                 │
│ Cycle Executor:                                                 │
│   - State machine transitions                                   │
│   - Rule persistence (N consecutive frames)                    │
│   - Cycle completion tracking                                  │
└──────────────────────┬────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. RULE EVALUATION                                              │
│                                                                 │
│ For each activity:                                              │
│   - Resolve rule inputs (detections, predefined, derived)       │
│   - Execute rule functions (spatial, logic)                     │
│   - Check persistence (N consecutive frames)                    │
│   - Update derived_data                                         │
└──────────────────────┬────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│ 8. INSTRUCTION GENERATION                                       │
│                                                                 │
│ Activity Instruction Sender:                                    │
│   - Get instruction text for activity                            │
│   - Generate audio via T2V endpoint                            │
│   - Send Kafka message to video_instruction_kafka_topic       │
│                                                                 │
│ Message Types:                                                  │
│   - status="inProgress": Activity started                       │
│   - status="completed": Activity completed                     │
│   - status="failed": Anomaly detected                           │
└──────────────────────┬────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 9. UI RECEPTION                                                 │
│                                                                 │
│ UI Consumer:                                                    │
│   - Listens to video_instruction_kafka_topic                   │
│   - Displays instructions                                       │
│   - Plays audio                                                 │
│   - Shows feedback                                              │
└─────────────────────────────────────────────────────────────────┘
```

### Data Sources

**1. executor_input_data** (Live, per frame):
```python
{
    "source_id": "source1",
    "detections": {"Person": [[x1,y1,x2,y2]]},
    "frame_number": 123,
    "frame_id": 123,
    "timestamp": "2024-01-01T00:00:00",
    "things_present": ["personPresent", "rightHandAbove90"],
    "pose_landmarks": {...},
    "sessionId": "session123",
    "manualId": "23"
}
```

**2. predefined_data** (Static, loaded once):
```python
{
    "Zone1": [[x1,y1,x2,y2]],
    "Zone2": [[x1,y1,x2,y2]],
    "threshold": 0.1,
    "models": {...}
}
```

**3. derived_data** (Computed, updated by rules):
```python
{
    "decision": True,
    "center": (500, 300),
    "iou": 0.85,
    "carrying": True
}
```

---

## Configuration

### Environment Variables (`.env`)

```bash
# Kafka
kafka_url=localhost:9092
video_instruction_kafka_topic=via-instruction

# MongoDB
mongo_connection_string_stateless=mongodb://localhost:27017
database_name=via_db

# Models
load_all_models_at_start=false
# Note: YOLO model path removed - YOLO was only for SOP testing

# Services
t2v_endpoint=http://localhost:8000/t2v
llava_endpoint=http://localhost:8001/llava

# Redis
redis_host=localhost
redis_port=6379
redis_db=0

# Processing
fps=30
pose_fps=15
continuity=5
pose_continuity=5

# Port
port_number=8078
```

### Consumer Configuration (`Consumer/consumer_config.yaml`)

```yaml
routing:
  pose_detection:
    - 23
    - 24
  action_detection:
    - 1
    - 2
  gender_detection:
    - 5
    - 6
```

### SOP Configuration (MongoDB)

**Collection: `sop_master`**
```json
{
    "_id": ObjectId("..."),
    "sopId": "EZA_SOP_POSE",
    "type": "cycle",
    "activities": [...],
    "startActivity": ["PERSON_PRESENT"],
    "endActivity": ["HANDS_DOWN"]
}
```

**Collection: `sop_activity_rule_map`**
```json
{
    "_id": ObjectId("..."),
    "sop_id": "EZA_SOP_POSE",
    "rules_map": [
        {
            "activity_id": "PERSON_PRESENT",
            "activity_rules": [...],
            "anomaly_rules": [...],
            "predefined_values": {...}
        }
    ]
}
```

---

## Example Flows

### Example 1: Pose Detection → SOP Execution

**Scenario**: User performs pose-based exercise (manualId=23)

**Flow**:
```
1. Frame arrives via Kafka
   Message: {manualId: 23, frameUri: "base64...", ...}

2. Routing
   consumer_config.yaml: 23 → pose_detection

3. Pose Detection
   MediaPipe detects: personPresent, rightHandAbove90
   things_present = ["personPresent", "rightHandAbove90"]

4. SOP Resolution
   sop_manager.get_sop_id_for_manual("23", "source1")
   → Returns: "EZA_SOP_POSE"

5. SOP Execution
   - Load SOP: EZA_SOP_POSE (type: cycle)
   - Create CycleExecutor
   - Convert to SOP format: {"Person": [[x1,y1,x2,y2]]}

6. Cycle Execution
   - Check start_activity: PERSON_PRESENT
   - Rules pass → Start cycle
   - Current activity: PERSON_PRESENT
   - Transition to: HAND_RAISED

7. Instruction
   - Activity: HAND_RAISED
   - Text: "Please raise your right hand"
   - Generate audio via T2V
   - Send Kafka message: status="inProgress"

8. User performs action
   - rightHandAbove90 detected
   - Rules pass (5 consecutive frames)
   - Transition to: HANDS_DOWN

9. Completion
   - Activity: HAND_RAISED completed
   - Send: status="completed"
   - Next activity: HANDS_DOWN
   - Send: status="inProgress"
```

### Example 2: Gender Detection → SOP Execution

**Scenario**: Gender-based workflow (manualId=5)

**Flow**:
```
1. Frame arrives via Kafka
   Message: {manualId: 5, frameUri: "base64...", ...}

2. Routing
   consumer_config.yaml: 5 → gender_detection

3. Gender Detection
   CNN detects: age=25, gender="male", emotion="happy"
   gender_data = {"age": 25, "gender": "male", "emotion": "happy"}

4. SOP Resolution
   sop_manager.get_sop_id_for_manual("5", "source1")
   → Returns: "EZA_SOP_GENDER" (from MongoDB)

5. SOP Execution
   - Load SOP from MongoDB: EZA_SOP_GENDER (type: cycle)
   - Create CycleExecutor
   - Pass gender_data as additional_data

6. Cycle Execution
   - Start activity: PERSON_DETECTED
   - Check rules based on gender_data
   - Transition to next activity based on rule evaluation

7. Instruction
   - Activity-specific instruction sent
   - Generate audio via T2V
   - Send Kafka message: status="inProgress"

8. Completion
   - Activity rules pass
   - Send: status="completed"
   - Analytics updated
```

### Example 3: Node Executor (Class-Based Triggering)

**Scenario**: Multiple detections from Pose model

**Flow**:
```
1. Pose Detection
   MediaPipe detects: personPresent, rightHandAbove90, leftHandAbove90
   things_present = ["personPresent", "rightHandAbove90", "leftHandAbove90"]
   detections = {"Person": [[x1,y1,x2,y2]]}

2. SOP Execution (Node Type)
   - Activity 1: model_class=["Person"]
     → Triggers (Person detected)
   - Activity 2: Checks things_present for specific conditions
     → Triggers if conditions met
   - Activity 3: model_class=["Tool"]
     → Skips (Tool not detected)

3. Parallel Execution
   - Matching activities execute simultaneously
   - Each evaluates its own rules
   - Results aggregated in ExecutionResult
```

---

## Key Design Decisions

### 1. **Model Manager Singleton**
- **Why**: Prevents duplicate model loading, saves memory
- **Benefit**: Shared models between API and Consumer

### 2. **Executor Caching**
- **Why**: SOP loading is expensive, executors are stateless per frame
- **Benefit**: Faster execution, reduced database queries

### 3. **Rule Persistence**
- **Why**: Prevents false positives from single-frame detections
- **Benefit**: More reliable activity transitions

### 4. **Unified Executor Interface**
- **Why**: Supports both Node and Cycle SOPs with same API
- **Benefit**: Easier to maintain, consistent behavior

### 5. **Kafka-Based Communication**
- **Why**: Decouples processing from UI, supports multiple consumers
- **Benefit**: Scalable, fault-tolerant

### 6. **Thread Pool Processing**
- **Why**: Handle high-throughput video streams
- **Benefit**: Parallel processing, non-blocking API responses

---

## Troubleshooting

### Common Issues

**1. Models Not Loading**
- Check: `load_all_models_at_start` in config
- Check: Model file paths in `.env`
- Check: GPU availability (if required)

**2. SOP Not Executing**
- Check: SOP ID resolution from MongoDB
- Check: MongoDB connection and collections (sop_master, sop_activity_rule_map)
- Check: SOP validation (structure, rules)
- Check: Model class matching (detected classes vs activity.model_class)

**3. Instructions Not Sending**
- Check: Kafka producer connection
- Check: `video_instruction_kafka_topic` in config
- Check: T2V endpoint availability

**4. Rules Not Passing**
- Check: Rule input resolution (detections, predefined, derived)
- Check: Persistence requirements (N consecutive frames)
- Check: Rule function implementations

---

## Summary

The Videos in Action system provides a complete end-to-end solution for:
- **Real-time video analysis** using multiple AI/ML models
- **Rule-based workflow execution** via SOP system
- **User guidance** through real-time instructions and feedback
- **Scalable architecture** supporting high-throughput processing

The system is designed to be:
- **Modular**: Each component can be updated independently
- **Extensible**: New models, SOPs, and rules can be added easily
- **Reliable**: Persistence checks, error handling, caching
- **Performant**: Thread pools, model caching, executor reuse

---

**Document Version**: 1.0  
**Last Updated**: 2024  
**Maintained By**: VIA Development Team
