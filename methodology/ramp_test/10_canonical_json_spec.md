# Ramp Test Canonical Report Structure

## Specyfikacja JSON v1.0

> **Cel:** Pełny zapis wyniku testu, niezależny od UI, wystarczający do ponownej interpretacji.

---

## 1. Struktura Główna

```json
{
  "$schema": "ramp_test_result_v1.json",
  "version": "1.0.0",
  "metadata": { ... },
  "test_validity": { ... },
  "thresholds": { ... },
  "smo2_context": { ... },
  "conflicts": { ... },
  "raw_signals": { ... },
  "interpretation": { ... }
}
```

---

## 2. Sekcja: `metadata` (REQUIRED)

```json
"metadata": {
  "test_date": "2026-01-02",
  "test_time": "10:30:00",
  "analysis_timestamp": "2026-01-02T10:45:23Z",
  "method_version": "1.0.0",
  "protocol": {
    "type": "step_test",
    "step_duration_sec": 180,
    "power_increment_watts": 25,
    "starting_power_watts": 100
  },
  "athlete_id": "optional_hash",
  "session_id": "uuid",
  "source_file": "session_20260102.csv",
  "analyzer": "Tri_Dashboard/ramp_pipeline",
  "notes": "Optional free text"
}
```

| Pole | Typ | Required | Opis |
|------|-----|----------|------|
| test_date | string (ISO date) | ✅ | Data testu |
| analysis_timestamp | string (ISO datetime) | ✅ | Czas analizy |
| method_version | string (semver) | ✅ | Wersja algorytmu |
| protocol | object | ✅ | Parametry protokołu |
| athlete_id | string | ❌ | Opcjonalny identyfikator |
| session_id | string | ✅ | UUID sesji |

---

## 3. Sekcja: `test_validity` (REQUIRED)

```json
"test_validity": {
  "status": "conditional",
  "issues": ["Rampa 7 min (zalecane ≥8 min)"],
  "metrics": {
    "ramp_duration_sec": 420,
    "power_range_watts": 180,
    "exhaustion_reached": true,
    "rpe_final": 9
  },
  "signal_quality": {
    "power": {"quality_score": 0.98, "artifact_ratio": 0.01},
    "hr": {"quality_score": 0.92, "artifact_ratio": 0.05},
    "smo2": {"quality_score": 0.85, "artifact_ratio": 0.08}
  }
}
```

| Pole | Typ | Wartości | Opis |
|------|-----|----------|------|
| status | enum | `valid`, `conditional`, `invalid` | Ważność testu |
| issues | array[string] | — | Lista problemów |
| metrics | object | — | Metryki jakości |
| signal_quality | object | — | Jakość per sygnał |

---

## 4. Sekcja: `thresholds` (REQUIRED jeśli wykryto)

```json
"thresholds": {
  "vt1": {
    "range_watts": [175, 195],
    "midpoint_watts": 185,
    "range_hr": [138, 148],
    "midpoint_hr": 143,
    "confidence": 0.72,
    "confidence_level": "medium",
    "sources": ["VE", "SmO2"],
    "method": "step_ve_slope_range",
    "stability_score": 0.65,
    "variability_watts": 8.5,
    "step_number": 5
  },
  "vt2": {
    "range_watts": [230, 260],
    "midpoint_watts": 245,
    "range_hr": [165, 175],
    "midpoint_hr": 170,
    "confidence": 0.55,
    "confidence_level": "medium",
    "sources": ["VE"],
    "method": "step_ve_slope_range",
    "stability_score": 0.50,
    "variability_watts": 15.0,
    "step_number": 8
  }
}
```

| Pole | Typ | Required | Opis |
|------|-----|----------|------|
| range_watts | array[2] | ✅ | [lower, upper] |
| midpoint_watts | number | ✅ | Wartość centralna |
| confidence | number (0-1) | ✅ | Pewność detekcji |
| confidence_level | enum | ✅ | `high`/`medium`/`low` |
| sources | array[string] | ✅ | Źródła detekcji |
| method | string | ✅ | Metoda detekcji |

> ⚠️ **NIGDY** nie zapisuj progu jako pojedynczej liczby. Zawsze `range_watts`.

---

## 5. Sekcja: `smo2_context` (REQUIRED jeśli SmO₂ dostępne)

