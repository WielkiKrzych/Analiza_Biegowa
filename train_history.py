#!/usr/bin/env python3
"""
Batch Training Script for AI Coach.

Przetwarza wszystkie pliki CSV/JSON z folderu treningi_csv i trenuje model PhysioNet
do predykcji tętna na podstawie mocy i kadencji.

Użycie:
    python train_history.py --stats   # Tylko statystyki folderu
    python train_history.py --train   # Pełny trening modelu

Integracja:
    - Zapisuje historię do: brain_evolution_history.json (dla AI Coach)
    - Zapisuje model do: cycling_brain_weights.npz (dla predykcji)
    - Zapisuje metryki do: training_history.db (dla SessionStore)
"""
import os
import argparse
import time
import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

# --- KONFIGURACJA ---
BASE_DIR = Path(__file__).parent
DATA_FOLDER = BASE_DIR / "treningi_csv"

# Import z istniejących modułów
try:
    from modules.config import Config
    MODEL_FILE = Config.MODEL_FILE
    HISTORY_FILE = Config.HISTORY_FILE
except ImportError:
    MODEL_FILE = "cycling_brain_weights.npz"
    HISTORY_FILE = "brain_evolution_history.json"

# Import bazy danych sesji
try:
    from modules.db.session_store import SessionStore, SessionRecord
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

# --- MLX SETUP ---
MLX_AVAILABLE = False
try:
    import mlx.core as mx
    import mlx.nn as nn
    import mlx.optimizers as optim
    MLX_AVAILABLE = True
    print("✅ Wykryto Apple Silicon (MLX). Gotowy do treningu.")
except ImportError:
    print("⚠️ Brak biblioteki MLX. Zainstaluj: pip install mlx")


# --- MODEL DEFINITION (musi być identyczny jak w ml_logic.py) ---
if MLX_AVAILABLE:
    class PhysioNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.l1 = nn.Linear(3, 64)
            self.l2 = nn.Linear(64, 64)
            self.l3 = nn.Linear(64, 1)

        def __call__(self, x):
            x = nn.relu(self.l1(x))
            x = nn.relu(self.l2(x))
            return self.l3(x)


# --- FUNKCJE POMOCNICZE ---

def load_data(filepath: Path) -> pd.DataFrame:
    """Smart Loader: Radzi sobie z zagnieżdżonymi JSONami i CSV."""
    file_ext = filepath.suffix.lower()
    filename = filepath.name
    
    try:
        if file_ext == '.json':
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                df = pd.DataFrame(data)
            elif isinstance(data, dict):
                # Szukamy klucza z danymi
                candidates = ['samples', 'data', 'records', 'trackPoints', 'points', 'streams', 'rows']
                target_list = None
                
                for key in candidates:
                    if key in data and isinstance(data[key], list):
                        target_list = data[key]
                        break
                
                if target_list is None:
                    max_len = 0
                    for k, v in data.items():
                        if isinstance(v, list) and len(v) > max_len:
                            if len(v) > 0 and isinstance(v[0], dict):
                                target_list = v
                                max_len = len(v)
                
                if target_list is None:
                    try:
                        df = pd.DataFrame.from_dict(data, orient='columns')
                    except ValueError:
                        df = pd.json_normalize(data)
                else:
                    df = pd.json_normalize(target_list)
            else:
                return pd.DataFrame()
        else:
            # CSV/TXT
            try:
                df = pd.read_csv(filepath, low_memory=False)
            except:
                df = pd.read_csv(filepath, sep=';', low_memory=False)
        
        # Czyszczenie
        if 'df' in locals() and not df.empty:
            df.columns = [str(c).lower().strip() for c in df.columns]
            df.columns = [c.split('.')[-1] for c in df.columns]
            return df
        else:
            print(f"   -> ⚠️ Pusty plik: {filename}")
            return pd.DataFrame()
            
    except Exception as e:
        print(f"   -> ⚠️ Błąd odczytu {filename}: {e}")
        return pd.DataFrame()


