# Physiological Methodology & Assumptions

## 1. Executive Summary
This document outlines the physiological assumptions, algorithms, and thresholds currently implemented in the **Tri_Dashboard** application for analyzing Ventilatory Thresholds (VT) and Muscle Oxygen Saturation (SmO₂) kinetics. It serves as a basis for validation and hypothesis testing.

## 2. Methodology & Algorithms

### 2.1. Signal Processing
Data smoothing is applied to reduce signal noise before analysis:
*   **Power (Watts):** 5-second moving average (centered).
*   **Ventilation (VE):** 10-second moving average (centered).
*   **SmO₂:** 3-second or 10-second moving average (context-dependent).
*   **Slope Calculation:** Linear regression (`scipy.stats.linregress`) performed over the duration of a selected step or interval.

### 2.2. Threshold Detection Logic
The application uses **Slope Change Detection** to identify physiological breakpoints. It assumes that specific changes in the rate of change (slope) of VE or SmO₂ correspond to specific metabolic domains.

#### Ventilatory Thresholds (VT) via Minute Ventilation (VE)
The code (`thresholds.py`, `vent.py`) segments exercise intensity based on the slope of VE vs. Time (L/min per second).

| Zone | Physiological Interpretation | Implied Assumption (Metric: VE Slope) |
| :--- | :--- | :--- |
| **Recovery** | Below aerobic engagement | `slope < 0.02` |
| **Aerobic (Z2)** | Below VT1 | `0.02 <= slope <= 0.05` |
| **Threshold (Z3-Z4)** | Between VT1 and VT2 | `0.05 < slope <= 0.15` |
| **VO2max/Anaerobic** | Above VT2 (Respiratory Compensation) | `slope > 0.15` |

#### Metabolic Thresholds (LT) via Muscle Oxygen (SmO₂)
The code (`thresholds.py`, `smo2.py`) segments intensity based on the desaturation trend of SmO₂ vs. Time (% per second).

| Zone | Physiological Interpretation | Implied Assumption (Metric: SmO₂ Slope) |
| :--- | :--- | :--- |
| **Recovery/Luxury** | Oxygen Supply > Demand | `slope > 0.005` |
| **Steady State (LT1-LT2)** | Oxygen Supply ≈ Demand | `-0.005 <= slope <= 0.005` |
| **Approaching LT2** | Slow desaturation | `-0.01 <= slope < -0.005` |
| **Severe Domain (>LT2)** | High O₂ Deficit / Instability | `slope < -0.01` |

### 2.3. SmO₂ Kinetics (Tau)
The application fits a **Mono-Exponential Model** to SmO₂ onset kinetics:
$$ SmO_2(t) = A \cdot (1 - e^{-(t - td)/\tau}) $$

**Interpretation of Time Constant ($\tau$):**
*   **< 15s:** Excellent (Elite oxidative capacity)
*   **15s - 25s:** Good
*   **25s - 40s:** Moderate
*   **40s - 60s:** Slow
*   **> 60s:** Very Slow

---

## 3. Explicit Physiological Assumptions

### Assumption 1: Fixed Slope Universality
**Current Logic:** The slope thresholds (e.g., `0.05` for VT1, `-0.01` for LT2) are hardcoded constants.
**Physiological Implication:** Assumes these rate-of-change values are universal across different athletes, lung volumes, and step test protocols (e.g., 1-minute steps vs. 3-minute steps).

### Assumption 2: Linear vs. Non-Linear Breakpoints
**Current Logic:** Using discrete slope "buckets" implies that transitions are sharp and align perfectly with these numeric cutoffs.
**Physiological Implication:** Assumes that the "Aerobic Threshold" is always marked by a transition from a slope of 0.005 to negative, ignoring potential "slow component" drifts that might occur below LT1 in fatigued states.

### Assumption 3: SmO₂ Representative of Systemic Metabolism
**Current Logic:** SmO₂ thresholds (LT1/LT2) derived from a local muscle sensor (e.g., vastus lateralis) are used to prescribe systemic training zones.
**Physiological Implication:** Assumes that the locomotor muscle interrogated is the primary limiter and its metabolic state perfectly reflects systemic lactate turning points.

---

## 4. Testable Hypotheses
*Rewritten from assumptions for validation.*

### Hypothesis 1 (VT1 Detection)
> **If** a subject exercises at an intensity where the VE slope exceeds **0.05 L/min/s**, **then** their blood lactate concentration is rising above resting baseline (>2 mmol/L), indicating the transition from moderate to heavy intensity domain.

### Hypothesis 2 (VT2/RCP Detection)
> **If** the VE slope exceeds **0.15 L/min/s** during a ramp test, **then** the subject has exceeded their Critical Power (CP) or Respiratory Compensation Point (RCP), as evidenced by a disproportionate increase in VE relative to VCO₂ (hyperventilation).

### Hypothesis 3 (SmO₂ Steady State)
> **If** the slope of SmO₂ remains between **-0.005 and +0.005 %/s** over a 3-minute interval, **then** the athlete is exercising within the heavy intensity domain (between LT1 and LT2), where lactate production and clearance are in equilibrium (Maximal Lactate Steady State not yet exceeded).

### Hypothesis 4 (Severe Domain Onset)
> **If** SmO₂ desaturation exceeds a rate of **-0.01 %/s**, **then** the athlete is operating in the severe intensity domain (>LT2), leading to rapid depletion of W' (anaerobic work capacity) and eventual task failure.

---

## 5. Critique: Unsupported or Ambiguous Areas

1.  **Arbitrary Thresholds:** The values `0.05`, `0.15`, `-0.01`, etc., lack citation or dynamic adjustment mechanisms. They do not account for:
    *   **Protocol sensitivity:** A 1-minute step ramp will produce different slopes than a 3-minute step test.
    *   **Subject variability:** A small female athlete with max VE of 80 L/min will have different slopes than a large rower with max VE of 200 L/min.
2.  **Noise Sensitivity:** `linregress` is sensitive to outliers. A single deep breath or sensor artifact could skew the slope into a different "zone" bucket.
3.  **Kinetics Model Simplicity:** The mono-exponential model assumes a simple delay (`td`) and onset (`tau`). It does not account for the "slow component" of O₂ kinetics often seen in heavy/severe exercise.
