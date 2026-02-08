# Mapa Implementacyjna — Moduły Obliczeniowe

## 1. Przegląd Architektury

```
┌─────────────────────────────────────────────────────────────────────┐
│                         RAMP TEST PIPELINE                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  [1] WEJŚCIE     [2] WALIDACJA    [3] PRZETWARZANIE   [4] DETEKCJA │
│      ↓               ↓                 ↓                   ↓        │
│  RawData  →   TestValidator  →  SignalPreprocessor  →  VTDetector  │
│                                                                     │
│                    [5] AGREGACJA        [6] INTERPRETACJA           │
│                         ↓                    ↓                      │
│                  ResultAggregator  →   ReportGenerator              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Moduły Obliczeniowe

### 2.1 Moduł: TestValidator

**Odpowiedzialność:** Ocena ważności testu (nieważny/warunkowy/wiarygodny)

**Dane wejściowe:**
```
- df: DataFrame z danymi testu
- protocol: RampProtocol (czas, tempo wzrostu)
- metadata: TestMetadata (data, notatki, RPE)
```

**Operacje:**
- Sprawdzenie długości rampy
- Zliczanie artefaktów w każdym sygnale
- Wykrycie przerw i zatrzymań
- Ocena stabilności kadencji

**Obiekt wynikowy:**
```
TestValidityResult:
  - validity: Enum (INVALID, CONDITIONAL, VALID)
  - issues: List[str]
  - artifact_ratios: Dict[signal, float]
  - ramp_duration_sec: int
  - is_exhaustion_reached: bool
```

---

### 2.2 Moduł: SignalPreprocessor

**Odpowiedzialność:** Czyszczenie i normalizacja sygnałów

**Dane wejściowe:**
```
- df: DataFrame z surowymi danymi
- signal_config: Dict[signal_name, ProcessingConfig]
```

**Operacje (per sygnał):**
- Interpolacja braków (< 5 s)
- Filtracja artefaktów (median filter)
- Wygładzanie (rolling mean)
- Detekcja outlierów

**Obiekt wynikowy:**
```
ProcessedSignals:
  - power: CleanSeries
  - hr: CleanSeries
  - smo2: Optional[CleanSeries]
  - rr_intervals: Optional[CleanSeries]
  - quality_flags: Dict[signal, QualityMetrics]
```

---

### 2.3 Moduł: VTDetector

**Odpowiedzialność:** Detekcja VT1/VT2 z każdego sygnału

**Submoduły:**

#### 2.3.1 HRBasedDetector
```
Wejście: power, hr (obie CleanSeries)
Wyjście: HRThresholdResult
  - vt1_range: (lower_W, upper_W)
  - vt2_range: (lower_W, upper_W)
  - confidence: float
  - method: str
```

#### 2.3.2 VEBasedDetector (jeśli dostępne)
```
Wejście: power, ve (obie CleanSeries)
Wyjście: VEThresholdResult
  - vt1_range, vt2_range, confidence, method
```

#### 2.3.3 DFABasedDetector
```
Wejście: power, rr_intervals
Wyjście: DFAThresholdResult
  - vt1_alpha_crossing: Optional[float] (W przy α1 ≈ 0.75)
  - vt2_alpha_crossing: Optional[float] (W przy α1 ≈ 0.50)
  - confidence: float
  - quality_flags: DFAQualityFlags
```

#### 2.3.4 SmO2Detector
```
Wejście: power, smo2
Wyjście: SmO2ThresholdResult
  - lt1_range: Optional[(lower_W, upper_W)]
  - lt2_range: Optional[(lower_W, upper_W)]
  - confidence: float
  - is_local_signal: True  # zawsze
  - limitations: List[str]
```

---

### 2.4 Moduł: ConflictDetector

**Odpowiedzialność:** Wykrycie konfliktów między sygnałami

**Dane wejściowe:**
```
- hr_result: HRThresholdResult
- ve_result: Optional[VEThresholdResult]
- dfa_result: Optional[DFAThresholdResult]
- smo2_result: Optional[SmO2ThresholdResult]
- processed_signals: ProcessedSignals
```

**Operacje:**
- Porównanie lokalizacji VT między sygnałami
- Wykrycie cardiac drift
- Wykrycie HR plateau
- Sprawdzenie spójności DFA
- Analiza rozbieżności SmO₂

**Obiekt wynikowy:**
```
ConflictReport:
  - conflicts: List[SignalConflict]
  - agreement_score: float (0–1)
  - recommendations: List[str]
```

---

### 2.5 Moduł: ResultAggregator

**Odpowiedzialność:** Połączenie wyników w finalne VT1/VT2

**Dane wejściowe:**
```
- hr_result: HRThresholdResult
- ve_result: Optional[VEThresholdResult]
- dfa_result: Optional[DFAThresholdResult]
- smo2_result: Optional[SmO2ThresholdResult]
- conflict_report: ConflictReport
```

**Operacje:**
- Ważona agregacja przedziałów (wagi wg hierarchii)
- Obliczenie wartości centralnej
- Obliczenie confidence score
- Przypisanie źródeł

**Obiekt wynikowy:**
```
AggregatedThresholds:
  vt1:
    - range: (lower_W, upper_W)
    - midpoint: float
    - hr_range: Optional[(lower_bpm, upper_bpm)]
    - confidence: float
    - sources: List[str]  # ["HR", "VE", "SmO2"]
  vt2:
    - (analogicznie)
  smo2_context:
    - lt1_watts: Optional[float]
    - lt2_watts: Optional[float]
    - deviation_from_vt: Optional[float]
    - interpretation: str
