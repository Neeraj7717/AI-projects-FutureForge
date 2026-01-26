"""
SOP Cycle Executor - Generic executor for cycle-based SOPs.

This executor handles the flow:
1. Receives detections from processor
2. Evaluates rules based on activity_rule_map
3. Manages state machine transitions
4. Tracks cycles (start → activities → end → restart)

Data Stores:
- executor_input_data: Live detection data (updated each frame)
- predefined_data: Static config values (loaded once)
- derived_data: Computed state and analytics (updated by executor)
"""
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import importlib.util
import json
import os
import uuid
import logging
from datetime import datetime, timezone
try:
    import redis
    HAS_REDIS = True
except Exception:
    HAS_REDIS = False
    redis = None

try:
    from Config.settings import Settings
    _cfg = Settings()
except Exception:
    _cfg = None
try:
    from pymongo import MongoClient
    HAS_PYMONGO = True
except ImportError:
    HAS_PYMONGO = False

# Import activity instruction sender
try:
    from model.activity_instruction_sender import get_instruction_sender
    HAS_INSTRUCTION_SENDER = True
except ImportError as e:
    HAS_INSTRUCTION_SENDER = False
    # cycle_logger not yet defined, will log later if needed

# Set up logger for cycle executor
try:
    from utils.eizen_utils.logger_utils.logger_operations import LoggerOperations
    cycle_logger = LoggerOperations(logger_name='CycleExecutor', log_level=logging.INFO, use_log_file=False)
except ImportError:
    # Fallback to standard logging if custom logger not available
    cycle_logger = logging.getLogger('CycleExecutor')
    cycle_logger.setLevel(logging.INFO)
    if not cycle_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        cycle_logger.addHandler(handler)


# =============================================================================
# External State Tracker (Simulating Redis/Database)
# =============================================================================

class RuleStateTracker:
    """
    External component to track rule persistence and stability.
    This logic can be moved to Redis or another external store easily.
    """

    def __init__(self):
        # Maps rule_id -> (consecutive_success_count, last_updated_frame)
        self.persistence_state: Dict[str, Tuple[int, int]] = {}
        
    def update_rule_state(self, rule_id: str, is_passing: bool, current_frame: int):
        """Update the tracking state for a given rule with frame awareness."""
        current_count, last_frame = self.persistence_state.get(rule_id, (0, -1))
        
        # GAP DETECTION REMOVED for robustness in live streams
        # We count "consecutive observed frames". If frames are dropped (e.g. 1, 3, 5),
        # we still count them as a sequence to avoid constant resetting.
        # if last_frame != -1 and current_frame > last_frame + 1:
        #     current_count = 0
        
        if is_passing:
            self.persistence_state[rule_id] = (current_count + 1, current_frame)
        else:
            self.persistence_state[rule_id] = (0, current_frame)
            
    def is_rule_confirmed(self, rule_id: str, required_frames: int) -> bool:
        """Check if rule has been passing for required number of frames."""
        current_count, _ = self.persistence_state.get(rule_id, (0, 0))
        
        # If persistence is 1 or less, it's immediate
        if required_frames <= 1:
            return current_count >= 1
            
        return current_count >= required_frames
    
    def reset(self):
        """Clear all persistence state."""
        self.persistence_state.clear()



@dataclass
class CycleState:
    """State for a single cycle execution."""
    is_active: bool = False
    cycle_count: int = 0
    current_activity: Optional[str] = None
    previous_activity: Optional[str] = None
    cycle_start_frame: Optional[int] = None
    cycle_start_time: Optional[str] = None
    
    # Activity timing
    activity_timing: Dict[str, Dict] = field(default_factory=dict)


