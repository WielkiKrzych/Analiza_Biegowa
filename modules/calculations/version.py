"""
Ramp Test Methodology Versioning.

Defines the current version of the analysis algorithm.
Used by persistence and reporting modules to ensure traceability.
"""
import json
from pathlib import Path
from typing import Dict, Any

# GLOBAL CONSTANT - Single Source of Truth
RAMP_METHOD_VERSION = "1.0.0"

def get_methodology_info() -> Dict[str, Any]:
    """
    Load detailed methodology version info from JSON.
    Returns dict with version, features, etc.
    """
    # Try to find the JSON file relative to project root
    # Assuming this file is in modules/calculations/
    # Project root is ../../
    
    current_dir = Path(__file__).parent
    project_root = current_dir.parent.parent
    version_file = project_root / "methodology" / "ramp_test" / "methodology_version.json"
    
    try:
        if version_file.exists():
            with open(version_file, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
        
    # Fallback
    return {
        "version": RAMP_METHOD_VERSION,
        "description": "Version info not found"
    }
