# Analiza Biegową - Plan Transformacji (Cycling → Running)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform existing cycling analysis app (power-based) into running analysis app with pace-based metrics, dual mode support (pace + running power), and comprehensive running dynamics.

**Architecture:** Keep modular Streamlit architecture, replace power-centric calculations with pace-centric equivalents, add running-specific modules (GAP, running dynamics, race predictor), maintain backward compatibility via dual mode.

**Tech Stack:** Python 3.11+, Streamlit, NumPy, Pandas, Polars (optional), Plotly/Matplotlib for charts

**Domain:** Running sports science - pace (min/km), threshold pace, Critical Speed (CS), D' (anaerobic distance), Grade-Adjusted Pace (GAP), running dynamics (cadence SPM, GCT, stride length).

---

## Phase 1: Core Refactoring - Settings & Domain Models

### Task 1.1: Update Settings Manager

**Files:**
- Modify: `modules/settings.py:1-47`

**Context:** Current settings use `rider_` prefix and cycling-specific params (crank_length, cp, w_prime). Need to change to `runner_` and running params (threshold_pace, cs, d_prime).

**Step 1: Write the failing test**

Create: `tests/test_settings_running.py`

```python
import pytest
from modules.settings import SettingsManager

def test_default_settings_running():
    """Test that default settings are running-oriented."""
    sm = SettingsManager()
    defaults = sm.default_settings
    
    # Should have runner_ prefix, not rider_
    assert "runner_weight" in defaults
    assert "runner_height" in defaults
    assert "runner_age" in defaults
    
    # Should have running-specific params
    assert "threshold_pace" in defaults  # min/km
    assert "critical_speed" in defaults  # m/s or min/km
    assert "d_prime" in defaults  # meters
    
    # Should NOT have cycling-specific params
    assert "crank_length" not in defaults
    assert "cp" not in defaults  # will be replaced
    assert "w_prime" not in defaults  # will be replaced
    
    # Default threshold pace should be realistic (4:00-6:00 min/km)
    assert 240 <= defaults["threshold_pace"] <= 360  # seconds per km

def test_load_settings_returns_defaults():
    """Test that load_settings returns default settings."""
    sm = SettingsManager()
    settings = sm.load_settings()
    assert settings["runner_weight"] == sm.default_settings["runner_weight"]
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/wielkikrzychmbp/Documents/Analiza_Biegowa
python -m pytest tests/test_settings_running.py -v
```

Expected: FAIL with `AssertionError: 'runner_weight' not in defaults`

**Step 3: Implement new SettingsManager**

Modify: `modules/settings.py`

```python
import streamlit as st

SETTINGS_FILE = 'user_settings.json'

class SettingsManager:
    def __init__(self, file_path=SETTINGS_FILE):
        self.file_path = file_path
        self.default_settings = {
            # Athlete basic data
            "runner_weight": 75.0,  # kg
            "runner_height": 175,   # cm
            "runner_age": 30,
            "is_male": True,
            
            # Running performance metrics
            "threshold_pace": 300,     # seconds per km (5:00 min/km)
            "critical_speed": 3.33,    # m/s (equivalent to 5:00 min/km)
            "d_prime": 200,            # meters (anaerobic distance capacity)
            
            # Thresholds from ventilatory markers
            "vt1_pace": 330,           # seconds per km (5:30 min/km)
            "vt2_pace": 270,           # seconds per km (4:30 min/km)
            "vt1_vent": 71.0,          # L/min (keep for compatibility)
            "vt2_vent": 109.0,         # L/min (keep for compatibility)
            
            # Running form preferences
            "preferred_cadence": 170,  # SPM (steps per minute)
            "target_stride_length": 0, # 0 = auto-calculate from height
        }

    def load_settings(self):
        """Returns hardcoded default settings, ignoring any saved file."""
        return self.default_settings

    def save_settings(self, settings_dict):
        """Settings persistence is disabled to enforce hardcoded defaults."""
        return True

    def get_ui_values(self):
        """Helper to get values for UI (Session State or Load)."""
        if 'user_settings' not in st.session_state:
            st.session_state['user_settings'] = self.load_settings()
        return st.session_state['user_settings']

    def update_from_ui(self, key, value):
        """Callback to update specific setting."""
        if 'user_settings' not in st.session_state:
            st.session_state['user_settings'] = self.load_settings()
        st.session_state['user_settings'][key] = value
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_settings_running.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add modules/settings.py tests/test_settings_running.py
git commit -m "feat(settings): transform to running-oriented settings

- Change rider_ prefix to runner_
- Replace cp/w_prime with threshold_pace/critical_speed/d_prime
- Remove crank_length cycling parameter
- Add preferred_cadence and target_stride_length"
```

---

### Task 1.2: Create Pace Utilities Module

**Files:**
- Create: `modules/calculations/pace_utils.py`
- Create: `tests/calculations/test_pace_utils.py`

**Context:** Pace calculations are central to running. Need utility functions for pace conversion (min/km ↔ m/s), pace zones, etc.

**Step 1: Write the failing test**

Create: `tests/calculations/test_pace_utils.py`

```python
import pytest
import numpy as np
from modules.calculations.pace_utils import (
    pace_to_speed, speed_to_pace, format_pace, 
    pace_to_seconds, seconds_to_pace_str
)

def test_pace_to_speed():
    """Test converting min/km to m/s."""
    # 5:00 min/km = 300s/km = 3.33 m/s
    assert pace_to_speed(300) == pytest.approx(3.333, rel=0.01)
    # 4:00 min/km = 240s/km = 4.17 m/s
    assert pace_to_speed(240) == pytest.approx(4.167, rel=0.01)

def test_speed_to_pace():
    """Test converting m/s to min/km."""
    # 3.33 m/s = 300s/km = 5:00 min/km
    assert speed_to_pace(3.333) == pytest.approx(300, rel=0.01)
    # 4.17 m/s = 240s/km = 4:00 min/km
    assert speed_to_pace(4.167) == pytest.approx(240, rel=0.01)

def test_pace_speed_roundtrip():
    """Test that pace→speed→pace roundtrip works."""
    original_pace = 300  # 5:00 min/km
    speed = pace_to_speed(original_pace)
    recovered_pace = speed_to_pace(speed)
    assert original_pace == pytest.approx(recovered_pace, rel=0.001)

def test_format_pace():
    """Test formatting pace as mm:ss."""
    assert format_pace(300) == "5:00"
    assert format_pace(245) == "4:05"
    assert format_pace(367) == "6:07"

def test_pace_to_seconds():
    """Test converting mm:ss string to seconds."""
    assert pace_to_seconds("5:00") == 300
    assert pace_to_seconds("4:30") == 270
    assert pace_to_seconds("6:15") == 375

def test_seconds_to_pace_str():
    """Test converting seconds to mm:ss string."""
    assert seconds_to_pace_str(300) == "5:00"
    assert seconds_to_pace_str(270) == "4:30"
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/calculations/test_pace_utils.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'modules.calculations.pace_utils'`

**Step 3: Implement pace utilities**

Create: `modules/calculations/pace_utils.py`

```python
"""
Pace utilities for running analysis.

Conversions between pace (min/km) and speed (m/s).
"""
import numpy as np
from typing import Union


def pace_to_speed(pace_sec_per_km: float) -> float:
    """
    Convert pace (seconds per km) to speed (m/s).
    
    Args:
        pace_sec_per_km: Pace in seconds per kilometer
        
    Returns:
        Speed in meters per second
        
    Example:
        >>> pace_to_speed(300)  # 5:00 min/km
        3.333...
    """
    if pace_sec_per_km <= 0:
        return 0.0
    # 1000 meters / pace seconds
    return 1000.0 / pace_sec_per_km


def speed_to_pace(speed_m_per_s: float) -> float:
    """
    Convert speed (m/s) to pace (seconds per km).
    
    Args:
        speed_m_per_s: Speed in meters per second
        
    Returns:
        Pace in seconds per kilometer
        
    Example:
        >>> speed_to_pace(3.333)  # 3.33 m/s
        300.0  # 5:00 min/km
    """
    if speed_m_per_s <= 0:
        return float('inf')
    # 1000 meters / speed
    return 1000.0 / speed_m_per_s


def format_pace(pace_sec_per_km: float) -> str:
    """
    Format pace as mm:ss string.
    
    Args:
        pace_sec_per_km: Pace in seconds per kilometer
        
    Returns:
        Formatted string like "5:00"
    """
    if pace_sec_per_km <= 0 or not np.isfinite(pace_sec_per_km):
        return "--:--"
    
    minutes = int(pace_sec_per_km // 60)
    seconds = int(pace_sec_per_km % 60)
    return f"{minutes}:{seconds:02d}"


def pace_to_seconds(pace_str: str) -> float:
    """
    Convert mm:ss string to seconds per km.
    
    Args:
        pace_str: Pace string like "5:00" or "5:30"
        
    Returns:
        Seconds per kilometer
    """
    try:
        parts = pace_str.strip().split(':')
        if len(parts) == 2:
            minutes = float(parts[0])
            seconds = float(parts[1])
            return minutes * 60 + seconds
        elif len(parts) == 1:
            return float(parts[0]) * 60  # Assume minutes only
    except (ValueError, IndexError):
        pass
    return 0.0


def seconds_to_pace_str(seconds: float) -> str:
    """
    Convert seconds to mm:ss pace string.
    
    Args:
        seconds: Seconds per kilometer
        
    Returns:
        Formatted pace string
    """
    return format_pace(seconds)


def calculate_pace(distance_m: float, time_sec: float) -> float:
    """
    Calculate pace (sec/km) from distance and time.
    
    Args:
        distance_m: Distance in meters
        time_sec: Time in seconds
        
    Returns:
        Pace in seconds per kilometer
    """
    if distance_m <= 0 or time_sec <= 0:
        return 0.0
    # pace = time / distance * 1000
    return time_sec / distance_m * 1000


def pace_array_to_speed_array(pace_array: np.ndarray) -> np.ndarray:
    """
    Vectorized conversion of pace array to speed array.
    
    Args:
        pace_array: Array of paces in sec/km
        
    Returns:
        Array of speeds in m/s
    """
    with np.errstate(divide='ignore', invalid='ignore'):
        speed = np.where(pace_array > 0, 1000.0 / pace_array, 0.0)
    return speed


def speed_array_to_pace_array(speed_array: np.ndarray) -> np.ndarray:
    """
    Vectorized conversion of speed array to pace array.
    
    Args:
        speed_array: Array of speeds in m/s
        
    Returns:
        Array of paces in sec/km
    """
    with np.errstate(divide='ignore', invalid='ignore'):
        pace = np.where(speed_array > 0, 1000.0 / speed_array, np.inf)
    return pace
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/calculations/test_pace_utils.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add modules/calculations/pace_utils.py tests/calculations/test_pace_utils.py
git commit -m "feat(pace): add pace utility module

- pace_to_speed and speed_to_pace conversions
- format_pace for mm:ss display
- Vectorized array conversions
- Input validation for edge cases"
```

---

## Phase 2: Pace Module & Zones

