# Activity Instruction System

## Overview

The Activity Instruction System automatically sends speech instructions to the UI via Kafka when activities start in the SOP cycle. It also repeats instructions if activities are not completed correctly.

## How It Works

### 1. **Activity Detection & Instruction Mapping**

When an activity starts, the system automatically maps it to a speech instruction:

| Activity | Instruction |
|----------|-------------|
| `PERSON_PRESENT` | "Please stand" |
| `HAND_RAISED` | "Please raise your right hand" |
| `HANDS_DOWN` | "Please lower your right hand" |
| `LEFT_HAND_RAISED` | "Please raise your left hand" |
| `LEFT_HAND_DOWN` | "Please lower your left hand" |
| `BOTH_HANDS_RAISED` | "Please raise both hands" |
| `BOTH_HANDS_DOWN` | "Please lower both hands" |

### 2. **Instruction Sending Flow**

```
Activity Starts → Generate Speech → Send to Kafka → UI Receives → Speech AI Speaks
```

1. **Activity Transition Detected**: When SOP cycle transitions to a new activity
2. **Instruction Generated**: System maps activity to instruction text
3. **Audio Generated**: Text-to-Voice (T2V) API generates audio file
4. **Kafka Message Sent**: Instruction sent to `video_instruction_kafka_topic`
5. **UI Receives**: Frontend receives message and plays audio

### 3. **Instruction Repetition Logic**

The system tracks activity completion and repeats instructions if needed:

- **Tracks Failures**: Counts consecutive frames where activity rules fail
- **Repeats After 3 Failures**: After 3 consecutive failures (~1 second at 30fps)
- **Repeat Message**: Adds "Please try again. " prefix to instruction
- **Prevents Spam**: Only repeats if 60+ frames have passed since last instruction

### 4. **Kafka Message Format**

```json
{
  "sessionId": "session_123",
  "manualId": "23",
  "sourceId": "6",
  "step": "Please raise your right hand",
  "stepId": "ACTIVITY_HAND_RAISED",
  "status": "inProgress",
  "audioUrl": "https://cdn.example.com/audio.mp3",
  "activityId": "HAND_RAISED",
  "cycleCount": 1,
  "frameNumber": 126,
  "isRepeat": false,
  "repetition": 0
}
```

## Integration Points

### In SOP Cycle Executor

1. **Cycle Start** (`_start_cycle`):
   - Sends instruction for starting activity (e.g., "Please stand")

2. **Activity Transition** (`_transition_to_activity`):
   - Sends instruction for new activity (e.g., "Please raise your right hand")
   - Resets failure count for new activity

3. **Activity Check** (`_check_activity_transition`):
   - Monitors current activity completion
   - Triggers instruction repetition if activity fails

## Configuration

### Activity Instruction Mapping

Edit `model/activity_instruction_sender.py` to customize instructions:

```python
self.activity_instructions = {
    "PERSON_PRESENT": "Please stand",
    "HAND_RAISED": "Please raise your right hand",
    # Add more mappings...
}
```

### Failure Threshold

Adjust in `sop_cycle_executor.py`:

```python
# Repeat after 3 consecutive failures
if consecutive_failures >= 3:
    # Send repeat instruction
```

### Repeat Interval

Adjust in `activity_instruction_sender.py`:

```python
# Only repeat if 60+ frames have passed
if (frame_number - last_frame) >= 60:
    # Send repeat instruction
```

## Example Flow

### Cycle 1: Stand → Raise Hand → Lower Hand

1. **Frame 1**: Cycle starts
   - Activity: `PERSON_PRESENT`
   - Instruction: "Please stand" ✅
   - Sent to Kafka

2. **Frame 126**: Transition detected
   - Activity: `HAND_RAISED`
   - Instruction: "Please raise your right hand" ✅
   - Sent to Kafka

3. **Frames 127-178**: User raising hand
   - Activity: `HAND_RAISED`
   - Rules checking: ✅ Passing
   - No repeat needed

4. **Frame 268**: Transition detected
   - Activity: `HANDS_DOWN`
   - Instruction: "Please lower your right hand" ✅
   - Sent to Kafka

5. **Frame 269**: Cycle completes
   - All activities completed successfully ✅

### Example: Activity Not Completed

1. **Frame 200**: Activity `HAND_RAISED` starts
   - Instruction: "Please raise your right hand" ✅

2. **Frames 201-203**: Activity rules failing
   - Failure count: 1, 2, 3
   - After 3 failures: Repeat instruction
   - Instruction: "Please try again. Please raise your right hand" ✅

3. **Frame 224**: User finally raises hand
   - Activity rules: ✅ Passing
   - Failure count reset: 0
   - Transition to next activity

## Files Modified

1. **`model/activity_instruction_sender.py`** (NEW)
   - Activity instruction sender class
   - Kafka integration
   - T2V audio generation
   - Instruction repetition logic

2. **`sop_cycle_executor.py`** (MODIFIED)
   - Added `_send_activity_instruction()` method
   - Added `_check_and_repeat_instruction()` method
   - Integrated into `_start_cycle()` and `_transition_to_activity()`
   - Added failure tracking in `_check_activity_transition()`
   - Added `session_id` and `manual_id` storage in `SourceState`

## Testing

To test the system:

1. **Start SOP cycle**: Should send "Please stand" instruction
2. **Raise hand**: Should send "Please raise your right hand" instruction
3. **Don't raise hand**: After 3 failures, should repeat instruction
4. **Lower hand**: Should send "Please lower your right hand" instruction

## Troubleshooting

### Instructions Not Sending

1. Check Kafka connection: `config.kafka_url`
2. Check T2V endpoint: `config.t2v_endpoint`
3. Verify `session_id` and `manual_id` are available in executor state
4. Check logs for errors in `ActivityInstructionSender`

### Instructions Repeating Too Often

1. Increase failure threshold (default: 3)
2. Increase repeat interval (default: 60 frames)
3. Check activity rules are correctly configured

### Instructions Not Repeating

1. Check failure tracking is working
2. Verify `consecutive_failures >= 3` condition
3. Check repeat interval hasn't passed

## Future Enhancements

- [ ] Support for multiple languages
- [ ] Custom instruction templates per manual
- [ ] Voice gender selection per instruction
- [ ] Instruction priority levels
- [ ] Activity-specific repeat thresholds
