"""
SOP Data Loader - Loads raw SOP data from MongoDB or ThingsBoard.
Returns raw JSON data with structure validation.
"""
import traceback
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict

DEFAULT_MONGO_URI = "mongodb://Eizen:Eizen123@183.82.116.237:27018/"
DEFAULT_DATABASE_NAME = "Asample"

DEFAULT_MONGO_COLLECTIONS = {
    "source": "source",
    "sop_master": "sop_master",
    "sop_rule_master": "sop_rule_master",
    "sop_activity_rule_map": "sop_activity_rule_map",
    "sop_analytics_template": "sop_analytics_template"
}

DEFAULT_THINGSBOARD_KEYS = {
    "sop_id": "sopId",
    "sop_config": "sopConfig",
    "sop_master": "sop_master",
    "sop_rule_master": "sop_rule_master",
    "sop_activity_rule_map": "sop_activity_rule_map"
}


# =============================================================================
# DATA CLASSES FOR VALIDATION
# =============================================================================

@dataclass
class Activity:
    activityId: str
    prevAct: List[str] = field(default_factory=list)
    nextAct: List[str] = field(default_factory=list)
    model_class: List[str] = field(default_factory=list)
    model_id: Optional[str] = None
    function: Optional[str] = None
    expectedTime: Optional[int] = None
    description: Optional[str] = None  # Instruction text for this activity
    instruction: Optional[str] = None  # Alias for description


@dataclass
class SOPMaster:
    sopId: str
    type: str = "node"
    name: str = ""
    completeAllActivity: bool = True
    startActivity: List[str] = field(default_factory=list)
    endActivity: List[str] = field(default_factory=list)
    activities: List[Activity] = field(default_factory=list)


@dataclass
class RuleMapping:
    activity_id: str
    predefined_values: Dict = field(default_factory=dict)
    activity_rules: List = field(default_factory=list)
    anomaly_rules: List = field(default_factory=list)
    output_to: str = "derived_data"


@dataclass
class SOPActivityRuleMap:
    sop_id: str
    rules_map: List[RuleMapping] = field(default_factory=list)


@dataclass
class SOPRule:
    rule_name: str
    desc: str = ""
    input: List[str] = field(default_factory=list)
    output: List[str] = field(default_factory=list)


