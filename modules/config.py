"""Runtime settings for the running dashboard."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    APP_TITLE = os.getenv("APP_TITLE", "Analiza Biegowa")
    APP_ICON = os.getenv("APP_ICON", "🏃")
    APP_LAYOUT = os.getenv("APP_LAYOUT", "wide")
    CSS_FILE = os.getenv("CSS_FILE", str(BASE_DIR / "style.css"))

    DEFAULT_BODY_WEIGHT_KG = float(os.getenv("DEFAULT_BODY_WEIGHT_KG", "75.0"))
    DEFAULT_RUNNER_HEIGHT_CM = int(os.getenv("DEFAULT_RUNNER_HEIGHT_CM", "180"))
    DEFAULT_THRESHOLD_PACE_SEC_PER_KM = int(os.getenv("DEFAULT_THRESHOLD_PACE_SEC_PER_KM", "233"))

    ROLLING_WINDOW_60S = int(os.getenv("ROLLING_WINDOW_60S", "60"))
    SMOOTH_WINDOW = int(os.getenv("SMOOTH_WINDOW", "30"))
    SMOOTH_WINDOW_SHORT = int(os.getenv("SMOOTH_WINDOW_SHORT", "5"))
    RESAMPLE_THRESHOLD = int(os.getenv("RESAMPLE_THRESHOLD", "10000"))
    RESAMPLE_STEP = int(os.getenv("RESAMPLE_STEP", "5"))
    MIN_DF_LENGTH = int(os.getenv("MIN_DF_LENGTH", "10"))

    VALIDATION_MAX_HR = int(os.getenv("VALIDATION_MAX_HR", "250"))
    VALIDATION_MAX_CADENCE = int(os.getenv("VALIDATION_MAX_CADENCE", "250"))
    COLOR_PACE = "#00cc96"
    COLOR_HR = "#ef553b"