### Task 2.1: Create Main Pace Module

**Files:**
- Create: `modules/calculations/pace.py`
- Create: `tests/calculations/test_pace.py`

**Context:** This replaces `power.py` as the main performance module. Implements pace zones, pace duration curve, and running phenotype classification.

**Step 1: Write the failing test**

Create: `tests/calculations/test_pace.py`

```python
import pytest
import numpy as np
import pandas as pd
from modules.calculations.pace import (
    calculate_pace_zones_time,
    calculate_pace_duration_curve,
    classify_running_phenotype,
    estimate_vo2max_from_pace,
    get_phenotype_description
)

def test_calculate_pace_zones_time():
    """Test calculating time spent in each pace zone."""
    # Create sample dataframe with pace data
    df = pd.DataFrame({
        'pace': [300, 300, 330, 330, 330, 270, 270, 240]  # sec/km
    })
    
    # Threshold pace at 300 sec/km (5:00 min/km)
    zones = calculate_pace_zones_time(df, threshold_pace=300)
    
    # Should have 5 zones based on % of threshold
    assert "Z1 Recovery" in zones
    assert "Z2 Aerobic" in zones
    assert "Z3 Tempo" in zones
    assert "Z4 Threshold" in zones
    assert "Z5 Interval" in zones
    
    # Check specific counts
    assert zones["Z3 Tempo"] == 3  # 330 sec/km (slower than threshold)
    assert zones["Z4 Threshold"] == 2  # 270 sec/km (faster than threshold)
    assert zones["Z5 Interval"] == 1  # 240 sec/km (much faster)

def test_calculate_pace_duration_curve():
    """Test calculating pace duration curve."""
    # Create 10 minutes of data with varying pace
    np.random.seed(42)
    pace_data = np.concatenate([
        np.full(300, 330),  # 5 min @ 5:30
        np.full(300, 300),  # 5 min @ 5:00
    ])
    
    df = pd.DataFrame({'pace_sec_per_km': pace_data})
    
    pdc = calculate_pace_duration_curve(df)
    
    # Should have entries for different durations
    assert len(pdc) > 0
    # Best (lowest) pace should be around 300 sec/km
    assert min(pdc.values()) <= 310

def test_classify_running_phenotype():
    """Test running phenotype classification."""
    # Marathoner profile: strong endurance, lower sprint
    pdc = {
        60: 240,    # 1 min: 4:00 min/km
        300: 255,   # 5 min: 4:15 min/km
        1200: 270,  # 20 min: 4:30 min/km
        3600: 285   # 60 min: 4:45 min/km
    }
    
    phenotype = classify_running_phenotype(pdc, weight=70)
    assert phenotype in ["marathoner", "all_rounder", "endurance_specialist"]

def test_estimate_vo2max_from_pace():
    """Test VO2max estimation from pace."""
    # Using Daniels formula approximation
    vo2max = estimate_vo2max_from_pace(
        vvo2max_pace=240,  # 4:00 min/km at vVO2max
        weight=70
    )
    
    # Should be reasonable VO2max for trained runner (45-65)
    assert 40 <= vo2max <= 80

def test_get_phenotype_description():
    """Test phenotype description."""
    emoji, name, desc = get_phenotype_description("marathoner")
    assert emoji is not None
    assert "marathon" in name.lower() or "wytrzymałość" in desc.lower()
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/calculations/test_pace.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Implement main pace module**

Create: `modules/calculations/pace.py`

```python
"""
SRP: Main pace module for running analysis.

Replaces power.py for running context.
Implements pace zones, pace duration curve, and phenotype classification.
"""

from typing import Union, Any, Dict, Tuple, Optional
import numpy as np
import pandas as pd

from .pace_utils import pace_to_speed, speed_to_pace
from .common import ensure_pandas


def calculate_pace_zones_time(
    df_pl: Union[pd.DataFrame, Any], 
    threshold_pace: float,
    zones: dict = None
) -> dict:
    """
    Calculate time spent in each pace zone.
    
    Default zones based on % of threshold pace:
    - Z1 Recovery: >115% threshold (slower)
    - Z2 Aerobic: 105-115% threshold
    - Z3 Tempo: 95-105% threshold
    - Z4 Threshold: 88-95% threshold
    - Z5 Interval: 75-88% threshold
    - Z6 Repetition: <75% threshold (faster)
    
    Note: For pace, LOWER is FASTER, so percentages are inverted vs power.
    
    Args:
        df_pl: DataFrame with 'pace' column (sec/km)
        threshold_pace: Threshold pace in sec/km
        zones: Optional custom zone definitions (as % of threshold)
        
    Returns:
        Dict mapping zone name to seconds spent
    """
    df = ensure_pandas(df_pl)
    
    if "pace" not in df.columns or threshold_pace <= 0:
        return {}
    
    if zones is None:
        # Zones as % of threshold pace
        # Lower pace % = faster = higher zone
        zones = {
            "Z1 Recovery": (1.15, 2.0),    # >15% slower than threshold
            "Z2 Aerobic": (1.05, 1.15),    # 5-15% slower
            "Z3 Tempo": (0.95, 1.05),      # Within 5%
            "Z4 Threshold": (0.88, 0.95),  # 5-12% faster
            "Z5 Interval": (0.75, 0.88),   # 12-25% faster
            "Z6 Repetition": (0.0, 0.75),  # >25% faster
        }
    
    pace = df["pace"].fillna(threshold_pace * 2)  # NaN = very slow
    results = {}
    
    for zone_name, (low_pct, high_pct) in zones.items():
        low_pace = threshold_pace * low_pct
        high_pace = threshold_pace * high_pct
        
        # For pace: lower value = faster
        mask = (pace >= low_pace) & (pace < high_pace)
        seconds_in_zone = mask.sum()
        results[zone_name] = int(seconds_in_zone)
    
    return results


DEFAULT_PDC_DURATIONS = [60, 120, 180, 300, 600, 1200, 1800, 3600, 7200]


def calculate_pace_duration_curve(
    df_pl: Union[pd.DataFrame, Any], 
    durations: list = None
) -> dict:
    """
    Calculate Pace Duration Curve (best pace for each duration).
    
    Similar to Power Duration Curve but for pace.
    Returns the BEST (lowest) pace achieved for each duration.
    
    Args:
        df_pl: DataFrame with 'pace' column (sec/km)
        durations: List of durations in seconds
        
    Returns:
        Dict mapping duration (seconds) to best pace (sec/km)
    """
    df = ensure_pandas(df_pl)
    
    if "pace" not in df.columns:
        return {}
    
    if durations is None:
        durations = DEFAULT_PDC_DURATIONS
    
    pace = df["pace"].fillna(method='ffill').fillna(method='bfill').values
    n = len(pace)
    
    results = {}
    for duration in durations:
        if n < duration:
            results[duration] = None
            continue
        
        # Rolling mean for this duration
        rolling = pd.Series(pace).rolling(window=duration, min_periods=duration).mean()
        # Best pace = minimum (lower = faster)
        best_pace = rolling.min()
        
        if pd.notna(best_pace):
            results[duration] = float(best_pace)
        else:
            results[duration] = None
    
    return results


def classify_running_phenotype(pdc: dict, weight: float) -> str:
    """
    Classify runner phenotype based on Pace Duration Curve.
    
    Phenotypes:
    - sprinter: Strong short distances (400m-1km)
    - middle_distance: Strong 5K-10K
    - marathoner: Strong half to full marathon
    - ultra_runner: Strong ultra distances
    - all_rounder: Balanced profile
    
    Args:
        pdc: Pace Duration Curve (duration sec -> pace sec/km)
        weight: Runner weight in kg
        
    Returns:
        Phenotype string identifier
    """
    if not pdc or weight <= 0:
        return "unknown"
    
    # Get key pace values
    p1k = pdc.get(60)      # 1 km
    p5k = pdc.get(300)     # 5 km
    p10k = pdc.get(600)    # 10 km
    p21k = pdc.get(1200)   # Half marathon pace (if available)
    p42k = pdc.get(3600)   # Marathon pace
    
    if not any([p1k, p5k, p10k]):
        return "unknown"
    
    # Need at least 5K and 10K data for classification
    if p5k is None or p10k is None:
        return "unknown"
    
    # Calculate pace drop from 5K to 10K
    # Marathoners maintain pace better (smaller drop)
    pace_drop_5k_10k = (p10k - p5k) / p5k if p5k > 0 else 0
    
    # Calculate pace drop from 1K to 5K (if available)
    pace_drop_1k_5k = None
    if p1k:
        pace_drop_1k_5k = (p5k - p1k) / p1k if p1k > 0 else 0
    
    # Phenotype scoring
    scores = {
        "sprinter": 0,
        "middle_distance": 0,
        "marathoner": 0,
        "ultra_runner": 0,
        "all_rounder": 0
    }
    
    # Sprinter: High drop from 1K to 5K (fast short, slow long)
    if pace_drop_1k_5k and pace_drop_1k_5k > 0.15:
        scores["sprinter"] += 2
    
    # Marathoner: Small drop from 5K to 10K, has marathon data
    if pace_drop_5k_10k < 0.05:
        scores["marathoner"] += 2
    if p42k:
        scores["marathoner"] += 1
    
    # Ultra runner: Has half marathon and marathon data, very small drop
    if p21k and p42k:
        pace_drop_21k_42k = (p42k - p21k) / p21k if p21k > 0 else 1
        if pace_drop_21k_42k < 0.10:
            scores["ultra_runner"] += 2
    
    # Middle distance: Balanced 5K-10K, moderate drop
    if 0.03 <= pace_drop_5k_10k <= 0.08:
        scores["middle_distance"] += 2
    
    # All-rounder: Has data across all distances, balanced
    available_distances = sum(1 for p in [p1k, p5k, p10k, p21k, p42k] if p is not None)
    if available_distances >= 3 and max(scores.values()) <= 2:
        scores["all_rounder"] += 2
    
    # Find highest scoring phenotype
    phenotype = max(scores, key=scores.get)
    
    if scores[phenotype] == 0:
        return "unknown"
    
    return phenotype


def get_phenotype_description(phenotype: str) -> tuple:
    """
    Get phenotype emoji, name, and description.
    
    Args:
        phenotype: Phenotype identifier
        
    Returns:
        Tuple of (emoji, name, description)
    """
    phenotypes = {
        "sprinter": (
            "⚡",
            "Sprinter",
            "Mocny w krótkich dystansach (400m-1km). Wysoka prędkość maksymalna."
        ),
        "middle_distance": (
            "🏃",
            "Średnie dystanse",
            "Specjalista 5K-10K. Dobre połączenie szybkości i wytrzymałości."
        ),
        "marathoner": (
            "🏃‍♂️",
            "Maratończyk",
            "Specjalista maratonu. Doskonała wytrzymałość i ekonomia biegu."
        ),
        "ultra_runner": (
            "🦶",
            "Ultra-biegacz",
            "Specjalista ultra. Niesamowita wytrzymałość i odporność."
        ),
        "all_rounder": (
            "🔄",
            "Wszechstronny",
            "Zbalansowany profil. Dobry na różnych dystansach."
        ),
        "unknown": (
            "❓",
            "Nieznany",
            "Za mało danych do klasyfikacji."
        )
    }
    
    return phenotypes.get(phenotype, phenotypes["unknown"])