def validate_structure(data: Dict) -> Dict:
    """Validate using dataclasses."""
    errors = []

    try:
        # Validate sop_master
        sm = data.get("sop_master")
        if sm:
            try:
                activities = []
                for a in sm.get("activities", []):
                    try:
                        # Normalize field names: support both camelCase and snake_case
                        normalized_activity = {}
                        # Handle activityId/activity_id
                        if "activity_id" in a and "activityId" not in a:
                            normalized_activity["activityId"] = a["activity_id"]
                        elif "activityId" in a:
                            normalized_activity["activityId"] = a["activityId"]
                        else:
                            normalized_activity["activityId"] = a.get("activityId") or a.get("activity_id", "")
                        
                        # Handle prevAct/prev_act
                        normalized_activity["prevAct"] = a.get("prev_act") or a.get("prevAct", [])
                        # Handle nextAct/next_act
                        normalized_activity["nextAct"] = a.get("next_act") or a.get("nextAct", [])
                        # Handle expectedTime/expected_time
                        normalized_activity["expectedTime"] = a.get("expected_time") or a.get("expectedTime", 0)
                        # Other fields
                        normalized_activity["model_class"] = a.get("model_class", [])
                        normalized_activity["model_id"] = a.get("model_id")
                        normalized_activity["function"] = a.get("function")
                        # Handle instruction/description fields
                        normalized_activity["description"] = a.get("instruction") or a.get("description") or a.get("step_text")
                        normalized_activity["instruction"] = normalized_activity["description"]
                        
                        activities.append(Activity(**normalized_activity))
                    except TypeError as e:
                        errors.append(f"sop_master.activity validation error: {str(e)}")
                
                # Normalize sop_master fields
                sop_id = sm.get("sopId") or sm.get("sop_id", "")
                start_activity = sm.get("start_activity") or sm.get("startActivity", [])
                end_activity = sm.get("end_activity") or sm.get("endActivity", [])
                
                SOPMaster(
                    sopId=sop_id,
                    startActivity=start_activity,
                    endActivity=end_activity,
                    activities=activities
                )
            except TypeError as e:
                errors.append(f"sop_master validation error: {str(e)}")
        else:
            errors.append("sop_master: missing")

        # Validate sop_activity_rule_map
        rm = data.get("sop_activity_rule_map")
        if rm:
            try:
                rules_map = []
                for r in rm.get("rules_map", []):
                    try:
                        rules_map.append(RuleMapping(**r))
                    except TypeError as e:
                        errors.append(f"sop_activity_rule_map.rules_map validation error: {str(e)}")
                SOPActivityRuleMap(
                    sop_id=rm.get("sop_id", ""),
                    rules_map=rules_map
                )
            except TypeError as e:
                errors.append(f"sop_activity_rule_map validation error: {str(e)}")
        else:
            errors.append("sop_activity_rule_map: missing")

        # Validate sop_rules
        rules = data.get("sop_rules", [])
        if rules:
            for r in rules:
                try:
                    SOPRule(**r)
                except TypeError as e:
                    errors.append(f"sop_rules validation error for rule {r.get('rule_name', r.get('_id', 'unknown'))}: {str(e)}")
        else:
            errors.append("sop_rules: missing or empty")

        # Check all activities in sop_master are in rules_map
        if sm and rm:
            # Normalize activity IDs from sop_master (support both camelCase and snake_case)
            master_activities = set()
            for a in sm.get("activities", []):
                act_id = a.get("activityId") or a.get("activity_id")
                if act_id:
                    master_activities.add(act_id)
            
            # Normalize activity IDs from rules_map
            map_activities = set()
            for r in rm.get("rules_map", []):
                act_id = r.get("activity_id") or r.get("activityId")
                if act_id:
                    map_activities.add(act_id)
            
            missing = master_activities - map_activities
            for act in missing:
                errors.append(f"activity '{act}' not in rules_map")

        # Check all rules in rules_map exist in sop_rules
        if rm and rules:
            # Build available rules set - check both rule_name and _id fields
            available_rules = set()
            for r in rules:
                rule_name = r.get("rule_name") or r.get("_id")
                if rule_name:
                    available_rules.add(rule_name)
            
            for mapping in rm.get("rules_map", []):
                for rule in mapping.get("activity_rules", []):
                    if isinstance(rule, dict):
                        for name in rule.keys():
                            if name not in available_rules:
                                errors.append(f"rule '{name}' not in sop_rules (available: {available_rules})")
                    elif isinstance(rule, list):  # OR group
                        for r in rule:
                            if isinstance(r, dict):
                                for name in r.keys():
                                    if name not in available_rules:
                                        errors.append(f"rule '{name}' not in sop_rules (available: {available_rules})")
                for rule in mapping.get("anomaly_rules", []):
                    if isinstance(rule, dict):
                        for name in rule.keys():
                            if name not in available_rules:
                                errors.append(f"rule '{name}' not in sop_rules (available: {available_rules})")
                    elif isinstance(rule, list):
                        for r in rule:
                            if isinstance(r, dict):
                                for name in r.keys():
                                    if name not in available_rules:
                                        errors.append(f"rule '{name}' not in sop_rules (available: {available_rules})")

    except TypeError as e:
        errors.append(f"validation error: {str(e)}")

    return {"valid": len(errors) == 0, "errors": errors}


def load_sop(
    source_type: str = "mongodb",
    mongo_uri: str = DEFAULT_MONGO_URI,
    database_name: str = DEFAULT_DATABASE_NAME,
    source_id: Any = None,
    sop_id: str = None,
    collections: Dict[str, str] = None,
    config: Dict[str, Any] = None,
    keys: Dict[str, str] = None,
    local_json_path: str = None
) -> Optional[Dict]:
    """
    Load raw SOP data from MongoDB, ThingsBoard, or local JSON files.

    Returns:
        {
            "sop_master": {...},
            "sop_activity_rule_map": {...},
            "sop_rules": [...],
            "validation": {"valid": bool, "errors": [...]}
        }
    """
    source_type = source_type.lower()
    collections = {**DEFAULT_MONGO_COLLECTIONS, **(collections or {})}
    keys = {**DEFAULT_THINGSBOARD_KEYS, **(keys or {})}


    try:
        if source_type == "mongodb":
            return _load_from_mongodb(mongo_uri, database_name, source_id, sop_id, collections)
        elif source_type == "thingsboard":
            return _load_from_thingsboard(config, sop_id, keys)
        elif source_type == "local" or source_type == "local_json":
            return _load_from_local_json(sop_id, local_json_path)
        else:
            print(f"[load_sop] Unknown source type: {source_type}")
            return None
    except Exception as e:
        print(f"[load_sop] Error: {e}")
        traceback.print_exc()
        return None


