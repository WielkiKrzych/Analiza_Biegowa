"""
Trend Analysis Engine.

Calculates adaptation trends across multiple ramp tests for:
- VT1, VT2, CP, W'
- Efficiency Factor (EF)
- SmO2 slope
- Occlusion Index
- HSI

Output:
- Adaptation rate (% / week)
- Adaptation direction (central, peripheral, thermal)
- Engine Map data
"""
import os
import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger("Tri_Dashboard.TrendEngine")


@dataclass
class MetricTrend:
    """Single metric trend data."""
    name: str
    values: List[float] = field(default_factory=list)
    dates: List[datetime] = field(default_factory=list)
    rate_per_week: float = 0.0  # % change per week
    direction: str = "stable"  # improving, declining, stable
    classification: str = ""  # central, peripheral, thermal, etc.


@dataclass  
class TrendAnalysis:
    """Complete trend analysis result."""
    # Individual metrics
    vt1: MetricTrend = field(default_factory=lambda: MetricTrend("VT1"))
    vt2: MetricTrend = field(default_factory=lambda: MetricTrend("VT2"))
    cp: MetricTrend = field(default_factory=lambda: MetricTrend("CP"))
    w_prime: MetricTrend = field(default_factory=lambda: MetricTrend("W'"))
    ef: MetricTrend = field(default_factory=lambda: MetricTrend("EF"))
    smo2_slope: MetricTrend = field(default_factory=lambda: MetricTrend("SmO2 Slope"))
    occlusion_index: MetricTrend = field(default_factory=lambda: MetricTrend("Occlusion Index"))
    hsi: MetricTrend = field(default_factory=lambda: MetricTrend("HSI"))
    
    # Overall analysis
    adaptation_direction: str = "balanced"  # central, peripheral, thermal, balanced
    adaptation_score: float = 0.0  # 0-100
    tests_analyzed: int = 0
    date_range_days: int = 0
    
    # Engine map data (for radar chart)
    engine_map: Dict[str, float] = field(default_factory=dict)


def load_ramp_test_history(index_path: str = "reports/ramp_tests/index.csv") -> List[Dict[str, Any]]:
    """
    Load all ramp test reports from the archive.
    
    Returns:
        List of report data dictionaries sorted by date (oldest first)
    """
    from modules.reporting.persistence import load_ramp_test_report
    
    if not os.path.exists(index_path):
        logger.warning(f"Index file not found: {index_path}")
        return []
    
    try:
        df = pd.read_csv(index_path)
    except Exception as e:
        logger.error(f"Error reading index: {e}")
        return []
    
    if df.empty:
        return []
    
    # Sort by date ascending
    if 'test_date' in df.columns:
        df['test_date'] = pd.to_datetime(df['test_date'])
        df = df.sort_values(by='test_date', ascending=True)
    
    # Vectorized approach - avoid iterrows()
    def load_report_safe(row):
        json_path = row.get('json_path')
        if json_path and os.path.exists(json_path):
            try:
                report = load_ramp_test_report(json_path)
                report['_test_date'] = row['test_date']
                return report
            except Exception as e:
                logger.warning(f"Error loading report {json_path}: {e}")
        return None
    
    # Use apply instead of iterrows for better performance
    reports = df.apply(load_report_safe, axis=1).dropna().tolist()
    
    return reports


