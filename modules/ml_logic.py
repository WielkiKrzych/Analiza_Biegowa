import os
import json
import time
import logging
import numpy as np
from abc import ABC, abstractmethod
from typing import Optional, Tuple, List, Any
from modules.config import Config

logger = logging.getLogger(__name__)

# ============================================================
# SOLID: Dependency Inversion Principle (DIP)
# Abstrakcja dla callbacków UI - logika ML nie zależy od Streamlit
# ============================================================

class TrainingCallback(ABC):
    """Abstrakcja dla raportowania postępu treningu ML.
    
    Pozwala na oddzielenie logiki ML od konkretnej implementacji UI.
    """
    
    @abstractmethod
    def on_status(self, message: str) -> None:
        """Wyświetla wiadomość statusu."""
        pass
    
    @abstractmethod
    def on_progress(self, current: int, total: int) -> None:
        """Aktualizuje pasek postępu."""
        pass
    
    @abstractmethod
    def on_error(self, error: Exception) -> None:
        """Obsługuje błąd."""
        pass
    
    @abstractmethod
    def on_complete(self) -> None:
        """Wywołane po zakończeniu treningu - czyszczenie UI."""
        pass


class SilentCallback(TrainingCallback):
    """Domyślny callback - nie robi nic (dla testów i predykcji)."""
    
    def on_status(self, message: str) -> None:
        pass
    
    def on_progress(self, current: int, total: int) -> None:
        pass
    
    def on_error(self, error: Exception) -> None:
        logger.warning(f"ML Error: {error}")
    
    def on_complete(self) -> None:
        pass


MLX_AVAILABLE = False
try:
    import mlx.core as mx
    import mlx.nn as nn
    import mlx.optimizers as optim
    import mlx.utils
    MLX_AVAILABLE = True
except ImportError:
    pass

