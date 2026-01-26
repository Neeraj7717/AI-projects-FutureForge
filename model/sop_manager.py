"""
SOP Manager - Manages SOP executors for VIA application
Integrates sop_unified_executor, sop_loader, sop_cycle, sop_node, sop_rule_functions
"""
import logging
import traceback
from typing import Dict, Any, Optional, List
from Config.settings import Settings
from utils.eizen_utils.logger_utils.logger_operations import LoggerOperations

# Import SOP components
try:
    import sop_loader
    from sop_unified_executor import SOPExecutor, create_executor
    HAS_SOP = True
except ImportError as e:
    HAS_SOP = False
    print(f"[SOPManager] Warning: SOP modules not available: {e}")

sop_logger = LoggerOperations(logger_name='SOPManager', log_level=logging.INFO, use_log_file=False)

config = Settings()


class SOPManager:
    """
    Manages SOP executors for different sources/manuals.
    Provides unified interface to execute SOPs after detections.
    """
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SOPManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            if not HAS_SOP:
                sop_logger.warning("SOP modules not available. SOP execution will be skipped.")
                self._initialized = True
                return
            
            # Cache for SOP executors: (sourceId, manualId) -> executor
            self.executors: Dict[str, SOPExecutor] = {}
            
            # Cache for SOP data: sop_id -> sop_data
            self.sop_data_cache: Dict[str, Dict] = {}
            
            # Mapping: manualId -> sop_id (can be configured or loaded from DB)
            self.manual_to_sop: Dict[str, str] = {}
            
            self._initialized = True
            sop_logger.info("SOPManager initialized")
    
    def get_sop_id_for_manual(self, manualId: str, sourceId: str = None) -> Optional[str]:
        """
        Get SOP ID for a given manualId.
        Can be configured in settings or loaded from database.
        """
        # Check cache first
        if manualId in self.manual_to_sop:
            return self.manual_to_sop[manualId]
        
        # Try to load from MongoDB (manual collection)
        try:
            import pymongo
            client = pymongo.MongoClient(config.mongo_connection_string_stateless)
            db = client[config.database_name]
            manual = db["manual"].find_one({"_id": int(manualId)})
            
            if manual:
                # Check for sop_id field
                if "sop_id" in manual:
                    sop_id = manual["sop_id"]
                    self.manual_to_sop[manualId] = sop_id
                    sop_logger.info(f"Found sop_id '{sop_id}' for manualId {manualId} in MongoDB")
                    return sop_id
                
                # Also check sop_activity_rule_map collection for sop_id
                rule_map = db["sop_activity_rule_map"].find_one({"sop_id": {"$regex": f".*{manualId}.*"}})
                if not rule_map:
                    # Try exact match with manualId as sop_id
                    rule_map = db["sop_activity_rule_map"].find_one({"sop_id": f"EZA_SOP_{manualId}"})
                if not rule_map:
                    # Try with manualId directly
                    rule_map = db["sop_activity_rule_map"].find_one({"sop_id": str(manualId)})
                
                if rule_map and "sop_id" in rule_map:
                    sop_id = rule_map["sop_id"]
                    self.manual_to_sop[manualId] = sop_id
                    sop_logger.info(f"Found sop_id '{sop_id}' for manualId {manualId} from rule_map")
                    return sop_id
                
                # Check if there's a JSON file with sop_id (like pose_activity_rule_map.json or abb_activity_rule_map.json)
                # For manualId 23, try pose SOP first, then ABB SOP
                try:
                    import json
                    import os
                    from pathlib import Path
                    
                    # Get project root (where abbjsons folder is)
                    current_file = Path(__file__).resolve()
                    project_root = current_file.parent.parent
                    abbjsons_path = project_root / "abbjsons"
                    
                    # Try pose SOP files first (for pose detection)
                    pose_files = [
                        abbjsons_path / "pose_activity_rule_map.json",
                        project_root / "abbjsons" / "pose_activity_rule_map.json",
                    ]
                    
                    for json_file in pose_files:
                        if json_file.exists():
                            with open(json_file, 'r') as f:
                                rule_data = json.load(f)
                                if "sop_id" in rule_data:
                                    sop_id = rule_data["sop_id"]
                                    if manualId == "23":  # Use pose SOP for manualId 23
                                        self.manual_to_sop[manualId] = sop_id
                                        sop_logger.info(f"Found sop_id '{sop_id}' for manualId {manualId} from pose JSON file: {json_file}")
                                        return sop_id
                    
                    # Fallback to ABB SOP files
                    abb_files = [
                        abbjsons_path / "abb_activity_rule_map.json",
                        project_root / "abbjsons" / "abb_activity_rule_map.json",
                    ]
                    
                    for json_file in abb_files:
                        if json_file.exists():
                            with open(json_file, 'r') as f:
                                rule_data = json.load(f)
                                if "sop_id" in rule_data:
                                    sop_id = rule_data["sop_id"]
                                    if manualId == "23":  # Use ABB SOP as fallback
                                        self.manual_to_sop[manualId] = sop_id
                                        sop_logger.info(f"Found sop_id '{sop_id}' for manualId {manualId} from ABB JSON file: {json_file}")
                                        return sop_id
                except Exception as e:
                    sop_logger.debug(f"Could not load from JSON file: {e}")
                    
        except Exception as e:
            sop_logger.debug(f"Could not load sop_id from manual {manualId}: {e}")
        
        # Default: try to use manualId as sop_id or check for known mappings
        # For manualId 23, try common SOP ID patterns (including pose SOP)
        if manualId == "23":
            # Try pose SOP first, then other patterns
            possible_sop_ids = ["EZA_SOP_POSE", "EZA_SOP_ABB", f"EZA_SOP_{manualId}", f"SOP_{manualId}"]
            for possible_id in possible_sop_ids:
                try:
                    # Try to load this SOP to see if it exists
                    test_data = self._load_sop_data(possible_id)
                    if test_data:
                        self.manual_to_sop[manualId] = possible_id
                        sop_logger.info(f"Auto-detected sop_id '{possible_id}' for manualId {manualId}")
                        return possible_id
                except Exception as e:
                    sop_logger.debug(f"Could not load SOP {possible_id}: {e}")
                    continue
        
        sop_logger.debug(f"No sop_id found for manualId {manualId}")
        return None
    
    def get_executor(self, sourceId: str, manualId: str, sop_id: str = None) -> Optional[SOPExecutor]:
        """
        Get or create SOP executor for a source/manual combination.
        
        Args:
            sourceId: Source identifier
            manualId: Manual identifier
            sop_id: Optional SOP ID (if not provided, will try to resolve)
        
        Returns:
            SOPExecutor instance or None if not available
        """
        if not HAS_SOP:
            return None
        
        # Resolve sop_id if not provided
        if not sop_id:
            sop_id = self.get_sop_id_for_manual(manualId, sourceId)
            if not sop_id:
                sop_logger.debug(f"No SOP ID found for manualId {manualId}")
                return None
        
        # Create cache key
        cache_key = f"{sourceId}:{manualId}:{sop_id}"
        
        # Return cached executor if exists
        if cache_key in self.executors:
            return self.executors[cache_key]
        
        # Load SOP data
        sop_data = self._load_sop_data(sop_id)
        if not sop_data:
            sop_logger.warning(f"Could not load SOP data for sop_id: {sop_id}")
            return None
        
        # Create executor
        try:
            executor = create_executor(
                sop_data=sop_data,
                sop_id=sop_id,
                source_type="mongodb",
                additional_predefined={}
            )
            
            if executor:
                self.executors[cache_key] = executor
                sop_logger.info(f"[SOP] Executor created: {sop_id}")
                return executor
        except Exception as e:
            sop_logger.error(f"Error creating SOP executor: {e}")
            traceback.print_exc()
            return None
    
    def _load_sop_data(self, sop_id: str) -> Optional[Dict]:
        """Load SOP data from local JSON files first, then MongoDB as fallback."""
        # Check cache
        if sop_id in self.sop_data_cache:
            return self.sop_data_cache[sop_id]
        
        # Try loading from local JSON files first (for testing)
        try:
            sop_data = sop_loader.load_sop(
                source_type="local",
                sop_id=sop_id
            )
            
            if sop_data and sop_data.get("validation", {}).get("valid", False):
                self.sop_data_cache[sop_id] = sop_data
                sop_logger.info(f"[SOP] Loaded: {sop_id}")
                return sop_data
        except Exception as e:
            pass  # Silent fallback to MongoDB
        
        # Fallback to MongoDB
        try:
            sop_data = sop_loader.load_sop(
                source_type="mongodb",
                sop_id=sop_id,
                mongo_uri=config.mongo_connection_string_stateless,
                database_name=config.database_name
            )
            
            if sop_data and sop_data.get("validation", {}).get("valid", False):
                self.sop_data_cache[sop_id] = sop_data
                sop_logger.info(f"[SOP] Loaded: {sop_id}")
                return sop_data
            else:
                sop_logger.warning(f"[SOP] Validation failed: {sop_id}")
        except Exception as e:
            sop_logger.error(f"Error loading SOP data for {sop_id} from MongoDB: {e}")
            traceback.print_exc()
        
        return None
    
    def execute_sop(
        self,
        sourceId: str,
        manualId: str,
        detections: Dict[str, List[List[float]]],
        frame_number: int = 0,
        timestamp: str = None,
        additional_data: Dict = None
    ) -> Optional[Dict]:
        """
        Execute SOP after detections.
        
        Args:
            sourceId: Source identifier
            manualId: Manual identifier
            detections: Dict of class_name -> list of bounding boxes [[x1,y1,x2,y2], ...]
            frame_number: Frame number
            timestamp: Frame timestamp
            additional_data: Additional data to pass to executor
        
        Returns:
            ExecutionResult dict or None if SOP not available
        """
        if not HAS_SOP:
            return None
        
        try:
            # Get executor
            executor = self.get_executor(sourceId, manualId)
            if not executor:
                return None
            
            # Prepare input data
            input_data = {
                "source_id": sourceId,
                "detections": detections,
                "frame_number": frame_number,
                "frame_id": frame_number,
                "timestamp": timestamp or str(frame_number),
                "manualId": str(manualId),  # Ensure manualId is always included
            }
            
            # Add additional data if provided
            if additional_data:
                input_data.update(additional_data)
            
            # Set input and execute
            executor.set_input_data(input_data)
            result = executor.execute_all()
            
            # Reset for next frame
            executor.reset()
            
            # Convert result to dict for easier handling
            if result:
                return {
                    "success": result.success,
                    "activities_executed": result.activities_executed,
                    "current_activity": result.current_activity,
                    "cycle_active": result.cycle_active,
                    "cycle_count": result.cycle_count,
                    "transition": result.transition,
                    "cycle_completed": result.cycle_completed,
                    "derived_data": result.derived_data,
                    "activity_results": {
                        k: {
                            "success": v.success,
                            "triggered": v.triggered,
                            "results": v.results
                        } for k, v in result.activity_results.items()
                    } if hasattr(result, 'activity_results') else {}
                }
            
        except Exception as e:
            sop_logger.error(f"Error executing SOP: {e}")
            traceback.print_exc()
        
        return None
    
    def shutdown_source(self, sourceId: str, manualId: str):
        """Shutdown and cleanup executor for a source."""
        cache_key = f"{sourceId}:{manualId}"
        matching_keys = [k for k in self.executors.keys() if k.startswith(cache_key)]
        
        for key in matching_keys:
            executor = self.executors[key]
            try:
                if hasattr(executor, 'shutdown'):
                    executor.shutdown(sourceId)
                if hasattr(executor, 'reset_state'):
                    executor.reset_state()
            except Exception as e:
                sop_logger.error(f"Error shutting down executor {key}: {e}")
            
            del self.executors[key]
    
    def clear_cache(self):
        """Clear all cached executors and SOP data."""
        self.executors.clear()
        self.sop_data_cache.clear()
        self.manual_to_sop.clear()


# Global singleton instance
sop_manager = SOPManager()
