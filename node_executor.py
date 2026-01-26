"""
Node Executor
=============
Executes Node-based SOPs where activities run based on detection class matches.

This is the standalone NodeExecutor that works with the unified SOPExecutor.

Flow:
1. Detection happens BEFORE executor (preprocessing)
2. Executor receives detection results in executor_input_data
3. For each activity:
   - Check if detected classes match activity.model_class
   - If match → Execute activity_rules and anomaly_rules
   - If no match → Skip activity
4. Return all 3 data sources

Usage with SOPExecutor (unified):
---------------------------------
    from sop_unified_executor import SOPExecutor
    import sop_loader
    
    # Load SOP with type="node"
    sop_data = sop_loader.load_sop(source_type="mongodb", sop_id="MY_NODE_SOP")
    
    # Create unified executor (will use NodeExecutor internally)
    executor = SOPExecutor(sop_data, additional_predefined={...})
    
    # Process frames
    executor.set_input_data({
        "frame": frame,
        "detections": detection_results,
        "detected_classes": ["bear", "cow"]
    })
    result = executor.execute_all()
    executor.reset()

Direct usage:
-------------
    from node_executor import NodeExecutor
    
    sop_data = load_sop(...)
    executor = NodeExecutor(sop_data, additional_predefined={...})
    
    executor.set_input_data({...})
    result = executor.execute_all()
"""

import time
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

# Add parent directory for imports
current_dir = Path(__file__).resolve().parent
parent_dir = current_dir.parent
sys.path.append(str(parent_dir))

# Try to import rule evaluator from different locations
try:
    from sop_rules import RuleEvaluator, create_rule_evaluator
except ImportError:
    try:
        sys.path.insert(0, str(parent_dir))
        from sop_rules import RuleEvaluator, create_rule_evaluator
    except ImportError:
        # Fallback: Create a simple rule evaluator if not available
        print("[NodeExecutor] Warning: sop_rules not found, using basic evaluator")
        
        class RuleEvaluator:
            def __init__(self):
                self.derived_data = {}
            
            def set_data_sources(self, executor_input_data, predefined_data, derived_data):
                self.derived_data = derived_data
            
            def evaluate_rules(self, rules):
                return True, {}, []
            
            def reset_derived_data(self):
                self.derived_data = {}
            
            def reset_state(self):
                self.derived_data = {}
        
        def create_rule_evaluator():
            return RuleEvaluator()


# =============================================================================
# RESULT DATACLASSES
# =============================================================================

@dataclass
class ActivityResult:
    """Result from executing a single activity."""
    activity_id: str
    success: bool = True
    triggered: bool = True  # False if skipped due to model_class mismatch
    results: Dict[str, Any] = field(default_factory=dict)
    rule_details: List[Dict] = field(default_factory=list)
    anomaly_results: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class ExecutionResult:
    """Result from executing all activities for a frame."""
    frame_id: Optional[int] = None
    timestamp: float = 0.0
    executor_input_data: Dict[str, Any] = field(default_factory=dict)
    predefined_data: Dict[str, Any] = field(default_factory=dict)
    derived_data: Dict[str, Any] = field(default_factory=dict)
    activity_results: Dict[str, ActivityResult] = field(default_factory=dict)
    activities_executed: int = 0
    activities_skipped: int = 0
    success: bool = True
    
    # Cycle-specific fields (for compatibility with CycleExecutor)
    current_activity: Optional[str] = None
    cycle_active: bool = False
    cycle_count: int = 0
    transition: Optional[Dict] = None
    cycle_completed: Optional[Dict] = None


# =============================================================================
# NODE EXECUTOR
# =============================================================================