MODEL_FILE = Config.MODEL_FILE
HISTORY_FILE = Config.HISTORY_FILE

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

    def save_model(model, filepath: str) -> None:
        """Zapisuje wagi modelu do pliku."""
        flattened_params = {}
        for k, v in model.parameters().items():
            if isinstance(v, dict):
                 for sub_k, sub_v in v.items():
                     flattened_params[f"{k}.{sub_v}"] = sub_v
            else:
                flattened_params[k] = v
        mx.savez(filepath, **dict(mlx.utils.tree_flatten(model.parameters())))

    def load_model(model, filepath: str, callback: Optional[TrainingCallback] = None) -> bool:
        """Ładuje wagi modelu z pliku.
        
        Args:
            model: Instancja PhysioNet
            filepath: Ścieżka do pliku z wagami
            callback: Opcjonalny callback do raportowania błędów
        
        Returns:
            True jeśli wagi zostały załadowane, False w przeciwnym razie
        """
        if os.path.exists(filepath):
            try:
                weights = mx.load(filepath)
                
                try:
                    model.update(weights)
                except Exception:
                    current_params = model.parameters()
                    new_params = {}
                    
                    for k, v in weights.items():
                        parts = k.split('.')
                        if len(parts) == 2:
                            layer, param = parts
                            if layer not in new_params: new_params[layer] = {}
                            new_params[layer][param] = v
                    
                    model.update(new_params)
                
                return True
            except Exception as e:
                if callback:
                    callback.on_error(e)
                logger.warning(f"Model loading error: {e}")
                return False
        return False

    def update_history(hr_base: Optional[float], hr_thresh: Optional[float]) -> List[dict]:
        """Zapisuje historię Baza/Próg do JSON z obsługą None."""
        history = []
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r') as f:
                    history = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.debug(f"Could not load history: {e}")
        
        entry = {
            "timestamp": time.time(),
            "date": time.strftime("%Y-%m-%d %H:%M"),
            "hr_base": float(hr_base) if hr_base is not None else None,
            "hr_thresh": float(hr_thresh) if hr_thresh is not None else None
        }
        history.append(entry)
        
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history, f)
        return history

    def predict_only(df, callback: Optional[TrainingCallback] = None) -> Optional[np.ndarray]:
        """Tylko predykcja (bez treningu) - dla automatycznego wykresu.
        
        Args:
            df: DataFrame z danymi treningowymi
            callback: Opcjonalny callback do raportowania błędów
        
        Returns:
            Tablica numpy z predykcjami HR lub None
        """
        if not os.path.exists(MODEL_FILE):
            return None
            
        w = df['watts_smooth'].values / 500.0
        c = df['cadence_smooth'].values / 120.0 if 'cadence_smooth' in df else np.zeros_like(w)
        t = df['time_min'].values / df['time_min'].max()
        
        X_np = np.column_stack((w, c, t)).astype(np.float32)
        X_np = np.nan_to_num(X_np, copy=False) 
        
        X = mx.array(X_np)
        
        model = PhysioNet()
        if load_model(model, MODEL_FILE, callback):
            y_pred_scaled = model(X)
            return np.array(y_pred_scaled).flatten() * 200.0
        return None
    
    def filter_and_prepare(df, target_watts: int, tolerance: int = 15, 
                           min_samples: int = 30) -> Tuple[Optional[Any], Optional[Any]]:
        """Filtruje dane do określonej strefy mocy i przygotowuje do treningu."""
        mask = (df['watts_smooth'] >= target_watts - tolerance) & \
            (df['watts_smooth'] <= target_watts + tolerance)
        
        if mask.sum() < min_samples:
            return None, None

        df_filtered = df[mask].copy()
        w = df_filtered['watts_smooth'].values / 500.0
        c = df_filtered['cadence_smooth'].values / 120.0 if 'cadence_smooth' in df_filtered else np.zeros_like(w)
        t = df_filtered['time_min'].values / df['time_min'].max()
        y = df_filtered['heartrate_smooth'].values / 200.0

        X_np = np.column_stack((w, c, t)).astype(np.float32)
        X_np = np.nan_to_num(X_np, copy=False)
        
        y_np = y.astype(np.float32).reshape(-1, 1)
        y_np = np.nan_to_num(y_np, copy=False)

        X = mx.array(X_np)
        Y = mx.array(y_np)
        return X, Y

    def train_cycling_brain(df, epochs: int = Config.ML_EPOCHS, 
                            callback: Optional[TrainingCallback] = None,
                            training_zones: Optional[List[Tuple[str, int]]] = None):
        """Trenuje model predykcji HR na podstawie mocy i kadencji.
        
        Args:
            df: DataFrame z danymi treningowymi
            epochs: Liczba epok treningu dla każdej strefy
            callback: Opcjonalny callback do raportowania postępu (DIP)
            training_zones: Lista stref do kalibracji [(nazwa, moc_w)], domyślnie base/thresh
        
        Returns:
            Tuple: (predykcje, hr_base, hr_thresh, czy_załadowano_model, historia)
        """
        # Użyj domyślnego callbacka jeśli nie podano
        if callback is None:
            callback = SilentCallback()
        
        # Domyślne strefy treningowe (OCP - można rozszerzyć bez modyfikacji)
        if training_zones is None:
            training_zones = [("base", 280), ("thresh", 360)]
        
        model = PhysioNet()
        mx.eval(model.parameters())
        
        loaded = load_model(model, MODEL_FILE, callback)
        
        def mse_loss(pred, target): return mx.mean((pred - target) ** 2)
        optimizer = optim.Adam(learning_rate=Config.ML_LEARNING_RATE)
        def train_step(model, X, y):
            loss = mse_loss(model(X), y)
            return loss
        loss_and_grad_fn = nn.value_and_grad(model, train_step)

        results = {zone[0]: None for zone in training_zones}
        
        callback.on_status("Trenowanie modelu ogólnego (cały plik)...")
        w_all = df['watts_smooth'].values / 500.0
        c_all = df['cadence_smooth'].values / 120.0 if 'cadence_smooth' in df else np.zeros_like(w_all)
        t_all = df['time_min'].values / df['time_min'].max()
        y_all = df['heartrate_smooth'].values / 200.0
        
        X_all_np = np.column_stack((w_all, c_all, t_all)).astype(np.float32)
        X_all_np = np.nan_to_num(X_all_np, copy=False)
        
        Y_all_np = y_all.astype(np.float32).reshape(-1, 1)
        Y_all_np = np.nan_to_num(Y_all_np, copy=False)

        X_all = mx.array(X_all_np)
        Y_all = mx.array(Y_all_np)
        
        for i in range(100): 
            loss, grads = loss_and_grad_fn(model, X_all, Y_all)
            optimizer.update(model, grads)
            mx.eval(model.parameters(), optimizer.state)
        
        y_pred_full = np.array(model(X_all)).flatten() * 200.0
        save_model(model, MODEL_FILE) 
        
        # Reset progress bar for next phase
        callback.on_progress(0, 1)

        step = 0
        total_steps = len(training_zones) * epochs
        
        for name, watts in training_zones:
            callback.on_status(f"Kalibracja strefy: {watts}W...")
            
            X_chunk, y_chunk = filter_and_prepare(df, watts)
            
            if X_chunk is not None:
                for i in range(epochs):
                    loss, grads = loss_and_grad_fn(model, X_chunk, y_chunk)
                    optimizer.update(model, grads)
                    mx.eval(model.parameters(), optimizer.state)
                    if i % 10 == 0: 
                        step += 10
                        callback.on_progress(step, total_steps)
                
                in_vec = mx.array([[watts/500.0, 80.0/120.0, 0.5]]) 
                pred = float(model(in_vec)[0][0]) * 200.0
                results[name] = pred
            else:
                results[name] = None
                step += epochs
                
        callback.on_complete()

        history = update_history(results.get("base"), results.get("thresh"))

        return y_pred_full, results.get("base"), results.get("thresh"), loaded, history

else:
    # Fallback gdy MLX nie jest dostępny
    
    class TrainingCallback(ABC):
        """Pusta definicja dla kompatybilności."""
        pass
    
    class SilentCallback:
        """Pusta definicja dla kompatybilności."""
        pass
    
    def train_cycling_brain(*args, **kwargs): return None, None, None, None, None
    def predict_only(*args, **kwargs): return None
    def update_history(*args, **kwargs): return []
