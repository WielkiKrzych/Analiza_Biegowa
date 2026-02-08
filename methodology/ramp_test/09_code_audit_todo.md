# TODO Refaktoru: Kod vs Metodologia Ramp Test

## Legenda

- ✅ **Zgodne** — kod jest zgodny z metodologią
- ⚠️ **Wykracza** — kod robi więcej niż metodologia
- 🔴 **Zbyt agresywne** — kod podejmuje decyzje bez wystarczających podstaw
- ❌ **Punktowe progi** — kod implikuje punkty zamiast przedziałów
- ⛔ **Brak confidence** — decyzja bez oceny jakości sygnału

---

## 1. FRAGMENTY ZGODNE Z METODOLOGIĄ ✅

| Plik | Lokalizacja | Opis |
|------|-------------|------|
| `metabolic.py` | L55 | `is_supporting_only=True` — SmO₂ jako sygnał wspierający ✅ |
| `metabolic.py` | L23–37 | Dokumentacja ograniczeń SmO₂ jako sygnału lokalnego ✅ |
| `threshold_types.py` | `StepSmO2Result` | Pole `limitations` i `get_interpretation_note()` ✅ |
| `threshold_types.py` | `TransitionZone` | Ma `range_watts`, `confidence`, `stability_score` ✅ |
| `ventilatory.py` | `detect_vt_transition_zone` | Zwraca `TransitionZone` z przedziałem ✅ |
| `ventilatory.py` | `run_sensitivity_analysis` | Ocena stabilności VT ✅ |

---

## 2. FRAGMENTY DO REFAKTORU

### 2.1 Punktowe Progi Zamiast Przedziałów ❌

| Plik | Linia | Problem | TODO |
|------|-------|---------|------|
| `ventilatory.py` | L140 | `result.vt1_watts = round(v1_stage['avg_power'], 0)` — **punkt** | Zwracaj przedział `(lower, upper)` |
| `ventilatory.py` | L152 | `result.vt2_watts = round(...)` — **punkt** | j.w. |
| `metabolic.py` | L97 | `result.smo2_1_watts = item['avg_power']` — **punkt** | Zwracaj przedział lub zaznacz jako "punkt środkowy" |
| `threshold_types.py` | L85–86 | `StepTestResult.vt1_watts`, `vt2_watts` — **pola punktowe** | Dodaj `vt1_range`, `vt2_range` |
| `threshold_types.py` | L132–138 | `StepVTResult.vt1_watts`, `vt2_watts` — **pola punktowe** | j.w. |

### 2.2 Brak Confidence Score ⛔

| Plik | Linia | Problem | TODO |
|------|-------|---------|------|
| `ventilatory.py` | L140–146 | VT1 wykryte bez `confidence` | Oblicz confidence na podstawie: liczby zgodnych sygnałów, wyrazistości załamania |
| `ventilatory.py` | L150–158 | VT2 wykryte bez `confidence` | j.w. |
| `metabolic.py` | L97–103 | SmO₂ LT1 bez `confidence` | Dodaj confidence (niski, bo lokalny sygnał) |
| `thresholds.py` | L65–80 | VT z `detect_vt_from_steps` kopiowane bez confidence | Przekazuj confidence z detektora |

### 2.3 Strefy Obliczane Bez Jakości ⛔

| Plik | Linia | Problem | TODO |
|------|-------|---------|------|
| `thresholds.py` | L122–142 | `calculate_training_zones_from_thresholds` — brak parametru `confidence` | Dodaj parametr confidence, zwracaj ostrzeżenie przy niskiej pewności |
| `thresholds.py` | L129 | Strefy HR oparte na `max_hr` (stała) — brak walidacji | Pozwól na pominięcie stref HR jeśli brak danych |

### 2.4 Zbyt Agresywne Decyzje 🔴

| Plik | Linia | Problem | TODO |
|------|-------|---------|------|
| `ventilatory.py` | L133 | `search(0, 0.10)` — hardcoded threshold spike | Uzasadnij dlaczego 0.10, dokumentuj |
| `ventilatory.py` | L79–80 | `vt1_slope_threshold=0.05, vt2_slope_threshold=0.05` — identyczne progi | Różne progi dla VT1/VT2 zgodnie z fizjologią |
| `ventilatory.py` | L194, L196 | Hardcoded progi `0.05`, `0.15` bez kontekstu | Dokumentuj pochodzenie progów |

### 2.5 Brak Walidacji Testu ⛔

| Plik | Lokalizacja | Problem | TODO |
|------|-------------|---------|------|
| `thresholds.py` | `analyze_step_test` | Brak sprawdzenia ważności testu (czas rampy, artefakty) | Dodaj `TestValidator` przed analizą |
| `thresholds.py` | L44–52 | Sprawdza tylko obecność kolumn, nie jakość danych | Zliczaj artefakty, przerwy |

### 2.6 Brak Detekcji Konfliktów ⛔

| Plik | Lokalizacja | Problem | TODO |
|------|-------------|---------|------|
| `thresholds.py` | L77–81 | SmO₂ wynik kopiowany bez porównania z VT | Wywołuj `ConflictDetector`, raportuj rozbieżność |
| `thresholds.py` | cały | Brak detekcji cardiac drift, HR plateau | Dodaj moduł konfliktów |

---

## 3. PODSUMOWANIE PRIORYTETÓW

### Wysoki Priorytet (łamie metodologię)

1. **VT jako przedział** — zmień `vt1_watts` na `vt1_range: Tuple[float, float]`
2. **Confidence score** — każdy wynik VT musi mieć `confidence: float`
3. **Walidacja testu** — przed analizą sprawdź ważność

### Średni Priorytet (niekompletne)

4. **SmO₂ rozbieżność** — raportuj różnicę LT vs VT
5. **Strefy z ostrzeżeniem** — przy niskiej pewności dodaj disclaimer
6. **Dokumentacja progów** — uzasadnij hardcoded wartości

### Niski Priorytet (kosmetyczne)

7. **Nazewnictwo** — `smo2_1_watts` → `smo2_lt1_watts` (czytelność)
8. **Typy** — użyj `Optional[Tuple[float, float]]` dla przedziałów

---

## 4. MAPOWANIE NA MODUŁY ALGORYTMICZNE

| Moduł z mapy | Obecny kod | Status |
|--------------|------------|--------|
| TestValidator | ❌ Brak | **DO IMPLEMENTACJI** |
| SignalPreprocessor | Częściowo w `common.py` | DO ROZBUDOWY |
| VTDetector.VE | `detect_vt_from_steps` | DO REFAKTORU (przedziały, confidence) |
| VTDetector.SmO2 | `detect_smo2_from_steps` | DO REFAKTORU (confidence, rozbieżność) |
| ConflictDetector | `signals/conflicts.py` | ✅ ISTNIEJE, **DO INTEGRACJI** |
| ResultAggregator | ❌ Brak | **DO IMPLEMENTACJI** |
| ZoneCalculator | `calculate_training_zones_from_thresholds` | DO REFAKTORU (confidence) |
| InterpretationEngine | `interpretation.py` | ✅ ZREFAKTOROWANY |
| ReportGenerator | ❌ Brak (tylko UI) | **DO IMPLEMENTACJI** |

---

*Lista TODO v1.0 — 2026-01-02*
