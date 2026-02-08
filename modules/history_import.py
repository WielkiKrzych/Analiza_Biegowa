"""
Historical Training Importer.

Batch import of CSV files from the 'treningi_csv' folder into training_history.db.
"""
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional
import re

from modules.db import SessionStore, SessionRecord
from modules.utils import load_data
from modules.calculations import process_data, calculate_metrics, calculate_normalized_power
from services.data_validation import validate_dataframe


# Default folder path
TRAINING_FOLDER = Path(__file__).parent.parent / "treningi_csv"


def extract_date_from_filename(filename: str) -> Optional[str]:
    """Extract date from filename if present.
    
    Supports formats:
    - 2024-12-28_trening.csv
    - trening_28.12.2024.csv
    - 20241228.csv
    - session_20241228_120000.csv
    
    Returns:
        Date string in YYYY-MM-DD format or None
    """
    # Pattern 1: YYYY-MM-DD
    match = re.search(r'(\d{4})-(\d{2})-(\d{2})', filename)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    
    # Pattern 2: DD.MM.YYYY
    match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', filename)
    if match:
        return f"{match.group(3)}-{match.group(2)}-{match.group(1)}"
    
    # Pattern 3: YYYYMMDD
    match = re.search(r'(\d{4})(\d{2})(\d{2})', filename)
    if match:
        year = int(match.group(1))
        if 2020 <= year <= 2030:  # Sanity check
            return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    
    return None


def import_single_file(
    filepath: Path,
    cp: float = 280,
    store: Optional[SessionStore] = None
) -> Tuple[bool, str]:
    """Import a single CSV file into the database.
    
    Args:
        filepath: Path to CSV file
        cp: Critical Power for metrics calculation
        store: Optional SessionStore instance
        
    Returns:
        Tuple of (success, message)
    """
    if store is None:
        store = SessionStore()
    
    try:
        # Load and process data
        with open(filepath, 'rb') as f:
            df_raw = load_data(f)
        
        if df_raw is None or df_raw.empty:
            return False, f"Pusty plik: {filepath.name}"
            
        # Validate logic
        is_valid, error = validate_dataframe(df_raw)
        if not is_valid:
            return False, f"Błąd walidacji ({filepath.name}): {error}"
        
        df = process_data(df_raw)
        metrics = calculate_metrics(df, cp)
        
        # Calculate NP and TSS
        if 'watts' in df.columns and len(df) >= 30:
            np_val = calculate_normalized_power(df)
            if cp > 0:
                if_factor = np_val / cp
                tss = (len(df) * np_val * if_factor) / (cp * 3600) * 100
            else:
                if_factor = 0
                tss = 0
        else:
            np_val = metrics.get('avg_watts', 0)
            if_factor = 0
            tss = 0
        
        # Extract date from filename
        date_str = extract_date_from_filename(filepath.name)
        if not date_str:
            # Use file modification time
            mod_time = datetime.fromtimestamp(filepath.stat().st_mtime)
            date_str = mod_time.strftime('%Y-%m-%d')
        
        # Create session record
        record = SessionRecord(
            date=date_str,
            filename=filepath.name,
            duration_sec=len(df),
            tss=tss,
            np=np_val,
            if_factor=if_factor,
            avg_watts=metrics.get('avg_watts', 0),
            avg_hr=metrics.get('avg_hr', 0),
            max_hr=df['heartrate'].max() if 'heartrate' in df.columns else 0,
            work_kj=metrics.get('work_kj', 0) if 'work_kj' in metrics else (df['watts'].sum() / 1000 if 'watts' in df.columns else 0),
            avg_cadence=metrics.get('avg_cadence', 0),
            mmp_5s=df['watts'].rolling(5).mean().max() if 'watts' in df.columns else None,
            mmp_1m=df['watts'].rolling(60).mean().max() if 'watts' in df.columns else None,
            mmp_5m=df['watts'].rolling(300).mean().max() if 'watts' in df.columns and len(df) >= 300 else None,
            mmp_20m=df['watts'].rolling(1200).mean().max() if 'watts' in df.columns and len(df) >= 1200 else None,
        )
        
        store.add_session(record)
        return True, f"✅ {filepath.name}: TSS={tss:.0f}, NP={np_val:.0f}W"
        
    except Exception as e:
        return False, f"❌ {filepath.name}: {str(e)}"


def import_training_folder(
    folder_path: Optional[Path] = None,
    cp: float = 280,
    progress_callback: Optional[callable] = None
) -> Tuple[int, int, List[str]]:
    """Import all CSV files from the training folder.
    
    Args:
        folder_path: Path to folder (default: 'Treningi CSV')
        cp: Critical Power for calculations
        progress_callback: Optional callback(current, total, message) for progress updates
        
    Returns:
        Tuple of (success_count, fail_count, messages)
    """
    if folder_path is None:
        folder_path = TRAINING_FOLDER
    
    folder_path = Path(folder_path)
    
    if not folder_path.exists():
        return 0, 0, [f"Folder nie istnieje: {folder_path}"]
    
    # Find all CSV files
    csv_files = list(folder_path.glob("*.csv")) + list(folder_path.glob("*.CSV"))
    csv_files = sorted(set(csv_files))  # Remove duplicates, sort
    
    if not csv_files:
        return 0, 0, ["Brak plików CSV w folderze"]
    
    store = SessionStore()
    success_count = 0
    fail_count = 0
    messages = []
    
    for i, filepath in enumerate(csv_files):
        success, msg = import_single_file(filepath, cp, store)
        
        if success:
            success_count += 1
        else:
            fail_count += 1
        
        messages.append(msg)
        
        if progress_callback:
            progress_callback(i + 1, len(csv_files), msg)
    
    return success_count, fail_count, messages


def get_available_files(folder_path: Optional[Path] = None) -> List[dict]:
    """Get list of available CSV files with their info.
    
    Returns:
        List of dicts with 'name', 'size', 'date' keys
    """
    if folder_path is None:
        folder_path = TRAINING_FOLDER
    
    folder_path = Path(folder_path)
    
    if not folder_path.exists():
        return []
    
    csv_files = list(folder_path.glob("*.csv")) + list(folder_path.glob("*.CSV"))
    
    result = []
    for f in sorted(set(csv_files)):
        date = extract_date_from_filename(f.name)
        if not date:
            mod_time = datetime.fromtimestamp(f.stat().st_mtime)
            date = mod_time.strftime('%Y-%m-%d')
        
        result.append({
            'name': f.name,
            'size': f.stat().st_size,
            'date': date,
            'path': str(f)
        })
    
    return sorted(result, key=lambda x: x['date'], reverse=True)