def extract_metrics_from_report(report: Dict[str, Any]) -> Dict[str, float]:
    """
    Extract key metrics from a ramp test report.
    
    Returns dict with: vt1, vt2, cp, w_prime, ef, smo2_slope, occlusion_index, hsi
    """
    metrics = {}
    
    # VT1/VT2 from thresholds
    thresholds = report.get('thresholds', {})
    vt = thresholds.get('ventilatory', {})
    metrics['vt1'] = vt.get('vt1', {}).get('midpoint_watts', 0)
    metrics['vt2'] = vt.get('vt2', {}).get('midpoint_watts', 0)
    
    # CP from physiological markers or metadata
    physio = report.get('physiological_markers', {})
    metrics['cp'] = physio.get('cp', 0) or thresholds.get('cp_watts', 0)
    
    # W'
    metrics['w_prime'] = physio.get('w_prime', 0) or thresholds.get('w_prime_kj', 0)
    
    # Efficiency Factor
    metrics['ef'] = physio.get('efficiency_factor', 0)
    
    # SmO2 slope from SmO2 thresholds
    smo2 = thresholds.get('smo2', {})
    metrics['smo2_slope'] = smo2.get('regression_slope', 0) or smo2.get('slope', 0)
    
    # Occlusion Index from biomech
    biomech = report.get('biomechanical_analysis', {})
    metrics['occlusion_index'] = biomech.get('occlusion_index', 0)
    
    # HSI from thermal
    thermal = report.get('thermal_analysis', {})
    metrics['hsi'] = thermal.get('max_hsi', 0) or thermal.get('avg_hsi', 0)
    
    return metrics


def calculate_rate_per_week(values: List[float], dates: List[datetime]) -> float:
    """
    Calculate rate of change per week using linear regression.
    
    Returns % change per week relative to first value.
    """
    if len(values) < 2 or len(dates) < 2:
        return 0.0
    
    # Convert dates to days since first test
    first_date = dates[0]
    days = np.array([(d - first_date).days for d in dates])
    
    if days[-1] == 0:
        return 0.0
    
    # Linear regression
    try:
        slope, intercept = np.polyfit(days, values, 1)
    except:
        return 0.0
    
    # Convert to % per week
    # slope is change per day, multiply by 7 for per week
    weekly_change = slope * 7
    
    # Express as % of first value
    if values[0] != 0:
        rate_pct = (weekly_change / values[0]) * 100
    else:
        rate_pct = 0.0
    
    return round(rate_pct, 2)


def classify_direction(rate: float, is_inverse: bool = False) -> str:
    """
    Classify trend direction based on rate.
    
    Args:
        rate: % change per week
        is_inverse: True if lower is better (e.g., occlusion index)
    """
    threshold = 0.5  # 0.5% per week threshold for "stable"
    
    if is_inverse:
        rate = -rate
    
    if rate > threshold:
        return "improving"
    elif rate < -threshold:
        return "declining"
    else:
        return "stable"


def analyze_trends(reports: List[Dict[str, Any]]) -> TrendAnalysis:
    """
    Analyze trends across multiple ramp test reports.
    
    Returns TrendAnalysis with all metrics and classifications.
    """
    analysis = TrendAnalysis()
    
    if len(reports) < 2:
        logger.info("Need at least 2 tests for trend analysis")
        return analysis
    
    analysis.tests_analyzed = len(reports)
    
    # Extract metrics from each report
    all_metrics = []
    dates = []
    
    for report in reports:
        metrics = extract_metrics_from_report(report)
        test_date = report.get('_test_date')
        if test_date:
            all_metrics.append(metrics)
            dates.append(pd.to_datetime(test_date))
    
    if len(all_metrics) < 2:
        return analysis
    
    # Calculate date range
    analysis.date_range_days = (dates[-1] - dates[0]).days
    
    # Populate each metric trend
    metric_map = {
        'vt1': (analysis.vt1, False),
        'vt2': (analysis.vt2, False),
        'cp': (analysis.cp, False),
        'w_prime': (analysis.w_prime, False),
        'ef': (analysis.ef, False),
        'smo2_slope': (analysis.smo2_slope, True),  # More negative is worse
        'occlusion_index': (analysis.occlusion_index, True),  # Lower is better
        'hsi': (analysis.hsi, True),  # Lower is better
    }
    
    for metric_key, (trend, is_inverse) in metric_map.items():
        values = [m.get(metric_key, 0) for m in all_metrics]
        # Filter out zeros for proper trend calculation
        valid_pairs = [(v, d) for v, d in zip(values, dates) if v != 0]
        
        if len(valid_pairs) >= 2:
            trend.values = [p[0] for p in valid_pairs]
            trend.dates = [p[1] for p in valid_pairs]
            trend.rate_per_week = calculate_rate_per_week(trend.values, trend.dates)
            trend.direction = classify_direction(trend.rate_per_week, is_inverse)
    
    # Classify adaptation direction
    analysis.adaptation_direction = _classify_adaptation_direction(analysis)
    
    # Calculate engine map (normalized scores for radar chart)
    analysis.engine_map = _calculate_engine_map(analysis)
    
    # Calculate overall adaptation score
    analysis.adaptation_score = _calculate_adaptation_score(analysis)
    
    return analysis