```json
"smo2_context": {
  "signal_type": "LOCAL",
  "is_threshold_source": false,
  "drop_point": {
    "range_watts": [165, 185],
    "midpoint_watts": 175,
    "confidence": 0.45
  },
  "deviation_from_vt1_watts": -10,
  "modulation_applied": {
    "confidence_adjustment": 0.15,
    "range_adjustment_percent": -10
  },
  "interpretation": "SmO₂ (LOCAL) potwierdza VT → confidence zwiększone",
  "limitations": [
    "SmO₂ mierzy JEDEN mięsień",
    "Nie zastępuje VT z wentylacji"
  ]
}
```

| Pole | Typ | Required | Opis |
|------|-----|----------|------|
| signal_type | enum | ✅ | Zawsze `"LOCAL"` |
| is_threshold_source | boolean | ✅ | Zawsze `false` |
| deviation_from_vt1_watts | number | ✅ | Różnica vs VT1 |
| modulation_applied | object | ✅ | Jak wpłynął na VT |

---

## 6. Sekcja: `conflicts` (REQUIRED)

```json
"conflicts": {
  "agreement_score": 0.85,
  "signals_analyzed": ["VE", "HR", "SmO2 (LOCAL)"],
  "detected": [
    {
      "type": "smo2_early",
      "severity": "warning",
      "signal_a": "SmO2 (LOCAL)",
      "signal_b": "VE",
      "description": "SmO₂ reaguje 15 W wcześniej niż VT",
      "physiological_interpretation": "Limit lokalny przed systemowym",
      "magnitude_watts": 15,
      "confidence_penalty": 0.1
    }
  ],
  "recommendations": ["VT prawidłowe, SmO₂ wskazuje potencjał poprawy"]
}
```

| Pole | Typ | Required | Opis |
|------|-----|----------|------|
| agreement_score | number (0-1) | ✅ | Zgodność sygnałów |
| detected | array | ✅ | Lista konfliktów (może być pusta) |
| confidence_penalty | number | ✅ | Kara per konflikt |

---

## 7. Sekcja: `raw_signals` (OPTIONAL ale zalecane)

```json
"raw_signals": {
  "included": true,
  "compression": "gzip",
  "encoding": "base64",
  "columns": ["time", "power", "hr", "smo2", "ve"],
  "sampling_hz": 1,
  "data_points": 600,
  "data": "H4sIAAAAAAAAA..."
}
```

> Przechowywanie surowych danych umożliwia ponowną analizę.

---

## 8. Sekcja: `interpretation` (REQUIRED)

```json
"interpretation": {
  "overall_confidence": 0.68,
  "confidence_level": "medium",
  "language_qualifier": "prawdopodobnie",
  "can_generate_zones": true,
  "training_zones": {
    "z1_recovery": [0, 130],
    "z2_endurance": [130, 175],
    "z3_tempo": [175, 210],
    "z4_threshold": [210, 245],
    "z5_vo2max": [245, 300]
  },
  "warnings": ["Dane o średniej pewności"],
  "notes": ["VT2 szeroki zakres"]
}
```

---

## 9. Pola Obowiązkowe (Summary)

| Sekcja | Pole | Required |
|--------|------|----------|
| metadata | test_date, method_version, session_id | ✅ |
| test_validity | status, issues | ✅ |
| thresholds.vt1 | range_watts, confidence, sources | ✅ jeśli VT1 |
| thresholds.vt2 | range_watts, confidence, sources | ✅ jeśli VT2 |
| smo2_context | signal_type, is_threshold_source | ✅ jeśli SmO₂ |
| conflicts | agreement_score, detected | ✅ |
| interpretation | overall_confidence | ✅ |

---

## 10. Wersjonowanie

```
method_version: "MAJOR.MINOR.PATCH"

MAJOR: Zmiana algorytmu (wyniki nieporównywalne)
MINOR: Nowe funkcje (wyniki porównywalne)
PATCH: Bugfix (wyniki identyczne)
```

---

## 11. Przykład Minimalny (Valid Test)

```json
{
  "$schema": "ramp_test_result_v1.json",
  "version": "1.0.0",
  "metadata": {
    "test_date": "2026-01-02",
    "analysis_timestamp": "2026-01-02T10:45:23Z",
    "method_version": "1.0.0",
    "session_id": "abc123",
    "protocol": {"type": "step_test"}
  },
  "test_validity": {
    "status": "valid",
    "issues": []
  },
  "thresholds": {
    "vt1": {
      "range_watts": [180, 200],
      "midpoint_watts": 190,
      "confidence": 0.85,
      "confidence_level": "high",
      "sources": ["VE"]
    }
  },
  "conflicts": {
    "agreement_score": 1.0,
    "detected": []
  },
  "interpretation": {
    "overall_confidence": 0.85,
    "confidence_level": "high"
  }
}
```

---

*Specyfikacja v1.0 — 2026-01-02*
