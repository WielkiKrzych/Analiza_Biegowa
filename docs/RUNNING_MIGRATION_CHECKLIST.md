# Running Migration Checklist

## Core Modules
- [x] settings.py - runner_ prefix, threshold_pace, d_prime
- [x] pace_utils.py - pace/speed conversions
- [x] pace.py - zones, PDC, phenotype
- [x] d_prime.py - anaerobic distance capacity
- [x] running_dynamics.py - cadence, GCT, stride
- [x] gap.py - Grade-Adjusted Pace
- [x] race_predictor.py - Riegel formula
- [x] dual_mode.py - pace+power support

## Domain Models
- [x] session_type.py - progressive run detection

## UI Components
- [x] modules/ui/running.py - pace charts
- [x] app.py - updated for running params

## Testing
- [x] Unit tests (21 tests passing)
- [x] Integration tests

## Migration Summary

| Cycling | Running |
|---------|---------|
| Power (W) | Pace (min/km) |
| Critical Power (CP) | Critical Speed + Threshold Pace |
| W' (Joules) | D' (meters) |
| Normalized Power (NP) | Normalized Pace |
| TSS | RSS (Running Stress Score) |
| Cadence (RPM) | Cadence (SPM) |
| Ramp Test | Progressive Run |