def estimate_vo2max_from_pace(vvo2max_pace: float, weight: float) -> float:
    """
    Estimate VO2max from velocity at VO2max pace.
    
    Uses Jack Daniels approximation:
    VO2max ≈ (vVO2max_speed / 1000 * 60) * C + 7
    where C is the oxygen cost of running (~3.5 ml/kg/min per min/km)
    
    Args:
        vvo2max_pace: Pace at vVO2max in sec/km (typically 6-min race pace)
        weight: Runner weight in kg (for validation)
        
    Returns:
        Estimated VO2max in ml/kg/min
    """
    if vvo2max_pace <= 0 or weight <= 0:
        return 0.0
    
    # Convert pace to speed (m/min)
    speed_m_per_min = 1000.0 / vvo2max_pace * 60
    
    # Daniels formula: VO2 = -4.60 + 0.182258 * v + 0.000104 * v^2
    # where v is speed in meters/min
    v = speed_m_per_min
    vo2 = -4.60 + 0.182258 * v + 0.000104 * v * v
    
    # Clamp to reasonable range
    vo2 = max(20, min(90, vo2))
    
    return round(vo2, 1)


def calculate_fatigue_resistance_index_pace(
    pdc: Dict[int, float]
) -> float:
    """
    Calculate Fatigue Resistance Index for pace.
    
    FRI = pace_10k / pace_5k
    Lower is better (closer to 1.0 = better endurance)
    
    Args:
        pdc: Pace Duration Curve
        
    Returns:
        FRI ratio (typically 1.02-1.15)
    """
    p5k = pdc.get(300)   # 5K pace
    p10k = pdc.get(600)  # 10K pace
    
    if p5k is None or p10k is None or p5k <= 0:
        return 0.0
    
    return p10k / p5k


def get_fri_interpretation_pace(fri: float) -> str:
    """
    Get human-readable interpretation of FRI for pace.
    
    Args:
        fri: Fatigue Resistance Index
        
    Returns:
        Polish interpretation string
    """
    if fri <= 1.02:
        return "🟢 Wyjątkowa wytrzymałość"
    elif fri <= 1.05:
        return "🟢 Bardzo dobra wytrzymałość"
    elif fri <= 1.08:
        return "🟡 Dobra wytrzymałość"
    elif fri <= 1.12:
        return "🟠 Przeciętna"
    else:
        return "🔴 Niska wytrzymałość"
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/calculations/test_pace.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add modules/calculations/pace.py tests/calculations/test_pace.py
git commit -m "feat(pace): add main pace module with zones and PDC

- calculate_pace_zones_time with 6 zones based on threshold
- calculate_pace_duration_curve for best pace per duration
- classify_running_phenotype (sprinter/marathoner/ultra/all-rounder)
- estimate_vo2max_from_pace using Daniels formula"
```

---

## Phase 3: D' Model (Anaerobic Distance Capacity)

### Task 3.1: Create D' Balance Module

**Files:**
- Create: `modules/calculations/d_prime.py`
- Create: `tests/calculations/test_d_prime.py`

**Context:** D' (pronounced "D prime") is the running equivalent of W' in cycling. It's the finite anaerobic distance capacity that can be spent above Critical Speed (CS).

**Step 1: Write the failing test**

Create: `tests/calculations/test_d_prime.py`

```python
import pytest
import numpy as np
from modules.calculations.d_prime import (
    calculate_d_prime_balance,
    estimate_time_to_exhaustion_pace,
    count_surges
)

def test_calculate_d_prime_balance():
    """Test D' balance calculation."""
    # 10 minutes of running
    time = np.arange(0, 600, 1)  # 0 to 599 seconds
    
    # Constant pace: 2 min above CS, 2 min below, repeat
    # CS = 300 sec/km (5:00 min/km)
    pace = np.concatenate([
        np.full(120, 240),  # 120s @ 4:00 (above CS = faster)
        np.full(120, 360),  # 120s @ 6:00 (below CS = recovery)
        np.full(120, 240),  # another surge
        np.full(240, 360),  # long recovery
    ])
    
    d_prime_balance = calculate_d_prime_balance(
        pace_sec_per_km=pace,
        time_sec=time,
        critical_speed_pace=300,  # 5:00 min/km
        d_prime_capacity=200  # 200m
    )
    
    # D' should decrease during fast sections
    assert d_prime_balance[0] == 200  # Start full
    assert d_prime_balance[60] < 200  # Depleted after 60s fast
    assert d_prime_balance[240] > d_prime_balance[120]  # Recovered

def test_estimate_time_to_exhaustion_pace():
    """Test TTE estimation from pace."""
    tte = estimate_time_to_exhaustion_pace(
        target_pace=240,  # 4:00 min/km
        critical_speed_pace=300,  # 5:00 min/km
        d_prime=200
    )
    
    # Should be able to hold 4:00 pace for limited time
    assert tte > 0
    assert tte < 600  # Less than 10 minutes
    
    # At CS, TTE should be infinite
    tte_at_cs = estimate_time_to_exhaustion_pace(
        target_pace=300,
        critical_speed_pace=300,
        d_prime=200
    )
    assert np.isinf(tte_at_cs)

def test_count_surges():
    """Test counting surges above threshold."""
    d_prime_balance = np.array([200, 180, 150, 120, 100, 80, 60, 100, 140, 180, 200, 160, 120])
    
    surges = count_surges(d_prime_balance, d_prime_capacity=200, threshold_pct=0.3)
    
    # Should detect 2 surges (drops below 30% = 60m, then recovery)
    assert surges >= 1
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/calculations/test_d_prime.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Implement D' balance module**

Create: `modules/calculations/d_prime.py`

```python
"""
SRP: D' (D-prime) anaerobic distance capacity module.

Running equivalent of W' in cycling.
D' is the finite distance that can be run above Critical Speed (CS).
"""

from typing import Union, Optional
import numpy as np
from .pace_utils import pace_to_speed, speed_to_pace


def calculate_d_prime_balance(
    pace_sec_per_km: np.ndarray,
    time_sec: np.ndarray,
    critical_speed_pace: float,
    d_prime_capacity: float,
    tau: float = 60.0
) -> np.ndarray:
    """
    Calculate D' balance over time.
    
    D' is depleted when running faster than Critical Speed (lower pace),
    and recharges when running slower.
    
    Args:
        pace_sec_per_km: Array of paces in sec/km
        time_sec: Array of time values in seconds
        critical_speed_pace: Critical Speed pace in sec/km
        d_prime_capacity: Total D' capacity in meters
        tau: Time constant for D' reconstitution (seconds, default 60s)
        
    Returns:
        Array of D' balance values (meters remaining)
    """
    n = len(pace_sec_per_km)
    if n == 0:
        return np.array([])
    
    # Convert paces to speeds
    speeds = pace_to_speed(pace_sec_per_km)  # m/s
    critical_speed = pace_to_speed(critical_speed_pace)  # m/s
    
    d_prime_balance = np.zeros(n)
    d_prime_balance[0] = d_prime_capacity
    
    for i in range(1, n):
        dt = time_sec[i] - time_sec[i-1]
        current_speed = speeds[i]
        
        if current_speed > critical_speed:
            # Above CS: deplete D' based on excess speed
            excess_speed = current_speed - critical_speed  # m/s
            depletion = excess_speed * dt  # meters
            d_prime_balance[i] = max(0, d_prime_balance[i-1] - depletion)
        else:
            # Below CS: recharge D'
            # Exponential recovery model
            recharge_rate = (d_prime_capacity - d_prime_balance[i-1]) / tau
            recharge = recharge_rate * dt
            d_prime_balance[i] = min(d_prime_capacity, d_prime_balance[i-1] + recharge)
    
    return d_prime_balance


def estimate_time_to_exhaustion_pace(
    target_pace: float,
    critical_speed_pace: float,
    d_prime: float
) -> float:
    """
    Estimate Time to Exhaustion (TTE) at given pace.
    
    Based on Critical Speed model: TTE = D' / (v - CS)
    where v is target speed, CS is critical speed.
    
    Args:
        target_pace: Target pace in sec/km
        critical_speed_pace: Critical Speed pace in sec/km
        d_prime: D' capacity in meters
        
    Returns:
        Time to exhaustion in seconds (inf if target <= CS)
        
    Example:
        >>> estimate_time_to_exhaustion_pace(240, 300, 200)  # 4:00 vs 5:00
        120.0  # ~2 minutes
    """
    if target_pace <= 0:
        raise ValueError(f"target_pace must be positive, got {target_pace}")
    if critical_speed_pace < 0:
        raise ValueError(f"critical_speed_pace cannot be negative, got {critical_speed_pace}")
    if d_prime < 0:
        raise ValueError(f"d_prime cannot be negative, got {d_prime}")
    
    # Convert to speeds
    target_speed = pace_to_speed(target_pace)
    critical_speed = pace_to_speed(critical_speed_pace)
    
    if target_speed <= critical_speed:
        return float("inf")
    
    if d_prime <= 0:
        return 0.0
    
    excess_speed = target_speed - critical_speed
    return d_prime / excess_speed


def count_surges(
    d_prime_balance: np.ndarray,
    d_prime_capacity: float,
    threshold_pct: float = 0.3,
    recovery_pct: float = 0.8
) -> int:
    """
    Count number of surges (significant D' depletions).
    
    A surge is counted when D' drops below threshold.
    
    Args:
        d_prime_balance: D' balance array (meters remaining)
        d_prime_capacity: Full D' capacity (meters)
        threshold_pct: Threshold as fraction of D' (default 30%)
        recovery_pct: Recovery threshold to count next surge (default 80%)
        
    Returns:
        Number of surges
    """
    if d_prime_balance is None or len(d_prime_balance) == 0 or d_prime_capacity <= 0:
        return 0
    
    threshold = d_prime_capacity * threshold_pct
    recovery = d_prime_capacity * recovery_pct
    
    surges = 0
    below_threshold = False
    
    for val in d_prime_balance:
        if val < threshold and not below_threshold:
            # Just dropped below threshold
            surges += 1
            below_threshold = True
        elif val >= recovery:
            # Recovered enough to count next drop as new surge
            below_threshold = False
    
    return surges


def calculate_d_prime_utilization(
    d_prime_balance: np.ndarray,
    d_prime_capacity: float
) -> dict:
    """
    Calculate D' utilization statistics.
    
    Args:
        d_prime_balance: D' balance array
        d_prime_capacity: Full capacity
        
    Returns:
        Dict with utilization stats
    """
    if len(d_prime_balance) == 0:
        return {}
    
    min_balance = np.min(d_prime_balance)
    max_depletion = d_prime_capacity - min_balance
    utilization_pct = (max_depletion / d_prime_capacity) * 100
    
    # Time below various thresholds
    time_below_50 = np.sum(d_prime_balance < d_prime_capacity * 0.5)
    time_below_25 = np.sum(d_prime_balance < d_prime_capacity * 0.25)
    
    return {
        "min_balance_m": round(min_balance, 1),
        "max_depletion_m": round(max_depletion, 1),
        "utilization_pct": round(utilization_pct, 1),
        "time_below_50pct_sec": int(time_below_50),
        "time_below_25pct_sec": int(time_below_25),
    }
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/calculations/test_d_prime.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add modules/calculations/d_prime.py tests/calculations/test_d_prime.py
git commit -m "feat(d-prime): add anaerobic distance capacity module

- calculate_d_prime_balance with depletion/recharge model
- estimate_time_to_exhaustion_pace using CS model
- count_surges for high-intensity efforts tracking
- calculate_d_prime_utilization statistics"
```

