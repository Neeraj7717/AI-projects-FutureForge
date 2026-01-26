# UI Speech Not Working - Troubleshooting Guide

## Issue
Instructions are being sent to Kafka successfully, but the UI speech AI is not speaking them.

## Changes Made

### 1. **Producer Flush** ✅
- Added `producer.flush()` to ensure messages are sent immediately
- Messages were being buffered and not sent right away

### 2. **Numeric stepId** ✅
- Changed from `"ACTIVITY_{activity_id}"` to numeric format
- UI might filter out non-numeric stepIds
- Uses consistent hash-based numeric ID per activity

### 3. **startTime Field** ✅
- Added proper `startTime` timestamp (was empty string)
- UI might require this field to process messages

### 4. **Better Logging** ✅
- Added debug logging to see full Kafka message
- Logs topic name and audio URL

## Verification Steps

### 1. Check Kafka Topic
Verify the UI is consuming from the correct topic:
```bash
# Check what topic we're sending to
grep "video_instruction_kafka_topic" .env
```

### 2. Check Message Format
The message format should match what UI expects:
```json
{
  "sessionId": "...",
  "manualId": "23",
  "stepId": "123456",  // Now numeric
  "step": "Please stand",
  "audioUrl": "https://cdn-dev.eizen.ai/...",
  "status": "inProgress",
  "startTime": "2026-01-23T10:18:49.123456+00:00"
}
```

### 3. Check UI Consumer
The UI frontend should be:
- Consuming from `video_instruction_kafka_topic`
- Listening for messages with `audioUrl` field
- Playing audio when `audioUrl` is present

### 4. Check Logs
Look for these log messages:
```
Sent instruction: 'Please stand' for activity PERSON_PRESENT
Kafka message sent to topic 'video-instruction-topic': {...}
Generated audio for 'Please stand': https://...
```

## Common Issues

### Issue 1: UI Not Consuming from Kafka
**Symptom**: Messages sent but UI doesn't receive them
**Solution**: 
- Verify UI Kafka consumer is running
- Check UI is subscribed to correct topic
- Verify Kafka connection in UI

### Issue 2: UI Filtering Messages
**Symptom**: Messages sent but UI ignores them
**Solution**:
- Check if UI filters by `stepId` format (now numeric ✅)
- Check if UI requires specific fields (all added ✅)
- Check if UI requires `status` to be "inProgress" (already set ✅)

### Issue 3: Audio URL Not Accessible
**Symptom**: Messages received but audio doesn't play
**Solution**:
- Verify audio URL is accessible: `curl https://cdn-dev.eizen.ai/...`
- Check CORS settings on audio server
- Verify audio format is supported by UI

### Issue 4: UI Waiting for MongoDB
**Symptom**: UI might expect message in MongoDB first
**Solution**:
- Check if UI reads from MongoDB instead of Kafka
- If so, we need to also save to MongoDB (not implemented yet)

## Debugging Commands

### Check Kafka Messages
```bash
# Install kafka tools if needed
# Consume messages from topic to verify they're being sent
kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic video-instruction-topic \
  --from-beginning
```

### Test Audio URL
```bash
# Test if audio URL is accessible
curl -I https://cdn-dev.eizen.ai/text-to-audio/ldev/2026_01_23/audio_*.mp3
```

### Check UI Logs
Check the UI frontend console/logs for:
- Kafka connection status
- Messages received
- Audio playback errors

## Next Steps

1. **Verify Kafka Topic**: Confirm UI is consuming from `video_instruction_kafka_topic`
2. **Check UI Code**: Review UI frontend code to see how it processes messages
3. **Test Audio URLs**: Verify generated audio URLs are accessible
4. **Check UI Filters**: See if UI has any message filtering logic

## If Still Not Working

If the issue persists, we may need to:
1. Check UI frontend code to see exact message format expected
2. Verify UI Kafka consumer configuration
3. Add MongoDB persistence if UI reads from DB instead of Kafka
4. Check if UI requires additional fields we're not sending
