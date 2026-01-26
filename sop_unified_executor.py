"""
SOP Unified Executor
====================
Main entry point for SOP execution. Works with both Node and Cycle type SOPs.

This executor:
1. Receives sop_data (from sop_loader)
2. Automatically selects the correct executor based on sop_type
3. Provides a unified interface for all SOP types

Supported SOP Types:
- "node": Activities triggered by model_class detection match
- "cycle": Activities follow a state machine sequence

Usage:
------
    import sop_loader
    from sop_unified_executor import SOPExecutor
    
    # Load SOP
    sop_data = sop_loader.load_sop(source_type="mongodb", sop_id="MY_SOP")
    
    # Create executor (works for both node and cycle types)
    executor = SOPExecutor(sop_data, additional_predefined={...})
    
    # Process frames
    for frame in frames:
        executor.set_input_data({
            "frame": frame,
            "detections": detections,
            "detected_classes": ["class1", "class2"],
            "frame_id": frame_number,
            "timestamp": timestamp
        })
        
        result = executor.execute_all()
        
        # Handle result
        if result.success:
            print(f"Executed {result.activities_executed} activities")
        
        executor.reset()
    
    # Cleanup
    executor.reset_state()
"""

import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Type
from dataclasses import dataclass, field

# Add paths for imports
current_dir = Path(__file__).resolve().parent
parent_dir = current_dir.parent
sys.path.append(str(parent_dir))
sys.path.append(str(current_dir))  # For local imports

# Import CycleExecutor (from sop_cycle_executor.py)
try:
    from sop_cycle_executor import CycleExecutor
    HAS_CYCLE_EXECUTOR = True
except ImportError:
    HAS_CYCLE_EXECUTOR = False
    CycleExecutor = None
    print("[SOPExecutor] Warning: CycleExecutor not found, cycle SOPs not supported")

# Import NodeExecutor
try:
    from node_executor import NodeExecutor
    HAS_NODE_EXECUTOR = True
except ImportError:
    HAS_NODE_EXECUTOR = False
    NodeExecutor = None
    print("[SOPExecutor] Warning: NodeExecutor not found, node SOPs not supported")


# =============================================================================
# RESULT DATACLASSES
# =============================================================================

@dataclass
class ActivityResult:
    """Result from executing a single activity."""
    activity_id: str
    success: bool = True
    triggered: bool = True  # False if skipped
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
    
    # Cycle-specific fields (populated by cycle executor)
    current_activity: Optional[str] = None
    cycle_active: bool = False
    cycle_count: int = 0
    transition: Optional[Dict] = None
    cycle_completed: Optional[Dict] = None


# =============================================================================
# EXECUTOR REGISTRY
# =============================================================================

# Registry maps sop_type -> executor class
# Each executor must implement: 
#   __init__(sop_data, additional_predefined)
#   set_input_data(data)
#   execute_all() -> ExecutionResult
#   reset()
#   reset_state()
#   get_state()

_EXECUTOR_REGISTRY: Dict[str, Type] = {}


def register_executor(sop_type: str, executor_class: Type) -> None:
    """Register an executor class for an SOP type."""
    _EXECUTOR_REGISTRY[sop_type.lower()] = executor_class
    print(f"[SOPExecutor] Registered: {sop_type} -> {executor_class.__name__}")


def get_registered_types() -> List[str]:
    """Get list of registered SOP types."""
    return list(_EXECUTOR_REGISTRY.keys())


# Register available executors
if HAS_CYCLE_EXECUTOR and CycleExecutor:
    register_executor("cycle", CycleExecutor)

if HAS_NODE_EXECUTOR and NodeExecutor:
    register_executor("node", NodeExecutor)


# =============================================================================
# SOP EXECUTOR - Main Class
# =============================================================================

