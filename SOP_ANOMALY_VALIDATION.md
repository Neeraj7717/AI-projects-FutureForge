# SOP Anomaly Validation - How It Works

## ✅ Yes, the Rules Are Already in SOP Configuration!

The SOP configuration (`abbjsons/pose_activity_rule_map.json`) already has `anomaly_rules` that validate if activities are performed correctly.

## 📋 Current SOP Configuration for HAND_RAISED

### Activity Rules (What Should Happen)
```json
"activity_rules": [
    {
        "is_person_present": {...}  // Person must be present
    },
    {
        "is_hand_position": {
            "hand_position": "rightHandAbove90"  // RIGHT hand must be above 90
        }
    }
]
```

### Anomaly Rules (What Should NOT Happen)
```json
"anomaly_rules": [
    {
        "is_person_not_present": {
            "threshold": 5  // If person not present for 5 frames → anomaly
        }
    },
    [
        {
            "is_hand_position": {
                "hand_position": "leftHandAbove90"  // LEFT hand above 90 → WRONG!
            }
        },
        {
            "is_hand_position": {
                "hand_position": "leftHandBelow90"  // LEFT hand below 90 → WRONG!
            }
        }
    ]
]
```

**Note:** The `anomaly_rules` use OR logic (the `[...]` array means "any one of these"):
- If `leftHandAbove90` OR `leftHandBelow90` is detected → **Anomaly triggered!**

## 🔄 How the System Validates and Sends Messages

### Scenario: User is IN HAND_RAISED activity but raises LEFT hand

1. **Activity Rules Check** (Line 1134 in `sop_cycle_executor.py`):
   - `is_hand_position` with `rightHandAbove90` → **FAILS** (left hand detected, not right)
   - `current_activity_success = False`

2. **Anomaly Rules Check** (Line 1176 in `sop_cycle_executor.py`):
   - System calls `_check_anomaly_rules(source_id, "HAND_RAISED")`
   - Evaluates `anomaly_rules` from SOP config:
     - `is_hand_position` with `leftHandAbove90` → **PASSES** (left hand detected!)
   - **Result:** `anomaly_detected = True`

3. **Send Anomaly Message** (Line 1186 in `sop_cycle_executor.py`):
   - Calls `detect_and_send_wrong_activity()` with:
     - `activity_id = "HAND_RAISED"`
     - `things_present = ["personPresent", "leftHandAbove90"]`
   - Maps to message: **"I see your left hand raised. Please raise your right hand instead."**
   - Sends via Kafka to UI

4. **Persistence Check** (Line 1227 in `sop_cycle_executor.py`):
   - After persistence threshold (default: 1 frame for left hand rules)
   - If anomaly continues → Calls `_handle_anomaly()` → Resets cycle

## 📊 Complete Flow Diagram

```
User in HAND_RAISED activity
    ↓
Raises LEFT hand instead of RIGHT
    ↓
Activity Rules: ❌ FAIL (expects rightHandAbove90, got leftHandAbove90)
    ↓
Anomaly Rules: ✅ TRIGGER (detects leftHandAbove90 in anomaly_rules)
    ↓
Send Message: "I see your left hand raised. Please raise your right hand instead."
    ↓
After 1 frame persistence → Reset cycle (if continues)
```

## 🎯 Key Points

1. **Rules are in SOP config** - Already configured in `pose_activity_rule_map.json`
2. **Code uses the rules** - `_check_anomaly_rules()` evaluates the SOP's `anomaly_rules`
3. **Immediate feedback** - Message sent as soon as anomaly detected (before persistence)
4. **Cycle reset** - After persistence threshold, cycle resets (matches ABB behavior)

## 🔧 What Was Added to the Code

The code I added (lines 1171-1200 in `sop_cycle_executor.py`) does the following:

1. **When activity rules fail:**
   - First checks if `anomaly_rules` are triggered
   - If yes → Sends anomaly message immediately
   - If no → Still checks for wrong activity via `detect_and_send_wrong_activity()`

2. **Uses existing SOP rules:**
   - No new rules needed in SOP config
   - Uses the `anomaly_rules` already defined in `pose_activity_rule_map.json`

## ✅ Summary

**Yes, the validation rules are in the SOP configuration!** The code I added uses those existing rules to:
- Detect wrong activities (left hand when expecting right)
- Send immediate feedback messages
- Reset cycle after persistence threshold

The system now validates correctness using the SOP's `anomaly_rules` and provides immediate feedback when activities are performed incorrectly.
