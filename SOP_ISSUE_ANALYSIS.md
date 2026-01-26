# SOP System - Issue Analysis from Logs

## 🔍 What's Happening in Your Logs

### **Current Behavior (Working as Designed)**

1. **Cycle Started Successfully:**
   ```
   [Frame 1] CYCLE 1 STARTED at 'PERSON_PRESENT'
   ```
   - ✅ Cycle 1 started correctly
   - ✅ Transitioned from PERSON_PRESENT → HAND_RAISED

2. **Cycle Stuck at HAND_RAISED:**
   - Current activity: `HAND_RAISED`
   - Next activity: `HANDS_DOWN`
   - The cycle executor checks **next activity's rules** before transitioning

3. **Why It's Not Transitioning:**
   ```
   [DEBUG-RULE] matches_pose_combination: 
     expected: ['personPresent']
     actual: ['personPresent', 'rightHandAbove90']
     decision: False
   ```
   - The `matches_pose_combination` rule requires **exact match**
   - Expected: Only `['personPresent']` (hands down)
   - Actual: `['personPresent', 'rightHandAbove90']` (hands still raised)
   - **Result: Cannot transition to HANDS_DOWN because hands are still raised**

---

## 📊 Cycle Flow Explanation

### **State Machine:**
```
PERSON_PRESENT → HAND_RAISED → HANDS_DOWN → (restart)
```

### **Transition Logic:**
When at `HAND_RAISED`, the executor:
1. ✅ Checks `HAND_RAISED` activity rules (to stay in current activity)
2. ✅ Checks `HANDS_DOWN` activity rules (to see if can transition)
3. ❌ If `HANDS_DOWN` rules fail → Stay at `HAND_RAISED`
4. ✅ If `HANDS_DOWN` rules pass → Transition to `HANDS_DOWN`

### **HANDS_DOWN Activity Rules:**
```json
{
  "activity_rules": [
    {
      "matches_pose_combination": {
        "expected_combination": ["personPresent"]
      }
    }
  ]
}
```

**This means:** Transition to HANDS_DOWN only when:
- ✅ Person is present
- ✅ NO hand positions detected (hands are down)

---

## 🐛 The Issue

### **Problem:**
The `matches_pose_combination` rule does an **exact match**:
```python
decision = expected_sorted == actual_sorted
```

**Current behavior:**
- Expected: `['personPresent']`
- Actual: `['personPresent', 'rightHandAbove90']`
- Result: `False` (correct - hands are raised)

**This is actually CORRECT behavior!** The cycle should NOT transition to HANDS_DOWN while hands are raised.

---

## ✅ Why `activities=0`?

The log shows `activities=0` because:
- The cycle executor is checking **transition conditions** (next activity rules)
- It's NOT executing the current activity's rules in "execution mode"
- It's in "transition check mode"

The `activities_executed` counter only increments when activities are **fully executed**, not when checking transitions.

---

## 🔧 Possible Solutions

### **Option 1: Wait for Hands to Actually Go Down**
This is the **intended behavior**. The cycle will transition when:
- User lowers their hands
- `things_present` becomes `['personPresent']` (no hand positions)
- `matches_pose_combination` rule passes
- Cycle transitions to HANDS_DOWN

### **Option 2: Modify Rule Logic (If Needed)**

If you want the rule to check "contains" instead of "exact match":

```python
# In sop_rule_functions.py
def matches_pose_combination(...):
    # Current: Exact match
    decision = expected_sorted == actual_sorted
    
    # Alternative: Check if expected is subset of actual
    # decision = set(expected_sorted).issubset(set(actual_sorted))
```

**But this would change behavior:**
- `['personPresent']` would match `['personPresent', 'rightHandAbove90']`
- This might not be what you want for HANDS_DOWN detection

### **Option 3: Use Different Rule for HANDS_DOWN**

Instead of `matches_pose_combination`, use a rule that explicitly checks for "no hand positions":

```json
{
  "activity_rules": [
    {
      "is_person_present": {...}
    },
    {
      "is_hand_position": {
        "hand_position": "noHandRaised",  // Custom check
        "inverse": true  // Pass if NOT detected
      }
    }
  ]
}
```

---

## 📝 Understanding the Logs

### **What Each Log Line Means:**

1. **`[DEBUG-RULE] matches_pose_combination`**
   - Checking if HANDS_DOWN conditions are met
   - Called during transition check (not activity execution)

2. **`[ANOMALY-CHECK DEBUG] HAND_RAISED: Rule 'is_person_not_present' NOT satisfied`**
   - Anomaly check: Person is present (good)
   - This is a safety check to detect if person disappears

3. **`SOP executed: activity=HAND_RAISED, cycle=2, success=True, activities=0`**
   - Current activity: HAND_RAISED
   - Cycle number: 2 (cycle 1 completed, cycle 2 started)
   - Success: True (no errors)
   - Activities: 0 (transition check, not execution)

---

## 🎯 Expected Behavior

### **Normal Flow:**
1. **Frame 1:** Cycle starts at PERSON_PRESENT ✅
2. **Frame 2:** Transitions to HAND_RAISED ✅
3. **Frames 3-100:** Stays at HAND_RAISED (hands raised) ✅
4. **Frame 101:** Hands go down → `things_present = ['personPresent']`
5. **Frame 101:** `matches_pose_combination` passes → Transition to HANDS_DOWN ✅
6. **Frame 102:** At HANDS_DOWN, checks if PERSON_PRESENT detected again
7. **Frame 103:** Person still present → Cycle completes and restarts ✅

### **Current State:**
- Cycle is at HAND_RAISED (correct)
- Waiting for hands to go down (correct)
- Not transitioning because hands are still raised (correct)

---

## 🔍 Debugging Tips

### **To Verify Rule is Working:**

1. **Check when hands actually go down:**
   - Look for frames where `things_present` becomes `['personPresent']` only
   - At that point, `matches_pose_combination` should pass

2. **Add more debug logging:**
   ```python
   # In sop_rule_functions.py matches_pose_combination
   print(f"[MATCH-DEBUG] Expected: {expected_sorted}, Actual: {actual_sorted}, Match: {decision}")
   ```

3. **Check persistence:**
   - The rule might require N consecutive frames
   - Check if `persistence` or `confirm_frames` is set in rule config

---

## ✅ Conclusion

**The system is working correctly!**

The cycle is:
- ✅ Correctly staying at HAND_RAISED while hands are raised
- ✅ Correctly checking HANDS_DOWN conditions before transitioning
- ✅ Correctly preventing transition when hands are still raised

**To proceed:**
- Wait for user to lower their hands
- When `things_present = ['personPresent']` (no hand positions), the cycle will transition
- The cycle will complete and restart as designed

---

## 🛠️ If You Want to Change Behavior

If you want the cycle to transition differently, you can:

1. **Modify the rule logic** (exact match → subset match)
2. **Change the expected combination** in HANDS_DOWN activity
3. **Use a different rule** that better matches your use case
4. **Adjust persistence settings** if rules need N consecutive frames

But based on the logs, the current behavior appears to be **working as intended** for a pose detection workflow where you want to detect when hands are actually down.
