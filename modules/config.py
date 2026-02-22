import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).parent.parent


class Config:
    BASE_DIR = BASE_DIR
    # --- Application Settings ---
    APP_TITLE = os.getenv("APP_TITLE", "Pro Athlete Dashboard")
    APP_ICON = os.getenv("APP_ICON", "⚡")
    APP_LAYOUT = os.getenv("APP_LAYOUT", "wide")
    CSS_FILE = os.getenv("CSS_FILE", "style.css")

    # --- Analysis Parameters ---
    ROLLING_WINDOW_5MIN = int(os.getenv("ROLLING_WINDOW_5MIN", "300"))
    ROLLING_WINDOW_30S = int(os.getenv("ROLLING_WINDOW_30S", "30"))
    ROLLING_WINDOW_60S = int(os.getenv("ROLLING_WINDOW_60S", "60"))

    # Constants for smoothing (legacy support)
    SMOOTH_WINDOW = int(os.getenv("SMOOTH_WINDOW", "30"))
    SMOOTH_WINDOW_SHORT = int(os.getenv("SMOOTH_WINDOW_SHORT", "5"))

    # Filtering & Resampling
    RESAMPLE_THRESHOLD = int(os.getenv("RESAMPLE_THRESHOLD", "10000"))
    RESAMPLE_STEP = int(os.getenv("RESAMPLE_STEP", "5"))
    MIN_WATTS_ACTIVE = int(os.getenv("MIN_WATTS_ACTIVE", "10"))
    MIN_HR_ACTIVE = int(os.getenv("MIN_HR_ACTIVE", "40"))
    MIN_RECORDS_FOR_ROLLING = int(os.getenv("MIN_RECORDS_FOR_ROLLING", "30"))
    MIN_DF_LENGTH = int(os.getenv("MIN_DF_LENGTH", "10"))

    # --- Data Validation ---
    VALIDATION_MAX_WATTS = int(os.getenv("VALIDATION_MAX_WATTS", "3000"))
    VALIDATION_MAX_HR = int(os.getenv("VALIDATION_MAX_HR", "250"))
    VALIDATION_MAX_CADENCE = int(os.getenv("VALIDATION_MAX_CADENCE", "250"))
    VALIDATION_REQUIRED_COLS = ["time"]
    VALIDATION_DATA_COLS = ["watts", "heartrate", "cadence", "smo2", "power"]

    # --- ML Settings ---
    MODEL_FILE = os.getenv("MODEL_FILE", "cycling_brain_weights.npz")
    HISTORY_FILE = os.getenv("HISTORY_FILE", "brain_evolution_history.json")
    ML_EPOCHS = int(os.getenv("ML_EPOCHS", "200"))
    ML_LEARNING_RATE = float(os.getenv("ML_LEARNING_RATE", "0.02"))

    # --- Database ---
    DATA_DIR = BASE_DIR / "data"
    DB_NAME = os.getenv("DB_NAME", "training_history.db")
    DB_PATH = DATA_DIR / DB_NAME

    # --- UI Colors ---
    COLOR_POWER = os.getenv("COLOR_POWER", "#00cc96")
    COLOR_HR = os.getenv("COLOR_HR", "#ef553b")
    COLOR_SMO2 = os.getenv("COLOR_SMO2", "#ab63fa")
    COLOR_VE = os.getenv("COLOR_VE", "#ffa15a")
    COLOR_RR = os.getenv("COLOR_RR", "#19d3f3")
    COLOR_THB = os.getenv("COLOR_THB", "#e377c2")
    COLOR_TORQUE = os.getenv("COLOR_TORQUE", "#e377c2")

    # --- Threshold Detection Constants ---
    VT1_SLOPE_THRESHOLD = float(os.getenv("VT1_SLOPE_THRESHOLD", "0.05"))
    VT2_SLOPE_THRESHOLD = float(os.getenv("VT2_SLOPE_THRESHOLD", "0.10"))
    VT1_SLOPE_SPIKE_SKIP = float(os.getenv("VT1_SLOPE_SPIKE_SKIP", "0.10"))
    SLOPE_CONFIDENCE_MAX = float(os.getenv("SLOPE_CONFIDENCE_MAX", "0.4"))
    STABILITY_CONFIDENCE_MAX = float(os.getenv("STABILITY_CONFIDENCE_MAX", "0.4"))
    BASE_CONFIDENCE = float(os.getenv("BASE_CONFIDENCE", "0.2"))
    MAX_CONFIDENCE = float(os.getenv("MAX_CONFIDENCE", "0.95"))
    LOWER_STEP_WEIGHT = float(os.getenv("LOWER_STEP_WEIGHT", "0.3"))
    UPPER_STEP_WEIGHT = float(os.getenv("UPPER_STEP_WEIGHT", "0.7"))

    @classmethod
    def validate(cls) -> None:
        """Validate configuration values.
        
        Raises:
            ValueError: If any configuration value is invalid
        """
        # Validate positive values
        if cls.MIN_WATTS_ACTIVE < 0:
            raise ValueError(f"MIN_WATTS_ACTIVE must be >= 0, got {cls.MIN_WATTS_ACTIVE}")
        
        if cls.MIN_HR_ACTIVE < 0:
            raise ValueError(f"MIN_HR_ACTIVE must be >= 0, got {cls.MIN_HR_ACTIVE}")
        
        if cls.MIN_RECORDS_FOR_ROLLING < 1:
            raise ValueError(f"MIN_RECORDS_FOR_ROLLING must be >= 1, got {cls.MIN_RECORDS_FOR_ROLLING}")
        
        # Validate ranges
        if not (0.0 < cls.ML_LEARNING_RATE < 1.0):
            raise ValueError(f"ML_LEARNING_RATE must be in (0, 1), got {cls.ML_LEARNING_RATE}")
        
        if not (0.0 < cls.VT1_SLOPE_THRESHOLD < 1.0):
            raise ValueError(f"VT1_SLOPE_THRESHOLD must be in (0, 1), got {cls.VT1_SLOPE_THRESHOLD}")
        
        if not (0.0 < cls.VT2_SLOPE_THRESHOLD < 1.0):
            raise ValueError(f"VT2_SLOPE_THRESHOLD must be in (0, 1), got {cls.VT2_SLOPE_THRESHOLD}")
        
        # Validate confidence values
        for name, value in [
            ("SLOPE_CONFIDENCE_MAX", cls.SLOPE_CONFIDENCE_MAX),
            ("STABILITY_CONFIDENCE_MAX", cls.STABILITY_CONFIDENCE_MAX),
            ("BASE_CONFIDENCE", cls.BASE_CONFIDENCE),
            ("MAX_CONFIDENCE", cls.MAX_CONFIDENCE),
        ]:
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"{name} must be in [0, 1], got {value}")
        
        if cls.BASE_CONFIDENCE >= cls.MAX_CONFIDENCE:
            raise ValueError(
                f"BASE_CONFIDENCE ({cls.BASE_CONFIDENCE}) must be < "
                f"MAX_CONFIDENCE ({cls.MAX_CONFIDENCE})"
            )
        
        # Validate file paths
        if not isinstance(cls.DB_PATH, Path):
            raise ValueError(f"DB_PATH must be a Path object, got {type(cls.DB_PATH)}")
        
        if not isinstance(cls.DATA_DIR, Path):
            raise ValueError(f"DATA_DIR must be a Path object, got {type(cls.DATA_DIR)}")


# Validate configuration on module load
Config.validate()