---

## Phase 4: Running Dynamics

### Task 4.1: Create Running Dynamics Module

**Files:**
- Create: `modules/calculations/running_dynamics.py`
- Create: `tests/calculations/test_running_dynamics.py`

**Context:** Running dynamics from Garmin (or Stryd) include cadence (SPM), ground contact time (GCT), vertical oscillation, stride length. These are crucial for form analysis.

**Step 1: Write the failing test**

Create: `tests/calculations/test_running_dynamics.py`

```python
import pytest
import numpy as np
import pandas as pd
from modules.calculations.running_dynamics import (
    calculate_cadence_stats,
    calculate_gct_stats,
    calculate_stride_metrics,
    analyze_cadence_drift,
    calculate_running_effectiveness
)

def test_calculate_cadence_stats():
    """Test cadence statistics calculation."""
    cadence = np.array([170, 172, 168, 175, 180, 178, 174, 170])
    
    stats = calculate_cadence_stats(cadence)
    
    assert stats["mean_spm"] == pytest.approx(173.375, rel=0.01)
    assert stats["std_spm"] > 0
    assert "zone" in stats

def test_calculate_gct_stats():
    """Test ground contact time statistics."""
    gct = np.array([240, 245, 238, 250, 255, 248, 242, 240])  # milliseconds
    
    stats = calculate_gct_stats(gct)
    
    assert stats["mean_ms"] == pytest.approx(244.75, rel=0.01)
    assert "asymmetry_flag" in stats

def test_calculate_stride_metrics():
    """Test stride length and related metrics."""
    df = pd.DataFrame({
        'cadence': [170, 172, 168],  # SPM
        'pace': [300, 300, 300],     # 5:00 min/km = 3.33 m/s
    })
    
    metrics = calculate_stride_metrics(df, runner_height=175)
    
    assert "stride_length_m" in metrics
    assert metrics["stride_length_m"] > 0
    assert "height_ratio" in metrics  # stride length / height

def test_analyze_cadence_drift():
    """Test cadence drift detection."""
    # Simulate cadence drop in second half
    cadence = np.concatenate([
        np.full(300, 175),  # First half: 175 SPM
        np.full(300, 168),  # Second half: 168 SPM
    ])
    
    drift = analyze_cadence_drift(cadence)
    
    assert drift["drift_spm"] < 0  # Negative = drop
    assert abs(drift["drift_spm"]) == pytest.approx(7.0, rel=0.1)

def test_calculate_running_effectiveness():
    """Test running effectiveness calculation."""
    # Running power from Stryd/Garmin
    re = calculate_running_effectiveness(
        pace_sec_per_km=300,  # 5:00 min/km
        running_power=250,     # Watts
        weight_kg=70
    )
    
    # RE is typically 0.9-1.1 for good runners
    assert 0.5 < re < 1.5
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/calculations/test_running_dynamics.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Implement running dynamics module**

Create: `modules/calculations/running_dynamics.py`

```python
"""
Running Dynamics Analysis Module.

Analyzes biomechanical metrics from Garmin/Stryd:
- Cadence (SPM - steps per minute)
- Ground Contact Time (GCT)
- Vertical Oscillation
- Stride Length
- Running Effectiveness
"""

from typing import Dict, Optional, Union, Any
import numpy as np
import pandas as pd
from .pace_utils import pace_to_speed


def calculate_cadence_stats(cadence_spm: np.ndarray) -> Dict:
    """
    Calculate cadence statistics.
    
    Args:
        cadence_spm: Array of cadence values in steps per minute
        
    Returns:
        Dict with cadence statistics
    """
    valid_cadence = cadence_spm[(cadence_spm > 50) & (cadence_spm < 300)]
    
    if len(valid_cadence) == 0:
        return {
            "mean_spm": 0.0,
            "std_spm": 0.0,
            "min_spm": 0.0,
            "max_spm": 0.0,
            "zone": "unknown"
        }
    
    mean_spm = float(np.mean(valid_cadence))
    std_spm = float(np.std(valid_cadence))
    
    # Cadence zones
    if mean_spm < 160:
        zone = "low"
    elif mean_spm < 170:
        zone = "low-moderate"
    elif mean_spm < 180:
        zone = "optimal"
    elif mean_spm < 190:
        zone = "high"
    else:
        zone = "very-high"
    
    return {
        "mean_spm": round(mean_spm, 1),
        "std_spm": round(std_spm, 1),
        "min_spm": int(np.min(valid_cadence)),
        "max_spm": int(np.max(valid_cadence)),
        "zone": zone,
        "coefficient_of_variation": round(std_spm / mean_spm * 100, 1) if mean_spm > 0 else 0
    }


def calculate_gct_stats(gct_ms: np.ndarray) -> Dict:
    """
    Calculate Ground Contact Time statistics.
    
    Args:
        gct_ms: Array of GCT values in milliseconds
        
    Returns:
        Dict with GCT statistics
    """
    valid_gct = gct_ms[(gct_ms > 100) & (gct_ms < 400)]
    
    if len(valid_gct) == 0:
        return {
            "mean_ms": 0.0,
            "std_ms": 0.0,
            "classification": "unknown"
        }
    
    mean_ms = float(np.mean(valid_gct))
    
    # GCT classification
    if mean_ms < 200:
        classification = "excellent"
    elif mean_ms < 220:
        classification = "good"
    elif mean_ms < 240:
        classification = "average"
    else:
        classification = "needs-improvement"
    
    return {
        "mean_ms": round(mean_ms, 1),
        "std_ms": round(float(np.std(valid_gct)), 1),
        "min_ms": int(np.min(valid_gct)),
        "max_ms": int(np.max(valid_gct)),
        "classification": classification
    }


def calculate_stride_metrics(
    df_pl: Union[pd.DataFrame, Any],
    runner_height: float
) -> Dict:
    """
    Calculate stride length and related metrics.
    
    Args:
        df_pl: DataFrame with 'cadence' and 'pace' columns
        runner_height: Runner height in cm
        
    Returns:
        Dict with stride metrics
    """
    df = df_pl if isinstance(df_pl, pd.DataFrame) else df_pl.to_pandas()
    
    if "cadence" not in df.columns or "pace" not in df.columns:
        return {}
    
    # Filter valid data
    valid = df[(df["cadence"] > 50) & (df["cadence"] < 300) & (df["pace"] > 0)]
    
    if len(valid) == 0:
        return {}
    
    # Calculate stride length
    # Stride length = speed / (cadence / 60) * 2
    # (multiply by 2 because cadence is steps per minute, stride is per 2 steps)
    speed_m_s = pace_to_speed(valid["pace"].values)
    cadence_spm = valid["cadence"].values
    
    stride_length_m = speed_m_s / (cadence_spm / 60) * 2
    
    mean_stride = float(np.mean(stride_length_m))
    height_m = runner_height / 100
    
    return {
        "stride_length_m": round(mean_stride, 3),
        "stride_length_std_m": round(float(np.std(stride_length_m)), 3),
        "height_ratio": round(mean_stride / height_m, 2),
        "samples": len(valid)
    }


def analyze_cadence_drift(
    cadence_spm: np.ndarray,
    min_samples: int = 100
) -> Dict:
    """
    Analyze cadence drift over workout.
    
    Cadence drift (drop) indicates fatigue.
    
    Args:
        cadence_spm: Cadence array
        min_samples: Minimum samples required
        
    Returns:
        Dict with drift analysis
    """
    valid = cadence_spm[(cadence_spm > 50) & (cadence_spm < 300)]
    
    if len(valid) < min_samples:
        return {"drift_spm": 0.0, "drift_pct": 0.0, "classification": "insufficient-data"}
    
    mid = len(valid) // 2
    first_half = valid[:mid]
    second_half = valid[mid:]
    
    mean_first = float(np.mean(first_half))
    mean_second = float(np.mean(second_half))
    
    drift_spm = mean_second - mean_first
    drift_pct = (drift_spm / mean_first) * 100 if mean_first > 0 else 0
    
    # Classification
    if drift_pct < -5:
        classification = "significant-drop"
    elif drift_pct < -2:
        classification = "moderate-drop"
    elif drift_pct < 2:
        classification = "stable"
    else:
        classification = "increased"
    
    return {
        "drift_spm": round(drift_spm, 1),
        "drift_pct": round(drift_pct, 1),
        "mean_first_half": round(mean_first, 1),
        "mean_second_half": round(mean_second, 1),
        "classification": classification
    }


def calculate_running_effectiveness(
    pace_sec_per_km: float,
    running_power: float,
    weight_kg: float
) -> float:
    """
    Calculate Running Effectiveness (RE).
    
    RE = Speed (m/s) / Power (W/kg)
    
    Higher is better. Elite runners typically 0.98-1.05.
    
    Args:
        pace_sec_per_km: Pace in sec/km
        running_power: Running power in Watts
        weight_kg: Runner weight in kg
        
    Returns:
        Running Effectiveness ratio
    """
    if pace_sec_per_km <= 0 or running_power <= 0 or weight_kg <= 0:
        return 0.0
    
    speed = pace_to_speed(pace_sec_per_km)  # m/s
    power_per_kg = running_power / weight_kg  # W/kg
    
    return speed / power_per_kg


def analyze_vertical_oscillation(
    vo_cm: np.ndarray,
    stride_length_m: Optional[np.ndarray] = None
) -> Dict:
    """
    Analyze vertical oscillation.
    
    Args:
        vo_cm: Vertical oscillation in centimeters
        stride_length_m: Optional stride length for ratio calculation
        
    Returns:
        Dict with VO analysis
    """
    valid_vo = vo_cm[(vo_cm > 2) & (vo_cm < 15)]
    
    if len(valid_vo) == 0:
        return {}
    
    mean_vo = float(np.mean(valid_vo))
    
    # VO classification
    if mean_vo < 6:
        classification = "low-efficient"
    elif mean_vo < 8:
        classification = "optimal"
    elif mean_vo < 10:
        classification = "moderate"
    else:
        classification = "high-inefficient"
    
    result = {
        "mean_cm": round(mean_vo, 1),
        "std_cm": round(float(np.std(valid_vo)), 1),
        "classification": classification
    }
    
    # Vertical ratio if stride length available
    if stride_length_m is not None and len(stride_length_m) == len(valid_vo):
        vo_ratio = (mean_vo / 100) / np.mean(stride_length_m) * 100  # as percentage
        result["vertical_ratio_pct"] = round(vo_ratio, 1)
    
    return result


