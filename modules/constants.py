# Constants and configuration for Tri_Dashboard
# Centralized values to avoid magic numbers throughout the codebase

from typing import Dict, Tuple

# =============================================================================
# SMOOTHING WINDOWS
# =============================================================================
WINDOW_LONG: str = '30s'
WINDOW_SHORT: str = '5s'

# =============================================================================
# POWER ZONES (as fraction of CP)
# =============================================================================
ZONES: Dict[str, Tuple[float, float]] = {
    'Z1': (0.00, 0.55),  # Recovery
    'Z2': (0.55, 0.75),  # Endurance
    'Z3': (0.75, 0.90),  # Tempo
    'Z4': (0.90, 1.05),  # Threshold
    'Z5': (1.05, 1.20),  # VO2Max
    'Z6': (1.20, 10.0),  # Anaerobic (capped for binning)
}

ZONE_LABELS: Dict[str, str] = {
    'Z1': 'Z1 Recovery',
    'Z2': 'Z2 Endurance', 
    'Z3': 'Z3 Tempo',
    'Z4': 'Z4 Threshold',
    'Z5': 'Z5 VO2Max',
    'Z6': 'Z6 Anaerobic',
}

# =============================================================================
# MINIMUM SAMPLES FOR CALCULATIONS
# =============================================================================
MIN_SAMPLES_HRV: int = 100
MIN_SAMPLES_DFA_WINDOW: int = 30
MIN_SAMPLES_ACTIVE: int = 600
MIN_SAMPLES_Z2_DRIFT: int = 300

# =============================================================================
# PHYSIOLOGICAL DEFAULTS
# =============================================================================
EFFICIENCY_FACTOR: float = 0.22  # Mechanical efficiency for energy calculations
KCAL_PER_JOULE: float = 1 / 4184.0
KCAL_PER_GRAM_CARB: float = 4.0

# Carbohydrate contribution by zone
CARB_FRACTION_BELOW_VT1: float = 0.3
CARB_FRACTION_VT1_VT2: float = 0.8
CARB_FRACTION_ABOVE_VT2: float = 1.1

# =============================================================================
# HRV ANALYSIS
# =============================================================================
DFA_WINDOW_SEC: int = 300
DFA_STEP_SEC: int = 30
DFA_ALPHA_MIN: float = 0.3
DFA_ALPHA_MAX: float = 1.5

# =============================================================================
# FILTERING THRESHOLDS
# =============================================================================
MIN_WATTS_ACTIVE: int = 50
MIN_HR_ACTIVE: int = 90
MIN_HR_Z2: int = 60
MIN_WATTS_DECOUPLING: int = 100
MIN_HR_DECOUPLING: int = 80

# =============================================================================
# AI/ML SETTINGS
# =============================================================================
ML_PREDICTION_SCALE: float = 200.0  # HR scaling factor
ML_POWER_SCALE: float = 500.0
ML_CADENCE_SCALE: float = 120.0

# Default training targets (watts)
ML_TARGET_BASE: int = 280
ML_TARGET_THRESH: int = 360
ML_TOLERANCE: int = 15
ML_MIN_SAMPLES: int = 30