class NodeExecutor:
    """
    Node-based SOP Executor.

    Activities are triggered based on model_class match with detected classes.
    Detection happens BEFORE executor (preprocessing step).

    Flow:
    1. User runs detection separately (preprocessing)
    2. User passes detection results to executor via set_input_data()
    3. Executor checks each activity's model_class against detected_classes
    4. If match → Execute activity_rules then anomaly_rules
    5. Return all data sources
    
    Interface (compatible with SOPExecutor):
    - __init__(sop_data, additional_predefined)
    - set_input_data(data)
    - execute_all() -> ExecutionResult
    - execute_activity(activity_id) -> ActivityResult
    - reset()
    - reset_state()
    - get_state()
    - reload_predefined(new_predefined)
    - update_predefined(updates)
    """

    def __init__(self, sop_data: Dict, additional_predefined: Dict = None):
        """
        Initialize NodeExecutor with loader output.

        Args:
            sop_data: Output from load_sop()
            additional_predefined: Extra predefined values to merge with SOP predefined_values
        """
        self.sop_data = sop_data
        self.additional_predefined = additional_predefined or {}

        # Data sources
        self.executor_input_data: Dict[str, Any] = {}
        self.predefined_data: Dict[str, Any] = {}
        self.derived_data: Dict[str, Any] = {}

        # Rule evaluator (state is managed inside sop_rules.py at module level)
        self.rule_evaluator = create_rule_evaluator()

        # Build activity sequence
        self.activity_sequence = self._build_activity_sequence()

        # Build activity -> rules map for quick lookup
        self._activity_rules_map = self._build_activity_rules_map()

        # Frame counter
        self.frames_processed: int = 0

        sop_id = sop_data.get("sop_master", {}).get("sopId", "unknown")
        print(f"[NodeExecutor] Initialized for SOP: {sop_id}")
        print(f"[NodeExecutor] Activities: {self.activity_sequence}")

    def _build_activity_sequence(self) -> List[str]:
        """
        Build activity sequence from activities.

        Logic:
        1. If any activity has prevAct/nextAct → Build sequence using links
        2. Otherwise → Use array order from sop_master.activities
        """
        sop_master = self.sop_data.get("sop_master", {})
        activities = sop_master.get("activities", [])

        if not activities:
            return []

        # Check if any activity has prevAct/nextAct links
        has_links = any(
            a.get("prevAct") or a.get("nextAct")
            for a in activities
        )

        if has_links:
            # Build sequence from links
            sequence = self._build_sequence_from_links(activities)
        else:
            # Use array order - simple sequential execution
            sequence = [a.get("activityId") for a in activities if a.get("activityId")]

        return sequence

    def _build_sequence_from_links(self, activities: List[Dict]) -> List[str]:
        """
        Build activity sequence by following prevAct/nextAct links.

        1. Find first activity (no prevAct or prevAct is empty)
        2. Follow nextAct chain to build sequence
        """
        # Build lookup maps
        activity_map = {a.get("activityId"): a for a in activities}

        # Find first activity (no prevAct or empty prevAct)
        first_activity = None
        for activity in activities:
            prev_act = activity.get("prevAct", [])
            if not prev_act:  # No previous activity = start
                first_activity = activity.get("activityId")
                break

        if not first_activity:
            # Fallback: use first in array
            first_activity = activities[0].get("activityId")
            print(f"[NodeExecutor] No start activity found, using first: {first_activity}")

        # Follow nextAct chain
        sequence = []
        visited = set()
        current = first_activity

        while current and current not in visited:
            sequence.append(current)
            visited.add(current)

            # Get next activity
            activity = activity_map.get(current, {})
            next_acts = activity.get("nextAct", [])

            if next_acts:
                # Take first nextAct (for linear sequence)
                current = next_acts[0] if isinstance(next_acts, list) else next_acts
            else:
                current = None

        return sequence

    def _build_activity_rules_map(self) -> Dict[str, Dict]:
        """Build map of activity_id -> {predefined_values, activity_rules, anomaly_rules, model_class}."""
        result = {}

        # Get model_class from sop_master activities
        sop_master = self.sop_data.get("sop_master", {})
        activities = sop_master.get("activities", [])
        activity_model_class = {
            a.get("activityId"): a.get("model_class", [])
            for a in activities
        }

        # Get rules from sop_activity_rule_map
        rule_map = self.sop_data.get("sop_activity_rule_map", {})
        rules_map = rule_map.get("rules_map", [])

        for mapping in rules_map:
            activity_id = mapping.get("activity_id")
            if activity_id:
                result[activity_id] = {
                    "predefined_values": mapping.get("predefined_values", {}),
                    "activity_rules": mapping.get("activity_rules", []),
                    "anomaly_rules": mapping.get("anomaly_rules", []),
                    "model_class": activity_model_class.get(activity_id, [])
                }

        return result

    def set_input_data(self, data: Dict[str, Any]) -> None:
        """
        Set executor_input_data for current frame.

        Args:
            data: Dict containing:
                - frame: Current video frame
                - detections: Detection results (from preprocessing)
                - detected_classes: List of class names found in frame
                - frame_id / frame_number: Frame identifier
                - timestamp: Frame timestamp
        """
        self.executor_input_data = data

    def _should_trigger_activity(self, activity_id: str) -> bool:
        """
        Check if activity should be triggered based on model_class match.

        Returns True if:
        - Activity has no model_class (runs always)
        - Any detected_class matches activity's model_class
        """
        activity_config = self._activity_rules_map.get(activity_id, {})
        model_classes = activity_config.get("model_class", [])

        # If no model_class defined, activity always runs
        if not model_classes:
            return True

        # Get detected classes from input data
        detected_classes = self.executor_input_data.get("detected_classes", [])

        # Check if any detected class matches
        for detected in detected_classes:
            if detected in model_classes:
                return True

        return False

    def execute_activity(self, activity_id: str) -> ActivityResult:
        """
        Execute a single activity by ID.

        1. Check model_class match
        2. Load predefined_values
        3. Execute activity_rules
        4. Execute anomaly_rules
        """
        # Check if activity should trigger
        if not self._should_trigger_activity(activity_id):
            return ActivityResult(
                activity_id=activity_id,
                success=True,
                triggered=False,
                results={},
                rule_details=[{"skipped": "model_class not matched"}]
            )

        activity_config = self._activity_rules_map.get(activity_id, {})

        # Set predefined_data (merge SOP config + additional)
        self.predefined_data = {
            **activity_config.get("predefined_values", {}),
            **self.additional_predefined
        }

        # Set data sources for rule evaluator
        self.rule_evaluator.set_data_sources(
            executor_input_data=self.executor_input_data,
            predefined_data=self.predefined_data,
            derived_data=self.derived_data
        )

        result = ActivityResult(activity_id=activity_id, triggered=True)

        # Execute activity_rules
        activity_rules = activity_config.get("activity_rules", [])
        if activity_rules:
            try:
                success, combined_results, details = self.rule_evaluator.evaluate_rules(activity_rules)
                result.success = success
                result.results = combined_results
                result.rule_details = details

                # Update derived_data with results
                self.derived_data.update(self.rule_evaluator.derived_data)

            except Exception as e:
                print(f"[NodeExecutor] Error executing activity_rules for {activity_id}: {e}")
                result.success = False
                result.error = str(e)

        # Execute anomaly_rules (if present)
        anomaly_rules = activity_config.get("anomaly_rules", [])
        if anomaly_rules:
            try:
                success, anomaly_results, anomaly_details = self.rule_evaluator.evaluate_rules(anomaly_rules)
                result.anomaly_results = anomaly_results
                result.rule_details.extend([{"anomaly": d} for d in anomaly_details])

                # Update derived_data with anomaly results
                self.derived_data.update(self.rule_evaluator.derived_data)

            except Exception as e:
                print(f"[NodeExecutor] Error executing anomaly_rules for {activity_id}: {e}")
                result.anomaly_results = {"error": str(e)}

        return result

    def execute_all(self) -> ExecutionResult:
        """
        Execute all activities in sequence.

        Returns:
            ExecutionResult with all 3 data sources:
            - executor_input_data
            - predefined_data
            - derived_data
        """
        timestamp = time.time()

        result = ExecutionResult(
            frame_id=self.executor_input_data.get("frame_id"),
            timestamp=timestamp,
            executor_input_data=self.executor_input_data.copy()
        )

        # Execute each activity in sequence
        for activity_id in self.activity_sequence:
            activity_result = self.execute_activity(activity_id)
            result.activity_results[activity_id] = activity_result

            if activity_result.triggered:
                result.activities_executed += 1
                if not activity_result.success:
                    result.success = False
            else:
                result.activities_skipped += 1

        # Set final data sources
        result.predefined_data = self.predefined_data.copy()
        result.derived_data = self.derived_data.copy()

        self.frames_processed += 1

        return result

    def reset(self) -> None:
        """Reset derived_data for new frame."""
        self.derived_data = {}
        self.rule_evaluator.reset_derived_data()

    def reset_state(self) -> None:
        """Reset all stateful data (use between videos/sessions)."""
        self.derived_data = {}
        self.rule_evaluator.reset_state()
        self.frames_processed = 0

    def get_state(self) -> Dict[str, Any]:
        """Get current executor state."""
        sop_id = self.sop_data.get("sop_master", {}).get("sopId", "unknown")
        return {
            "sop_id": sop_id,
            "sop_type": "node",
            "frames_processed": self.frames_processed,
            "activity_count": len(self.activity_sequence),
            "activities": self.activity_sequence
        }

    def reload_predefined(self, new_predefined: Dict) -> None:
        """
        Replace all additional_predefined values.
        
        Args:
            new_predefined: New predefined values to replace existing ones.
        """
        self.additional_predefined = new_predefined

    def update_predefined(self, updates: Dict) -> None:
        """
        Merge updates into existing additional_predefined.
        
        Args:
            updates: Values to merge into existing predefined.
        """
        self.additional_predefined.update(updates)