def get_optimal_cadence_range(height_cm: float) -> tuple:
    """
    Get optimal cadence range based on runner height.
    
    Uses heuristic: 180 SPM is good for average height (175cm),
    ±5 SPM per 10cm deviation.
    
    Args:
        height_cm: Runner height in cm
        
    Returns:
        Tuple of (min_spm, max_spm)
    """
    base = 175  # Reference height
    deviation = (height_cm - base) / 10
    
    optimal = 180 + (deviation * -3)  # Taller = slightly lower cadence
    
    return (int(optimal - 5), int(optimal + 5))
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/calculations/test_running_dynamics.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add modules/calculations/running_dynamics.py tests/calculations/test_running_dynamics.py
git commit -m "feat(running-dynamics): add biomechanical analysis module

- calculate_cadence_stats with zones (low/optimal/high)
- calculate_gct_stats with classification
- calculate_stride_metrics with height ratio
- analyze_cadence_drift for fatigue detection
- calculate_running_effectiveness (RE)
- analyze_vertical_oscillation"
```

---

## Phase 5: Grade-Adjusted Pace (GAP)

### Task 5.1: Create GAP Module

**Files:**
- Create: `modules/calculations/gap.py`
- Create: `tests/calculations/test_gap.py`

**Context:** GAP adjusts pace for elevation changes. Running uphill at 5:00 min/km is harder than flat 5:00 min/km. GAP calculates equivalent flat pace.

**Step 1: Write the failing test**

Create: `tests/calculations/test_gap.py`

```python
import pytest
import numpy as np
from modules.calculations.gap import (
    calculate_gap,
    calculate_grade,
    pace_to_gap_factor
)

def test_calculate_grade():
    """Test grade calculation from elevation and distance."""
    # 10m climb over 1000m = 1% grade
    grade = calculate_grade(elevation_change_m=10, distance_m=1000)
    assert grade == pytest.approx(1.0, rel=0.01)
    
    # 50m climb over 1000m = 5% grade
    grade = calculate_grade(elevation_change_m=50, distance_m=1000)
    assert grade == pytest.approx(5.0, rel=0.01)

def test_pace_to_gap_factor():
    """Test GAP factor calculation."""
    # Uphill increases effective pace (makes it slower)
    factor_uphill = pace_to_gap_factor(grade=5.0)
    assert factor_uphill > 1.0
    
    # Downhill decreases effective pace (makes it faster)
    factor_downhill = pace_to_gap_factor(grade=-5.0)
    assert factor_downhill < 1.0
    
    # Flat = no change
    factor_flat = pace_to_gap_factor(grade=0.0)
    assert factor_flat == pytest.approx(1.0, rel=0.01)

def test_calculate_gap():
    """Test GAP calculation."""
    # Running 5:00 min/km (300s) on 5% uphill
    gap = calculate_gap(pace_sec_per_km=300, grade=5.0)
    
    # GAP should be faster than actual pace (flat equivalent)
    assert gap < 300
    
    # Running 5:00 min/km on flat
    gap_flat = calculate_gap(pace_sec_per_km=300, grade=0.0)
    assert gap_flat == pytest.approx(300, rel=0.1)

def test_gap_with_array():
    """Test GAP with arrays."""
    paces = np.array([300, 300, 300])  # 5:00 min/km
    grades = np.array([0, 5, -3])  # flat, uphill, downhill
    
    gaps = calculate_gap(paces, grades)
    
    # Uphill = faster equivalent
    assert gaps[1] < gaps[0]
    # Downhill = slower equivalent (downhill assist)
    assert gaps[2] > gaps[0]
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/calculations/test_gap.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Implement GAP module**

Create: `modules/calculations/gap.py`

```python
"""
Grade-Adjusted Pace (GAP) Module.

Adjusts pace for elevation changes to provide equivalent flat pace.
Based on research by Alberto Minetti and running power models.
"""

from typing import Union
import numpy as np


def calculate_grade(elevation_change_m: float, distance_m: float) -> float:
    """
    Calculate grade percentage.
    
    Args:
        elevation_change_m: Elevation change in meters
        distance_m: Horizontal distance in meters
        
    Returns:
        Grade as percentage (e.g., 5.0 for 5%)
    """
    if distance_m <= 0:
        return 0.0
    return (elevation_change_m / distance_m) * 100


def pace_to_gap_factor(grade: float) -> float:
    """
    Calculate GAP adjustment factor for given grade.
    
    Based on metabolic cost curves:
    - Uphill: significantly harder (factor > 1)
    - Downhill: easier but limited benefit (factor < 1, asymptotic)
    
    Args:
        grade: Grade percentage (positive = uphill, negative = downhill)
        
    Returns:
        Adjustment factor (multiply actual pace by this to get GAP)
        
    Example:
        >>> pace_to_gap_factor(5.0)  # 5% uphill
        0.85  # Actual 5:00 = GAP 4:15 (faster)
    """
    if grade >= 0:
        # Uphill: polynomial approximation of metabolic cost
        # Factors from Minetti et al. research
        factor = 1 - (0.03 * grade) + (0.0005 * grade**2)
    else:
        # Downhill: diminishing returns below -10%
        abs_grade = abs(grade)
        if abs_grade <= 10:
            factor = 1 + (0.018 * abs_grade) - (0.0004 * abs_grade**2)
        else:
            # Beyond -10%, extra downhill doesn't help much
            factor = 1 + (0.018 * 10) - (0.0004 * 100) + 0.001 * (abs_grade - 10)
    
    # Clamp to reasonable bounds
    return max(0.7, min(1.3, factor))


def calculate_gap(
    pace_sec_per_km: Union[float, np.ndarray],
    grade: Union[float, np.ndarray]
) -> Union[float, np.ndarray]:
    """
    Calculate Grade-Adjusted Pace.
    
    GAP shows what the pace would be on flat ground equivalent.
    Lower GAP = better performance (faster equivalent).
    
    Args:
        pace_sec_per_km: Actual pace in sec/km (scalar or array)
        grade: Grade percentage (scalar or array)
        
    Returns:
        GAP in sec/km
        
    Example:
        >>> calculate_gap(300, 5.0)  # 5:00 on 5% uphill
        255.0  # Equivalent to 4:15 on flat
    """
    factor = pace_to_gap_factor(grade)
    return pace_sec_per_km * factor


def calculate_gap_from_elevation(
    pace_sec_per_km: np.ndarray,
    elevation_m: np.ndarray,
    time_sec: np.ndarray
) -> np.ndarray:
    """
    Calculate GAP from elevation profile.
    
    Args:
        pace_sec_per_km: Pace array
        elevation_m: Elevation array
        time_sec: Time array
        
    Returns:
        GAP array
    """
    if len(pace_sec_per_km) < 2 or len(elevation_m) < 2:
        return pace_sec_per_km
    
    gaps = np.zeros_like(pace_sec_per_km)
    
    for i in range(len(pace_sec_per_km)):
        if i == 0:
            grade = 0.0
        else:
            # Calculate grade over last ~10 seconds
            lookback = min(10, i)
            ele_change = elevation_m[i] - elevation_m[i - lookback]
            
            # Distance covered
            pace = pace_sec_per_km[i]  # sec/km
            if pace > 0:
                speed = 1000 / pace  # m/s
                time = lookback  # seconds
                distance = speed * time
                grade = calculate_grade(ele_change, distance) if distance > 0 else 0
            else:
                grade = 0
        
        gaps[i] = calculate_gap(pace_sec_per_km[i], grade)
    
    return gaps


def calculate_hill_score(
    elevation_gain_m: float,
    distance_km: float,
    threshold_pace: float
) -> float:
    """
    Calculate hill score for a run.
    
    Combines elevation gain and distance into a difficulty score.
    
    Args:
        elevation_gain_m: Total elevation gain
        distance_km: Distance in km
        threshold_pace: Threshold pace in sec/km
        
    Returns:
        Hill score (0-100+)
    """
    if distance_km <= 0:
        return 0.0
    
    # Elevation gain per km
    elevation_per_km = elevation_gain_m / distance_km
    
    # Normalize: 50m/km = moderate, 100m/km = hard
    score = (elevation_per_km / 50) * 50
    
    return min(100, score)


def get_gap_interpretation(gap_difference: float) -> str:
    """
    Get interpretation of GAP vs actual pace difference.
    
    Args:
        gap_difference: GAP - actual pace (negative = performed better than pace suggests)
        
    Returns:
        Interpretation string
    """
    if gap_difference < -30:
        return "🔥 Wyjątkowa praca na podbiegach"
    elif gap_difference < -15:
        return "⚡ Dobra praca na podbiegach"
    elif gap_difference < 15:
        return "🟢 Płaski teren lub zbalansowane"
    else:
        return "🟡 Więcej zjazdów (korzystał z grawitacji)"
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/calculations/test_gap.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add modules/calculations/gap.py tests/calculations/test_gap.py
git commit -m "feat(gap): add Grade-Adjusted Pace module

- calculate_grade from elevation and distance
- pace_to_gap_factor using metabolic cost curves
- calculate_gap for equivalent flat pace
- calculate_hill_score for run difficulty
- get_gap_interpretation for performance context"
```

---

## Phase 6: Race Predictor

### Task 6.1: Create Race Predictor Module

**Files:**
- Create: `modules/calculations/race_predictor.py`
- Create: `tests/calculations/test_race_predictor.py`

**Context:** Race predictor estimates finish times for various distances based on a known performance. Uses Riegel formula and VO2max models.

**Step 1: Write the failing test**

Create: `tests/calculations/test_race_predictor.py`

```python
import pytest
from modules.calculations.race_predictor import (
    riegel_predict,
    predict_race_times,
    get_recommended_distances
)

def test_riegel_predict():
    """Test Riegel formula prediction."""
    # Predict 10K from 5K time
    # 5K in 25:00 (1500s)
    predicted_10k = riegel_predict(
        t1=1500,  # 25:00
        d1=5,     # 5 km
        d2=10     # 10 km
    )
    
    # 10K should be slower than double 5K (fatigue factor)
    # Expected around 51-52 minutes
    assert predicted_10k > 3000  # > 50 min
    assert predicted_10k < 3300  # < 55 min

def test_predict_race_times():
    """Test predicting multiple race times."""
    predictions = predict_race_times(
        known_distance_km=5,
        known_time_sec=1500,  # 25:00 5K
        vo2max=50
    )
    
    assert "5K" in predictions
    assert "10K" in predictions
    assert "Half Marathon" in predictions
    assert "Marathon" in predictions
    
    # Times should increase with distance
    assert predictions["10K"] > predictions["5K"]
    assert predictions["Half Marathon"] > predictions["10K"]
    assert predictions["Marathon"] > predictions["Half Marathon"]

def test_get_recommended_distances():
    """Test getting recommended target distances."""
    recs = get_recommended_distances(current_max=10)  # 10K runner
    
    assert isinstance(recs, list)
    assert len(recs) > 0
    # Should recommend stepping up
    assert any("Half" in r for r in recs) or any("15K" in r for r in recs)
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/calculations/test_race_predictor.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Implement race predictor**

Create: `modules/calculations/race_predictor.py`

```python
"""
Race Predictor Module.

Predicts finish times for various race distances using:
- Riegel formula (power law)
- VO2max models
- Recent performance data
"""