```

---

### 2.6 Moduł: ZoneCalculator

**Odpowiedzialność:** Przeliczenie progów na strefy treningowe

**Dane wejściowe:**
```
- thresholds: AggregatedThresholds
- zone_model: ZoneModel (5-zone, 7-zone, custom)
```

**Obiekt wynikowy:**
```
TrainingZones:
  - zones: List[Zone]
    - name: str
    - power_range: (lower_W, upper_W)
    - hr_range: Optional[(lower_bpm, upper_bpm)]
    - description: str
  - confidence_note: str
```

---

### 2.7 Moduł: InterpretationEngine

**Odpowiedzialność:** Generowanie obserwacji i sugestii

**Dane wejściowe:**
```
- thresholds: AggregatedThresholds
- conflict_report: ConflictReport
- test_validity: TestValidityResult
```

**Operacje:**
- Analiza profilu (VT1/VT2 ratio)
- Identyfikacja limitów
- Generowanie sugestii (z uwzględnieniem pewności)

**Obiekt wynikowy:**
```
InterpretationResult:
  - observations: List[Observation]
  - suggestions: List[Suggestion]
  - warnings: List[Warning]
  - confidence_level: Enum (HIGH, MEDIUM, LOW)
  - can_make_recommendations: bool
```

---

### 2.8 Moduł: ReportGenerator

**Odpowiedzialność:** Generowanie raportu końcowego

**Dane wejściowe:**
```
- test_validity: TestValidityResult
- thresholds: AggregatedThresholds
- zones: TrainingZones
- interpretation: InterpretationResult
- conflict_report: ConflictReport
- metadata: TestMetadata
```

**Obiekt wynikowy:**
```
RampTestReport:
  - summary: str
  - test_info: Dict
  - validity_section: str
  - vt_section: VTReportSection
  - smo2_section: SmO2ReportSection
  - conflicts_section: str
  - zones_section: str
  - suggestions_section: str
  - methodology_disclaimer: str
```

---

## 3. Dane Wejściowe — Podsumowanie

| Nazwa | Typ | Wymagane | Opis |
|-------|-----|----------|------|
| `time` | Series[float] | ✅ | Czas w sekundach |
| `power` | Series[float] | ✅ | Moc w Watach |
| `hr` | Series[float] | ✅ | Tętno w bpm |
| `ve` | Series[float] | ❌ | Wentylacja (jeśli dostępna) |
| `smo2` | Series[float] | ❌ | Saturacja mięśniowa |
| `rr_intervals` | Series[float] | ❌ | Interwały RR w ms |
| `cadence` | Series[float] | ❌ | Kadencja w rpm |
| `protocol` | RampProtocol | ✅ | Parametry protokołu |
| `metadata` | TestMetadata | ✅ | Informacje kontekstowe |

---

## 4. Obiekty Wynikowe — Podsumowanie

| Obiekt | Moduł źródłowy | Konsumenci |
|--------|----------------|------------|
| `TestValidityResult` | TestValidator | ReportGenerator, InterpretationEngine |
| `ProcessedSignals` | SignalPreprocessor | Wszystkie detektory |
| `HRThresholdResult` | VTDetector.HR | ResultAggregator |
| `VEThresholdResult` | VTDetector.VE | ResultAggregator |
| `DFAThresholdResult` | VTDetector.DFA | ResultAggregator, ConflictDetector |
| `SmO2ThresholdResult` | VTDetector.SmO2 | ResultAggregator, ConflictDetector |
| `ConflictReport` | ConflictDetector | ResultAggregator, ReportGenerator |
| `AggregatedThresholds` | ResultAggregator | ZoneCalculator, InterpretationEngine |
| `TrainingZones` | ZoneCalculator | ReportGenerator |
| `InterpretationResult` | InterpretationEngine | ReportGenerator |
| `RampTestReport` | ReportGenerator | UI / Export |

---

## 5. Przepływ Danych

```
RawData
   │
   ▼
TestValidator ──────────────────────────────────────────┐
   │                                                    │
   ▼                                                    │
SignalPreprocessor                                      │
   │                                                    │
   ├──▶ HRBasedDetector ──────┐                         │
   ├──▶ VEBasedDetector ──────┤                         │
   ├──▶ DFABasedDetector ─────┼──▶ ConflictDetector     │
   └──▶ SmO2Detector ─────────┘         │               │
                                        │               │
                                        ▼               │
                              ResultAggregator ◀────────┘
                                        │
                    ┌───────────────────┴───────────────────┐
                    │                                       │
                    ▼                                       ▼
             ZoneCalculator                      InterpretationEngine
                    │                                       │
                    └───────────────────┬───────────────────┘
                                        │
                                        ▼
                                 ReportGenerator
                                        │
                                        ▼
                                 RampTestReport
```

---

*Mapa implementacyjna v1.0 — 2026-01-02*
