"""
SOLID: Single Responsibility Principle - Reorganizacja obliczeń.

Ten pakiet grupuje funkcje obliczeniowe według odpowiedzialności:
- w_prime.py: Obliczenia W' Balance
- hrv.py: Analiza HRV / DFA
- thermal.py: Indeks ciepła HSI
- power.py: NP, strefy mocy, PDC, FRI, Match Burns, TTE, Phenotype
- nutrition.py: Spalanie węglowodanów
- metrics.py: Podstawowe metryki treningowe
- stamina.py: Stamina Score, VLamax estimation, Durability
- kinetics.py: VO2/SmO2 kinetics analysis
- thresholds.py: VT1/VT2, LT1/LT2 threshold detection
- data_processing.py: Przetwarzanie danych
- async_runner.py: Async calculation wrappers
- polars_adapter.py: Polars/Pandas interoperability
- repeatability.py: Repeatability and stability analysis
- quality.py: Data reliability checks
- interpretation.py: Training advice generation

Dla wstecznej kompatybilności, wszystkie funkcje są re-eksportowane z tego modułu.
"""

# ============================================================
# Re-eksport dla wstecznej kompatybilności z istniejącym kodem
# Import: from modules.calculations import calculate_metrics
# nadal działa jak wcześniej
# ============================================================

from .w_prime import (
    calculate_w_prime_balance,
    calculate_w_prime_fast,
    # Recovery Score (NEW)
    calculate_recovery_score,
    get_recovery_recommendation,
    estimate_w_prime_reconstitution,
)

from .hrv import (
    calculate_dynamic_dfa_v2,
)

from .thermal import (
    calculate_heat_strain_index,
    calculate_thermal_decay,
)

from .power import (
    calculate_normalized_power,
    calculate_pulse_power_stats,
    # Advanced power analytics
    calculate_power_duration_curve,
    calculate_fatigue_resistance_index,
    count_match_burns,
    calculate_power_zones_time,
    get_fri_interpretation,
    DEFAULT_PDC_DURATIONS,
    # TTE & Phenotype (NEW)
    estimate_tte,
    estimate_tte_range,
    classify_phenotype,
    get_phenotype_description,
)

from .nutrition import (
    estimate_carbs_burned,
)

from .metrics import (
    calculate_metrics,
    calculate_advanced_kpi,
    calculate_z2_drift,
    calculate_vo2max,
    calculate_trend,
)

from .data_processing import (
    process_data,
    ensure_pandas,
)

from .stamina import (
    calculate_stamina_score,
    estimate_vlamax_from_pdc,
    get_stamina_interpretation,
    get_vlamax_interpretation,
    calculate_aerobic_contribution,
    calculate_durability_index,
    get_durability_interpretation,
)

from .kinetics import (
    fit_smo2_kinetics,
    get_tau_interpretation,
    calculate_o2_deficit,
    detect_smo2_breakpoints,
    normalize_smo2_series,
    detect_smo2_trend,
    classify_smo2_context,
    calculate_resaturation_metrics,
    calculate_signal_lag,
    analyze_temporal_sequence,
    detect_physiological_state,
    generate_state_timeline,
)

from .thresholds import (
    detect_vt_transition_zone,
    analyze_step_test,
    calculate_training_zones_from_thresholds,
)

from .threshold_types import (
    TransitionZone,
    ThresholdResult,
    StepTestResult,
    HysteresisResult,
    SensitivityResult,
)

from .repeatability import (
    calculate_cv,
    calculate_sem,
    classify_reproducibility,
    calculate_repeatability_metrics,
    compare_session_to_baseline,
)

from .quality import (
    check_signal_quality,
    check_step_test_protocol,
    check_data_suitability,
)

from .interpretation import (
    generate_training_advice,
)

# Async runner exports
from .async_runner import (
    run_in_thread,
    run_async,
    async_wrapper,
    AsyncCalculationManager,
    submit_task,
    get_executor,
)

# Polars adapter exports
from .polars_adapter import (
    is_polars_available,
    to_polars,
    to_pandas,
    ensure_polars,
    fast_rolling_mean,
    fast_groupby_agg,
    fast_filter,
    fast_read_csv,
    fast_normalized_power,
    fast_power_duration_curve,
)

# Eksport wszystkich symboli dla import *
__all__ = [
    # W' Balance
    'calculate_w_prime_balance',
    'calculate_w_prime_fast',
    # W' Recovery (NEW)
    'calculate_recovery_score',
    'get_recovery_recommendation',
    'estimate_w_prime_reconstitution',
    # HRV
    'calculate_dynamic_dfa_v2',
    # Thermal
    'calculate_heat_strain_index',
    'calculate_thermal_decay',
    # Power - Basic
    'calculate_normalized_power',
    'calculate_pulse_power_stats',
    # Power - Advanced
    'calculate_power_duration_curve',
    'calculate_fatigue_resistance_index',
    'count_match_burns',
    'calculate_power_zones_time',
    'get_fri_interpretation',
    'DEFAULT_PDC_DURATIONS',
    # Power - TTE & Phenotype (NEW)
    'estimate_tte',
    'estimate_tte_range',
    'classify_phenotype',
    'get_phenotype_description',
    # Nutrition
    'estimate_carbs_burned',
    # Metrics
    'calculate_metrics',
    'calculate_advanced_kpi',
    'calculate_z2_drift',
    'calculate_vo2max',
    'calculate_trend',
    # Stamina
    'calculate_stamina_score',
    'estimate_vlamax_from_pdc',
    'get_stamina_interpretation',
    'get_vlamax_interpretation',
    'calculate_aerobic_contribution',
    # Durability
    'calculate_durability_index',
    'get_durability_interpretation',
    # Kinetics
    'fit_smo2_kinetics',
    'get_tau_interpretation',
    'calculate_o2_deficit',
    'detect_smo2_breakpoints',
    'normalize_smo2_series',
    'detect_smo2_trend',
    'classify_smo2_context',
    'calculate_resaturation_metrics',
    'calculate_signal_lag',
    'analyze_temporal_sequence',
    'detect_physiological_state',
    'generate_state_timeline',
    # Thresholds (MCP)
    'detect_vt_transition_zone',
    'analyze_step_test',
    'calculate_training_zones_from_thresholds',
    'TransitionZone',
    'ThresholdResult',
    'StepTestResult',
    'HysteresisResult',
    'SensitivityResult',
    # Repeatability
    'calculate_cv',
    'calculate_sem',
    'classify_reproducibility',
    'calculate_repeatability_metrics',
    'compare_session_to_baseline',
    # Quality
    'check_signal_quality',
    'check_step_test_protocol',
    'check_data_suitability',
    # Interpretation
    'generate_training_advice',
    # Data Processing
    'process_data',
    'ensure_pandas',
    # Async Runner
    'run_in_thread',
    'run_async',
    'async_wrapper',
    'AsyncCalculationManager',
    # Polars Adapter
    'is_polars_available',
    'to_polars',
    'to_pandas',
    'fast_rolling_mean',
    'fast_normalized_power',
    'fast_power_duration_curve',
]