@dataclass 
class SourceState:
    """Complete state for a source/camera."""
    source_id: str
    executor_input_data: Dict = field(default_factory=dict)
    predefined_data: Dict = field(default_factory=dict)
    derived_data: Dict = field(default_factory=dict)
    cycle_state: CycleState = field(default_factory=CycleState)
    tracker: RuleStateTracker = field(default_factory=RuleStateTracker)
    
    # Cycle history
    completed_cycles: List[Dict] = field(default_factory=list)
    
    # Analytics/KPI data (loaded from template, updated during execution)
    analytics_data: Dict = field(default_factory=dict)
    
    # Track which rules have already applied KPI updates this cycle
    # Session and manual info for instruction sending
    session_id: Optional[str] = None
    manual_id: Optional[str] = None
    
    # Track activity failures for instruction repetition
    activity_failure_count: Dict[str, int] = field(default_factory=dict)  # activity_id -> consecutive failures
    kpi_updates_applied: set = field(default_factory=set)

    # SOP -> UI/Speech message bookkeeping (avoid duplicates)
    sent_step_events: set = field(default_factory=set)  # entries like "cycle:activity:status:kind"
    step_start_times: Dict[str, str] = field(default_factory=dict)  # key="cycle:activity" -> iso startTime
    
    # Path to save analytics output (updated after each cycle)
    analytics_output_path: Optional[str] = None
    
    # Unique ID for this execution run (for DB storage)
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class SOPCycleExecutor:
    """
    Generic cycle-based SOP Executor.
    
    Cycle Flow:
    1. Wait for start_activity conditions to be met
    2. Cycle becomes active
    3. Progress through activities based on state machine
    4. When end_activity reached and start_activity detected again:
       - Complete cycle
       - Restart cycle
    
    This executor focuses ONLY on activity tracking and cycle counting.
    """
    
    def __init__(self):
        # SOP Configuration (loaded from JSONs)
        self.sop_master: Optional[Dict] = None
        self.activity_rule_map: Optional[Dict] = None
        self.rules_definitions: Dict[str, Dict] = {}
        
        # Rule functions module
        self.rule_functions = None
        
        # State per source
        self.sources: Dict[str, SourceState] = {}
        
        # Extracted config
        self.sop_id: str = ""
        self.sop_type: str = "cycle"
        self.start_activity: Optional[str] = None
        self.end_activity: Optional[str] = None
        self.activity_sequence: List[str] = []
        
        # MongoDB Config
        self.mongo_client = None
        self.mongo_db = None
        self.mongo_collection_name = None
        
        self.state_machine: Dict[str, Dict] = {}
        self.rules_map: Dict[str, Dict] = {}  # activity_id -> rule config
        self.cycle_kpi_updates: Dict[str, List] = {}
        
        # Session and manual IDs for instruction sending
        self._session_id: Optional[str] = None
        self._manual_id: Optional[str] = None

        # Redis for step-state (optional; matches legacy vip:{sessionId}:{manualId}:state)
        self.redis_client = None
        if HAS_REDIS and _cfg is not None:
            try:
                self.redis_client = redis.Redis(host=_cfg.redis_host, port=_cfg.redis_port, db=_cfg.redis_db)
            except Exception:
                self.redis_client = None

    def _utc_now_iso(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")

    def _activity_to_step_id(self, activity_id: str) -> str:
        """Map SOP activity_id to a stable numeric stepId string for UI."""
        try:
            if activity_id in self.activity_sequence:
                return str(self.activity_sequence.index(activity_id) + 1)
        except Exception:
            pass
        return str(abs(hash(activity_id)) % 1000000)

    def _update_step_redis(self, session_id: str, manual_id: str, step_id: str) -> None:
        """Best-effort update of vip:{sessionId}:{manualId}:state to mirror legacy flow."""
        if not self.redis_client or not session_id or not manual_id or not step_id:
            return
        try:
            key = f"vip:{session_id}:{manual_id}:state"
            self.redis_client.set(key, int(step_id))
        except Exception:
            return

    def _send_step_status_message(
        self,
        *,
        source_id: str,
        activity_id: str,
        status: str,
        cycle_count: int,
        step_text: str,
        is_repeat: bool = False,
        feedback: str = "",
    ) -> None:
        """
        Send SOP step messages in the same schema as instruction_graph/mongo_operations:
        emits inProgress/completed/failed with stepId/sessionId/manualId/startTime/endTime/audioUrl.
        """
        if not HAS_INSTRUCTION_SENDER:
            return

        state = self.sources.get(source_id)
        if not state:
            return

        session_id = getattr(self, "_session_id", None) or state.session_id
        manual_id = getattr(self, "_manual_id", None) or state.manual_id
        if not session_id or not manual_id:
            return

        kind = "repeat" if is_repeat else "init"
        event_key = f"{cycle_count}:{activity_id}:{status}:{kind}"
        if event_key in state.sent_step_events:
            return
        state.sent_step_events.add(event_key)

        sender = get_instruction_sender()
        step_id = self._activity_to_step_id(activity_id)

        start_key = f"{cycle_count}:{activity_id}"
        start_time = ""
        end_time = ""

        if status == "inProgress":
            start_time = self._utc_now_iso()
            state.step_start_times[start_key] = start_time
            self._update_step_redis(session_id, str(manual_id), step_id)
        else:
            start_time = state.step_start_times.get(start_key, "")
            end_time = self._utc_now_iso()

        sender.send_custom_instruction(
            step_text=step_text,
            source_id=source_id,
            session_id=session_id,
            manual_id=str(manual_id),
            step_id=step_id,
            status=status,
            start_time=start_time,
            end_time=end_time,
            audio_url="",  # keep completed/failed quiet; inProgress will auto-generate
            gender=1,
            repetition=1 if is_repeat else 0,
            context_url="",
            context_type="",
            feedback=feedback,
            feedback_url="",
            step_score="",
            video_url="",
        )

    def set_mongo_config(self, uri: str, db_name: str, collection_name: str = "derived_analytics"):
        """Configure MongoDB connection for saving analytics."""
        if not HAS_PYMONGO:
            return
        
        try:
            self.mongo_client = MongoClient(uri)
            self.mongo_db = self.mongo_client[db_name]
            self.mongo_collection_name = collection_name
            cycle_logger.info(f"[SOPCycleExecutor] MongoDB configured: {db_name}.{collection_name}")
        except Exception as e:
            cycle_logger.error(f"[SOPCycleExecutor] Error connecting to MongoDB: {e}")

    def _init_state_structs(self):
        # Helper to ensure these exist if __init__ flow was disrupted
        if not hasattr(self, 'state_machine'): self.state_machine = {}
        if not hasattr(self, 'rules_map'): self.rules_map = {}
        if not hasattr(self, 'cycle_kpi_updates'): self.cycle_kpi_updates = {}
    
    # =========================================================================
    # INITIALIZATION
    # =========================================================================
    
    def load_config(self, sop_data: Dict, rule_functions_path: str = None, derived_analytics: Dict = None):
        """
        Load SOP configuration from sop_loader output.
        
        Args:
            sop_data: Dict from sop_loader.load_sop()
            rule_functions_path: Path to Python file with rule functions
            derived_analytics: Optional dict (ignored for generic executor for now)
        """
        # Validate
        if not sop_data.get("validation", {}).get("valid", False):
            errors = sop_data.get("validation", {}).get("errors", [])
            raise ValueError(f"Invalid SOP configuration: {errors}")
        
        self.sop_master = sop_data["sop_master"]
        self.activity_rule_map = sop_data["sop_activity_rule_map"]
        self.rules_definitions = {r["rule_name"]: r for r in sop_data.get("sop_rules", [])}
        self.analytics_template = sop_data.get("sop_analytics_template")
        
        # Extract SOP metadata
        # Support both camelCase and snake_case for compatibility
        self.sop_id = self.sop_master.get("sopId") or self.sop_master.get("sop_id", "")
        self.sop_type = self.sop_master.get("type", "cycle")
        
        # Start/End activities - support both camelCase and snake_case
        start_list = self.sop_master.get("start_activity") or self.sop_master.get("startActivity", [])
        end_list = self.sop_master.get("end_activity") or self.sop_master.get("endActivity", [])
        self.start_activity = start_list[0] if start_list else None
        self.end_activity = end_list[0] if end_list else None
        
        # Build activity sequence and state machine
        for activity in self.sop_master.get("activities", []):
            # Support both camelCase and snake_case for compatibility
            act_id = activity.get("activityId") or activity.get("activity_id")
            if act_id:
                self.activity_sequence.append(act_id)
                # Support both camelCase and snake_case for compatibility
                prev_act = activity.get("prev_act") or activity.get("prevAct", [])
                next_act = activity.get("next_act") or activity.get("nextAct", [])
                expected_time = activity.get("expected_time") or activity.get("expectedTime", 0)
                # Get instruction text from activity (description or instruction field)
                instruction_text = activity.get("instruction") or activity.get("description") or activity.get("step_text") or None
                self.state_machine[act_id] = {
                    "prev_act": prev_act,
                    "next_act": next_act,
                    "expected_time": expected_time,
                    "instruction": instruction_text  # Store instruction text from SOP
                }
                # Log instruction loading for debugging
                if instruction_text:
                    cycle_logger.debug(f"Loaded instruction from SOP for {act_id}: '{instruction_text}'")
                else:
                    cycle_logger.warning(f"No instruction found in SOP for activity {act_id}")
        
        # Build rules map (activity_id -> config)
        self.predefined_data_storage = {}
        for rule_mapping in self.activity_rule_map.get("rules_map", []):
            act_id = rule_mapping.get("activity_id")
            self.rules_map[act_id] = rule_mapping
            
            # Consolidate predefined values
            # Using same key and value implies standard update behavior
            if "predefined_values" in rule_mapping:
                self.predefined_data_storage.update(rule_mapping["predefined_values"])
        
        # Load cycle-level KPI updates from config
        self.cycle_kpi_updates = self.activity_rule_map.get("cycle_kpi_updates", {})
            

        
        # Save consolidated predefined values to local JSON
        try:
            filename = f"predefined_values_{self.sop_id}.json"
            with open(filename, 'w') as f:
                json.dump(self.predefined_data_storage, f, indent=4)
            cycle_logger.info(f"[SOPCycleExecutor] Saved separate predefined values to '{filename}'")
        except Exception as e:
            cycle_logger.warning(f"[SOPCycleExecutor] Warning: Failed to save predefined values: {e}")
            
        # Load rule functions
        # Only load rule functions if not already loaded
        if rule_functions_path and not hasattr(self, 'rule_functions') or self.rule_functions is None:
            self._load_rule_functions(rule_functions_path)
        
        cycle_logger.info(f"[SOPCycleExecutor] Loaded SOP: {self.sop_id}")
        print(f"  Type: {self.sop_type}")
        print(f"  Start: {self.start_activity}, End: {self.end_activity}")
        print(f"  Activities: {self.activity_sequence}")
    
    def _load_rule_functions(self, path: str):
        """Load rule functions from Python file."""
        import os
        from pathlib import Path
        
        # If path is relative, try to resolve it relative to project root
        if not os.path.isabs(path):
            # Try to find project root (where sop_cycle_executor.py is located)
            current_file = Path(__file__).resolve()
            project_root = current_file.parent
            path = project_root / path
        else:
            path = Path(path)
        
        # If path doesn't exist, try alternative locations
        if not path.exists():
            # Try in project root
            current_file = Path(__file__).resolve()
            project_root = current_file.parent
            alt_path = project_root / "sop_rule_functions.py"
            if alt_path.exists():
                path = alt_path
            else:
                raise FileNotFoundError(f"Rule functions file not found: {path} (also tried {alt_path})")
        
        spec = importlib.util.spec_from_file_location("sop_rules", str(path))
        self.rule_functions = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.rule_functions)
        print(f"  Rule functions loaded from: {path}")


    
    def initialize_source(self, source_id: str, predefined_values: Dict = None):
        """
        Initialize state for a new source/camera.
        Loads predefined values from the local JSON file if available.
        """
        state = SourceState(source_id=source_id)
        
        # Load from consolidated JSON file if exists, else fallback to memory
        filename = f"predefined_values_{self.sop_id}.json"
        
        try:
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    file_data = json.load(f)
                state.predefined_data = file_data
                # print(f"[SOPCycleExecutor] Loaded predefined data from {filename}")
            else:
                state.predefined_data = self.predefined_data_storage.copy()
        except Exception as e:
            cycle_logger.warning(f"[SOPCycleExecutor] Error loading {filename}: {e}. using memory copy.")
            state.predefined_data = self.predefined_data_storage.copy()
        
        # Merge source-specific predefined values (e.g. from call arguments)
        if predefined_values:
            state.predefined_data.update(predefined_values)
        
        # Initialize derived_data structure
        state.derived_data = {
            "current_activity": None,
            "is_cycle_active": False,
            "cycle_count": 0,
            "rule_results": {}
        }
        
        # Initialize activity timing
        state.cycle_state.activity_timing = {
            act_id: {"start_frame": None, "end_frame": None, "start_time": None, "end_time": None}
            for act_id in self.activity_sequence
        }
        
        # Load analytics template for KPI tracking
        if hasattr(self, "analytics_template") and self.analytics_template:
            import copy
            state.analytics_data = copy.deepcopy(self.analytics_template)
            cycle_logger.info(f"[SOPCycleExecutor] Loaded analytics template from configuration (DB/Loader)")
        else:
            # Try to load SOP-specific analytics template based on sop_id
            analytics_template_path = None
            if hasattr(self, "sop_id") and self.sop_id:
                # Try phone assembly template
                if "PHONE_ASSEMBLY" in self.sop_id:
                    phone_template_path = os.path.join(
                        os.path.dirname(__file__), "phone_assembly", "phone_assembly_analytics_template.json"
                    )
                    if os.path.exists(phone_template_path):
                        analytics_template_path = phone_template_path
                # Try ABB template
                if not analytics_template_path:
                    abb_template_path = os.path.join(
                        os.path.dirname(__file__), "abbjsons", "abb_analytics_template.json"
                    )
                    if os.path.exists(abb_template_path):
                        analytics_template_path = abb_template_path
            
            # Fallback to ABB template if SOP-specific not found
            if not analytics_template_path:
                analytics_template_path = os.path.join(
                    os.path.dirname(__file__), "abbjsons", "abb_analytics_template.json"
                )
            
            try:
                if analytics_template_path and os.path.exists(analytics_template_path):
                    with open(analytics_template_path, 'r') as f:
                        state.analytics_data = json.load(f)
                    cycle_logger.info(f"[SOPCycleExecutor] Loaded analytics template from: {analytics_template_path}")
                else:
                    # Initialize with empty structure
                    state.analytics_data = {"kpi": {}, "cycles": [], "anomalies": []}
                    cycle_logger.warning(f"[SOPCycleExecutor] No analytics template found, using empty structure")
            except Exception as e:
                cycle_logger.warning(f"[SOPCycleExecutor] Warning: Failed to load analytics template: {e}")
                state.analytics_data = {"kpi": {}, "cycles": [], "anomalies": []}
        
        self.sources[source_id] = state
        cycle_logger.info(f"[SOPCycleExecutor] Initialized source: {source_id}")
    
    def shutdown(self, source_id: str) -> None:
        """
        Finalize processing for a source.
        If the cycle is currently at the end_activity, mark it as complete.
        """
        if source_id not in self.sources:
            return
            
        state = self.sources[source_id]
        cycle = state.cycle_state
        
        # Check if we are in the end activity and active
        if cycle.is_active and cycle.current_activity == self.end_activity:
            cycle_logger.info(f"  [Shutdown] Finalizing Cycle {cycle.cycle_count} (In End Activity '{self.end_activity}')")
            
            # Determine end frame (use last known frame from derived_data)
            last_frame = state.derived_data.get("frame_number", 0)
            
            # Record success
            completed_cycle = {
                "cycle_number": cycle.cycle_count,
                "start_frame": cycle.cycle_start_frame,
                "end_frame": last_frame,
                "activity_timing": dict(cycle.activity_timing),
                "status": "SUCCESS (Shutdown)"
            }
            state.completed_cycles.append(completed_cycle)
            
            # Build detailed cycle analytics and update
            cycle_analytics = self._build_cycle_analytics(
                source_id=source_id,
                cycle_num=cycle.cycle_count,
                start_frame=cycle.cycle_start_frame,
                end_frame=last_frame,
                activity_timing=cycle.activity_timing,
                status="SUCCESS",
                has_anomaly=False
            )
            self._update_analytics_after_cycle(source_id, cycle_analytics)
            
            # Apply cycle-level KPI updates (on_cycle_complete_success)
            success_updates = self.cycle_kpi_updates.get("on_cycle_complete_success", [])
            if success_updates:
                self._apply_kpi_updates(source_id, success_updates)
            
            cycle_logger.info(f"  [Shutdown] CYCLE {cycle.cycle_count} COMPLETED: SUCCESS")
            cycle.is_active = False  # Deactivate
    
    # =========================================================================
    # MAIN EXECUTION
    # =========================================================================
    
    def process_frame(
        self,
        source_id: str,
        detections: Dict[str, List[List[float]]],
        frame_number: int,
        timestamp: str,
        additional_fields: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Process a single frame with detections.
        
        Returns:
            {
                "current_activity": str or None,
                "cycle_active": bool,
                "cycle_count": int,
                "transition": {"from": str, "to": str} or None,
                "cycle_completed": {"status": "SUCCESS", ...} or None
            }
        """
        if source_id not in self.sources:
            self.initialize_source(source_id)
        
        state = self.sources[source_id]
        
        # Update derived data with frame number for RuleStateTracker
        state.derived_data["frame_number"] = frame_number
        
        cycle = state.cycle_state
        
        # Update executor_input_data
        # Include detections as both top-level keys and under "detections" key for flexibility
        state.executor_input_data = {
            **detections,  # Top-level: Person -> [[x1,y1,x2,y2]]
            "detections": detections,  # Nested: detections.Person -> [[x1,y1,x2,y2]]
            "frame_number": frame_number,
            "timestamp": timestamp,
            "source_id": source_id
        }
        
        # Merge additional fields (like things_present from pose detection)
        if additional_fields:
            state.executor_input_data.update(additional_fields)
            # Store session_id and manual_id if provided
            if "sessionId" in additional_fields:
                state.session_id = additional_fields["sessionId"]
                self._session_id = additional_fields["sessionId"]  # Also store in executor instance
            if "manualId" in additional_fields:
                state.manual_id = str(additional_fields["manualId"])
                self._manual_id = str(additional_fields["manualId"])  # Also store in executor instance
        
        # Also check executor_input_data for session_id and manual_id (from set_input_data)
        if not state.session_id and "sessionId" in state.executor_input_data:
            state.session_id = state.executor_input_data["sessionId"]
        if not state.manual_id and "manualId" in state.executor_input_data:
            state.manual_id = str(state.executor_input_data["manualId"])
        
        # Check if current activity is confirmed (completed correctly)
        # For start activity, also check if next activity is ready (to show proper status)
        if cycle.is_active and cycle.current_activity:
            is_start_activity = (cycle.current_activity == self.start_activity)
            
            if is_start_activity:
                # For start activity: success = True if current activity rules pass AND next activity is ready
                current_activity_passing = self._check_activity_rules(source_id, cycle.current_activity)
                next_activity_ready = False
                
                # Check if any next activity is ready
                next_activities = self.state_machine.get(cycle.current_activity, {}).get("next_act", [])
                for next_activity in next_activities:
                    if self._check_activity_rules(source_id, next_activity):
                        next_activity_ready = True
                        break
                
                # Start activity success = current activity passing AND next activity ready
                current_activity_confirmed = current_activity_passing and next_activity_ready
            else:
                # For other activities: require confirmation (with persistence)
                current_activity_confirmed = self._is_activity_confirmed(source_id, cycle.current_activity)
        else:
            # Cycle not active or no current activity - nothing to validate, so success = True
            current_activity_confirmed = True
        
        result = {
            "current_activity": cycle.current_activity,
            "cycle_active": cycle.is_active,
            "cycle_count": cycle.cycle_count,
            "transition": None,
            "cycle_completed": None,
            "success": current_activity_confirmed  # True if activity is confirmed/ready, False if waiting or not confirmed
        }
        
        # Check for activity transitions
        transition = self._check_activity_transition(source_id, frame_number, timestamp)
        if transition:
            result["transition"] = transition
            result["current_activity"] = cycle.current_activity
            result["cycle_active"] = cycle.is_active
            result["cycle_count"] = cycle.cycle_count
            # After transition, new activity is not yet confirmed
            result["success"] = False
            
            # Check if cycle completed
            if transition.get("cycle_completed"):
                result["cycle_completed"] = transition["cycle_completed"]
        
        # Update derived_data
        state.derived_data["current_activity"] = cycle.current_activity
        state.derived_data["is_cycle_active"] = cycle.is_active
        state.derived_data["cycle_count"] = cycle.cycle_count
        
        return result
    
    # =========================================================================
    # RULE EVALUATION
    # =========================================================================
    
    def _check_activity_rules(self, source_id: str, activity_id: str) -> bool:
        """
        Check if all activity_rules for an activity are satisfied.
        
        Returns True if all rules pass (with AND/OR logic).
        """
        if not activity_id or activity_id not in self.rules_map:
            return False
        
        rule_config = self.rules_map[activity_id]
        activity_rules = rule_config.get("activity_rules", [])
        
        # Evaluate rules
        state = self.sources.get(source_id)
        result = self._evaluate_rules(source_id, activity_rules)
        
        return result
    
    def _is_activity_confirmed(self, source_id: str, activity_id: str) -> bool:
        """
        Check if an activity is confirmed (all rules passing with persistence).
        
        This is stricter than _check_activity_rules - it requires that all rules
        have been passing for the required persistence frames.
        
        Returns True only if the activity is fully confirmed (completed correctly).
        """
        if not activity_id or activity_id not in self.rules_map:
            return False
        
        state = self.sources.get(source_id)
        if not state:
            return False
        
        rule_config = self.rules_map[activity_id]
        activity_rules = rule_config.get("activity_rules", [])
        
        if not activity_rules:
            return True  # No rules = always confirmed
        
        # Check each rule to see if it's confirmed (with persistence)
        for item in activity_rules:
            if isinstance(item, list):
                # OR group - at least one must be confirmed
                or_confirmed = False
                for rule in item:
                    if isinstance(rule, dict):
                        if self._is_rule_confirmed(source_id, rule):
                            or_confirmed = True
                            break
                if not or_confirmed:
                    return False  # None of the OR rules are confirmed
            elif isinstance(item, dict):
                # Single rule - must be confirmed
                if not self._is_rule_confirmed(source_id, item):
                    return False  # This rule is not confirmed
        
        return True  # All rules are confirmed
    
    def _is_rule_confirmed(self, source_id: str, rule_config: Dict) -> bool:
        """
        Check if a single rule is confirmed (passing with persistence).
        
        This checks the persistence state to see if the rule has been
        passing for the required number of frames.
        """
        state = self.sources.get(source_id)
        if not state:
            return False

        # `rule_config` is expected to be the *outer* rule dict from the SOP mapping:
        #   {"rule_name": {"static_values": {...}, "mapped_values": {...}, ...}}
        # But the persistence tracker in `_execute_single_rule()` keys off the *inner* config object:
        #   config = rule_config[rule_name]
        # So we must resolve to the same inner config here, otherwise confirmations never match.

        if isinstance(rule_config, dict) and len(rule_config) == 1:
            rule_name = next(iter(rule_config.keys()))
            inner_config = rule_config.get(rule_name, {})
        else:
            # Fallback: treat the passed object as already being the inner config
            inner_config = rule_config

        # Get persistence requirement (supports either inline "persistence" or static_values)
        persistence = inner_config.get("persistence")
        if persistence is None:
            persistence = inner_config.get("static_values", {}).get("persistence")
        if persistence is None:
            persistence = inner_config.get("static_values", {}).get("threshold", 1)

        persistence = int(persistence)

        # Must match `_execute_single_rule()` which uses id(inner_config)
        config_id = str(id(inner_config))

        return state.tracker.is_rule_confirmed(config_id, persistence)
    
    def _evaluate_rules(self, source_id: str, rules_list: List) -> bool:
        """
        Evaluate rules with AND/OR logic.
        
        Top level list = AND (all must pass)
        Nested list = OR (any one must pass)
        """
        if not rules_list:
            return True  # No rules = passes
        
        for item in rules_list:
            if isinstance(item, list):
                # OR group - any one must pass
                or_result = any(
                    self._execute_single_rule(source_id, rule)
                    for rule in item if isinstance(rule, dict)
                )
                if not or_result:
                    return False
            elif isinstance(item, dict):
                # Single rule - must pass (AND)
                if not self._execute_single_rule(source_id, item):
                    return False
        
        return True
    
    def _execute_single_rule(self, source_id: str, rule_config: Dict) -> bool:
        """
        Execute a single rule and return decision.
        """
        state = self.sources[source_id]
        
        # Get rule name (first key)
        rule_name = list(rule_config.keys())[0]
        config = rule_config[rule_name]
        
        # Build parameters
        params = {}
        
        # Add static_values but EXCLUDE executor-specific metadata keys
        # The rule function logic doesn't need persistence/threshold config
        static_vals = config.get("static_values", {}).copy() # Copy to avoid mutating config
        static_vals.pop("persistence", None)
        static_vals.pop("threshold", None) 
        static_vals.pop("confirm_frames", None)
        
        params.update(static_vals)
        
        # Resolve mapped_values
        for param_name, binding in config.get("mapped_values", {}).items():
            resolved_value = self._resolve_value(source_id, binding)
            params[param_name] = resolved_value
        
        # Get and call rule function
        rule_func = getattr(self.rule_functions, rule_name, None)
        if not rule_func:
            print(f"  [WARNING] Rule function not found: {rule_name}")
            return False
        
        try:
            result = rule_func(**params)
            
            # Store result in derived_data
            if "rule_results" not in state.derived_data:
                state.derived_data["rule_results"] = {}
            state.derived_data["rule_results"][rule_name] = result
            
            decision = result.get("decision", False)
            
            # Persistence Logic
            persistence = config.get("persistence")
            if persistence is None:
                persistence = config.get("static_values", {}).get("persistence")
            if persistence is None:
                persistence = config.get("static_values", {}).get("threshold", 1)
            
            persistence = int(persistence)
            
            # Use unique ID of the config object to track state for this specific rule usage
            config_id = str(id(config))
            
            # Get current frame for tracking gaps
            current_frame = state.derived_data.get("frame_number", 0)
            
            # Delegate tracking to External Tracker
            state.tracker.update_rule_state(config_id, decision, current_frame)
            
            # Check confirmation status
            final_decision = state.tracker.is_rule_confirmed(config_id, persistence)
            
            # Debug Persistence
            current_count, _ = state.tracker.persistence_state.get(config_id, (0, 0))
            if current_count > 0:
                # Removed verbose debug log
                pass
            
            # Apply KPI updates if configured (only once per confirmation per cycle)
            # Skip KPI updates for confirmation_mode rules - they are handled at cycle boundary
            kpi_updates_config = config.get("kpi_updates", {})
            is_confirmation_rule = config.get("static_values", {}).get("confirmation_mode", False)
            
            if kpi_updates_config and final_decision and not is_confirmation_rule:
                # Create unique key for this rule instance in this cycle
                cycle_num = state.cycle_state.cycle_count
                kpi_key = f"{config_id}_cycle_{cycle_num}_true"
                
                # Only apply once per cycle
                if kpi_key not in state.kpi_updates_applied:
                    updates = kpi_updates_config.get("on_true", [])
                    if updates:
                        self._apply_kpi_updates(source_id, updates)
                        state.kpi_updates_applied.add(kpi_key)
            
            # Also check on_false (for when decision is confirmed as False)
            if kpi_updates_config and not final_decision and not decision:
                cycle_num = state.cycle_state.cycle_count
                kpi_key = f"{config_id}_cycle_{cycle_num}_false"
                
                if kpi_key not in state.kpi_updates_applied:
                    updates = kpi_updates_config.get("on_false", [])
                    if updates:
                        self._apply_kpi_updates(source_id, updates)
                        state.kpi_updates_applied.add(kpi_key)
            
            return final_decision
            
        except Exception as e:
            print(f"  [ERROR] Rule {rule_name} failed: {e}")
            return False
    
    def _resolve_value(self, source_id: str, binding: str) -> Any:
        """
        Resolve a binding string to actual value.
        Supports nested paths like executor_input_data.detections.Person
        """
        state = self.sources[source_id]
        
        if not isinstance(binding, str):
            return binding  # Already a value
        
        parts = binding.split(".")
        source = parts[0]
        
        if source == "executor_input_data":
            # Handle nested paths like executor_input_data.detections.Person
            if len(parts) > 2:
                # Navigate through nested dicts
                value = state.executor_input_data
                for part in parts[1:]:
                    if isinstance(value, dict):
                        value = value.get(part)
                    else:
                        return None
                    if value is None:
                        return None
                return value
            else:
                # Simple path: executor_input_data.key
                key = parts[1] if len(parts) > 1 else None
                if key:
                    return state.executor_input_data.get(key)
                return state.executor_input_data
        
        elif source == "predefined_data":
            # Handle nested paths
            if len(parts) > 2:
                value = state.predefined_data
                for part in parts[1:]:
                    if isinstance(value, dict):
                        value = value.get(part)
                    else:
                        return None
                    if value is None:
                        return None
                return value
            else:
                key = parts[1] if len(parts) > 1 else None
                if key:
                    return state.predefined_data.get(key)
                return state.predefined_data
        
        elif source == "derived_data":
            if len(parts) >= 3:
                # derived_data.rule_results.rule_name.key
                rule_name = parts[2]
                if len(parts) >= 4:
                    output_key = parts[3]
                    return state.derived_data.get("rule_results", {}).get(rule_name, {}).get(output_key)
                return state.derived_data.get("rule_results", {}).get(rule_name)
            return state.derived_data.get(parts[1]) if len(parts) > 1 else state.derived_data
        
        return binding
    
    def _get_rule_name_from_group(self, rule_group) -> str:
        """Extract rule name from a rule group."""
        if isinstance(rule_group, dict):
            return list(rule_group.keys())[0]
        elif isinstance(rule_group, list) and rule_group:
            return self._get_rule_name_from_group(rule_group[0])
        return "unknown"
    
    def _apply_kpi_updates(self, source_id: str, updates: List[Dict]) -> None:
        """
        Apply KPI updates to analytics_data.
        
        Updates format:
        [
            {"target": "kpi.successful_picks", "op": "increment", "value": 1},
            {"target": "kpi.misplacement_count", "op": "set", "value": 5}
        ]
        """
        if not updates:
            return
            
        state = self.sources[source_id]
        analytics = state.analytics_data
        
        for update in updates:
            target = update.get("target", "")
            op = update.get("op", "increment")
            value = update.get("value", 1)
            
            if not target:
                continue
            
            # Parse target path (e.g., "kpi.successful_picks")
            parts = target.split(".")
            
            # Handle kpi.* targets - route to resultData.kpi
            if parts[0] == "kpi":
                parts = ["resultData", "kpi"] + parts[1:]
            
            # Navigate to parent object
            obj = analytics
            for part in parts[:-1]:
                if part not in obj:
                    obj[part] = {}
                obj = obj[part]
            
            # Apply operation
            field = parts[-1]
            current = obj.get(field, 0)
            
            if op in ("increment", "+", "add"):
                obj[field] = current + value
            elif op in ("decrement", "-", "sub"):
                obj[field] = current - value
            elif op == "set":
                obj[field] = value
            
            print(f"  [KPI] {target}: {current} -> {obj[field]} ({op} {value})")
    
    def _build_cycle_analytics(
        self, 
        source_id: str, 
        cycle_num: int,
        start_frame: int,
        end_frame: int,
        activity_timing: Dict,
        status: str,
        has_anomaly: bool = False,
        anomaly_type: str = None
    ) -> Dict:
        """
        Build a detailed cycle object for analytics output.
        """
        state = self.sources[source_id]
        fps = state.analytics_data.get("fps", 30)
        
        # Calculate times
        start_time_sec = start_frame / fps if start_frame else 0
        end_time_sec = end_frame / fps if end_frame else 0
        actual_time_sec = end_time_sec - start_time_sec
        
        # Build steps array
        steps = []
        for act_id in self.activity_sequence:
            timing = activity_timing.get(act_id, {})
            
            frame_start = timing.get("start_frame")
            frame_end = timing.get("end_frame")
            time_start = timing.get("start_time")
            time_end = timing.get("end_time")
            
            # Calculate time in seconds
            time_start_sec = frame_start / fps if frame_start else None
            time_end_sec = frame_end / fps if frame_end else None
            actual_step_time = (time_end_sec - time_start_sec) if (time_start_sec is not None and time_end_sec is not None) else None
            
            # Get expected time from state machine
            expected_time = self.state_machine.get(act_id, {}).get("expected_time", 0)
            
            step = {
                "name": act_id.lower(),
                "frame_start": frame_start,
                "frame_end": frame_end,
                "time_start_sec": time_start_sec,
                "time_end_sec": time_end_sec,
                "timestamp_start": {"$date": time_start} if time_start else None,
                "timestamp_end": {"$date": time_end} if time_end else None,
                "actual_time_sec": actual_step_time,
                "expected_time_sec": expected_time,
                "completed": frame_end is not None
            }
            steps.append(step)
        
        # Get expected cycle time
        expected_cycle_time = state.analytics_data.get("resultData", {}).get("expected_cycle_time", 15)
        
        # Build cycle object
        cycle_obj = {
            "cycle_number": cycle_num,
            "start_frame": start_frame,
            "end_frame": end_frame,
            "start_time_sec": start_time_sec,
            "end_time_sec": end_time_sec,
            "start_timestamp": {"$date": activity_timing.get(self.activity_sequence[0], {}).get("start_time")} if activity_timing else None,
            "end_timestamp": {"$date": activity_timing.get(self.end_activity, {}).get("end_time")} if activity_timing else None,
            "actual_time_sec": actual_time_sec,
            "expected_time_sec": expected_cycle_time,
            "completed": status == "SUCCESS" or "SUCCESS" in status,
            "has_anomaly": has_anomaly,
            "steps": steps,
            "anomaly_clips": []
        }
        
        return cycle_obj
    
    def _update_analytics_after_cycle(self, source_id: str, cycle_obj: Dict):
        """
        Update analytics data after a cycle completes and save to file.
        """
        state = self.sources[source_id]
        analytics = state.analytics_data
        
        # Ensure resultData structure exists
        if "resultData" not in analytics:
            analytics["resultData"] = {"cycles": [], "kpi": {}, "anomalies": []}
        
        result_data = analytics["resultData"]
        
        # Add cycle to cycles list
        if "cycles" not in result_data:
            result_data["cycles"] = []
        result_data["cycles"].append(cycle_obj)
        
        # Update total_cycles
        result_data["total_cycles"] = len(result_data["cycles"])
        
        # Calculate derived KPIs
        self._calculate_derived_kpis(source_id)
        
        # Auto-save analytics (Mongo preferred)
        if self.mongo_client:
            self._save_analytics_to_mongo(source_id)
        else:
            self._save_analytics_to_file(source_id)
    
    def _save_analytics_to_mongo(self, source_id: str):
        """Save analytics to MongoDB collection."""
        if self.mongo_client is None or self.mongo_db is None:
            return

        state = self.sources[source_id]
        analytics = state.analytics_data
        
        # Prepare document for MongoDB (add sop_id, timestamp)
        doc = analytics.copy()
        doc["sop_id"] = self.sop_id
        doc["source_id"] = source_id
        doc["run_id"] = state.run_id # Add run_id to document
        doc["last_updated"] = datetime.now()
        
        try:
            coll = self.mongo_db[self.mongo_collection_name]
            
            # Use run_id as unique key for this session
            coll.update_one(
                {"run_id": state.run_id},
                {"$set": doc},
                upsert=True
            )
            print(f"  [Analytics] Saved to MongoDB: {self.mongo_collection_name} (run_id: {state.run_id})")
        except Exception as e:
            print(f"  [Analytics] Error saving to MongoDB: {e}")

    def _save_analytics_to_file(self, source_id: str):
        """
        Save analytics data to file. Uses sop_id for the filename.
        """
        state = self.sources[source_id]
        
        # Determine output path if not set
        if not state.analytics_output_path:
            # Use sop_id for filename, save in ABB folder
            script_dir = os.path.dirname(os.path.abspath(__file__))
            filename = f"analytics_output_{self.sop_id}.json"
            state.analytics_output_path = os.path.join(script_dir, filename)
        
        try:
            with open(state.analytics_output_path, 'w') as f:
                json.dump(state.analytics_data, f, indent=2)
            print(f"  [Analytics] Saved to file: {state.analytics_output_path}")
        except Exception as e:
            print(f"  [Analytics] Error saving to file: {e}")
    
    def _calculate_derived_kpis(self, source_id: str):
        """
        Calculate derived KPIs: pph, avg_cycle_time, order_fulfilment_ratio.
        """
        state = self.sources[source_id]
        analytics = state.analytics_data
        result_data = analytics.get("resultData", {})
        kpi = result_data.get("kpi", {})
        cycles = result_data.get("cycles", [])
        
        if not cycles:
            return
        
        # Calculate avg_cycle_time
        completed_cycles = [c for c in cycles if c.get("completed", False)]
        if completed_cycles:
            total_time = sum(c.get("actual_time_sec", 0) for c in completed_cycles)
            kpi["avg_cycle_time"] = round(total_time / len(completed_cycles), 2)
        
        # Calculate PPH (picks per hour)
        successful_picks = kpi.get("successful_picks", 0)
        if completed_cycles and successful_picks > 0:
            total_processing_time = sum(c.get("actual_time_sec", 0) for c in completed_cycles)
            if total_processing_time > 0:
                kpi["pph"] = int((successful_picks / total_processing_time) * 3600)
        
        # Calculate order_fulfilment_ratio
        induct_count = analytics.get("requestData", {}).get("inductCount", 0)
        if induct_count > 0:
            kpi["order_fulfilment_ratio"] = f"{successful_picks}/{induct_count}"
        else:
            kpi["order_fulfilment_ratio"] = f"{successful_picks}/{len(cycles)}"
    
    # =========================================================================
    # STATE MACHINE TRANSITIONS
    # =========================================================================
    
    def _check_activity_transition(
        self,
        source_id: str,
        frame_number: int,
        timestamp: str
    ) -> Optional[Dict]:
        """
        Check if we should transition to a new activity.
        """
        state = self.sources[source_id]
        cycle = state.cycle_state
        
        current_activity = cycle.current_activity
        
        # CASE 1: Cycle not started - check start_activity
        if current_activity is None:
            if self.start_activity and self._check_activity_rules(source_id, self.start_activity):
                return self._start_cycle(source_id, frame_number, timestamp)
        
        # CASE 2: At end activity - handle confirmation rules + regular anomalies + restart
        elif current_activity == self.end_activity:
            cycle = state.cycle_state
            
            # 1. Track confirmation rules (rules with confirmation_mode: true)
            has_confirmation_rules = self._track_confirmation_rules(source_id, current_activity)
            
            # 2. Check regular anomaly rules (non-confirmation mode)
            if self._check_anomaly_rules(source_id, current_activity, skip_confirmation_rules=True):
                return self._handle_anomaly(source_id, current_activity, frame_number, timestamp)
            
            # 3. Check for cycle restart
            if self._check_activity_rules(source_id, self.start_activity):
                # Check if confirmation rules were satisfied
                if has_confirmation_rules and not self._are_confirmations_satisfied(source_id, current_activity):
                    # Confirmation failed - trigger anomaly
                    cycle_logger.warning(f"  [Frame {frame_number}] CONFIRMATION FAILED | Cycle Reset")
                    return self._handle_confirmation_anomaly(source_id, current_activity, frame_number, timestamp)
                else:
                    # All good - cycle success
                    return self._complete_and_restart_cycle(source_id, frame_number, timestamp)
        
        # CASE 3: In middle - check next activities from state machine
        else:
            # 1. Track confirmation rules (if any) for current activity
            has_confirmation_rules = self._track_confirmation_rules(source_id, current_activity)
            
            # 2. Check if current activity rules are satisfied (for instruction repetition)
            current_activity_success = self._check_activity_rules(source_id, current_activity)
            
            # 2a. Check for wrong activity (e.g., left hand raised when expecting right hand)
            # OR no activity (user not doing anything when they should)
            # This should happen BEFORE checking anomaly_rules, so we can send immediate feedback
            if not current_activity_success:
                # Get things_present from executor_input_data to detect wrong activity
                things_present = state.executor_input_data.get("things_present", [])
                # Also check additional_fields if things_present is not in executor_input_data
                if not things_present:
                    things_present = state.executor_input_data.get("additional_data", {}).get("things_present", [])
                
                # Ensure things_present is a list
                if not isinstance(things_present, list):
                    if isinstance(things_present, str):
                        # Try to parse if it's a JSON string
                        try:
                            import json
                            things_present = json.loads(things_present)
                        except:
                            things_present = [things_present] if things_present else []
                    else:
                        things_present = []
                
                # Always check for wrong activity when activity fails (even if things_present is empty)
                # This handles both wrong activity AND no activity scenarios
                session_id = getattr(self, '_session_id', None) or state.session_id
                manual_id = getattr(self, '_manual_id', None) or state.manual_id
                
                if session_id and manual_id:
                    cycle_logger.info(
                        f"  [Frame {frame_number}] Activity {current_activity} failed. "
                        f"Checking for wrong/no activity. things_present={things_present}"
                    )
                    if HAS_INSTRUCTION_SENDER:
                        instruction_sender = get_instruction_sender()
                        
                        # FIRST: Check if anomaly_rules are triggered (more specific detection)
                        # This matches ABB's approach - check anomaly_rules for current activity
                        anomaly_detected = False
                        if current_activity in self.rules_map:
                            # Check anomaly rules for current activity to see if wrong activity is detected
                            anomaly_detected = self._check_anomaly_rules(source_id, current_activity, skip_confirmation_rules=True)
                        
                        if anomaly_detected:
                            # Anomaly detected via anomaly_rules - send anomaly message
                            cycle_logger.warning(
                                f"  [Frame {frame_number}] Anomaly detected for current activity {current_activity} "
                                f"via anomaly_rules. Sending anomaly message."
                            )
                            
                            # Send anomaly message via detect_and_send_wrong_activity
                            wrong_activity_detected = instruction_sender.detect_and_send_wrong_activity(
                                activity_id=current_activity,
                                things_present=things_present,
                                source_id=source_id,
                                session_id=session_id,
                                manual_id=manual_id,
                                frame_number=frame_number,
                                cycle_count=cycle.cycle_count
                            )
                            
                            if wrong_activity_detected:
                                cycle_logger.info(
                                    f"  [Frame {frame_number}] Anomaly message sent for {current_activity} "
                                    f"(wrong activity detected via anomaly_rules)"
                                )
                        else:
                            # No anomaly detected via rules, but activity rules failed
                            # Send general wrong activity detection
                            wrong_activity_detected = instruction_sender.detect_and_send_wrong_activity(
                                activity_id=current_activity,
                                things_present=things_present,
                                source_id=source_id,
                                session_id=session_id,
                                manual_id=manual_id,
                                frame_number=frame_number,
                                cycle_count=cycle.cycle_count
                            )
                            
                            if wrong_activity_detected:
                                cycle_logger.info(
                                    f"  [Frame {frame_number}] Wrong/no activity detected and corrective message sent"
                                )
                    else:
                        cycle_logger.warning("Instruction sender not available for wrong activity detection")
            
            # Get things_present for repeat instruction (to send better messages)
            things_present_for_repeat = state.executor_input_data.get("things_present", [])
            if not things_present_for_repeat:
                things_present_for_repeat = state.executor_input_data.get("additional_data", {}).get("things_present", [])
            if not isinstance(things_present_for_repeat, list):
                things_present_for_repeat = []
            
            self._check_and_repeat_instruction(
                activity_id=current_activity,
                source_id=source_id,
                frame_number=frame_number,
                cycle_count=cycle.cycle_count,
                activity_success=current_activity_success,
                things_present=things_present_for_repeat
            )
            
            # 3. Check regular (non-confirmation) Anomaly Rules
            # Note: We already checked anomaly_rules above when activity failed (to send immediate message)
            # Here we check again to see if we should reset the cycle (after persistence threshold)
            # This matches ABB's approach - anomaly_rules can trigger cycle reset
            anomaly_confirmed = self._check_anomaly_rules(source_id, current_activity, skip_confirmation_rules=True)
            if anomaly_confirmed:
                # Anomaly confirmed after persistence - reset cycle (matches ABB behavior)
                cycle_logger.warning(
                    f"  [Frame {frame_number}] Anomaly CONFIRMED for {current_activity} after persistence. Resetting cycle."
                )
                return self._handle_anomaly(source_id, current_activity, frame_number, timestamp)

            # 4. Check if CURRENT activity is confirmed before allowing transition
            # Exception: Start activity (PERSON_PRESENT) doesn't need confirmation - it's a waiting state
            # For other activities, we require confirmation to ensure they're completed correctly
            is_start_activity = (current_activity == self.start_activity)
            
            if not is_start_activity:
                # For non-start activities, require confirmation before transitioning
                current_activity_confirmed = self._is_activity_confirmed(source_id, current_activity)
                
                if not current_activity_confirmed:
                    # Current activity not confirmed - block transition
                    cycle_logger.debug(
                        f"  [Frame {frame_number}] Transition BLOCKED: {current_activity} not confirmed yet. "
                        f"Waiting for correct completion..."
                    )
                    return None  # Don't transition - wait for current activity to be confirmed
            else:
                # Start activity - no confirmation needed, just check if current activity rules pass
                current_activity_confirmed = self._check_activity_rules(source_id, current_activity)
                if not current_activity_confirmed:
                    # Start activity rules not passing - don't allow transition
                    return None

            # 4a. Current activity is confirmed/ready -> emit a completion message ONCE
            # This mirrors instruction_graph behavior: send "completed" then send next "inProgress".
            if HAS_INSTRUCTION_SENDER:
                try:
                    # Get instruction ONLY from SOP, no hardcoded fallback
                    step_text = None
                    if hasattr(self, 'state_machine') and current_activity in self.state_machine:
                        step_text = self.state_machine[current_activity].get("instruction")
                    
                    # Only send if instruction exists in SOP
                    if step_text:
                        self._send_step_status_message(
                            source_id=source_id,
                            activity_id=current_activity,
                            status="completed",
                            cycle_count=cycle.cycle_count,
                            step_text=step_text,
                            is_repeat=False,
                            feedback=""
                        )
                except Exception:
                    pass
            
            # 5. Current activity is ready (confirmed or start activity passing) - now check Valid Transitions
            next_activities = self.state_machine.get(current_activity, {}).get("next_act", [])
            next_activity_passed = False
            
            # 5a. Send instruction for next activity IMMEDIATELY when current activity is ready
            # This ensures user gets instruction BEFORE performing the next activity
            # Initialize tracking if not exists
            if not hasattr(state, '_next_activity_instruction_sent'):
                state._next_activity_instruction_sent = {}
            
            for next_activity in next_activities:
                cache_key = f"{source_id}:{next_activity}"
                if cache_key not in state._next_activity_instruction_sent:
                    # Send instruction for next activity BEFORE checking if rules pass
                    # This gives user the instruction before they need to perform it
                    cycle_logger.info(
                        f"  [Frame {frame_number}] Current activity {current_activity} ready. "
                        f"Sending instruction for next activity: {next_activity} (before user performs it)"
                    )
                    self._send_activity_instruction(
                        activity_id=next_activity,
                        source_id=source_id,
                        frame_number=frame_number,
                        cycle_count=cycle.cycle_count
                    )
                    state._next_activity_instruction_sent[cache_key] = frame_number
            
            for next_activity in next_activities:
                if self._check_activity_rules(source_id, next_activity):
                    next_activity_passed = True
                    # Before transitioning, check if confirmation rules were satisfied
                    if has_confirmation_rules and not self._are_confirmations_satisfied(source_id, current_activity):
                        # Confirmation failed - trigger anomaly
                        cycle_logger.warning(f"  [Frame {frame_number}] CONFIRMATION FAILED: {current_activity} | Transition Blocked")
                        return self._handle_confirmation_anomaly(source_id, current_activity, frame_number, timestamp)
                    
                    # Clear confirmation state for this activity before transitioning
                    self._clear_confirmation_state(source_id, current_activity)
                    # Clear the instruction sent flag for this transition
                    if hasattr(state, '_next_activity_instruction_sent'):
                        cache_key = f"{source_id}:{next_activity}"
                        state._next_activity_instruction_sent.pop(cache_key, None)
                    cycle_logger.info(
                        f"  [Frame {frame_number}] Transition ALLOWED: {current_activity} {'confirmed' if not is_start_activity else 'ready'} → {next_activity}"
                    )
                    return self._transition_to_activity(source_id, next_activity, frame_number, timestamp)
            
            # 5a. If no next activity passed, check if we should send guidance for next activity
            # This helps when user is stuck and needs to perform the next activity
            if not next_activity_passed and next_activities:
                # Get things_present to determine what guidance to send
                things_present = state.executor_input_data.get("things_present", [])
                if not things_present:
                    things_present = state.executor_input_data.get("additional_data", {}).get("things_present", [])
                
                if not isinstance(things_present, list):
                    if isinstance(things_present, str):
                        try:
                            import json
                            things_present = json.loads(things_present)
                        except:
                            things_present = [things_present] if things_present else []
                    else:
                        things_present = []
                
                # Check if we should send guidance for the next activity
                # Send guidance if:
                # 1. Current activity is passing (user is ready for next step), OR
                # 2. Current activity is start activity (always allow guidance)
                # This ensures we check even when stuck
                should_check_guidance = current_activity_success or (current_activity == self.start_activity)
                
                if should_check_guidance:
                    session_id = getattr(self, '_session_id', None) or state.session_id
                    manual_id = getattr(self, '_manual_id', None) or state.manual_id
                    
                    if session_id and manual_id and HAS_INSTRUCTION_SENDER:
                        # Get the first next activity (primary next step)
                        primary_next_activity = next_activities[0] if next_activities else None
                        
                        if primary_next_activity:
                            # Check if enough time has passed since last guidance
                            cache_key = f"{source_id}:{session_id}"
                            last_guidance_key = f"guidance_{primary_next_activity}"
                            last_guidance_frame = state.derived_data.get(last_guidance_key, -1)
                            
                            # Send guidance every 5 frames (~0.17 seconds) when stuck (very frequent for immediate feedback)
                            # This ensures anomaly_rules persistence counters don't reset
                            if (frame_number - last_guidance_frame) >= 5:
                                instruction_sender = get_instruction_sender()
                                
                                # FIRST: Check if next activity's anomaly_rules are triggered (wrong activity detected)
                                # This matches ABB's approach - check anomaly_rules for the activity we're trying to enter
                                anomaly_detected = False
                                if primary_next_activity in self.rules_map:
                                    # Debug: Check what's in executor_input_data
                                    executor_data_tp = state.executor_input_data.get("things_present", [])
                                    additional_data_tp = state.executor_input_data.get("additional_data", {}).get("things_present", [])
                                    
                                    cycle_logger.info(
                                        f"  [Frame {frame_number}] 🔍 Checking anomaly_rules for next activity {primary_next_activity} "
                                        f"(current: {current_activity})"
                                    )
                                    cycle_logger.info(
                                        f"  [Frame {frame_number}] 📊 Data check: things_present={things_present}, "
                                        f"executor_input_data.things_present={executor_data_tp}, "
                                        f"executor_input_data.additional_data.things_present={additional_data_tp}"
                                    )
                                    
                                    # Temporarily check anomaly rules for next activity
                                    # We need to evaluate them to see if wrong activity is detected
                                    anomaly_detected = self._check_anomaly_rules(source_id, primary_next_activity, skip_confirmation_rules=True)
                                    
                                    if anomaly_detected:
                                        cycle_logger.warning(
                                            f"  [Frame {frame_number}] ✅ ANOMALY DETECTED via anomaly_rules for {primary_next_activity}! "
                                            f"(wrong activity detected - will send message)"
                                        )
                                    else:
                                        cycle_logger.info(
                                            f"  [Frame {frame_number}] ⚠️ Anomaly rules NOT confirmed for {primary_next_activity} "
                                            f"(may need more frames for persistence, or wrong activity not detected by rules)"
                                        )
                                
                                if anomaly_detected:
                                    # Anomaly detected via anomaly_rules - send anomaly message
                                    cycle_logger.warning(
                                        f"  [Frame {frame_number}] Anomaly detected for next activity {primary_next_activity} "
                                        f"(stuck in {current_activity}). Sending anomaly message."
                                    )
                                    
                                    # Send anomaly message via detect_and_send_wrong_activity
                                    guidance_sent = instruction_sender.detect_and_send_wrong_activity(
                                        activity_id=primary_next_activity,
                                        things_present=things_present,
                                        source_id=source_id,
                                        session_id=session_id,
                                        manual_id=manual_id,
                                        frame_number=frame_number,
                                        cycle_count=cycle.cycle_count
                                    )
                                    
                                    if guidance_sent:
                                        state.derived_data[last_guidance_key] = frame_number
                                        cycle_logger.info(
                                            f"  [Frame {frame_number}] Sent anomaly message for next activity {primary_next_activity} "
                                            f"(wrong activity detected while stuck in {current_activity})"
                                        )
                                else:
                                    # No anomaly detected via rules, but next activity rules are failing
                                    # Send general guidance based on what's detected
                                    guidance_sent = instruction_sender.detect_and_send_wrong_activity(
                                        activity_id=primary_next_activity,  # Check what's wrong with NEXT activity
                                        things_present=things_present,
                                        source_id=source_id,
                                        session_id=session_id,
                                        manual_id=manual_id,
                                        frame_number=frame_number,
                                        cycle_count=cycle.cycle_count
                                    )
                                    
                                    if guidance_sent:
                                        state.derived_data[last_guidance_key] = frame_number
                                        cycle_logger.info(
                                            f"  [Frame {frame_number}] Sent guidance for next activity {primary_next_activity} "
                                            f"(stuck in {current_activity})"
                                        )
        
        return None
    
    def _track_confirmation_rules(self, source_id: str, activity_id: str) -> bool:
        """
        Track rules with confirmation_mode: true.
        Returns True if there are any confirmation rules.
        
        Confirmation rules work opposite to regular anomalies:
        - Tracks consecutive frames where the rule returns False (good state)
        - If good for confirm_frames, marks as confirmed
        """
        if activity_id not in self.rules_map:
            return False
        
        state = self.sources[source_id]
        cycle = state.cycle_state
        rule_config = self.rules_map[activity_id]
        anomaly_rules = rule_config.get("anomaly_rules", [])
        
        has_confirmation_rules = False
        
        for rule_item in anomaly_rules:
            rules_to_check = [rule_item] if isinstance(rule_item, dict) else rule_item
            
            for sub in rules_to_check:
                if not isinstance(sub, dict):
                    continue
                    
                rule_name = list(sub.keys())[0]
                rule_cfg = sub[rule_name]
                static_vals = rule_cfg.get("static_values", {})
                
                # Check if this is a confirmation rule
                is_confirmation = static_vals.get("confirmation_mode", False)
                # Debug: Show what we found
                # Removed verbose debug log
                
                if not is_confirmation:
                    continue
                
                has_confirmation_rules = True
                confirm_frames = int(static_vals.get("confirm_frames", 5))
                
                # Skip if already confirmed
                confirm_key = f"{activity_id}_{rule_name}_confirmed"
                if state.derived_data.get(confirm_key, False):
                    continue
                
                # Execute rule to get result
                self._execute_single_rule(source_id, sub)
                res = state.derived_data.get("rule_results", {}).get(rule_name, {})
                decision = res.get("decision", False)
                
                # For confirmation: we track consecutive FALSE (good state)
                # because decision=True means "bad" (misplaced/anomaly condition)
                count_key = f"{activity_id}_{rule_name}_confirm_count"
                
                if not decision:  # Good state
                    current_count = state.derived_data.get(count_key, 0) + 1
                    state.derived_data[count_key] = current_count
                    
                    iou = res.get("iou", 0)
                    # Removed verbose debug log
                    
                    if current_count >= confirm_frames:
                        state.derived_data[confirm_key] = True
                        # Removed verbose debug log
                else:
                    # Bad state - reset count
                    state.derived_data[count_key] = 0
        
        return has_confirmation_rules
    
    def _are_confirmations_satisfied(self, source_id: str, activity_id: str) -> bool:
        """Check if all confirmation rules for the activity were satisfied."""
        if activity_id not in self.rules_map:
            return True
        
        state = self.sources[source_id]
        rule_config = self.rules_map[activity_id]
        anomaly_rules = rule_config.get("anomaly_rules", [])
        
        for rule_item in anomaly_rules:
            rules_to_check = [rule_item] if isinstance(rule_item, dict) else rule_item
            
            for sub in rules_to_check:
                if not isinstance(sub, dict):
                    continue
                    
                rule_name = list(sub.keys())[0]
                rule_cfg = sub[rule_name]
                static_vals = rule_cfg.get("static_values", {})
                
                if static_vals.get("confirmation_mode", False):
                    confirm_key = f"{activity_id}_{rule_name}_confirmed"
                    if not state.derived_data.get(confirm_key, False):
                        return False
        
        return True
    
    def _handle_confirmation_anomaly(self, source_id: str, activity_id: str, frame_number: int, timestamp: str) -> Dict:
        """Handle anomaly when confirmation rule wasn't satisfied before restart."""
        state = self.sources[source_id]
        cycle = state.cycle_state
        
        cycle_logger.warning(f"  [Frame {frame_number}] ANOMALY: {activity_id} (confirmation failed) | Cycle Reset")

        # Emit SOP step failed message for UI/Speech
        if HAS_INSTRUCTION_SENDER:
            try:
                # Get instruction ONLY from SOP, no hardcoded fallback
                step_text = None
                if hasattr(self, 'state_machine') and activity_id in self.state_machine:
                    step_text = self.state_machine[activity_id].get("instruction")
                
                # Only send if instruction exists in SOP
                if step_text:
                    self._send_step_status_message(
                        source_id=source_id,
                        activity_id=activity_id,
                        status="failed",
                        cycle_count=cycle.cycle_count,
                        step_text=step_text,
                        is_repeat=False,
                        feedback="confirmation failed"
                    )
            except Exception:
                pass
        
        # Record anomaly
        cycle_result = {
            "cycle_number": cycle.cycle_count,
            "status": "ANOMALY",
            "anomaly_type": "CONFIRMATION_FAILED",
            "activity": activity_id,
            "frame": frame_number,
            "timestamp": timestamp
        }
        state.completed_cycles.append(cycle_result)
        
        # Build detailed cycle analytics with confirmation anomaly
        cycle_analytics = self._build_cycle_analytics(
            source_id=source_id,
            cycle_num=cycle.cycle_count,
            start_frame=cycle.cycle_start_frame,
            end_frame=frame_number,
            activity_timing=cycle.activity_timing,
            status="ANOMALY",
            has_anomaly=True,
            anomaly_type="CONFIRMATION_FAILED"
        )
        self._update_analytics_after_cycle(source_id, cycle_analytics)
        
        # Reset cycle state
        cycle.current_activity = None
        cycle.previous_activity = activity_id
        cycle.is_active = False
        cycle.placement_confirmed = False
        cycle.consecutive_iou_success = 0
        
        # Apply KPI updates for confirmation mode rules that failed
        rule_config = self.rules_map.get(activity_id, {})
        anomaly_rules = rule_config.get("anomaly_rules", [])
        
        for rule_item in anomaly_rules:
            rules_to_check = [rule_item] if isinstance(rule_item, dict) else rule_item
            
            for sub in rules_to_check:
                if not isinstance(sub, dict):
                    continue
                    
                rule_name = list(sub.keys())[0]
                rule_cfg = sub[rule_name]
                static_vals = rule_cfg.get("static_values", {})
                
                # Only apply for confirmation_mode rules
                if static_vals.get("confirmation_mode", False):
                    kpi_updates = rule_cfg.get("kpi_updates", {})
                    on_true_updates = kpi_updates.get("on_true", [])
                    
                    if on_true_updates:
                        # Removed verbose debug log
                        self._apply_kpi_updates(source_id, on_true_updates)
        
        # Clear confirmation state
        self._clear_confirmation_state(source_id, activity_id)
        
        # Reset tracker
        state.tracker.reset()
        
        return {
            "current_activity": None,
            "cycle_active": False,
            "cycle_count": cycle.cycle_count,
            "transition": {"from": activity_id, "to": None},
            "cycle_completed": cycle_result
        }
    
    def _clear_confirmation_state(self, source_id: str, activity_id: str) -> None:
        """Clear confirmation tracking state for a new cycle."""
        if activity_id not in self.rules_map:
            return
        
        state = self.sources[source_id]
        rule_config = self.rules_map[activity_id]
        anomaly_rules = rule_config.get("anomaly_rules", [])
        
        for rule_item in anomaly_rules:
            rules_to_check = [rule_item] if isinstance(rule_item, dict) else rule_item
            
            for sub in rules_to_check:
                if not isinstance(sub, dict):
                    continue
                    
                rule_name = list(sub.keys())[0]
                rule_cfg = sub[rule_name]
                
                if rule_cfg.get("static_values", {}).get("confirmation_mode", False):
                    state.derived_data.pop(f"{activity_id}_{rule_name}_confirmed", None)
                    state.derived_data.pop(f"{activity_id}_{rule_name}_confirm_count", None)
    
    def _check_anomaly_rules(self, source_id: str, activity_id: str, skip_confirmation_rules: bool = False) -> bool:
        """
        Check if any ANOMALY rules for the activity are satisfied.
        Returns True if Anomaly Detected.
        
        IMPORTANT: Anomaly should only trigger if the activity rules are NOT passing.
        If the user is correctly performing the activity, anomalies should not trigger.
        
        If skip_confirmation_rules=True, rules with confirmation_mode: true are skipped.
        """
        if not activity_id or activity_id not in self.rules_map:
            cycle_logger.debug(f"  [ANOMALY-CHECK] {activity_id}: Not in rules_map, skipping")
            return False
            
        rule_config = self.rules_map[activity_id]
        anomaly_rules = rule_config.get("anomaly_rules", [])
        
        if not anomaly_rules:
            cycle_logger.debug(f"  [ANOMALY-CHECK] {activity_id}: No anomaly_rules configured")
            return False
        
        # CRITICAL: Only check anomalies if activity rules are NOT passing
        # If user is correctly doing the activity, don't trigger anomalies
        activity_rules_passing = self._check_activity_rules(source_id, activity_id)
        if activity_rules_passing:
            cycle_logger.debug(
                f"  [ANOMALY-CHECK] {activity_id}: Activity rules are passing, "
                f"skipping anomaly check (user is doing correct action)"
            )
            return False
        
        cycle_logger.info(f"  [ANOMALY-CHECK] {activity_id}: Checking {len(anomaly_rules)} anomaly rule(s)")
            
        # Anomaly detected if ALL rules in a group pass (AND) or ANY group passes (OR) logic?
        # Usually anomaly_rules is a List of Rules.
        # Processor.py Logic: Aggregate Persistence
        # 1. Check if ALL conditions (AND Logic) are met in the CURRENT frame (Raw).
        # 2. If met, increment a single persistence counter for the anomaly event.
        # 3. If persistence threshold reached, trigger anomaly.
        
        state = self.sources[source_id]
        
        # 1. Check Raw Logic
        aggregate_raw_passed = True
        max_persistence = 1
        passed_rule_names = []
        
        for rule_item in anomaly_rules:
            item_passed = False
            item_persistence = 1
            rule_name_debug = "Unknown"
            
            if isinstance(rule_item, dict):
                # Single Rule
                rule_name = list(rule_item.keys())[0]
                rule_cfg = rule_item[rule_name]
                
                # Skip confirmation rules if requested
                if skip_confirmation_rules and rule_cfg.get("static_values", {}).get("confirmation_mode", False):
                    continue
                
                # Execute to update derived_data
                self._execute_single_rule(source_id, rule_item)
                
                rule_name_debug = rule_name
                
                # Get Raw Decision
                res = state.derived_data.get("rule_results", {}).get(rule_name, {})
                item_passed = res.get("decision", False)
                
                # Debug: Log single rule evaluation
                cycle_logger.info(
                    f"  [ANOMALY-RULE] {activity_id}: Rule '{rule_name}' decision={item_passed}, "
                    f"result={res}"
                )
                
                # Get Configured Persistence
                item_persistence = int(rule_cfg.get("static_values", {}).get("persistence") or rule_cfg.get("static_values", {}).get("threshold", 1))
                
            elif isinstance(rule_item, list):
                # OR Group (Nested List)
                # Any one must pass (Raw)
                group_passed = False
                sub_names = []
                all_skipped = True  # Track if all rules in group were skipped
                
                for sub in rule_item:
                    if isinstance(sub, dict):
                        name = list(sub.keys())[0]
                        sub_cfg = sub[name]
                        
                        # Skip confirmation rules if requested
                        if skip_confirmation_rules and sub_cfg.get("static_values", {}).get("confirmation_mode", False):
                            continue
                        
                        all_skipped = False
                        self._execute_single_rule(source_id, sub)
                        sub_names.append(name)
                        
                        res = state.derived_data.get("rule_results", {}).get(name, {})
                        decision = res.get("decision", False)
                        
                        # Debug: Log OR group rule evaluation
                        cycle_logger.info(
                            f"  [ANOMALY-OR-GROUP] {activity_id}: Rule '{name}' decision={decision}, "
                            f"result={res}"
                        )
                        
                        if decision:
                            group_passed = True
                            # If passed, we consider this rule's persistence requirement
                            p = int(sub_cfg.get("static_values", {}).get("persistence") or sub_cfg.get("static_values", {}).get("threshold", 1))
                            item_persistence = max(item_persistence, p)
                            cycle_logger.info(
                                f"  [ANOMALY-OR-GROUP-PASS] {activity_id}: Rule '{name}' PASSED! "
                                f"Group passed=True, persistence={item_persistence}"
                            )
                            break
                
                # If all rules were skipped, skip this entire group
                if all_skipped:
                    continue
                            
                item_passed = group_passed
                rule_name_debug = f"OR({','.join(sub_names)})"

            if not item_passed:
                aggregate_raw_passed = False
                # Debug print for failure
                # Removed verbose debug log
                # Fast Fail? Processor.py evaluates ALL for logging? 
                # We can break if not satisfying AND logic.
                break
                
            passed_rule_names.append(rule_name_debug)
            max_persistence = max(max_persistence, item_persistence)

        # 2. Track Aggregate State
        # Use a unique ID for this Activity's Anomaly State
        group_id = f"{activity_id}_ANOMALY_AGGREGATE"
        current_frame = state.derived_data.get("frame_number", 0)
        
        state.tracker.update_rule_state(group_id, aggregate_raw_passed, current_frame)
        
        # 3. Check Confirmation
        is_confirmed = state.tracker.is_rule_confirmed(group_id, max_persistence)
        
        # Debug Aggregate
        current_count, _ = state.tracker.persistence_state.get(group_id, (0, 0))
        # Always log when checking anomaly rules to see what's happening
        cycle_logger.info(
            f"  [ANOMALY-TRACKER] {activity_id}: Raw={aggregate_raw_passed}, Count={current_count}/{max_persistence} "
            f"Rules: {', '.join(passed_rule_names) if passed_rule_names else 'None'}, "
            f"Confirmed={is_confirmed}"
        )

        if is_confirmed:
            cycle_logger.warning(
                f"  [ANOMALY-CONFIRMED] {activity_id}: Confirmed after {max_persistence} frames. "
                f"Rules: {', '.join(passed_rule_names)}"
            )
            return True
        else:
            if aggregate_raw_passed and current_count == 0:
                cycle_logger.debug(
                    f"  [ANOMALY-RAW] {activity_id}: Raw conditions met but counter not started yet. "
                    f"Rules: {', '.join(passed_rule_names)}"
                )
            
        return False

    def _handle_anomaly(self, source_id: str, activity_id: str, frame_number: int, timestamp: str) -> Dict:
        """Handle detected anomaly and send anomaly message."""
        state = self.sources[source_id]
        cycle = state.cycle_state

        # Emit SOP step failed message for UI/Speech (in addition to anomaly TTS)
        if HAS_INSTRUCTION_SENDER:
            try:
                # Get instruction ONLY from SOP, no hardcoded fallback
                step_text = None
                if hasattr(self, 'state_machine') and activity_id in self.state_machine:
                    step_text = self.state_machine[activity_id].get("instruction")
                
                # Only send if instruction exists in SOP
                if step_text:
                    self._send_step_status_message(
                        source_id=source_id,
                        activity_id=activity_id,
                        status="failed",
                        cycle_count=cycle.cycle_count,
                        step_text=step_text,
                        is_repeat=False,
                        feedback="anomaly detected"
                    )
            except Exception:
                pass
        
        cycle_logger.warning(f"  [Frame {frame_number}] ANOMALY: {activity_id} | Sending anomaly message")
        
        # Send anomaly message via instruction sender
        session_id = getattr(self, '_session_id', None) or state.session_id
        manual_id = getattr(self, '_manual_id', None) or state.manual_id
        
        if session_id and manual_id and HAS_INSTRUCTION_SENDER:
            # Get things_present to determine what wrong activity was performed
            things_present = state.executor_input_data.get("things_present", [])
            if not things_present:
                things_present = state.executor_input_data.get("additional_data", {}).get("things_present", [])
            
            # Ensure things_present is a list
            if not isinstance(things_present, list):
                if isinstance(things_present, str):
                    try:
                        import json
                        things_present = json.loads(things_present)
                    except:
                        things_present = [things_present] if things_present else []
                else:
                    things_present = []
            
            if things_present:
                # Detect and send wrong activity message
                instruction_sender = get_instruction_sender()
                instruction_sender.detect_and_send_wrong_activity(
                    activity_id=activity_id,
                    things_present=things_present,
                    source_id=source_id,
                    session_id=session_id,
                    manual_id=manual_id,
                    frame_number=frame_number,
                    cycle_count=cycle.cycle_count
                )
        
        failed_cycle_num = cycle.cycle_count
        
        # Record failed cycle
        completed_cycle = {
            "cycle_number": failed_cycle_num,
            "start_frame": cycle.cycle_start_frame,
            "end_frame": frame_number,
            "activity_timing": dict(cycle.activity_timing),
            "status": "ANOMALY",
            "failed_activity": activity_id
        }
        state.completed_cycles.append(completed_cycle)
        
        # Build detailed cycle analytics with anomaly
        cycle_analytics = self._build_cycle_analytics(
            source_id=source_id,
            cycle_num=failed_cycle_num,
            start_frame=cycle.cycle_start_frame,
            end_frame=frame_number,
            activity_timing=cycle.activity_timing,
            status="ANOMALY",
            has_anomaly=True,
            anomaly_type=activity_id
        )
        self._update_analytics_after_cycle(source_id, cycle_analytics)
        
        # Reset Cycle
        self._reset_cycle_state(source_id)
        
        return {
            "from": activity_id,
            "to": None,
            "cycle_completed": {
                "status": "ANOMALY",
                "cycle_number": failed_cycle_num,
                "failed_activity": activity_id
            }
        }
    
    
    def _apply_rule_updates(self, source_id: str, activity_id: str, decision: bool = True):
        """
        Apply derived updates defined within rule configurations.
        """
        if activity_id not in self.rules_map:
            return
            
        state = self.sources[source_id]
        rule_map = self.rules_map[activity_id]
        
        # Helper to recursively search for updates
        def check_config_for_updates(config):
            if isinstance(config, list):
                for item in config:
                    check_config_for_updates(item)
            elif isinstance(config, dict):
                for key, value in config.items():
                    if isinstance(value, dict) and "derived_updates" in value:
                        updates_config = value["derived_updates"]
                        key_str = "true" if decision else "false"
                        
                        if key_str in updates_config:
                            actions_list = updates_config[key_str]
                            self._apply_updates_list(state, actions_list)

        rules_list = rule_map.get("activity_rules", [])
        check_config_for_updates(rules_list)

    def _apply_updates_list(self, state: SourceState, actions_list: List[Dict]):
        """Apply a list of update actions to state."""
        for action in actions_list:
            target = action.get("target") or action.get("kpi")
            op = action.get("op")
            val = action.get("value", 1)
            
            if not target: continue
            
            # Default: Update Derived Data dict
            parts = target.split('.')
            target_obj = state.derived_data
            
            # Navigate to last parent
            for part in parts[:-1]:
                target_obj = target_obj.setdefault(part, {})
            
            field = parts[-1]
            
            # Apply Op to dict
            curr = target_obj.get(field, 0)
            if op == "increment" or op == "+" or op == "add":
                target_obj[field] = curr + val
            elif op == "decrement" or op == "-" or op == "sub":
                target_obj[field] = curr - val
            elif op == "set":
                target_obj[field] = val

    def _send_activity_instruction(
        self,
        activity_id: str,
        source_id: str,
        frame_number: int,
        cycle_count: int = 0,
        is_repeat: bool = False
    ) -> None:
        """
        Send activity instruction via Kafka.
        
        Args:
            activity_id: Activity identifier
            source_id: Source identifier
            frame_number: Current frame number
            cycle_count: Current cycle number
            is_repeat: Whether this is a repeat instruction
        """
        if not HAS_INSTRUCTION_SENDER:
            return
        
        try:
            state = self.sources.get(source_id)
            if not state:
                return
            
            session_id = state.session_id
            manual_id = state.manual_id
            
            if not session_id or not manual_id:
                cycle_logger.debug(
                    f"Skipping instruction for {activity_id}: session_id={session_id}, manual_id={manual_id} not available"
                )
                return
            
            cycle_logger.info(
                f"Sending instruction for activity {activity_id} (Cycle {cycle_count}, Frame {frame_number}) "
                f"to session={session_id}, manual={manual_id}"
            )
            
            # Get instruction ONLY from SOP, no hardcoded fallback
            step_text = None
            if hasattr(self, 'state_machine') and activity_id in self.state_machine:
                step_text = self.state_machine[activity_id].get("instruction")
            
            # If no instruction in SOP, skip sending (or use generic message)
            if not step_text:
                cycle_logger.warning(
                    f"No instruction found in SOP for activity {activity_id}. Skipping instruction."
                )
                return
            
            # Log that we're using SOP-based instruction
            cycle_logger.info(
                f"Using SOP instruction for {activity_id}: '{step_text}' (from SOP JSON file)"
            )
            
            if is_repeat:
                step_text = f"Please try again. {step_text}"

            self._send_step_status_message(
                source_id=source_id,
                activity_id=activity_id,
                status="inProgress",
                cycle_count=cycle_count,
                step_text=step_text,
                is_repeat=is_repeat,
                feedback=""
            )
        except Exception as e:
            cycle_logger.warning(f"Error sending activity instruction: {e}")
    
    def _check_and_repeat_instruction(
        self,
        activity_id: str,
        source_id: str,
        frame_number: int,
        cycle_count: int,
        activity_success: bool,
        things_present: list = None
    ) -> None:
        """
        Check if activity is completed correctly, repeat instruction if not.
        Sends specific corrective messages based on what's wrong.
        
        Args:
            activity_id: Current activity identifier
            source_id: Source identifier
            frame_number: Current frame number
            cycle_count: Current cycle number
            activity_success: Whether activity rules passed
            things_present: List of detected things (for better corrective messages)
        """
        if not HAS_INSTRUCTION_SENDER:
            return
        
        try:
            state = self.sources.get(source_id)
            if not state:
                return
            
            # Track consecutive failures
            if not activity_success:
                state.activity_failure_count[activity_id] = state.activity_failure_count.get(activity_id, 0) + 1
            else:
                # Reset failure count on success
                state.activity_failure_count[activity_id] = 0
                return
            
            consecutive_failures = state.activity_failure_count.get(activity_id, 0)
            
            # Repeat instruction after 3 consecutive failures (about 1 second at 30fps)
            if consecutive_failures >= 3:
                # Throttle repeats to avoid spam (roughly matches ActivityInstructionSender behavior)
                last_repeat_key = f"repeat_{activity_id}_last_frame"
                last_repeat_frame = state.derived_data.get(last_repeat_key, -1)
                if (frame_number - last_repeat_frame) >= 60:
                    self._send_activity_instruction(
                        activity_id=activity_id,
                        source_id=source_id,
                        frame_number=frame_number,
                        cycle_count=cycle_count,
                        is_repeat=True
                    )
                    state.derived_data[last_repeat_key] = frame_number
        except Exception as e:
            cycle_logger.warning(f"Error checking activity instruction: {e}")
    
    def _start_cycle(self, source_id: str, frame_number: int, timestamp: str) -> Dict:
        """Start a new cycle."""
        state = self.sources[source_id]
        cycle = state.cycle_state
        
        if not cycle.is_active:
            cycle.cycle_count += 1
        
        cycle.is_active = True
        cycle.current_activity = self.start_activity
        cycle.previous_activity = None
        cycle.cycle_start_frame = frame_number
        cycle.cycle_start_time = timestamp

        # IMPORTANT: reset rule persistence counters at the start of every cycle.
        # Otherwise, persistence from a previous cycle can make the next cycle
        # immediately "confirmed" and complete in a few frames.
        state.tracker.reset()
        
        # Reset activity timing
        for act_id in cycle.activity_timing:
            cycle.activity_timing[act_id] = {
                "start_frame": None, "end_frame": None,
                "start_time": None, "end_time": None
            }
        
        # Record start activity timing
        cycle.activity_timing[self.start_activity]["start_frame"] = frame_number
        cycle.activity_timing[self.start_activity]["start_time"] = timestamp
        
        cycle_logger.info(f"  [Frame {frame_number}] CYCLE {cycle.cycle_count} STARTED at '{self.start_activity}'")
        
        # Send instruction for starting activity
        self._send_activity_instruction(
            activity_id=self.start_activity,
            source_id=source_id,
            frame_number=frame_number,
            cycle_count=cycle.cycle_count
        )
        
        return {
            "from": None,
            "to": self.start_activity,
            "cycle_started": True,
            "cycle_number": cycle.cycle_count
        }
    
    def _transition_to_activity(
        self,
        source_id: str,
        next_activity: str,
        frame_number: int,
        timestamp: str
    ) -> Dict:
        """Transition to next activity in cycle."""
        state = self.sources[source_id]
        cycle = state.cycle_state
        
        prev_activity = cycle.current_activity
        
        # Apply updates from previous activity rules (Success/Completion)
        if prev_activity:
            self._apply_rule_updates(source_id, prev_activity, decision=True)
        
        # End previous activity timing
        if prev_activity and prev_activity in cycle.activity_timing:
            cycle.activity_timing[prev_activity]["end_frame"] = frame_number
            cycle.activity_timing[prev_activity]["end_time"] = timestamp
        
        # Start new activity timing
        cycle.activity_timing[next_activity]["start_frame"] = frame_number
        cycle.activity_timing[next_activity]["start_time"] = timestamp
        
        cycle.previous_activity = prev_activity
        cycle.current_activity = next_activity
        
        cycle_logger.info(f"  [Frame {frame_number}] TRANSITION: '{prev_activity}' -> '{next_activity}'")
        
        # Send instruction for new activity (only if not already sent in advance)
        # Check if we already sent instruction for this activity in advance
        state = self.sources[source_id]
        if hasattr(state, '_next_activity_instruction_sent'):
            cache_key = f"{source_id}:{next_activity}"
            if cache_key in state._next_activity_instruction_sent:
                # Instruction already sent in advance - skip to avoid duplicate
                cycle_logger.debug(
                    f"  [Frame {frame_number}] Instruction for {next_activity} already sent in advance, skipping duplicate"
                )
                state._next_activity_instruction_sent.pop(cache_key, None)
            else:
                # Instruction not sent yet - send it now
                self._send_activity_instruction(
                    activity_id=next_activity,
                    source_id=source_id,
                    frame_number=frame_number,
                    cycle_count=cycle.cycle_count
                )
        else:
            # No tracking - send instruction normally
            self._send_activity_instruction(
                activity_id=next_activity,
                source_id=source_id,
                frame_number=frame_number,
                cycle_count=cycle.cycle_count
            )
        
        # Reset failure count for new activity
        state = self.sources[source_id]
        if next_activity in state.activity_failure_count:
            state.activity_failure_count[next_activity] = 0
        
        return {
            "from": prev_activity,
            "to": next_activity,
            "cycle_started": False
        }
    
    def _complete_and_restart_cycle(
        self,
        source_id: str,
        frame_number: int,
        timestamp: str
    ) -> Dict:
        """Complete current cycle and start new one."""
        state = self.sources[source_id]
        cycle = state.cycle_state
        
        prev_activity = cycle.current_activity
        completed_cycle_num = cycle.cycle_count
        
        cycle_logger.info(f"  [Frame {frame_number}] CYCLE {completed_cycle_num} COMPLETED")
        
        # Store completed cycle
        completed_cycle = {
            "cycle_number": completed_cycle_num,
            "start_frame": cycle.cycle_start_frame,
            "end_frame": frame_number,
            "activity_timing": dict(cycle.activity_timing),
            "status": "SUCCESS"
        }
        state.completed_cycles.append(completed_cycle)
        
        # Build detailed cycle analytics and update
        cycle_analytics = self._build_cycle_analytics(
            source_id=source_id,
            cycle_num=completed_cycle_num,
            start_frame=cycle.cycle_start_frame,
            end_frame=frame_number,
            activity_timing=cycle.activity_timing,
            status="SUCCESS",
            has_anomaly=False
        )
        self._update_analytics_after_cycle(source_id, cycle_analytics)
        
        # Start new cycle - increment count since we completed previous one
        cycle.is_active = True
        cycle.cycle_count += 1
        cycle.current_activity = self.start_activity
        cycle.cycle_start_frame = frame_number
        cycle.cycle_start_time = timestamp

        # Reset persistence tracker for the restarted cycle as well.
        state.tracker.reset()
        
        # Reset activity timing for new cycle
        for act_id in cycle.activity_timing:
            cycle.activity_timing[act_id] = {
                "start_frame": None, "end_frame": None,
                "start_time": None, "end_time": None
            }
        cycle.activity_timing[self.start_activity]["start_frame"] = frame_number
        cycle.activity_timing[self.start_activity]["start_time"] = timestamp
        
        # Clear confirmation state for new cycle
        self._clear_confirmation_state(source_id, prev_activity)
        
        # Apply cycle-level KPI updates (on_cycle_complete_success)
        success_updates = self.cycle_kpi_updates.get("on_cycle_complete_success", [])
        if success_updates:
            self._apply_kpi_updates(source_id, success_updates)
        
        # Clear kpi_updates_applied for new cycle
        state.kpi_updates_applied.clear()
        
        cycle_logger.info(f"  [Frame {frame_number}] CYCLE {cycle.cycle_count} STARTED (restart)")

        # Send instruction for starting activity of the restarted cycle
        self._send_activity_instruction(
            activity_id=self.start_activity,
            source_id=source_id,
            frame_number=frame_number,
            cycle_count=cycle.cycle_count
        )
        
        return {
            "from": prev_activity,
            "to": self.start_activity,
            "cycle_started": True,
            "cycle_number": cycle.cycle_count,
            "cycle_completed": {
                "status": "SUCCESS",
                "cycle_number": completed_cycle_num
            }
        }
    
    def _reset_cycle_state(self, source_id: str):
        """Reset cycle-specific state."""
        state = self.sources[source_id]
        cycle = state.cycle_state
        
        cycle.is_active = False
        cycle.current_activity = None
        cycle.previous_activity = None
        cycle.cycle_start_frame = None
        cycle.cycle_start_time = None
        
        # Reset activity timing
        for act_id in cycle.activity_timing:
            cycle.activity_timing[act_id] = {
                "start_frame": None, "end_frame": None,
                "start_time": None, "end_time": None
            }
    
    def get_completed_cycles(self, source_id: str) -> List[Dict]:
        """Get list of completed cycles."""
        if source_id not in self.sources:
            return []
        return self.sources[source_id].completed_cycles
    
    # =========================================================================
    # NEW UNIFIED INTERFACE (Compatible with SOPExecutor and NodeExecutor)
    # These methods provide the same interface as NodeExecutor for use with
    # the unified SOPExecutor in sop_unified_executor.py
    # =========================================================================
    
    def set_input_data(self, data: Dict[str, Any]) -> None:
        """
        Set executor_input_data for current frame (NEW interface).
        
        Args:
            data: Dict containing:
                - frame: Current video frame (optional)
                - detections: Dict of class_name -> list of detections
                - detected_classes: List of class names found (optional)
                - frame_id / frame_number: Frame identifier
                - timestamp: Frame timestamp
                - source_id: Optional source identifier
        """
        self._pending_input_data = data
        
        # Update current source if provided
        source_id = data.get("source_id", self._default_source_id if hasattr(self, '_default_source_id') else "default_source")
        if source_id not in self.sources:
            self.initialize_source(source_id, self._additional_predefined if hasattr(self, '_additional_predefined') else {})
        self._current_source_id = source_id
    
    def execute_all(self):
        """
        Execute frame processing and return result (NEW interface).
        
        Internally calls process_frame() and converts the result to 
        ExecutionResult dataclass format for compatibility with NodeExecutor.
        
        Returns:
            ExecutionResult with all data sources and cycle status
        """
        import time as time_module
        from dataclasses import dataclass, field
        from typing import Optional, Dict, Any, List
        
        # ExecutionResult dataclass (inline for compatibility)
        @dataclass
        class ExecutionResult:
            frame_id: Optional[int] = None
            timestamp: float = 0.0
            executor_input_data: Dict[str, Any] = field(default_factory=dict)
            predefined_data: Dict[str, Any] = field(default_factory=dict)
            derived_data: Dict[str, Any] = field(default_factory=dict)
            activity_results: Dict[str, Any] = field(default_factory=dict)
            activities_executed: int = 0
            activities_skipped: int = 0
            success: bool = True
            current_activity: Optional[str] = None
            cycle_active: bool = False
            cycle_count: int = 0
            transition: Optional[Dict] = None
            cycle_completed: Optional[Dict] = None
        
        timestamp = time_module.time()
        
        # Get pending data
        data = getattr(self, '_pending_input_data', {})
        source_id = data.get("source_id", getattr(self, '_current_source_id', 'default_source'))
        frame_number = data.get("frame_number", data.get("frame_id", 0))
        frame_timestamp = data.get("timestamp", str(timestamp))
        
        # Extract detections
        detections = data.get("detections", {})
        if not detections and "detected_classes" in data:
            detections = {cls: [] for cls in data.get("detected_classes", [])}
        
        # Merge additional_data into main data dict BEFORE process_frame
        # This includes things_present, pose_landmarks, etc.
        additional_data = data.get("additional_data", {})
        if additional_data:
            # Merge additional_data fields directly into data
            for key, value in additional_data.items():
                if key not in data:  # Don't overwrite existing keys
                    data[key] = value
        
        # Ensure source state exists
        if source_id not in self.sources:
            self.initialize_source(source_id)
        
        state = self.sources[source_id]
        
        # Update executor_input_data BEFORE calling process_frame
        # This ensures rules have access to all data when they execute
        state.executor_input_data = {
            **detections,  # Top-level: Person -> [[x1,y1,x2,y2]]
            "detections": detections,  # Nested: detections.Person -> [[x1,y1,x2,y2]]
            "frame_number": frame_number,
            "timestamp": frame_timestamp,
            "source_id": source_id
        }
        
        # Add all other data fields (including things_present from additional_data)
        for key, value in data.items():
            if key not in ["detections", "frame_number", "timestamp", "source_id", "additional_data"]:
                state.executor_input_data[key] = value
        
        # CRITICAL: Ensure things_present is at top level of executor_input_data for rule evaluation
        # The mapped_values "executor_input_data.things_present" needs it at top level
        if "things_present" not in state.executor_input_data:
            # Try to get from additional_data if it exists
            if "additional_data" in data and isinstance(data["additional_data"], dict):
                if "things_present" in data["additional_data"]:
                    state.executor_input_data["things_present"] = data["additional_data"]["things_present"]
                    cycle_logger.debug(f"  [set_input_data] Moved things_present from additional_data to top level: {state.executor_input_data['things_present']}")
        
        # Store session_id and manual_id if provided
        if "sessionId" in data:
            state.session_id = data["sessionId"]
            self._session_id = data["sessionId"]  # Also store in executor instance
        if "manualId" in data:
            state.manual_id = str(data["manualId"])
            self._manual_id = str(data["manualId"])  # Also store in executor instance
        
        # Prepare additional fields to pass to process_frame
        additional_fields = {}
        for key, value in data.items():
            if key not in ["detections", "frame_number", "timestamp", "source_id", "additional_data", "frame_id"]:
                additional_fields[key] = value
        
        # Also merge additional_data fields
        if additional_data:
            additional_fields.update(additional_data)
        
        # Call the original process_frame with additional fields
        cycle_result = self.process_frame(
            source_id=source_id,
            detections=detections,
            frame_number=frame_number,
            timestamp=frame_timestamp,
            additional_fields=additional_fields
        )
        
        # Get source state
        source_state = self.sources.get(source_id)
        
        # Build ExecutionResult
        result = ExecutionResult(
            frame_id=frame_number,
            timestamp=timestamp,
            executor_input_data=data.copy(),
            predefined_data=source_state.predefined_data.copy() if source_state else {},
            derived_data=source_state.derived_data.copy() if source_state else {},
            success=True
        )
        
        # Copy cycle-specific results
        if cycle_result:
            result.current_activity = cycle_result.get("current_activity")
            result.cycle_active = cycle_result.get("cycle_active", False)
            result.cycle_count = cycle_result.get("cycle_count", 0)
            result.transition = cycle_result.get("transition")
            result.cycle_completed = cycle_result.get("cycle_completed")
            
            if result.transition:
                result.activities_executed = 1
        
        return result
    
    def reset(self) -> None:
        """Reset derived_data for new frame (NEW interface)."""
        self._pending_input_data = {}
    
    def reset_state(self) -> None:
        """Reset all stateful data (NEW interface). Call between videos/sessions."""
        self._pending_input_data = {}
        
        # Reset all sources
        for source_id, source_state in self.sources.items():
            source_state.tracker.reset()
            source_state.cycle_state.is_active = False
            source_state.cycle_state.current_activity = None
            source_state.cycle_state.cycle_count = 0
            source_state.kpi_updates_applied.clear()
        
        cycle_logger.info(f"[SOPCycleExecutor] State reset for all sources")
    
    def get_state(self) -> Dict[str, Any]:
        """Get current executor state (NEW interface)."""
        source_id = getattr(self, '_current_source_id', 'default_source')
        
        state = {
            "sop_id": self.sop_id,
            "sop_type": "cycle",
            "frames_processed": getattr(self, '_frames_processed', 0),
            "activity_count": len(self.activity_sequence),
            "activities": self.activity_sequence
        }
        
        # Add cycle-specific state
        source_state = self.sources.get(source_id)
        if source_state:
            state["cycle_state"] = {
                "is_active": source_state.cycle_state.is_active,
                "cycle_count": source_state.cycle_state.cycle_count,
                "current_activity": source_state.cycle_state.current_activity
            }
        
        return state
    
    def get_analytics_data(self, source_id: str = None) -> Optional[Dict]:
        """Get analytics data for a source (NEW interface)."""
        sid = source_id or getattr(self, '_current_source_id', 'default_source')
        source_state = self.sources.get(sid)
        if source_state:
            return source_state.analytics_data
        return None
    
    def reload_predefined(self, new_predefined: Dict) -> None:
        """Replace all predefined values (NEW interface)."""
        if hasattr(self, '_additional_predefined'):
            self._additional_predefined = new_predefined.copy()
        
        for source_id, source_state in self.sources.items():
            source_state.predefined_data = new_predefined.copy()
    
    def update_predefined(self, updates: Dict) -> None:
        """Merge updates into existing predefined values (NEW interface)."""
        if hasattr(self, '_additional_predefined'):
            self._additional_predefined.update(updates)
        
        for source_id, source_state in self.sources.items():
            source_state.predefined_data.update(updates)


# =============================================================================
# CYCLE EXECUTOR WITH DIRECT INIT (for use with SOPExecutor)
# =============================================================================

class CycleExecutor(SOPCycleExecutor):
    """
    CycleExecutor with direct initialization pattern.
    
    This class extends SOPCycleExecutor to provide the same __init__ interface
    as NodeExecutor, making it compatible with the unified SOPExecutor.
    
    Usage:
        executor = CycleExecutor(sop_data, additional_predefined={...})
        executor.set_input_data({...})
        result = executor.execute_all()
        executor.reset()
    """
    
    def __init__(self, sop_data: Dict, additional_predefined: Dict = None):
        """
        Initialize CycleExecutor with sop_data directly.
        
        Args:
            sop_data: Output from sop_loader.load_sop()
            additional_predefined: Extra predefined values (models, config, etc.)
        """
        # Call parent __init__ first
        super().__init__()
        
        # Store for later use
        self._sop_data = sop_data
        self._additional_predefined = additional_predefined or {}
        self._default_source_id = "default_source"
        self._current_source_id = self._default_source_id
        self._frames_processed = 0
        self._pending_input_data = {}
        
        # Load rule functions module BEFORE load_config
        try:
            import sop_rule_functions
            self.rule_functions = sop_rule_functions
        except ImportError:
            try:
                from pathlib import Path
                import importlib.util
                current_dir = Path(__file__).resolve().parent
                rule_path = current_dir / "sop_rule_functions.py"
                if rule_path.exists():
                    spec = importlib.util.spec_from_file_location("sop_rule_functions", rule_path)
                    rule_functions = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(rule_functions)
                    self.rule_functions = rule_functions
                    cycle_logger.info(f"[CycleExecutor] Loaded rule functions from: {rule_path}")
            except Exception as e:
                cycle_logger.warning(f"[CycleExecutor] Warning: Could not load rule functions: {e}")
        
        # Load config (rule_functions already set, so path is not needed)
        self.load_config(
            sop_data=sop_data,
            rule_functions_path="sop_rule_functions.py"  # Provide path for fallback loading
        )
        
        # Initialize default source
        self.initialize_source(
            self._default_source_id,
            additional_predefined
        )
        
        sop_id = sop_data.get("sop_master", {}).get("sopId", "unknown")
        cycle_logger.info(f"[CycleExecutor] Initialized for SOP: {sop_id}")
        cycle_logger.info(f"[CycleExecutor] Activities: {self.activity_sequence}")


