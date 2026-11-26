"""Shared calculations used by the session and its views."""

from .data_processing import process_data
from .metrics import calculate_advanced_kpi, calculate_metrics, calculate_trend, calculate_z2_drift
from .nutrition import estimate_carbs_burned
from .power import calculate_normalized_power, calculate_power_duration_curve
from .thermal import calculate_heat_strain_index, calculate_thermal_decay
from .w_prime import calculate_w_prime_balance
