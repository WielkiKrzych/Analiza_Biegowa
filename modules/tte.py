"""
Time-to-Exhaustion (TTE) Detection Module.

Computes the maximum continuous duration an athlete can sustain
a target power percentage (e.g., 100% FTP ±5%).
"""

from typing import Dict, List, Optional, Tuple, Callable
import json
import numpy as np
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from dataclasses import dataclass
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from modules.config import Config


@dataclass
class TTEResult:
    """Result of TTE computation for a single session."""

    session_id: str
    tte_seconds: int
    target_pct: float
    ftp: float
    tolerance_pct: float
    target_power_min: float
    target_power_max: float
    timestamp: Optional[str] = None


def compute_tte(
    power_series: pd.Series, target_pct: float, ftp: float, tol_pct: float = 5.0
) -> int:
    """Compute Time-to-Exhaustion at a given FTP percentage.

    Finds the longest continuous segment where power stays within
    target_pct ± tol_pct of FTP.

    Args:
        power_series: Power values at 1Hz (or will be resampled)
        target_pct: Target percentage of FTP (e.g., 100 for 100% FTP)
        ftp: Functional Threshold Power in watts
        tol_pct: Tolerance percentage (default 5%)

    Returns:
        Maximum continuous duration in seconds
    """
    if power_series is None or len(power_series) == 0:
        return 0

    # Calculate target power range
    target_power = ftp * (target_pct / 100.0)
    power_min = target_power * (1 - tol_pct / 100.0)
    power_max = target_power * (1 + tol_pct / 100.0)

    # Fill NaN with 0 (treated as below threshold)
    power = power_series.fillna(0).values

    # Create boolean mask for valid power range
    in_range = (power >= power_min) & (power <= power_max)

    # Find longest continuous run of True values
    max_duration = 0
    current_duration = 0

    for val in in_range:
        if val:
            current_duration += 1
            max_duration = max(max_duration, current_duration)
        else:
            current_duration = 0

    return max_duration


def compute_tte_result(
    power_series: pd.Series,
    target_pct: float,
    ftp: float,
    tol_pct: float = 5.0,
    session_id: Optional[str] = None,
) -> TTEResult:
    """Compute TTE and return a structured result.

    Args:
        power_series: Power values
        target_pct: Target percentage of FTP
        ftp: Functional Threshold Power
        tol_pct: Tolerance percentage
        session_id: Optional session identifier

    Returns:
        TTEResult with all computed values
    """
    tte_seconds = compute_tte(power_series, target_pct, ftp, tol_pct)

    target_power = ftp * (target_pct / 100.0)
    power_min = target_power * (1 - tol_pct / 100.0)
    power_max = target_power * (1 + tol_pct / 100.0)

    return TTEResult(
        session_id=session_id or datetime.now().strftime("%Y%m%d_%H%M%S"),
        tte_seconds=tte_seconds,
        target_pct=target_pct,
        ftp=ftp,
        tolerance_pct=tol_pct,
        target_power_min=power_min,
        target_power_max=power_max,
        timestamp=datetime.now().isoformat(),
    )


def rolling_tte(history: List[Dict], window_days: int = 30) -> Dict[str, float]:
    """Compute rolling TTE statistics from historical data.

    Args:
        history: List of dicts with 'date' and 'tte_seconds' keys
        window_days: Rolling window size in days

    Returns:
        Dict with 'median', 'mean', 'max', 'min', 'count'
    """
    if not history:
        return {"median": 0, "mean": 0, "max": 0, "min": 0, "count": 0}

    # Filter to window
    cutoff = datetime.now() - timedelta(days=window_days)

    filtered = []
    for entry in history:
        entry_date = entry.get("date")
        if entry_date:
            if isinstance(entry_date, str):
                try:
                    entry_date = datetime.fromisoformat(entry_date)
                except ValueError:
                    continue
            if entry_date >= cutoff:
                tte = entry.get("tte_seconds", 0)
                if tte > 0:
                    filtered.append(tte)

    if not filtered:
        return {"median": 0, "mean": 0, "max": 0, "min": 0, "count": 0}

    return {
        "median": float(np.median(filtered)),
        "mean": float(np.mean(filtered)),
        "max": float(max(filtered)),
        "min": float(min(filtered)),
        "count": len(filtered),
    }


def compute_trend_data(history: List[Dict], windows: List[int] = [30, 90]) -> Dict[int, Dict]:
    """Compute trend data for multiple rolling windows.

    Args:
        history: List of session dicts with 'date' and 'tte_seconds'
        windows: List of window sizes in days

    Returns:
        Dict mapping window_days to rolling stats
    """
    return {w: rolling_tte(history, w) for w in windows}