from typing import Dict, Optional
import math


def riegel_predict(t1: float, d1: float, d2: float, exponent: float = 1.06) -> float:
    """
    Predict time for distance d2 based on performance at d1.
    
    Riegel formula: t2 = t1 * (d2/d1)^exponent
    
    Args:
        t1: Time for distance d1 (seconds)
        d1: Known distance (km)
        d2: Target distance (km)
        exponent: Fatigue factor (1.06 for running, 1.15 for ultra)
        
    Returns:
        Predicted time in seconds
        
    Example:
        >>> riegel_predict(1500, 5, 10)  # 25:00 5K to 10K
        3180  # ~53:00
    """
    if t1 <= 0 or d1 <= 0 or d2 <= 0:
        return 0.0
    
    # Adjust exponent for ultra distances
    if d2 > 42:
        exponent = 1.15
    elif d2 > 21:
        exponent = 1.08
    
    return t1 * math.pow(d2 / d1, exponent)


def format_time(seconds: float) -> str:
    """Format seconds as HH:MM:SS or MM:SS."""
    if seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours}:{minutes:02d}:{secs:02d}"


def predict_race_times(
    known_distance_km: float,
    known_time_sec: float,
    vo2max: Optional[float] = None
) -> Dict[str, float]:
    """
    Predict times for standard race distances.
    
    Args:
        known_distance_km: Distance of known performance
        known_time_sec: Time for known distance
        vo2max: Optional VO2max for second opinion
        
    Returns:
        Dict of race name -> predicted time (seconds)
    """
    distances = {
        "5K": 5,
        "10K": 10,
        "15K": 15,
        "10 Miles": 16.093,
        "Half Marathon": 21.097,
        "30K": 30,
        "Marathon": 42.195,
        "50K": 50,
        "50 Miles": 80.467,
    }
    
    predictions = {}
    
    for name, distance in distances.items():
        if distance == known_distance_km:
            predictions[name] = known_time_sec
        else:
            predictions[name] = riegel_predict(known_time_sec, known_distance_km, distance)
    
    return predictions


def predict_race_times_formatted(
    known_distance_km: float,
    known_time_sec: float
) -> Dict[str, str]:
    """
    Get formatted race time predictions.
    
    Args:
        known_distance_km: Known distance in km
        known_time_sec: Known time in seconds
        
    Returns:
        Dict of race name -> formatted time string
    """
    predictions = predict_race_times(known_distance_km, known_time_sec)
    return {name: format_time(t) for name, t in predictions.items()}


def estimate_equivalent_performances(pace_sec_per_km: float) -> Dict[str, float]:
    """
    Estimate equivalent race paces from current fitness.
    
    Args:
        pace_sec_per_km: Threshold or recent race pace
        
    Returns:
        Dict of race distance -> pace (sec/km)
    """
    # Assume this is threshold pace (~1 hour race pace)
    # Marathon ~15% slower, 5K ~10% faster
    
    return {
        "5K": pace_sec_per_km * 0.90,
        "10K": pace_sec_per_km * 0.95,
        "Half Marathon": pace_sec_per_km * 1.05,
        "Marathon": pace_sec_per_km * 1.15,
    }


def get_recommended_distances(current_max_km: float) -> list:
    """
    Get recommended next target distances.
    
    Args:
        current_max_km: Current longest race distance
        
    Returns:
        List of recommendations
    """
    if current_max_km < 5:
        return ["5K - build aerobic base", "8K - extend endurance"]
    elif current_max_km < 10:
        return ["10K - classic distance", "15K - bridge to half"]
    elif current_max_km < 21:
        return ["Half Marathon - major milestone", "25K - ultra prep"]
    elif current_max_km < 42:
        return ["Marathon - the ultimate challenge", "50K - first ultra"]
    else:
        return ["50 Miles - extend ultra range", "100K - ultra milestone"]


def calculate_performance_rating(
    distance_km: float,
    time_sec: float,
    age: int,
    is_male: bool
) -> float:
    """
    Calculate age-graded performance rating (0-100).
    
    Args:
        distance_km: Race distance
        time_sec: Finish time
        age: Runner age
        is_male: True for male, False for female
        
    Returns:
        Performance rating (world record = 100)
    """
    # Simplified age-grading (approximate)
    # World record paces (sec/km) - rough estimates
    wr_paces = {
        5: 160,   # ~13:20 5K
        10: 165,  # ~27:30 10K
        21.097: 175,  # ~59:00 half
        42.195: 180,  # ~2:01:00 marathon
    }
    
    # Find closest distance
    closest = min(wr_paces.keys(), key=lambda x: abs(x - distance_km))
    wr_pace = wr_paces[closest]
    
    # Calculate actual pace
    actual_pace = time_sec / distance_km
    
    # Basic rating
    rating = (wr_pace / actual_pace) * 100
    
    # Age adjustment (simplified)
    if age > 30:
        age_factor = 1 + (age - 30) * 0.005  # 0.5% per year after 30
        rating *= age_factor
    
    # Gender adjustment
    if not is_male:
        rating *= 1.11  # ~11% adjustment
    
    return min(100, round(rating, 1))
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/calculations/test_race_predictor.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add modules/calculations/race_predictor.py tests/calculations/test_race_predictor.py
git commit -m "feat(race-predictor): add race time prediction module

- riegel_predict using power law formula
- predict_race_times for standard distances (5K to ultra)
- estimate_equivalent_performances
- calculate_performance_rating (age-graded)"
```

---

## Phase 7: Session Type Detection

### Task 7.1: Add Progressive Run Detection

**Files:**
- Modify: `modules/domain/session_type.py`
- Create: `tests/domain/test_session_type_running.py`

**Context:** Running uses progressive runs (increasing pace each km) instead of ramp tests (increasing power). Need to detect progressive run patterns.

**Step 1: Write the failing test**

Create: `tests/domain/test_session_type_running.py`

```python
import pytest
import numpy as np
import pandas as pd
from modules.domain.session_type import (
    classify_progressive_run,
    classify_session_type
)

def test_classify_progressive_run():
    """Test progressive run detection."""
    # Simulate progressive run: pace decreases 15s/km each km
    # Starting at 6:00/km, ending at ~4:30/km
    pace = np.concatenate([
        np.full(600, 360),  # 10 min @ 6:00
        np.full(600, 345),  # 10 min @ 5:45
        np.full(600, 330),  # 10 min @ 5:30
        np.full(600, 315),  # 10 min @ 5:15
        np.full(600, 300),  # 10 min @ 5:00
        np.full(600, 285),  # 10 min @ 4:45
    ])
    
    result = classify_progressive_run(pd.Series(pace))
    
    assert result.is_progressive == True
    assert result.confidence > 0.5

def test_classify_session_type_with_pace():
    """Test session type classification with pace data."""
    # Create DataFrame with pace column
    df = pd.DataFrame({
        'pace': np.full(600, 300),  # 10 min @ constant 5:00
    })
    
    session_type = classify_session_type(df, filename="easy_run.csv")
    
    # Should be TRAINING since it's constant pace
    assert str(session_type) == "Training"
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/domain/test_session_type_running.py -v
```

Expected: FAIL with `AttributeError: module has no attribute 'classify_progressive_run'`

**Step 3: Add progressive run detection to session_type.py**

Modify: `modules/domain/session_type.py` (add after existing code)

```python
# Add to imports
def classify_progressive_run(
    pace: pd.Series,
    step_duration_range: tuple = (300, 900)  # 5-15 min per step
) -> 'ProgressiveClassificationResult':
    """
    Deterministic progressive run classifier.
    
    Progressive run: Pace gets faster (lower) at consistent intervals.
    
    Args:
        pace: Pace series in sec/km (assumed 1Hz sampling)
        step_duration_range: Expected step duration (min, max) in seconds
        
    Returns:
        ProgressiveClassificationResult
    """
    criteria_met = []
    criteria_failed = []
    
    MIN_DURATION_SEC = 600  # 10 minutes minimum
    if len(pace) < MIN_DURATION_SEC:
        return ProgressiveClassificationResult(
            is_progressive=False,
            confidence=0.0,
            reason=f"Za mało danych ({len(pace)}s < {MIN_DURATION_SEC}s minimum)",
            criteria_met=[],
            criteria_failed=["min_duration"]
        )
    
    # Clean data
    pace_clean = pace.dropna()
    if len(pace_clean) < MIN_DURATION_SEC:
        return ProgressiveClassificationResult(
            is_progressive=False,
            confidence=0.0,
            reason="Za dużo brakujących danych",
            criteria_met=[],
            criteria_failed=["valid_data"]
        )
    
    pace_arr = pace_clean.values
    
    # Detect pace steps
    steps = _detect_pace_steps(pace_arr, step_duration_range)
    
    if len(steps) < 2:
        return ProgressiveClassificationResult(
            is_progressive=False,
            confidence=0.0,
            reason=f"Wykryto tylko {len(steps)} segmentów (minimum 2)",
            criteria_met=[],
            criteria_failed=["min_steps"]
        )
    
    # Check if pace generally decreases (gets faster)
    step_paces = [s['mean_pace'] for s in steps]
    decreases = sum(1 for i in range(1, len(step_paces)) 
                   if step_paces[i] < step_paces[i-1])  # Lower pace = faster
    monotonicity_ratio = decreases / (len(step_paces) - 1)
    
    if monotonicity_ratio >= 0.7:
        criteria_met.append("pace_decreasing")
    else:
        criteria_failed.append("pace_decreasing")
    
    # Check consistent step duration
    step_durations = [s['duration'] for s in steps]
    duration_cv = np.std(step_durations) / np.mean(step_durations) if np.mean(step_durations) > 0 else 1
    
    if duration_cv < 0.5:
        criteria_met.append("consistent_duration")
    else:
        criteria_failed.append("consistent_duration")
    
    # Calculate confidence
    total_criteria = 2
    met_count = len(criteria_met)
    confidence = met_count / total_criteria
    
    is_progressive = met_count >= 2
    
    if is_progressive:
        reason = f"Progressive Run wykryty ({met_count}/{total_criteria} kryteriów)"
    else:
        reason = f"NIE jest Progressive Run. Niespełnione: {', '.join(criteria_failed)}"
    
    return ProgressiveClassificationResult(
        is_progressive=is_progressive,
        confidence=confidence,
        reason=reason,
        criteria_met=criteria_met,
        criteria_failed=criteria_failed
    )


@dataclass
class ProgressiveClassificationResult:
    """Result of progressive run classification."""
    is_progressive: bool
    confidence: float
    reason: str
    criteria_met: List[str]
    criteria_failed: List[str]