class SOPExecutor:
    """
    Main SOP Executor that works with both Node and Cycle type SOPs.
    
    Automatically selects the correct executor based on sop_type in the SOP data.
    Provides a unified interface regardless of the underlying executor.
    
    Attributes:
        sop_data: The loaded SOP configuration
        sop_type: Type of SOP ("node" or "cycle")
        sop_id: Unique SOP identifier
    """
    
    def __init__(self, sop_data: Dict, additional_predefined: Dict = None):
        """
        Initialize SOP executor.
        
        Args:
            sop_data: Output from sop_loader.load_sop()
            additional_predefined: Extra predefined values (models, config, regions, etc.)
        """
        self.sop_data = sop_data
        self.additional_predefined = additional_predefined or {}
        self._executor = None
        
        # Extract SOP metadata
        sop_master = sop_data.get("sop_master", {})
        self.sop_id = sop_master.get("sopId", "unknown")
        
        # Get sop_type (support both 'type' and 'sopType' keys)
        self.sop_type = sop_master.get("type") or sop_master.get("sopType", "cycle")
        self.sop_type = self.sop_type.lower()
        
        # Select and initialize executor
        self._init_executor()
    
    def _init_executor(self) -> None:
        """Initialize the appropriate executor based on sop_type."""
        executor_class = _EXECUTOR_REGISTRY.get(self.sop_type)
        
        if executor_class is None:
            available = get_registered_types()
            print(f"[SOPExecutor] ERROR: No executor for type '{self.sop_type}'")
            print(f"[SOPExecutor] Available types: {available}")
            
            # Fallback to cycle if available
            if "cycle" in _EXECUTOR_REGISTRY:
                print(f"[SOPExecutor] Falling back to 'cycle' executor")
                executor_class = _EXECUTOR_REGISTRY["cycle"]
            else:
                raise ValueError(f"No executor available for sop_type: {self.sop_type}")
        
        # Create executor instance
        self._executor = executor_class(self.sop_data, self.additional_predefined)
        print(f"[SOPExecutor] Initialized for SOP: {self.sop_id} | Type: {self.sop_type}")
    
    # =========================================================================
    # MAIN INTERFACE
    # =========================================================================
    
    def set_input_data(self, data: Dict[str, Any]) -> None:
        """
        Set input data for current frame.
        
        Args:
            data: Dict containing:
                - frame: Current video frame (optional)
                - detections: Detection results dict
                - detected_classes: List of detected class names
                - frame_id / frame_number: Frame identifier
                - timestamp: Frame timestamp
                - source_id: Optional source identifier
        """
        self._executor.set_input_data(data)
    
    def execute_all(self) -> ExecutionResult:
        """
        Execute all activities and return result.
        
        Returns:
            ExecutionResult with:
                - activity_results: Dict of activity_id -> ActivityResult
                - success: Overall success status
                - derived_data: Computed data from rules
                - For cycle type: cycle_count, current_activity, transitions
        """
        return self._executor.execute_all()
    
    def execute_activity(self, activity_id: str) -> ActivityResult:
        """
        Execute a single activity by ID.
        
        Args:
            activity_id: ID of the activity to execute
            
        Returns:
            ActivityResult for the executed activity
        """
        if hasattr(self._executor, 'execute_activity'):
            return self._executor.execute_activity(activity_id)
        else:
            print(f"[SOPExecutor] execute_activity not supported by {self.sop_type} executor")
            return ActivityResult(activity_id=activity_id, success=False, triggered=False)
    
    def reset(self) -> None:
        """
        Reset derived data for next frame.
        Call this between frames to clear temporary state.
        """
        self._executor.reset()
    
    def reset_state(self) -> None:
        """
        Reset all state data.
        Call this between videos/sessions for complete reset.
        """
        self._executor.reset_state()
    
    def get_state(self) -> Dict[str, Any]:
        """
        Get current executor state.
        
        Returns:
            Dict with state information (sop_id, sop_type, frames_processed, etc.)
        """
        state = self._executor.get_state()
        state["sop_type"] = self.sop_type
        return state
    
    # =========================================================================
    # PREDEFINED VALUES
    # =========================================================================
    
    def reload_predefined(self, new_predefined: Dict) -> None:
        """
        Replace all predefined values.
        
        Args:
            new_predefined: New predefined values to use
        """
        self.additional_predefined = new_predefined.copy()
        if hasattr(self._executor, 'reload_predefined'):
            self._executor.reload_predefined(new_predefined)
    
    def update_predefined(self, updates: Dict) -> None:
        """
        Merge updates into existing predefined values.
        
        Args:
            updates: Values to merge
        """
        self.additional_predefined.update(updates)
        if hasattr(self._executor, 'update_predefined'):
            self._executor.update_predefined(updates)
    
    # =========================================================================
    # CYCLE-SPECIFIC METHODS
    # =========================================================================
    
    def get_completed_cycles(self, source_id: str = None) -> List[Dict]:
        """
        Get completed cycles (cycle type only).
        
        Args:
            source_id: Optional source identifier
            
        Returns:
            List of completed cycle dictionaries
        """
        if hasattr(self._executor, 'get_completed_cycles'):
            return self._executor.get_completed_cycles(source_id)
        return []
    
    def get_analytics_data(self, source_id: str = None) -> Optional[Dict]:
        """
        Get analytics data (cycle type only).
        
        Args:
            source_id: Optional source identifier
            
        Returns:
            Analytics data dictionary
        """
        if hasattr(self._executor, 'get_analytics_data'):
            return self._executor.get_analytics_data(source_id)
        return None
    
    def shutdown(self, source_id: str = None) -> None:
        """
        Shutdown and finalize.
        
        Args:
            source_id: Optional source identifier
        """
        if hasattr(self._executor, 'shutdown'):
            self._executor.shutdown(source_id)
    
    # =========================================================================
    # DIRECT EXECUTOR ACCESS
    # =========================================================================
    
    @property
    def executor(self):
        """Direct access to underlying executor (for advanced use)."""
        return self._executor
    
    @property
    def rule_functions(self):
        """Access to rule functions module."""
        if hasattr(self._executor, 'rule_functions'):
            return self._executor.rule_functions
        return None
    
    @rule_functions.setter
    def rule_functions(self, value):
        """Set rule functions module."""
        if hasattr(self._executor, 'rule_functions'):
            self._executor.rule_functions = value


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def create_executor(
    sop_data: Dict = None,
    sop_id: str = None,
    source_type: str = "mongodb",
    config: Dict = None,
    additional_predefined: Dict = None
) -> Optional[SOPExecutor]:
    """
    Convenience function to create executor.
    
    Can either pass sop_data directly, or pass sop_id to load from database.
    
    Args:
        sop_data: Pre-loaded SOP data (if available)
        sop_id: SOP ID to load (if sop_data not provided)
        source_type: Source type for loader
        config: Config for loader
        additional_predefined: Extra predefined values
        
    Returns:
        SOPExecutor instance, or None if failed
    """
    if sop_data is None:
        # Load using sop_loader
        try:
            import sop_loader
            sop_data = sop_loader.load_sop(
                source_type=source_type,
                sop_id=sop_id,
                config=config
            )
        except Exception as e:
            print(f"[create_executor] Error loading SOP: {e}")
            return None
    
    if not sop_data:
        print("[create_executor] No SOP data available")
        return None
    
    return SOPExecutor(sop_data, additional_predefined)