def _load_from_mongodb(mongo_uri, database_name, source_id, sop_id, collections) -> Optional[Dict]:
    """Load raw SOP data from MongoDB."""
    from pymongo import MongoClient

    client = MongoClient(mongo_uri)
    db = client[database_name]

    try:
        # Resolve sop_id from source if not provided
        if not sop_id and source_id:
            src = None
            for field in ["topic", "name", "source_id", "_id"]:
                src = db[collections["source"]].find_one({field: source_id})
                if src:
                    break
            if src:
                sop_id = src.get("sop_id")

        if not sop_id:
            print("[load_sop] Could not resolve sop_id")
            return None

        # Load sop_master
        sop_master = db[collections["sop_master"]].find_one({"sopId": sop_id})
        if not sop_master:
            sop_master = db[collections["sop_master"]].find_one({"sop_id": sop_id})
        if sop_master:
            sop_master.pop("_id", None)

        # Load sop_activity_rule_map
        rule_map = db[collections["sop_activity_rule_map"]].find_one({"sop_id": sop_id})
        if rule_map:
            rule_map.pop("_id", None)

        # Get required rule names from rules_map
        required_rules = set()
        if rule_map and rule_map.get("rules_map"):
            for activity in rule_map["rules_map"]:
                for rule in activity.get("activity_rules", []):
                    if isinstance(rule, dict):
                        required_rules.update(rule.keys())
                    elif isinstance(rule, list):  # OR group
                        for r in rule:
                            if isinstance(r, dict):
                                required_rules.update(r.keys())
                for rule in activity.get("anomaly_rules", []):
                    if isinstance(rule, dict):
                        required_rules.update(rule.keys())
                    elif isinstance(rule, list):
                        for r in rule:
                            if isinstance(r, dict):
                                required_rules.update(r.keys())

        # Load only required rules
        sop_rules = []
        if required_rules:
            for rule_name in required_rules:
                rule = db[collections["sop_rule_master"]].find_one({"rule_name": rule_name})
                if rule:
                    rule.pop("_id", None)
                    sop_rules.append(rule)

        # Load analytics template (optional)
        analytics_template = None
        if "sop_analytics_template" in collections:
            analytics_template = db[collections["sop_analytics_template"]].find_one({"sop_id": sop_id})
            if analytics_template:
                analytics_template.pop("_id", None)
                # Analytics template loaded

        data = {
            "sop_master": sop_master,
            "sop_activity_rule_map": rule_map,
            "sop_rules": sop_rules,
            "sop_analytics_template": analytics_template
        }

        data["validation"] = validate_structure(data)

        # Loaded SOP data
        return data

    finally:
        client.close()