def get_tte_history_from_db(days: int = 90, target_pct: float = 100.0) -> List[Dict]:
    """Fetch historical TTE data from training_history.db.

    Args:
        days: Historical window in days
        target_pct: The target FTP percentage to look for in extra_metrics

    Returns:
        List of dicts with 'date', 'tte_seconds', 'session_id'
    """
    db_path = Config.DB_PATH
    history = []

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT id, date, filename, extra_metrics 
                FROM sessions 
                WHERE date >= date('now', ?)
                ORDER BY date ASC
            """,
                (f"-{days} days",),
            )

            for row in cursor.fetchall():
                extra = json.loads(row["extra_metrics"] or "{}")
                tte_data = extra.get("tte", {})
                # tte_data stores { "target_pct_str": tte_seconds }
                tte_val = tte_data.get(str(int(target_pct)))

                if tte_val is not None:
                    history.append(
                        {
                            "session_id": row["filename"],
                            "date": row["date"],
                            "tte_seconds": int(tte_val),
                        }
                    )
    except Exception as e:
        print(f"Error fetching TTE history: {e}")

    return history


def save_tte_to_db(filename: str, session_date: str, target_pct: float, tte_seconds: int) -> bool:
    """Save/Update TTE value in the session's extra_metrics.

    Args:
        filename: Session filename (unique identifier with date)
        session_date: Session date string (YYYY-MM-DD)
        target_pct: FTP percentage
        tte_seconds: Computed TTE

    Returns:
        Success boolean
    """
    db_path = Config.DB_PATH
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            # 1. Get existing extra_metrics
            cursor = conn.execute(
                "SELECT extra_metrics FROM sessions WHERE filename = ? AND date = ?",
                (filename, session_date),
            )
            row = cursor.fetchone()
            if not row:
                return False

            extra = json.loads(row["extra_metrics"] or "{}")
            if "tte" not in extra:
                extra["tte"] = {}

            # Save for specific target_pct
            extra["tte"][str(int(target_pct))] = tte_seconds

            # 2. Update DB
            conn.execute(
                "UPDATE sessions SET extra_metrics = ? WHERE filename = ? AND date = ?",
                (json.dumps(extra), filename, session_date),
            )
            conn.commit()
            return True
    except Exception as e:
        print(f"Error saving TTE to db: {e}")
        return False


def _compute_single_session_tte(
    csv_path: Path, target_pcts: List[float], ftp: float, tol_pct: float
) -> Optional[Dict]:
    """Helper for parallel processing of a single file."""
    from modules.utils import load_data
    from modules.calculations import process_data

    try:
        with open(csv_path, "rb") as f:
            df_raw = load_data(f)

        if df_raw is None or df_raw.empty or "watts" not in df_raw.columns:
            return None

        df = process_data(df_raw)
        power_series = df["watts"]

        results = {}
        for pct in target_pcts:
            # We use the existing compute_tte within this process
            tte_val = compute_tte(power_series, pct, ftp, tol_pct)
            results[str(int(pct))] = int(tte_val)

        return results
    except Exception as e:
        logger.warning(f"TTE computation failed: {e}")
        return None


def batch_compute_tte_for_all_sessions(
    ftp: float,
    target_pcts: List[float] = [100.0],
    tol_pct: float = 5.0,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> Tuple[int, int]:
    """
    Optimized batch processing using parallel execution and directory caching.

    Complexity Analysis:
    - Current Big O: O(N * (G + L + P + C))
      N=Sessions, G=Directory Glob, L=Load, P=Process, C=Compute
    - Expected Big O: O(N_files + (N * (L + P + C)) / Cores)
    """
    db_path = Config.DB_PATH
    training_folder = Path(Config.BASE_DIR) / "treningi_csv"

    success_count = 0
    fail_count = 0

    # 1. Directory Caching: Scan folder once O(N_files)
    # Mapping of stem -> Full Path for O(1) matching
    file_cache = {p.stem: p for p in training_folder.glob("*.csv")}

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT id, filename, extra_metrics FROM sessions")
            sessions = cursor.fetchall()
            total = len(sessions)

            # 2. Parallel Processing Setup
            # Using ProcessPoolExecutor for CPU-bound load_data and compute_tte
            with ProcessPoolExecutor() as executor:
                futures = {}
                row_map = {}  # future -> row_id

                for i, row in enumerate(sessions):
                    filename = row["filename"]
                    row_id = row["id"]

                    # O(1) Lookup
                    csv_path = file_cache.get(Path(filename).stem)

                    if not csv_path or not csv_path.exists():
                        fail_count += 1
                        if progress_callback:
                            progress_callback(i + 1, total, f"❌ {filename}: Not found")
                        continue

                    future = executor.submit(
                        _compute_single_session_tte, csv_path, target_pcts, ftp, tol_pct
                    )
                    futures[future] = (row_id, filename, row["extra_metrics"])

                # 3. Collect Results as they complete
                updates = []
                for j, future in enumerate(as_completed(futures)):
                    row_id, fname, old_extra_json = futures[future]
                    try:
                        new_tte = future.result()
                        if new_tte:
                            extra = json.loads(old_extra_json or "{}")
                            if "tte" not in extra:
                                extra["tte"] = {}
                            extra["tte"].update(new_tte)

                            updates.append((json.dumps(extra), row_id))
                            success_count += 1
                            msg = f"✅ {fname}: OK"
                        else:
                            fail_count += 1
                            msg = f"❌ {fname}: Data error"
                    except Exception as e:
                        fail_count += 1
                        msg = f"⚠️ {fname}: {str(e)}"

                    if progress_callback:
                        progress_callback(j + 1, total, msg)

                # 4. Batch DB Update (N+1 Solution)
                if updates:
                    conn.executemany("UPDATE sessions SET extra_metrics = ? WHERE id = ?", updates)
                    conn.commit()

    except Exception as e:
        print(f"Parallel TTE error: {e}")

    return success_count, fail_count


def export_tte_json(result: TTEResult) -> str:
    """Export TTE result to JSON string.

    Args:
        result: TTEResult object

    Returns:
        JSON string representation
    """
    data = {
        "session_id": result.session_id,
        "tte_seconds": result.tte_seconds,
        "tte_formatted": format_tte(result.tte_seconds),
        "target_pct": result.target_pct,
        "ftp": result.ftp,
        "tolerance_pct": result.tolerance_pct,
        "target_power_range": {
            "min": round(result.target_power_min, 0),
            "max": round(result.target_power_max, 0),
        },
        "timestamp": result.timestamp,
    }
    return json.dumps(data, indent=2)


def format_tte(seconds: int) -> str:
    """Format TTE duration to mm:ss string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "05:30")
    """
    if seconds <= 0:
        return "00:00"

    mins = seconds // 60
    secs = seconds % 60
    return f"{mins:02d}:{secs:02d}"
