"""
SOLID: Single Responsibility Principle - Reorganizacja obliczeń.

Ten pakiet grupuje funkcje obliczeniowe według odpowiedzialności:
- hrv.py: Analiza HRV / DFA
- thermal.py: Indeks ciepła HSI
- nutrition.py: Spalanie węglowodanów
- metrics.py: Podstawowe metryki treningowe
- pace.py: Tempo, strefy tempa, PDC, RSS, GAP
- dual_mode.py: Normalized Pace, RSS, running stress
- running_dynamics.py: Kadencja, GCT, stride length, VO
- data_processing.py: Przetwarzanie danych
- polars_adapter.py: Polars/Pandas interoperability
- repeatability.py: Repeatability and stability analysis
- quality.py: Data reliability checks
- interpretation.py: Training advice generation
- thresholds.py: VT1/VT2, LT1/LT2 threshold detection

Dla wstecznej kompatybilności, wszystkie funkcje są re-eksportowane z tego modułu.
"""

# ============================================================
# Re-eksport dla wstecznej kompatybilności z istniejącym kodem
# Import: from modules.calculations import calculate_metrics
# nadal działa jak wcześniej
# ============================================================

# Async runner exports
from .async_runner import (
    AsyncCalculationManager,
    async_wrapper,
    get_executor,
    run_async,
    run_in_thread,
    submit_task,
)
from .data_processing import ensure_pandas, process_data
from .hrv import calculate_dynamic_dfa_v2
from .interpretation import generate_training_advice
from .kinetics import (
    analyze_temporal_sequence,
    calculate_o2_deficit,
    calculate_resaturation_metrics,
    calculate_signal_lag,
    classify_smo2_context,
    detect_physiological_state,
    detect_smo2_breakpoints,
    detect_smo2_trend,
    fit_smo2_kinetics,
    generate_state_timeline,
    get_tau_interpretation,
    normalize_smo2_series,
)
from .metrics import (
    calculate_advanced_kpi,
    calculate_metrics,
    calculate_trend,
    calculate_vo2max,
    calculate_z2_drift,
)
from .nutrition import estimate_carbs_burned

# Polars adapter exports
from .polars_adapter import (
    ensure_polars,
    fast_filter,
    fast_groupby_agg,
    fast_normalized_power,
    fast_power_duration_curve,
    fast_read_csv,
    fast_rolling_mean,
    is_polars_available,
    to_pandas,
    to_polars,
)
from .power import (
    DEFAULT_PDC_DURATIONS,
    calculate_fatigue_resistance_index,
    calculate_normalized_power,
    calculate_power_duration_curve,
    calculate_power_zones_time,
    calculate_pulse_power_stats,
    classify_phenotype,
    count_match_burns,
    estimate_tte,
    estimate_tte_range,
    get_fri_interpretation,
    get_phenotype_description,
)
from .quality import check_data_suitability, check_signal_quality, check_step_test_protocol
from .repeatability import (
    calculate_cv,
    calculate_repeatability_metrics,
    calculate_sem,
    classify_reproducibility,
    compare_session_to_baseline,
)
from .stamina import (
    calculate_aerobic_contribution,
    calculate_durability_index,
    calculate_stamina_score,
    estimate_vlamax_from_pdc,
    get_durability_interpretation,
    get_stamina_interpretation,
    get_vlamax_interpretation,
)
from .thermal import calculate_heat_strain_index, calculate_thermal_decay
from .threshold_types import (
    HysteresisResult,
    SensitivityResult,
    StepTestResult,
    ThresholdResult,
    TransitionZone,
)
from .thresholds import (
    analyze_step_test,
    calculate_training_zones_from_thresholds,
    detect_vt_transition_zone,
)
from .w_prime import (
    calculate_recovery_score,
    calculate_w_prime_balance,
    calculate_w_prime_fast,
    estimate_w_prime_reconstitution,
    get_recovery_recommendation,
)

# Eksport wszystkich symboli dla import *
__all__ = [
    # W' Balance
    "calculate_w_prime_balance",
    "calculate_w_prime_fast",
    # W' Recovery (NEW)
    "calculate_recovery_score",
    "get_recovery_recommendation",
    "estimate_w_prime_reconstitution",
    # HRV
    "calculate_dynamic_dfa_v2",
    # Thermal
    "calculate_heat_strain_index",
    "calculate_thermal_decay",
    # Power - Basic
    "calculate_normalized_power",
    "calculate_pulse_power_stats",
    # Power - Advanced
    "calculate_power_duration_curve",
    "calculate_fatigue_resistance_index",
    "count_match_burns",
    "calculate_power_zones_time",
    "get_fri_interpretation",
    "DEFAULT_PDC_DURATIONS",
    # Power - TTE & Phenotype (NEW)
    "estimate_tte",
    "estimate_tte_range",
    "classify_phenotype",
    "get_phenotype_description",
    # Nutrition
    "estimate_carbs_burned",
    # Metrics
    "calculate_metrics",
    "calculate_advanced_kpi",
    "calculate_z2_drift",
    "calculate_vo2max",
    "calculate_trend",
    # Stamina
    "calculate_stamina_score",
    "estimate_vlamax_from_pdc",
    "get_stamina_interpretation",
    "get_vlamax_interpretation",
    "calculate_aerobic_contribution",
    # Durability
    "calculate_durability_index",
    "get_durability_interpretation",
    # Kinetics
    "fit_smo2_kinetics",
    "get_tau_interpretation",
    "calculate_o2_deficit",
    "detect_smo2_breakpoints",
    "normalize_smo2_series",
    "detect_smo2_trend",
    "classify_smo2_context",
    "calculate_resaturation_metrics",
    "calculate_signal_lag",
    "analyze_temporal_sequence",
    "detect_physiological_state",
    "generate_state_timeline",
    # Thresholds (MCP)
    "detect_vt_transition_zone",
    "analyze_step_test",
    "calculate_training_zones_from_thresholds",
    "TransitionZone",
    "ThresholdResult",
    "StepTestResult",
    "HysteresisResult",
    "SensitivityResult",
    # Repeatability
    "calculate_cv",
    "calculate_sem",
    "classify_reproducibility",
    "calculate_repeatability_metrics",
    "compare_session_to_baseline",
    # Quality
    "check_signal_quality",
    "check_step_test_protocol",
    "check_data_suitability",
    # Interpretation
    "generate_training_advice",
    # Data Processing
    "process_data",
    "ensure_pandas",
    # Async Runner
    "run_in_thread",
    "run_async",
    "async_wrapper",
    "AsyncCalculationManager",
    # Polars Adapter
    "is_polars_available",
    "to_polars",
    "to_pandas",
    "fast_rolling_mean",
    "fast_normalized_power",
    "fast_power_duration_curve",
]