def _load_from_local_json(sop_id: str, json_path: str = None) -> Optional[Dict]:
    """Load raw SOP data from local JSON files in abbjsons, gender_detection, phone_assembly folders."""
    import json
    import os
    from pathlib import Path
    
    # Try to find project root (where sop_loader.py is located)
    current_file = Path(__file__).resolve()
    project_root = current_file.parent
    
    # If json_path is provided, use it; otherwise try multiple directories
    if json_path:
        json_path = Path(json_path)
        if not json_path.exists():
            print(f"[load_sop] Local JSON path does not exist: {json_path}")
            return None
    else:
        # Try multiple directories based on sop_id
        possible_dirs = []
        
        # Check sop_id to determine likely directory
        if sop_id and "GENDER" in sop_id.upper():
            possible_dirs = [
                project_root / "gender_detection",
                project_root / "abbjsons"
            ]
        elif sop_id and "PHONE" in sop_id.upper() or sop_id and "ASSEMBLY" in sop_id.upper():
            possible_dirs = [
                project_root / "phone_assembly",
                project_root / "abbjsons"
            ]
        elif sop_id and "POSE" in sop_id.upper():
            possible_dirs = [
                project_root / "pose_detection",
                project_root / "abbjsons"
            ]
        else:
            # Default: try all common directories
            possible_dirs = [
                project_root / "gender_detection",
                project_root / "phone_assembly",
                project_root / "pose_detection",
                project_root / "abbjsons"
            ]
        
        # Find first existing directory
        json_path = None
        for dir_path in possible_dirs:
            if dir_path.exists():
                json_path = dir_path
                break
        
        if not json_path:
            print(f"[load_sop] Could not find any SOP directory in: {possible_dirs}")
            return None
    
    if not sop_id:
        print("[load_sop] sop_id is required for local JSON loading")
        return None
    
    try:
        # Try different naming patterns for pose SOP, phone assembly, and gender detection
        possible_files = {
            "sop_master": [
                json_path / f"{sop_id.lower()}_sop_master.json",
                json_path / f"pose_sop_master.json",  # For EZA_SOP_POSE
                json_path / f"abb_sop_master.json",   # For EZA_SOP_ABB
                json_path / f"gender_sop_master.json",  # For EZA_SOP_GENDER
                json_path / f"sop_master.json",  # For phone_assembly
            ],
            "activity_rule_map": [
                json_path / f"{sop_id.lower()}_activity_rule_map.json",
                json_path / f"pose_activity_rule_map.json",  # For EZA_SOP_POSE
                json_path / f"abb_activity_rule_map.json",  # For EZA_SOP_ABB
                json_path / f"gender_activity_rule_map.json",  # For EZA_SOP_GENDER
                json_path / f"sop_activity_rule_mapper.json",  # For phone_assembly
            ],
            "central_rules": [
                json_path / f"{sop_id.lower()}_central_rules.json",
                json_path / f"pose_central_rules.json",  # For EZA_SOP_POSE
                json_path / f"abb_central_rules.json",   # For EZA_SOP_ABB
                json_path / f"gender_central_rules.json",  # For EZA_SOP_GENDER
            ]
        }
        
        # Load sop_master
        sop_master = None
        for file_path in possible_files["sop_master"]:
            if file_path.exists():
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    # Handle array format (first element) or direct object
                    if isinstance(data, list) and len(data) > 0:
                        # Find matching sopId
                        for item in data:
                            if item.get("sopId") == sop_id or item.get("sop_id") == sop_id:
                                sop_master = item.copy()  # Make a copy
                                break
                        if not sop_master and len(data) == 1:
                            sop_master = data[0].copy()  # Use first if only one
                    elif isinstance(data, dict):
                        if data.get("sopId") == sop_id or data.get("sop_id") == sop_id:
                            sop_master = data.copy()
                if sop_master:
                    # Remove MongoDB _id field if present
                    sop_master.pop("_id", None)
                    # Found sop_master
                    break
        
        if not sop_master:
            # Could not find sop_master
            return None
        
        # Load activity_rule_map
        rule_map = None
        for file_path in possible_files["activity_rule_map"]:
            if file_path.exists():
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    # Handle array format or direct object
                    if isinstance(data, list) and len(data) > 0:
                        # Find matching sop_id
                        for item in data:
                            if item.get("sop_id") == sop_id:
                                rule_map = item.copy()  # Make a copy
                                break
                        if not rule_map and len(data) == 1:
                            rule_map = data[0].copy()
                    elif isinstance(data, dict):
                        if data.get("sop_id") == sop_id:
                            rule_map = data.copy()
                if rule_map:
                    # Remove MongoDB _id field if present
                    rule_map.pop("_id", None)
                    # Found activity_rule_map
                    break
        
        if not rule_map:
            # Could not find activity_rule_map
            return None
        
        # Load central_rules (sop_rules)
        sop_rules = []
        for file_path in possible_files["central_rules"]:
            if file_path.exists():
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    # Handle array format
                    if isinstance(data, list):
                        sop_rules = [r.copy() for r in data]  # Make copies
                    elif isinstance(data, dict):
                        sop_rules = [data.copy()]
                if sop_rules:
                    # Remove MongoDB _id fields if present
                    for rule in sop_rules:
                        rule.pop("_id", None)
                    # Found rules
                    break
        
        # Get required rule names from rules_map
        required_rules = set()
        if rule_map and rule_map.get("rules_map"):
            for activity in rule_map["rules_map"]:
                for rule in activity.get("activity_rules", []):
                    if isinstance(rule, dict):
                        required_rules.update(rule.keys())
                    elif isinstance(rule, list):  # OR group
                        for r in rule:
                            if isinstance(r, dict):
                                required_rules.update(r.keys())
                for rule in activity.get("anomaly_rules", []):
                    if isinstance(rule, dict):
                        required_rules.update(rule.keys())
                    elif isinstance(rule, list):
                        for r in rule:
                            if isinstance(r, dict):
                                required_rules.update(r.keys())
        
        # Filter rules to only include required ones
        if required_rules:
            filtered_rules = []
            for r in sop_rules:
                rule_name = r.get("rule_name") or r.get("_id")
                rule_id = r.get("_id") or r.get("rule_name")
                # Check if either rule_name or _id matches
                if rule_name in required_rules or rule_id in required_rules:
                    filtered_rules.append(r)
            if filtered_rules:
                sop_rules = filtered_rules
                # Filtered to required rules
            else:
                # WARNING: No rules matched required_rules, keeping all rules
                pass
        else:
            # No required_rules found, keeping all rules
            pass
        
        data = {
            "sop_master": sop_master,
            "sop_activity_rule_map": rule_map,
            "sop_rules": sop_rules
        }
        
        # Validate structure
        data["validation"] = validate_structure(data)
        
        # Only log if validation failed (errors will be logged by SOPManager)
        if not data["validation"]["valid"]:
            pass  # Validation errors handled by caller
        
        return data
        
    except Exception as e:
        print(f"[load_sop] Error loading from local JSON: {e}")
        traceback.print_exc()
        return None