def process_data(df: pd.DataFrame) -> pd.DataFrame:
    """Przetwarza dane: normalizacja, interpolacja, wygładzanie."""
    if df.empty:
        return df

    if 'time' not in df.columns:
        df['time'] = np.arange(len(df)).astype(float)
    
    df = df.sort_values('time').reset_index(drop=True)
    
    # Konwersja numeryczna
    cols_to_numeric = ['watts', 'heartrate', 'cadence', 'time']
    for c in cols_to_numeric:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')

    # Interpolacja
    num_cols = df.select_dtypes(include=['float64', 'int64']).columns
    if len(num_cols) > 0:
        df[num_cols] = df[num_cols].interpolate(method='linear').ffill().bfill()

    # Smoothing (30s)
    window = 30
    if 'watts' in df.columns:
        df['watts_smooth'] = df['watts'].rolling(window=window, min_periods=1).mean()
    if 'heartrate' in df.columns:
        df['heartrate_smooth'] = df['heartrate'].rolling(window=window, min_periods=1).mean()
    if 'cadence' in df.columns:
        df['cadence_smooth'] = df['cadence'].rolling(window=window, min_periods=1).mean()
    
    df['time_min'] = df['time'] / 60.0
    return df


def filter_and_prepare(df: pd.DataFrame, target_watts: int, 
                       tolerance: int = 15, min_samples: int = 30):
    """Filtruje dane do strefy mocy i przygotowuje tensory MLX."""
    if df.empty or 'watts_smooth' not in df.columns:
        return None, None

    mask = (df['watts_smooth'] >= target_watts - tolerance) & \
           (df['watts_smooth'] <= target_watts + tolerance)
    
    if mask.sum() < min_samples:
        return None, None

    df_filtered = df[mask].copy()

    w = df_filtered['watts_smooth'].values / 500.0
    c = df_filtered['cadence_smooth'].values / 120.0 if 'cadence_smooth' in df_filtered else np.zeros_like(w)
    t = df_filtered['time_min'].values / df['time_min'].max()
    y_target = df_filtered['heartrate_smooth'].values / 200.0

    X_np = np.column_stack((w, c, t)).astype(np.float32)
    y_np = y_target.astype(np.float32).reshape(-1, 1)

    return mx.array(X_np), mx.array(y_np)


def update_history(hr_base, hr_thresh, filename: str):
    """Zapisuje historię Baza/Próg do JSON."""
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                history = json.load(f)
        except:
            pass
    
    entry = {
        "timestamp": time.time(),
        "date": time.strftime("%Y-%m-%d %H:%M"),
        "source_file": filename,
        "hr_base": float(hr_base) if hr_base is not None else None,
        "hr_thresh": float(hr_thresh) if hr_thresh is not None else None
    }
    history.append(entry)
    
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)


def save_to_session_store(filename: str, df: pd.DataFrame, hr_base, hr_thresh):
    """Zapisuje metryki sesji do bazy danych."""
    if not DB_AVAILABLE:
        return
    
    try:
        store = SessionStore()
        
        # Podstawowe metryki
        avg_watts = df['watts'].mean() if 'watts' in df.columns else 0
        avg_hr = df['heartrate'].mean() if 'heartrate' in df.columns else 0
        max_hr = df['heartrate'].max() if 'heartrate' in df.columns else 0
        avg_cadence = df['cadence'].mean() if 'cadence' in df.columns else 0
        duration = int(df['time'].max()) if 'time' in df.columns else 0
        work_kj = df['watts'].sum() / 1000 if 'watts' in df.columns else 0
        
        # Extra metrics - AI Coach data
        extra = {
            "hr_base": hr_base,
            "hr_thresh": hr_thresh,
            "batch_processed": True
        }
        
        # Wyciągnij datę z nazwy pliku jeśli możliwe
        date_str = datetime.now().strftime("%Y-%m-%d")
        # Próbuj wyciągnąć datę z nazwy pliku (format: *DD.MM.YYYY*)
        import re
        match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', filename)
        if match:
            date_str = f"{match.group(3)}-{match.group(2)}-{match.group(1)}"
        
        record = SessionRecord(
            date=date_str,
            filename=filename,
            duration_sec=duration,
            avg_watts=avg_watts,
            avg_hr=avg_hr,
            max_hr=max_hr,
            avg_cadence=avg_cadence,
            work_kj=work_kj,
            extra_metrics=json.dumps(extra)
        )
        
        store.add_session(record)
        
    except Exception as e:
        print(f"   -> ⚠️ Błąd zapisu do DB: {e}")


def get_folder_stats():
    """Wyświetla statystyki folderu treningi_csv."""
    if not DATA_FOLDER.exists():
        print(f"❌ Folder '{DATA_FOLDER}' nie istnieje!")
        return []
    
    files = list(DATA_FOLDER.glob("*.csv"))
    files += list(DATA_FOLDER.glob("*.txt"))
    files += list(DATA_FOLDER.glob("*.json"))
    
    print(f"\n📂 Folder: {DATA_FOLDER}")
    print(f"   Pliki CSV: {len(list(DATA_FOLDER.glob('*.csv')))}")
    print(f"   Pliki JSON: {len(list(DATA_FOLDER.glob('*.json')))}")
    print(f"   Pliki TXT: {len(list(DATA_FOLDER.glob('*.txt')))}")
    print(f"   RAZEM: {len(files)} plików")
    
    if files:
        total_size = sum(f.stat().st_size for f in files)
        print(f"   Rozmiar: {total_size / (1024*1024):.1f} MB")
    
    return files