def _classify_adaptation_direction(analysis: TrendAnalysis) -> str:
    """
    Classify overall adaptation direction based on metric trends.
    
    Returns: central, peripheral, thermal, or balanced
    """
    scores = {"central": 0, "peripheral": 0, "thermal": 0}
    
    # Central indicators: VT1, VT2, CP, EF
    if analysis.vt1.direction == "improving":
        scores["central"] += 2
    if analysis.vt2.direction == "improving":
        scores["central"] += 2
    if analysis.cp.direction == "improving":
        scores["central"] += 3
    if analysis.ef.direction == "improving":
        scores["central"] += 2
    
    # Peripheral indicators: SmO2 slope, Occlusion Index, W'
    if analysis.smo2_slope.direction == "improving":
        scores["peripheral"] += 3
    if analysis.occlusion_index.direction == "improving":
        scores["peripheral"] += 3
    if analysis.w_prime.direction == "improving":
        scores["peripheral"] += 2
    
    # Thermal indicators: HSI
    if analysis.hsi.direction == "improving":
        scores["thermal"] += 4
    
    # Find dominant direction
    max_score = max(scores.values())
    if max_score == 0:
        return "balanced"
    
    dominant = [k for k, v in scores.items() if v == max_score]
    
    if len(dominant) > 1:
        return "balanced"
    
    return dominant[0]


def _calculate_engine_map(analysis: TrendAnalysis) -> Dict[str, float]:
    """
    Calculate normalized engine map values for radar chart.
    
    Returns dict with values 0-100 for each metric.
    """
    engine_map = {}
    
    # Convert rate per week to 0-100 scale
    # Assuming ±5% per week is the extreme range
    def normalize_rate(rate: float, is_inverse: bool = False) -> float:
        if is_inverse:
            rate = -rate
        # Map -5% to 0, +5% to 100, 0% to 50
        normalized = 50 + (rate / 5) * 50
        return max(0, min(100, normalized))
    
    engine_map["VT1"] = normalize_rate(analysis.vt1.rate_per_week)
    engine_map["VT2"] = normalize_rate(analysis.vt2.rate_per_week)
    engine_map["CP"] = normalize_rate(analysis.cp.rate_per_week)
    engine_map["W'"] = normalize_rate(analysis.w_prime.rate_per_week)
    engine_map["EF"] = normalize_rate(analysis.ef.rate_per_week)
    engine_map["SmO2"] = normalize_rate(analysis.smo2_slope.rate_per_week, is_inverse=True)
    engine_map["Occlusion"] = normalize_rate(analysis.occlusion_index.rate_per_week, is_inverse=True)
    engine_map["HSI"] = normalize_rate(analysis.hsi.rate_per_week, is_inverse=True)
    
    return engine_map


def _calculate_adaptation_score(analysis: TrendAnalysis) -> float:
    """
    Calculate overall adaptation score (0-100).
    
    Higher = better overall adaptation.
    """
    # Weight each metric
    weights = {
        "cp": 0.25,
        "vt1": 0.15,
        "vt2": 0.15,
        "w_prime": 0.10,
        "ef": 0.10,
        "smo2_slope": 0.10,
        "occlusion_index": 0.08,
        "hsi": 0.07,
    }
    
    engine_map = analysis.engine_map
    
    score = 0
    for metric, weight in weights.items():
        # Map metric name to engine map key
        key_map = {
            "cp": "CP", "vt1": "VT1", "vt2": "VT2", "w_prime": "W'",
            "ef": "EF", "smo2_slope": "SmO2", "occlusion_index": "Occlusion", "hsi": "HSI"
        }
        key = key_map.get(metric, metric)
        score += engine_map.get(key, 50) * weight
    
    return round(score, 1)
