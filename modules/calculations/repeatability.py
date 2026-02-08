"""
Repeatability Analysis Module.

Calculates intra-individual metabolic stability and reproducibility metrics.
Key Metrics:
- CV (Coefficient of Variation): Noise vs Signal.
- SEM (Standard Error of Measurement): Typical error range.
- Reproducibility Classification: Excellent (<3%), Good (<6%), Moderate (<10%), Unstable (>10%).
"""
import numpy as np
from typing import List, Dict, Union

def calculate_cv(values: List[float]) -> float:
    """Calculate Coefficient of Variation (%)."""
    if len(values) < 2:
        return 0.0
    mean_val = np.mean(values)
    if mean_val == 0:
        return 0.0
    std_val = np.std(values, ddof=1) # Sample std deviation
    return (std_val / mean_val) * 100.0

def calculate_sem(values: List[float]) -> float:
    """Calculate Standard Error of Measurement."""
    if len(values) < 2:
        return 0.0
    std_val = np.std(values, ddof=1)
    return std_val / np.sqrt(len(values))

def classify_reproducibility(cv: float) -> str:
    """Classify the stability of a metric based on CV."""
    if cv < 3.0:
        return "Excellent"
    elif cv < 6.0:
        return "Good"
    elif cv < 10.0:
        return "Moderate"
    else:
        return "Unstable"

def calculate_repeatability_metrics(
    sessions_metrics: List[Dict[str, float]]
) -> Dict[str, Dict[str, Union[float, str]]]:
    """
    Calculate repeatability stats for a list of session results.
    
    Args:
        sessions_metrics: List of dicts, e.g. [{'vt1': 200}, {'vt1': 210}]
        
    Returns:
        Dict of stats per metric: 
        {
            'vt1': {'mean': 205, 'std': 7.07, 'cv': 3.4, 'class': 'Good'},
            ...
        }
    """
    if not sessions_metrics:
        return {}
        
    # Aggregate values by key
    aggregated = {}
    for session in sessions_metrics:
        for k, v in session.items():
            if v is None: continue
            if k not in aggregated:
                aggregated[k] = []
            aggregated[k].append(float(v))
            
    results = {}
    for metric, values in aggregated.items():
        if len(values) < 2:
            results[metric] = {
                "mean": values[0] if values else 0,
                "std": 0,
                "cv": 0,
                "sem": 0,
                "class": "N/A (1 sample)"
            }
            continue
            
        mean_val = np.mean(values)
        std_val = np.std(values, ddof=1)
        cv = (std_val / mean_val * 100.0) if mean_val != 0 else 0
        sem = std_val / np.sqrt(len(values))
        
        results[metric] = {
            "mean": round(mean_val, 2),
            "std": round(std_val, 2),
            "cv": round(cv, 2),
            "sem": round(sem, 2),
            "class": classify_reproducibility(cv)
        }
        
    return results

def compare_session_to_baseline(
    current_metrics: Dict[str, float],
    baseline_stats: Dict[str, Dict[str, float]]
) -> Dict[str, Dict[str, any]]:
    """
    Compare a single session against a baseline (repeatability stats).
    
    Args:
        current_metrics: Dict of current values {'vt1': 215}
        baseline_stats: Output from calculate_repeatability_metrics
        
    Returns:
        Dict with comparison details per metric.
    """
    comparison = {}
    
    for metric, current_val in current_metrics.items():
        if metric not in baseline_stats:
            continue
            
        stats = baseline_stats[metric]
        baseline_mean = stats.get('mean', 0)
        baseline_cv = stats.get('cv', 0)
        
        if baseline_mean == 0:
            pct_diff = 0
        else:
            pct_diff = ((current_val - baseline_mean) / baseline_mean) * 100.0
            
        # Interpretation
        # If change is > 1.5-2x CV, it's likely significant
        threshold_cv = max(baseline_cv, 1.0) # Min threshold 1%
        
        is_significant = abs(pct_diff) > (threshold_cv * 1.5)
        
        status = "Stable"
        if is_significant:
            status = "Significant Change" if abs(pct_diff) > (threshold_cv * 2.0) else "Possible Change"
            
        comparison[metric] = {
            "current": current_val,
            "baseline": baseline_mean,
            "pct_diff": round(pct_diff, 1),
            "is_significant": is_significant,
            "status": status,
            "baseline_cv": baseline_cv
        }
        
    return comparison
