# Power-Duration Curve & Critical Power Model

## Overview

The power-duration module (`modules/power_duration.py`) provides advanced analysis of cycling power data:

1. **Mean Maximal Power (MMP)** calculation for durations from 1s to 60min
2. **Critical Power (CP) model** fitting using non-linear regression
3. **Personal Record (PR)** detection against historical bests
4. **Log-log visualization** with historical curve overlays
5. **Manual history acceptance** to control which sessions update records

## Mathematical Model

The Critical Power model is a hyperbolic relationship:

```
P(t) = W'/t + CP
```

Where:
- **P(t)** = Power sustainable for duration t
- **CP** = Critical Power (sustainable indefinitely in theory)
- **W'** = Anaerobic Work Capacity (finite energy above CP)

## Usage

```python
from modules.power_duration import (
    compute_max_mean_power,
    fit_critical_power,
    detect_personal_records,
    plot_power_duration
)

# Load power data (1Hz required)
power_series = df['power']

# Compute MMP
pdc = compute_max_mean_power(power_series)

# Fit CP model (uses 2-20 min data by default)
cp_model = fit_critical_power(
    durations=list(pdc.keys()),
    max_mean_powers=list(pdc.values())
)

print(f"CP = {cp_model.cp:.0f} W")
print(f"W' = {cp_model.w_prime/1000:.1f} kJ")

# Detect PRs
prs = detect_personal_records(current_pdc=pdc, history_pdc=historical_best)

# Create log-log chart
fig = plot_power_duration(
    current_pdc=pdc,
    cp_model=cp_model,
    history_30d=pdc_30d,
    personal_records=prs
)
```

## Exports

| Function | Output |
|----------|--------|
| `export_model_json(cp_model, path)` | JSON with CP, W', RMSE, R² |
| `export_pr_csv(prs, path)` | CSV with duration, power, timestamp |
| `export_chart_png(fig, path)` | High-resolution PNG image |

## Testing

```bash
pytest tests/test_power_duration.py -v
```