def train_loop():
    """Główna pętla treningowa."""
    if not MLX_AVAILABLE:
        print("❌ MLX wymagany do treningu. Przerwano.")
        return
    
    files = get_folder_stats()
    if not files:
        print(f"⚠️ Nie znaleziono plików w folderze '{DATA_FOLDER}'.")
        return

    print(f"\n🚀 Rozpoczynam przetwarzanie {len(files)} plików...\n")
    files.sort()

    # Model
    model = PhysioNet()
    mx.eval(model.parameters())
    
    def mse_loss(pred, target):
        return mx.mean((pred - target) ** 2)
    
    optimizer = optim.Adam(learning_rate=0.02)
    
    def train_step(model, X, y):
        pred = model(X)
        loss = mse_loss(pred, y)
        return loss

    loss_and_grad_fn = nn.value_and_grad(model, train_step)
    
    # Cele treningowe
    targets = {
        "BASE": 280,    # Baza tlenowa
        "THRESH": 360   # Próg
    }

    total_start = time.time()
    processed = 0
    
    for idx, file_path in enumerate(files):
        filename = file_path.name
        print(f"[{idx+1}/{len(files)}] {filename}")
        
        try:
            df_raw = load_data(file_path)
            if df_raw.empty:
                continue

            df = process_data(df_raw)
            if len(df) < 100:
                print(f"   -> ⚠️ Za mało danych ({len(df)} rekordów)")
                continue

            results = {}

            for name, watts in targets.items():
                X_chunk, y_chunk = filter_and_prepare(df, watts, tolerance=15, min_samples=60)
                
                if X_chunk is not None:
                    # Fine-tuning
                    for _ in range(100):
                        loss, grads = loss_and_grad_fn(model, X_chunk, y_chunk)
                        optimizer.update(model, grads)
                        mx.eval(model.parameters(), optimizer.state)
                    
                    # Predykcja
                    cadence_norm = 90.0 / 120.0
                    in_tensor = mx.array([[watts/500.0, cadence_norm, 0.5]])
                    pred_hr = float(model(in_tensor)[0][0]) * 200.0
                    results[name] = pred_hr
                    print(f"   -> {name} ({watts}W): {pred_hr:.1f} bpm ✓")
                else:
                    results[name] = None
                    print(f"   -> {name} ({watts}W): Brak danych w tym zakresie")

            # Zapisz historię
            update_history(results.get("BASE"), results.get("THRESH"), filename)
            
            # Zapisz do bazy danych sesji
            save_to_session_store(filename, df, results.get("BASE"), results.get("THRESH"))
            
            processed += 1

        except Exception as e:
            print(f"   -> 💥 Błąd: {e}")

    # Zapisz model
    print("\n" + "-" * 50)
    params = model.parameters()
    flat_params = {}
    for layer_name, layer_params in params.items():
        if isinstance(layer_params, dict):
            for param_name, param_value in layer_params.items():
                flat_params[f"{layer_name}.{param_name}"] = param_value
        else:
            flat_params[layer_name] = layer_params
    
    mx.savez(MODEL_FILE, **flat_params)
    
    total_time = time.time() - total_start
    print(f"✅ GOTOWE!")
    print(f"   Przetworzono: {processed}/{len(files)} plików")
    print(f"   Czas: {total_time:.1f} sekund")
    print(f"   Model: {MODEL_FILE}")
    print(f"   Historia: {HISTORY_FILE}")


def main():
    parser = argparse.ArgumentParser(
        description="Batch Training Script dla AI Coach",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Przykłady:
  python train_history.py --stats   # Tylko statystyki folderu
  python train_history.py --train   # Pełny trening modelu
        """
    )
    parser.add_argument("--stats", action="store_true", help="Wyświetl tylko statystyki folderu")
    parser.add_argument("--train", action="store_true", help="Uruchom pełny trening")
    args = parser.parse_args()
    
    if args.stats:
        get_folder_stats()
    elif args.train:
        train_loop()
    else:
        parser.print_help()
        print("\n💡 Użyj --stats lub --train")


if __name__ == "__main__":
    main()
