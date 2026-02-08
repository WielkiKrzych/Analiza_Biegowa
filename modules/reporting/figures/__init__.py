"""
Static Figure Generator for Ramp Test PDF Reports.
Orchestrates figure generation for various chart types.
"""
from pathlib import Path
from typing import Dict, Any, Optional

from .common import DPI, get_color, save_figure
from .ramp_profile import generate_ramp_profile_chart
from .smo2_vs_power import generate_smo2_power_chart
from .cp_curve import generate_cp_curve_chart, generate_pdc_chart
from .ve_profile import generate_ve_profile_chart
from .thermal import generate_thermal_chart, generate_efficiency_chart
from .limiters import generate_radar_chart, generate_vlamax_balance_chart
from .vent_full import generate_full_vent_chart
from .drift import generate_power_hr_scatter, generate_power_smo2_scatter, generate_drift_heatmap
from .biomech import generate_biomech_chart, generate_torque_smo2_chart


def generate_all_ramp_figures(
    report_data: Dict[str, Any],
    output_dir: str,
    config: Optional[Any] = None,
    source_df: Optional["pd.DataFrame"] = None,
    manual_overrides: Optional[Dict[str, Any]] = None
) -> Dict[str, str]:
    """Generate all ramp test figures and save to directory.
    
    Args:
        report_data: Canonical JSON report dictionary
        output_dir: Directory to save figures
        config: Optional configuration dictionary or object
        source_df: Optional source DataFrame with raw data
        manual_overrides: Dict of manual threshold values that override saved values
            (VT1/VT2 watts, SmO2 LT1/LT2, etc.)
        
    Returns:
        Dict mapping figure name to file path
    """
    config = config or {}
    manual_overrides = manual_overrides or {}
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    session_id = report_data.get("metadata", {}).get("session_id", "unknown")[:8]
    
    # Handle config as dict if passed, or use attributes
    if isinstance(config, dict):
        ext = config.get('format', 'png')
        # Merge manual_overrides into config for passing to generators
        config['manual_overrides'] = manual_overrides
    else:
        ext = getattr(config, 'format', 'png')
        # If config is object, add manual_overrides as attribute
        if hasattr(config, '__dict__'):
            config.__dict__['manual_overrides'] = manual_overrides
    
    paths = {}
    failed_charts = []
    
    # helper to generate path and run function
    def add_fig(name, fn, args=None, needs_df=True):
        fpath = output_path / f"{name}_{session_id}.{ext}"
        try:
            if needs_df:
                fn(report_data, config, str(fpath), source_df=source_df)
            else:
                fn(report_data, config, str(fpath))
            paths[name] = str(fpath)
            print(f"[Figures] ✔ Generated: {name}")
        except Exception as e:
            import logging
            logging.getLogger("figures").error(f"Failed to generate {name}: {e}")
            failed_charts.append(f"{name}: {e}")
            print(f"[Figures] ✗ FAILED: {name} - {e}")

    # 1. Core
    add_fig("ramp_profile", generate_ramp_profile_chart)
    add_fig("smo2_power", generate_smo2_power_chart)
    add_fig("pdc_curve", generate_pdc_chart, needs_df=False)
    add_fig("ve_profile", generate_ve_profile_chart)
    
    # 2. Thermal
    add_fig("thermal_hsi", generate_thermal_chart)
    add_fig("thermal_efficiency", generate_efficiency_chart)
    
    # 3. Model & Limiters
    add_fig("limiters_radar", generate_radar_chart)
    add_fig("vlamax_balance", generate_vlamax_balance_chart)
    
    # 4. Drift & Decoupling
    add_fig("drift_hr", generate_power_hr_scatter)
    add_fig("drift_smo2", generate_power_smo2_scatter)
    
    # NEW: Heatmaps
    add_fig("drift_heatmap_hr", lambda *a, **k: generate_drift_heatmap(*a, mode="hr", **k))
    add_fig("drift_heatmap_smo2", lambda *a, **k: generate_drift_heatmap(*a, mode="smo2", **k))
    
    # 5. Biomech
    add_fig("biomech_summary", generate_biomech_chart)
    add_fig("biomech_torque_smo2", generate_torque_smo2_chart)
    
    # 6. Optional: Vent Full
    add_fig("vent_full", generate_full_vent_chart)
    
    # Summary log
    print(f"[Figures] Summary: {len(paths)} generated, {len(failed_charts)} failed")
    if failed_charts:
        print(f"[Figures] Failed charts: {failed_charts}")
    
    return paths


__all__ = [
    "generate_all_ramp_figures",
    "generate_ramp_profile_chart",
    "generate_smo2_power_chart",
    "generate_pdc_chart",
    "generate_cp_curve_chart",
    "generate_vlamax_balance_chart",
    "generate_biomech_chart",
    "generate_drift_heatmap",
    "DPI",
]