def _detect_pace_steps(pace_arr: np.ndarray, duration_range: tuple) -> List[dict]:
    """Detect distinct pace steps in the data."""
    min_dur, max_dur = duration_range
    window = min(60, len(pace_arr) // 10)
    if window < 10:
        window = 10
    
    # Smooth to find plateaus
    smoothed = pd.Series(pace_arr).rolling(window=window, center=True).mean().fillna(method='bfill').fillna(method='ffill').values
    
    # Detect changes using gradient
    gradient = np.gradient(smoothed)
    
    # Find step boundaries
    step_threshold = 2.0  # sec/km change threshold
    step_starts = [0]
    
    in_transition = False
    for i in range(1, len(gradient)):
        if abs(gradient[i]) > step_threshold and not in_transition:
            in_transition = True
        elif abs(gradient[i]) <= step_threshold and in_transition:
            in_transition = False
            if i - step_starts[-1] >= min_dur:
                step_starts.append(i)
    
    # Build step list
    steps = []
    for i in range(len(step_starts)):
        start = step_starts[i]
        end = step_starts[i + 1] if i + 1 < len(step_starts) else len(pace_arr)
        duration = end - start
        
        if duration >= min_dur:
            mean_pace = np.mean(pace_arr[start:end])
            steps.append({
                'start': start,
                'end': end,
                'mean_pace': mean_pace,
                'duration': duration
            })
    
    return steps
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/domain/test_session_type_running.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add modules/domain/session_type.py tests/domain/test_session_type_running.py
git commit -m "feat(session-type): add progressive run detection

- classify_progressive_run for pace-based test detection
- ProgressiveClassificationResult dataclass
- _detect_pace_steps algorithm
- Complements existing ramp test detection for cycling"
```

---

## Phase 8: UI Adaptation

### Task 8.1: Create Running UI Components

**Files:**
- Create: `modules/ui/running.py`
- Create: `tests/ui/test_running_ui.py`

**Context:** Need UI components specific to running: pace charts, GAP display, running dynamics visualizations.

**Step 1: Write the failing test**

Create: `tests/ui/test_running_ui.py`

```python
import pytest
import pandas as pd
from modules.ui.running import (
    format_pace_for_display,
    get_pace_zone_color,
    calculate_pace_summary_stats
)

def test_format_pace_for_display():
    """Test pace formatting for UI."""
    assert format_pace_for_display(300) == "5:00"
    assert format_pace_for_display(245.5) == "4:05"
    assert format_pace_for_display(0) == "--:--"

def test_get_pace_zone_color():
    """Test pace zone color mapping."""
    # Zone 1 (recovery) - slower than threshold
    color = get_pace_zone_color(pace=345, threshold_pace=300)
    assert color == "#3498db"  # Blue
    
    # Zone 4 (threshold)
    color = get_pace_zone_color(pace=285, threshold_pace=300)
    assert color == "#e74c3c"  # Red

def test_calculate_pace_summary_stats():
    """Test pace summary statistics."""
    df = pd.DataFrame({
        'pace': [300, 330, 285, 300, 315],
        'gap': [295, 325, 280, 295, 310]
    })
    
    stats = calculate_pace_summary_stats(df, threshold_pace=300)
    
    assert "avg_pace" in stats
    assert "avg_gap" in stats
    assert "time_in_zones" in stats
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/ui/test_running_ui.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Implement running UI module**

Create: `modules/ui/running.py`

```python
"""
Running-specific UI components.

Charts, metrics, and visualizations for running analysis.
"""

from typing import Dict, Optional
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go

from modules.calculations.pace_utils import format_pace
from modules.calculations.pace import calculate_pace_zones_time


def format_pace_for_display(pace_sec_per_km: float) -> str:
    """Format pace for UI display."""
    return format_pace(pace_sec_per_km)


def get_pace_zone_color(pace: float, threshold_pace: float) -> str:
    """
    Get color for pace zone.
    
    Args:
        pace: Current pace in sec/km
        threshold_pace: Threshold pace in sec/km
        
    Returns:
        Hex color code
    """
    ratio = pace / threshold_pace if threshold_pace > 0 else 1.0
    
    if ratio > 1.15:
        return "#3498db"  # Blue - Recovery
    elif ratio > 1.05:
        return "#2ecc71"  # Green - Aerobic
    elif ratio > 0.95:
        return "#f1c40f"  # Yellow - Tempo
    elif ratio > 0.88:
        return "#e67e22"  # Orange - Threshold
    else:
        return "#e74c3c"  # Red - Interval/Repetition


def calculate_pace_summary_stats(
    df: pd.DataFrame,
    threshold_pace: float
) -> Dict:
    """Calculate summary statistics for pace data."""
    stats = {}
    
    if "pace" in df.columns:
        paces = df["pace"].dropna()
        stats["avg_pace"] = float(paces.mean())
        stats["min_pace"] = float(paces.min())  # Fastest
        stats["max_pace"] = float(paces.max())  # Slowest
    
    if "gap" in df.columns:
        gaps = df["gap"].dropna()
        stats["avg_gap"] = float(gaps.mean())
    
    # Time in zones
    if "pace" in df.columns:
        stats["time_in_zones"] = calculate_pace_zones_time(df, threshold_pace)
    
    return stats


def render_pace_chart(df: pd.DataFrame, threshold_pace: float):
    """Render pace chart with zones."""
    if "pace" not in df.columns:
        st.warning("Brak danych tempa")
        return
    
    fig = go.Figure()
    
    # Pace line
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df["pace"],
        mode='lines',
        name='Tempo',
        line=dict(color='#3498db', width=2)
    ))
    
    # GAP line if available
    if "gap" in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df["gap"],
            mode='lines',
            name='GAP',
            line=dict(color='#2ecc71', width=2, dash='dash')
        ))
    
    # Threshold line
    fig.add_hline(
        y=threshold_pace,
        line_dash="dot",
        line_color="red",
        annotation_text="Próg"
    )
    
    fig.update_layout(
        title="Tempo podczas biegu",
        yaxis_title="Tempo (s/km)",
        xaxis_title="Czas",
        yaxis=dict(autorange="reversed")  # Lower pace = higher on chart
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_pace_zones_bar(time_in_zones: Dict[str, int]):
    """Render bar chart of time in pace zones."""
    if not time_in_zones:
        return
    
    zones = list(time_in_zones.keys())
    times = [time_in_zones[z] / 60 for z in zones]  # Convert to minutes
    
    colors = ["#3498db", "#2ecc71", "#f1c40f", "#e67e22", "#e74c3c", "#9b59b6"]
    
    fig = go.Figure(data=[
        go.Bar(x=zones, y=times, marker_color=colors[:len(zones)])
    ])
    
    fig.update_layout(
        title="Czas w strefach tempa",
        yaxis_title="Czas (min)",
        xaxis_title="Strefa"
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_running_dynamics_summary(cadence_stats: Dict, gct_stats: Dict):
    """Render running dynamics summary cards."""
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Kadencja",
            f"{cadence_stats.get('mean_spm', 0):.0f} SPM",
            delta=cadence_stats.get('zone', 'unknown')
        )
    
    with col2:
        st.metric(
            "Czas kontaktu",
            f"{gct_stats.get('mean_ms', 0):.0f} ms",
            delta=gct_stats.get('classification', 'unknown')
        )
    
    with col3:
        st.metric(
            "RE",
            f"{cadence_stats.get('re', 0):.2f}",
            help="Running Effectiveness"
        )
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/ui/test_running_ui.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add modules/ui/running.py tests/ui/test_running_ui.py
git commit -m "feat(ui): add running-specific UI components

- format_pace_for_display with mm:ss format
- get_pace_zone_color for visual zone indication
- render_pace_chart with GAP overlay
- render_pace_zones_bar for zone distribution
- render_running_dynamics_summary"
```

---

## Phase 9: Dual Mode Support

### Task 9.1: Create Dual Mode Adapter

**Files:**
- Create: `modules/calculations/dual_mode.py`
- Create: `tests/calculations/test_dual_mode.py`

**Context:** Support both pace-based analysis and running power (Stryd/Garmin) when available. Fall back to pace when power unavailable.

**Step 1: Write the failing test**

Create: `tests/calculations/test_dual_mode.py`

```python
import pytest
import pandas as pd
import numpy as np
from modules.calculations.dual_mode import (
    detect_available_metrics,
    get_primary_metric,
    calculate_normalized_pace
)

def test_detect_available_metrics():
    """Test detection of available metrics."""
    # Only pace
    df_pace = pd.DataFrame({'pace': [300, 310, 295]})
    metrics = detect_available_metrics(df_pace)
    assert metrics["has_pace"] == True
    assert metrics["has_power"] == False
    
    # Both pace and power
    df_both = pd.DataFrame({
        'pace': [300, 310, 295],
        'power': [250, 260, 240]
    })
    metrics = detect_available_metrics(df_both)
    assert metrics["has_pace"] == True
    assert metrics["has_power"] == True

def test_get_primary_metric():
    """Test primary metric selection."""
    df_both = pd.DataFrame({
        'pace': [300, 310, 295],
        'power': [250, 260, 240]
    })
    
    # With power available, default to power
    primary = get_primary_metric(df_both, prefer_power=True)
    assert primary == "power"
    
    # Can prefer pace
    primary = get_primary_metric(df_both, prefer_power=False)
    assert primary == "pace"

def test_calculate_normalized_pace():
    """Test normalized pace calculation."""
    df = pd.DataFrame({'pace': np.full(300, 300)})  # 5 min constant
    
    np_val = calculate_normalized_pace(df)
    
    # NP should be close to avg for constant pace
    assert abs(np_val - 300) < 10
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/calculations/test_dual_mode.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Implement dual mode adapter**

Create: `modules/calculations/dual_mode.py`

```python
"""
Dual Mode Support Module.

Supports both pace-based and power-based analysis.
Automatically detects available metrics and adapts calculations.
"""

from typing import Dict, Optional, Union, Any
import pandas as pd
import numpy as np


def detect_available_metrics(df: pd.DataFrame) -> Dict[str, bool]:
    """
    Detect which metrics are available in the data.
    
    Args:
        df: DataFrame with running data
        
    Returns:
        Dict with availability flags
    """
    return {
        "has_pace": "pace" in df.columns or "speed" in df.columns,
        "has_power": "power" in df.columns or "watts" in df.columns,
        "has_cadence": "cadence" in df.columns,
        "has_gct": "ground_contact" in df.columns or "gct" in df.columns,
        "has_vo": "vertical_oscillation" in df.columns or "vo" in df.columns,
        "has_stride": "stride_length" in df.columns,
        "has_hr": "heartrate" in df.columns or "hr" in df.columns,
        "has_elevation": "elevation" in df.columns or "altitude" in df.columns,
    }


def get_primary_metric(
    df: pd.DataFrame,
    prefer_power: bool = True
) -> str:
    """
    Determine primary metric for analysis.
    
    Args:
        df: DataFrame
        prefer_power: If True, prefer power when available
        
    Returns:
        "pace" or "power"
    """
    metrics = detect_available_metrics(df)
    
    if prefer_power and metrics["has_power"]:
        return "power"
    elif metrics["has_pace"]:
        return "pace"
    elif metrics["has_power"]:
        return "power"
    else:
        return "unknown"


def get_metric_column(df: pd.DataFrame, metric_type: str) -> Optional[str]:
    """
    Get actual column name for a metric type.
    
    Args:
        df: DataFrame
        metric_type: Type of metric ("pace", "power", "cadence", etc.)
        
    Returns:
        Column name or None
    """
    column_mappings = {
        "pace": ["pace", "speed", "avg_pace"],
        "power": ["power", "watts", "running_power"],
        "cadence": ["cadence", "spm", "steps_per_minute"],
        "hr": ["heartrate", "hr", "heart_rate"],
    }
    
    candidates = column_mappings.get(metric_type, [])
    for col in candidates:
        if col in df.columns:
            return col
    
    return None


def calculate_normalized_pace(
    df: Union[pd.DataFrame, Any],
    rolling_window_sec: int = 30
) -> float:
    """
    Calculate Normalized Pace (NP equivalent for running).
    
    Similar to NP: accounts for variability in pace.
    
    Args:
        df: DataFrame with 'pace' column
        rolling_window_sec: Smoothing window
        
    Returns:
        Normalized pace in sec/km
    """
    from .common import ensure_pandas
    
    df = ensure_pandas(df)
    col = get_metric_column(df, "pace")
    
    if col is None:
        return 0.0
    
    pace = df[col].fillna(method='ffill')
    
    # Convert to speed for calculation (higher speed = harder)
    speed = 1000.0 / pace  # m/s
    
    # Rolling average
    rolling = speed.rolling(window=rolling_window_sec, min_periods=1).mean()
    
    # 4th power (like NP)
    rolling_pow4 = np.power(rolling, 4)
    avg_pow4 = np.nanmean(rolling_pow4)
    
    # 4th root
    normalized_speed = np.power(avg_pow4, 0.25)
    
    # Convert back to pace
    normalized_pace = 1000.0 / normalized_speed if normalized_speed > 0 else 0
    
    return float(normalized_pace)


def calculate_running_stress_score(
    df: pd.DataFrame,
    threshold_pace: float,
    duration_sec: float
) -> float:
    """
    Calculate Running Stress Score (RSS) - running equivalent of TSS.
    
    RSS = (Normalized Pace / Threshold Pace)^2 * Duration (hours) * 100
    
    Args:
        df: DataFrame
        threshold_pace: Threshold pace in sec/km
        duration_sec: Duration in seconds
        
    Returns:
        RSS score
    """
    np_pace = calculate_normalized_pace(df)
    
    if threshold_pace <= 0 or duration_sec <= 0:
        return 0.0
    
    # Intensity factor (pace ratio - note: lower pace = higher intensity)
    if np_pace <= 0:
        return 0.0
    
    intensity_factor = threshold_pace / np_pace
    duration_hours = duration_sec / 3600
    
    rss = intensity_factor**2 * duration_hours * 100
    
    return round(rss, 1)


def adapt_calculation_for_mode(
    calculation_name: str,
    df: pd.DataFrame,
    **kwargs
) -> Any:
    """
    Adapter to run calculation in appropriate mode.
    
    Args:
        calculation_name: Name of calculation
        df: DataFrame
        **kwargs: Additional arguments
        
    Returns:
        Calculation result
    """
    primary = get_primary_metric(df)
    
    if calculation_name == "zones":
        if primary == "power" and "power_zones" in kwargs:
            # Use power zones
            pass
        else:
            # Use pace zones
            from .pace import calculate_pace_zones_time
            return calculate_pace_zones_time(df, kwargs.get("threshold_pace", 300))
    
    elif calculation_name == "stress_score":
        if primary == "power":
            # Could use power-based TSS
            pass
        else:
            return calculate_running_stress_score(
                df,
                kwargs.get("threshold_pace", 300),
                kwargs.get("duration_sec", 3600)
            )
    
    # Default: return None
    return None
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/calculations/test_dual_mode.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add modules/calculations/dual_mode.py tests/calculations/test_dual_mode.py
git commit -m "feat(dual-mode): add dual mode support for pace+power

- detect_available_metrics for auto-detection
- get_primary_metric with power/pace preference
- calculate_normalized_pace (NP equivalent)
- calculate_running_stress_score (RSS = running TSS)
- adapt_calculation_for_mode adapter"
```

---

## Phase 10: Testing, Cleanup & Integration

### Task 10.1: Create Integration Tests

**Files:**
- Create: `tests/integration/test_running_pipeline.py`

**Step 1: Write integration test**

Create: `tests/integration/test_running_pipeline.py`

```python
"""
Integration tests for running analysis pipeline.
"""

import pytest
import pandas as pd
import numpy as np


def test_full_running_pipeline():
    """Test complete running analysis pipeline."""
    # Create sample running data
    np.random.seed(42)
    n_samples = 600  # 10 minutes @ 1Hz
    
    df = pd.DataFrame({
        'time': np.arange(n_samples),
        'pace': 300 + np.random.normal(0, 10, n_samples),  # ~5:00 min/km
        'heartrate': 150 + np.random.normal(0, 5, n_samples),
        'cadence': 170 + np.random.normal(0, 3, n_samples),
        'power': 250 + np.random.normal(0, 10, n_samples),
    })
    
    # Test pace calculations
    from modules.calculations.pace import calculate_pace_zones_time
    zones = calculate_pace_zones_time(df, threshold_pace=300)
    assert len(zones) > 0
    
    # Test D' balance
    from modules.calculations.d_prime import calculate_d_prime_balance
    d_balance = calculate_d_prime_balance(
        df['pace'].values,
        df['time'].values,
        critical_speed_pace=300,
        d_prime_capacity=200
    )
    assert len(d_balance) == n_samples
    
    # Test running dynamics
    from modules.calculations.running_dynamics import calculate_cadence_stats
    cadence_stats = calculate_cadence_stats(df['cadence'].values)
    assert cadence_stats['mean_spm'] > 0
    
    # Test dual mode
    from modules.calculations.dual_mode import detect_available_metrics
    metrics = detect_available_metrics(df)
    assert metrics['has_pace'] == True
    assert metrics['has_power'] == True


def test_pace_duration_curve_integration():
    """Test pace duration curve with real-like data."""
    from modules.calculations.pace import calculate_pace_duration_curve
    
    # Create varying pace data
    paces = np.concatenate([
        np.full(120, 360),  # Warmup
        np.full(300, 300),  # Steady
        np.full(180, 270),  # Fast finish
    ])
    
    df = pd.DataFrame({'pace': paces})
    pdc = calculate_pace_duration_curve(df)
    
    assert len(pdc) > 0
    # Best pace should be the fastest (lowest number)
    best_pace = min([v for v in pdc.values() if v is not None])
    assert best_pace <= 300
```

**Step 2: Run test**

```bash
python -m pytest tests/integration/test_running_pipeline.py -v
```

Expected: PASS

**Step 3: Commit**

```bash
git add tests/integration/test_running_pipeline.py
git commit -m "test(integration): add running pipeline integration tests

- Full pipeline test with pace, HR, cadence, power
- Pace Duration Curve integration test
- D' balance validation"
```

---

### Task 10.2: Update app.py Entry Point

**Files:**
- Modify: `app.py` (adapt to running context)

**Step 1: Update imports and main flow**

Modify: `app.py` (key sections)

```python
# Update parameters extraction
runner_weight = params.get("runner_weight", 75.0)
threshold_pace_input = params.get("threshold_pace", 300)  # sec/km
cs_input = params.get("critical_speed", 3.33)  # m/s
d_prime_input = params.get("d_prime", 200)  # meters
vt1_pace = params.get("vt1_pace", 330)
vt2_pace = params.get("vt2_pace", 270)
runner_age = params.get("runner_age", 30)
is_male = params.get("is_male", True)

# Update validation
if runner_weight <= 0 or threshold_pace_input <= 0:
    st.error("Błąd: Waga i tempo progowe muszą być większe od zera.")
    st.stop()

# Update metric displays
m1, m2, m3 = st.columns(3)
m1.metric("Tempo Normalizowane", f"{np_header:.0f} s/km")
m2.metric("RSS", f"{rss_header:.0f}", help=f"IF: {if_header:.2f}")
m3.metric("Dystans", f"{distance_km:.2f} km")

# Update tabs
with tab_performance:
    UIComponents.show_breadcrumb("⚡ Performance")
    t1, t2, t3, t4, t5, t6 = st.tabs([
        "🏃 Running",      # Changed from Power
        "🦶 Biomechanika", # Changed from Biomech
        "📐 Model",
        "❤️ HR",
        "🧬 Hematologia",
        "📈 Drift Maps",
    ])
```

**Step 2: Commit**

```bash
git add app.py
git commit -m "feat(app): update main app for running context

- Change rider_ to runner_ parameters
- Update metric displays for pace/RSS
- Update tab labels for running context
- Add threshold_pace and d_prime support"
```

---

### Task 10.3: Final Cleanup

**Files:**
- Various cleanup tasks

**Step 1: Create cleanup checklist**

Create: `docs/RUNNING_MIGRATION_CHECKLIST.md`

```markdown
# Running Migration Checklist

## Core Modules ✅
- [x] settings.py - runner_ prefix, threshold_pace, d_prime
- [x] pace_utils.py - pace/speed conversions
- [x] pace.py - zones, PDC, phenotype
- [x] d_prime.py - anaerobic distance capacity
- [x] running_dynamics.py - cadence, GCT, stride
- [x] gap.py - Grade-Adjusted Pace
- [x] race_predictor.py - Riegel formula
- [x] dual_mode.py - pace+power support

## Domain Models ✅
- [x] session_type.py - progressive run detection

## UI Components ✅
- [x] running.py - pace charts, zone bars

## Integration ✅
- [x] app.py - main entry point
- [x] Tests for all new modules

## TODO (Post-MVP)
- [ ] Remove or archive old cycling modules (power.py, w_prime.py)
- [ ] Update documentation
- [ ] Add sample running data files
- [ ] Create user guide for runners
```

**Step 2: Commit**

```bash
git add docs/RUNNING_MIGRATION_CHECKLIST.md
git commit -m "docs: add running migration checklist

- Track progress of cycling→running transformation
- List completed and pending tasks"
```

---

## Summary

This plan transforms a cycling analysis app (power-based) into a running analysis app with:

1. **Core Running Metrics**: Pace-based zones, Critical Speed, D' (anaerobic distance)
2. **Running Dynamics**: Cadence (SPM), GCT, stride analysis
3. **Advanced Features**: Grade-Adjusted Pace (GAP), race predictor
4. **Dual Mode**: Support for both pace and running power (Stryd)
5. **Progressive Run Detection**: For test/tempo workouts

**Total New Files**: 14 modules + tests
**Modified Files**: settings.py, app.py, session_type.py

**Estimated Time**: 4 weeks (as outlined in phases)

---

## Next Steps

1. **Review this plan** - Any changes needed?
2. **Start Phase 1** - Create worktree and begin implementation
3. **Execute via subagent** - Use `superpowers:executing-plans` or `subagent-driven-development`

**Ready to execute?**