def _load_from_thingsboard(config, sop_id, keys) -> Optional[Dict]:
    """Load raw SOP data from ThingsBoard config."""
    import json

    if not config:
        print("[load_sop] No config provided")
        return None

    sop_config = config.get(keys["sop_config"], {})

    if isinstance(sop_config, str):
        sop_config = json.loads(sop_config)

    if isinstance(sop_config, list):
        if len(sop_config) == 3 and all(isinstance(item, list) for item in sop_config):
            # ThingsBoard format: [[sop_masters], [rules], [rule_maps]]
            sop_config = {
                "sop_master": sop_config[0],
                "sop_rule_master": sop_config[1],
                "sop_activity_rule_map": sop_config[2]
            }
        elif len(sop_config) > 0 and isinstance(sop_config[0], dict):
            # Check if it's a list of config objects or the actual data
            if "sop_master" in sop_config[0]:
                sop_config = sop_config[0]
            else:
                # It's likely the sop_master list directly, wrap it
                sop_config = {
                    "sop_master": sop_config,
                    "sop_rule_master": config.get(keys["sop_rule_master"], []),
                    "sop_activity_rule_map": config.get(keys["sop_activity_rule_map"], [])
                }
        else:
            print("[load_sop] Invalid sopConfig structure")
            return None

    # Get sop_id
    sop_id = sop_id or config.get(keys["sop_id"], "")
    if not sop_id:
        print("[load_sop] Could not resolve sop_id")
        return None

    # Get sop_master
    sop_master_data = sop_config.get(keys["sop_master"], [])
    if isinstance(sop_master_data, list):
        sop_master = next((s for s in sop_master_data if s.get("sopId") == sop_id), None)
    else:
        sop_master = sop_master_data

    # Get sop_activity_rule_map
    rule_map_data = sop_config.get(keys["sop_activity_rule_map"], [])
    if isinstance(rule_map_data, list):
        rule_map = next((m for m in rule_map_data if m.get("sop_id") == sop_id), None)
    else:
        rule_map = rule_map_data

    # Get required rule names
    required_rules = set()
    if rule_map and rule_map.get("rules_map"):
        for activity in rule_map["rules_map"]:
            for rule in activity.get("activity_rules", []):
                if isinstance(rule, dict):
                    required_rules.update(rule.keys())
                elif isinstance(rule, list):
                    for r in rule:
                        if isinstance(r, dict):
                            required_rules.update(r.keys())
            for rule in activity.get("anomaly_rules", []):
                if isinstance(rule, dict):
                    required_rules.update(rule.keys())
                elif isinstance(rule, list):
                    for r in rule:
                        if isinstance(r, dict):
                            required_rules.update(r.keys())

    # Get only required rules
    all_rules = sop_config.get(keys["sop_rule_master"], [])
    sop_rules = [r for r in all_rules if r.get("rule_name") in required_rules]

    data = {
        "sop_master": sop_master,
        "sop_activity_rule_map": rule_map,
        "sop_rules": sop_rules
    }

    data["validation"] = validate_structure(data)

    print(f"[load_sop] Loaded: {sop_id} ({len(sop_rules)} rules)")
    return data
