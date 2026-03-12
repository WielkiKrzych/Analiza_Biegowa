## 📋 Changelog

### 2026-03-12 - Garmin FIT Integration & Running Dynamics

**Nowe źródło danych: pliki .FIT (Garmin)**
- 🆕 Aplikacja MergeCSV obsługuje teraz pliki `.FIT` obok `.CSV` — automatycznie parsuje dane z Garmin Connect
- 🆕 Dane z FIT doklejane jako dodatkowe kolumny w pliku wyjściowym CSV

**Nowe metryki z FIT w zakładce Performance > Biomechanika:**
- 🦶 **Stance Time Balance (L/P)** — balans kontaktu z podłożem z wykresem i klasyfikacją asymetrii
- 📐 **Vertical Ratio** — stosunek oscylacji do długości kroku z kolorowymi strefami
- ⏱️ **GCT** — rozpoznaje prawdziwe dane z czujnika Garmin (vs estymacja z kadencji)
- 📏 **Step Length** — preferuje rzeczywisty pomiar z FIT zamiast obliczania z kadencji/tempa

**Nowe sekcje w zakładce Podsumowanie:**
- 🦶 **Running Dynamics** — panel metryki (GCT, Balans, VR, Krok) + wykres 4-panelowy
- 🔴🔵 **O2Hb / HHb** — wykres oksyhemoglobiny i deoksyhemoglobiny z nakładką tempa
- 💓 **HRV (RMSSD)** — wykres per-sekundowy z nakładką HR + interpretacja
- 🌡️ **Temperatura** — metryka z danych FIT
- 📊 Nowe wiersze metryk: Running Dynamics + Dane Dodatkowe (HRV, Temp, O2Hb, HHb)

**Poprawki:**
- 🐛 Fix wypełnienia wykresu tempa na odwróconej osi Y w Podsumowaniu
- ⚡ `gap.py`: Wektoryzacja `calculate_grade` dla array/Series
- 🔧 `utils.py`: Nowe kolumny FIT w konwersji numerycznej, preferowanie rzeczywistego GCT

---

### 2026-03-08 - Audit Code Review (P0-P3 Fixes)

**Naprawione błędy P0 (CRITICAL):**
- 🐛 `session_orchestrator.py`: Deserializacja `_df_clean_pl_bytes` → `_df_clean_pl` w ścieżce cache
- 🐛 `threshold_analysis_ui.py`: Analiza VT teraz działa bez miernika mocy (pace-based branch)
- ✅ `hr_zones.py`: Nowy moduł stref HR (Karvonen + LTHR models)

**Naprawione błędy P1 (IMPORTANT):**
- 🐛 `cardio_advanced.py`: HR Recovery używa HR peak zamiast power peak
- 🐛 `heart_rate.py`: Usunięte `inplace=True` - unikanie mutacji DataFrame
- 🐛 `smo2.py`: Zmienione wygładzanie z 5s mean na 15s median (bardziej odporne na outliery)
- 🐛 `smo2.py`, `vent.py`: Poprawione etykiety wykresów "Tempo" → "Moc" (Watts)

**Naprawione błędy P2 (MEDIUM):**
- ✅ `hrv.py`: Dodany pNN50 (% RR intervals >50ms different)
- ✅ `metrics.py`: Dodane TRIMP i hrTSS (training load bez power meter)

**Naprawione błędy P3 (LOW):**
- 🐛 `report.py`, `kpi.py`: Kadencja "RPM" → "SPM" (steps/min dla biegania)

**Already Fixed (z poprzedniego audit):**
- 🐛 `pace.py` via `data_processing.py`: Resampling tempa przez konwersję speed→mean→pace
- 🐛 `data_processing.py`: GAP (Grade-Adjusted Pace) calculation aktywowany
- 🐛 `metrics.py`: Pace:HR Decoupling dla biegaczy (speed/HR efficiency factor)
- 🐛 `pace.py`: Z1 upper limit = infinity (catches all ultra-slow)
- 🐛 `dual_mode.py`: NP division by zero protection
- 🐛 `running_dynamics.py`: Stride length bez ×2 (Garmin SPM is dual-step)
- 🐛 `app.py`: MD5 hash dla plików zamiast name+size
- 🐛 `app.py`: `metrics.get()` zamiast `metrics.pop()` (cache mutation)
- 🐛 `app.py`: Duration z kolumny time, nie len(df)
- 🐛 `app.py`: Cumulative distance z time×speed
- 🐛 `dual_mode.py`: IF capped at 2.0
- 🐛 `metrics.py`: Durability index harmonic mean dla pace
- 🐛 `hrv.py`: Logger import dodany
- 🐛 `cardiac_drift.py`: Efficiency Factor formula fixed

---

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Streamlit-1.30+-red?style=for-the-badge&logo=streamlit" alt="Streamlit">
  <img src="https://img.shields.io/badge/Tests-31%2F31-green?style=for-the-badge" alt="Tests">
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" alt="License">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Performance-⚡_Optimized-brightgreen?style=flat-square">
  <img src="https://img.shields.io/badge/Tempo-📊_Based-blue?style=flat-square">
  <img src="https://img.shields.io/badge/Numba-JIT-orange?style=flat-square">
  <img src="https://img.shields.io/badge/Polars-Fast-purple?style=flat-square">
</p>

---

## 🚀 Szybki Start

```bash
# Klonowanie repozytorium
git clone https://github.com/WielkiKrzych/Analiza_Biegowa.git
cd Analiza_Biegowa

# Instalacja zależności
pip install -r requirements.txt

# Uruchomienie aplikacji
streamlit run app.py
```

---

## 🎯 Kluczowa Zmiana: Tempo zamiast Mocy

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   PRZED                           PO                        │
│   ─────                           ──                        │
│                                                             │
│   SmO2 vs ⚡ Moc                  SmO2 vs ⏱️ Tempo          │
│   VE vs ⚡ Moc                    VE vs ⏱️ Tempo            │
│   HR vs ⚡ Moc                    HR vs ⏱️ Tempo            │
│                                                             │
│   ┌──────────┐                    ┌──────────┐             │
│   │    ⚡    │                    │   ⏱️    │             │
│   │  Power   │  ───────────────▶  │  Pace   │             │
│   │   [W]    │                    │ [min/km]│             │
│   └──────────┘                    └──────────┘             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Dlaczego tempo?**
- 🏃 Tempo to naturalny wskaźnik dla biegaczy (min/km)
- 📊 Lepsza korelacja z fizjologią (HR, SmO2, VE)
- 🎯 Bezpośrednie odniesienie do doświadczenia z treningu
- ⚡ Format: `m:ss` (np. `4:30` zamiast `4.5`)

### 🕐 Format Czasu: hh:mm:ss

Wszystkie wykresy czasowe wyświetlają teraz oś X w formacie **hh:mm:ss** (godziny:minuty:sekundy) zamiast minut dziesiętnych.

```
PRZED:                    PO:
0, 5, 10, 15 min         00:00:00, 00:05:00, 00:10:00

5.5 min                  00:05:30
```

**Korzyści:**
- ✅ Czytelniejszy format dla długich treningów (>1h)
- ✅ Łatwiejsze śledzenie interwałów
- ✅ Zgodność z konwencjami sportowymi

---

## 🏗️ Architektura Systemu

```
┌─────────────────────────────────────────────────────────────┐
│                    🚀 STREAMLIT APP                          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ 📋 Tabs     │  │ 🎨 Theme    │  │ 💾 Cache    │         │
│  │ (29 mod)    │  │ Manager     │  │ Manager     │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    🔧 SERVICES LAYER                         │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐  ┌─────────────────────┐          │
│  │ ⚡ Orchestrator     │  │ ✅ Validation       │          │
│  │ (Numba JIT +       │  │ (Schema Check)      │          │
│  │  Polars)            │  │                     │          │
│  └─────────────────────┘  └─────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    📦 MODULES LAYER                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  🧮 CALCULATIONS          🎨 UI            💾 DATABASE      │
│  ───────────────          ─────            ──────────       │
│  • ⏱️ pace.py            • 📊 charts      • 🗄️ SQLite      │
│  • 🔋 d_prime.py         • 📈 reports     • 📂 sessions    │
│  • 🫁 ventilatory.py     • 🎯 metrics    • 📝 notes       │
│  • 💪 power.py           • 🗺️ maps       • ⚙️ settings    │
│  • ❤️ hrv.py             • 📱 mobile                        │
│  • 🩸 smo2_advanced.py                                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Główne Zakładki

```
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│   📊 OVERVIEW    │   ⚡ PERFORMANCE   │   🫀 PHYSIOLOGY   │   🧠 AI      │
│   ────────────   │   ─────────────    │   ─────────────    │   ─────     │
│                                                                          │
│   • 📈 Report      • 🏃 Running         • ❤️ HRV           • 🤖 ML       │
│   • 📋 Summary     • 🦶 Biomechanics    • 🩸 SmO2          • 🍽️ Nutrition│
│   • 🎯 KPIs        • 📐 Model           • 🫁 Ventilation   • 🔍 Limiters │
│   • 📊 Charts      • ❤️ HR Zones        • 🌡️ Thermal                      │
│   • 🗺️ Maps        • 🩸 Hematology      • 💧 Hydration                    │
│   • 📝 Notes       • 📉 Drift Maps                                        │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Pipeline Przetwarzania

```
    📁 CSV Input
       │
       ▼
┌─────────────────────┐
│  ⚡ Polars Loader   │  ← Szybkie I/O (10-100x)
│  (TTL Cache 1h)     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  🔄 Normalize       │  ← Mapowanie kolumn
│     Columns         │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  🧹 Clean &         │  ← Walidacja danych
│     Validate        │
└──────────┬──────────┘
           │
      ┌────┴────┐
      ▼         ▼
┌─────────┐ ┌─────────┐
│ 📊 Pandas│ │ ⚡ Numba │  ← Równoległe przetwarzanie
│ Standard│ │   JIT   │
└────┬────┘ └────┬────┘
     │           │
     └─────┬─────┘
           ▼
┌─────────────────────┐
│  🎯 Metrics Calc    │  ← W', NP, HR, Tempo
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  💾 Cache Results   │  ← @st.cache_data
└─────────────────────┘
```

---

## 📈 Kluczowe Metryki

| Metryka | Ikona | Opis | Jednostka |
|---------|-------|------|-----------|
| **Tempo** | ⏱️ | Główny wskaźnik intensywności | min/km |
| **Normalized Pace** | 📈 | Algorytm 4-potęgowy | min/km |
| **Critical Speed** | 🎯 | Prędkość krytyczna | m/s |
| **D'** | 🔋 | Pojemność anaerobowa | m |
| **RSS** | ⚖️ | Running Stress Score | punkty |
| **GAP** | 🏔️ | Grade-Adjusted Pace | min/km |
| **Cadence** | 👟 | Kadencja kroków | SPM |
| **GCT** | 🦶 | Ground Contact Time | ms |
| **VO** | 📊 | Vertical Oscillation | cm |
| **RE** | 💪 | Running Effectiveness | % |
| **VR** | 📐 | Vertical Ratio | % |
| **Balance** | ⚖️ | Stance Time Balance (L/P) | % |
| **Step Length** | 📏 | Długość kroku (FIT) | m |
| **HRV** | 💓 | RMSSD per sekundę | ms |
| **O2Hb** | 🔴 | Oksyhemoglobina | a.u. |
| **HHb** | 🔵 | Deoksyhemoglobina | a.u. |

---

## 🎨 Wykresy Fizjologiczne (vs Tempo)

```
┌─────────────────────────────────────────────────────────────┐
│  🩸 SmO2 vs Tempo              🫁 VE vs Tempo                │
│                                                             │
│  SmO2 [%]                       VE [L/min]                  │
│     │                              │                        │
│  80 ┤    ╭─╮                    100┤      ╭──╮              │
│     │   ╱   ╲                      │     ╱    ╲             │
│  60 ┤──╱     ╲──                60 ┤────╱      ╲───         │
│     │ ╱       ╲                    │  ╱          ╲          │
│  40 ┤╱         ╲─               30 ┤╱            ╲──        │
│     └────────────                  └────────────────        │
│       3:00  5:00                    3:00  5:00  7:00        │
│       ⏱️ min/km                     ⏱️ min/km               │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  ❤️ HR vs Tempo                🩸 THb vs Tempo               │
│                                                             │
│  HR [bpm]                       THb [g/dL]                  │
│     │                              │                        │
│ 180 ┤        ╭─                 95 ┤        ╭──╮            │
│     │       ╱                      │       ╱    ╲           │
│ 150 ┤──────╱                    85 ┤──────╱      ╲──        │
│     │     ╱                        │     ╱                   │
│ 120 ┤────╱                      75 ┤────╱                    │
│     └────────────                  └────────────────        │
│       3:00  5:00                    3:00  5:00  7:00        │
│       ⏱️ min/km                     ⏱️ min/km               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 Struktura Projektu

```
📁 Analiza_Biegowa/
│
├── 🚀 app.py                          ← Główny punkt wejścia
├── 📦 pyproject.toml                  ← Zależności
├── 📖 README.md                       ← Dokumentacja
│
├── 📁 modules/
│   │
│   ├── 🧮 calculations/              ← 43 moduły obliczeniowe
│   │   ├── ⏱️ pace.py               ← Strefy tempa, PDC
│   │   ├── 🔋 d_prime.py            ← Model D'
│   │   ├── 🫁 ventilatory.py        ← VT1/VT2 detection
│   │   ├── 💪 power.py              ← Metryki mocy
│   │   ├── ❤️ hrv.py                ← HRV (DFA α1)
│   │   ├── 🩸 smo2_advanced.py      ← SmO2 kinetics
│   │   └── ⚡ polars_adapter.py      ← Szybkie I/O
│   │
│   ├── 🎨 ui/                        ← 29 komponentów UI
│   │   ├── 🏃 running.py            ← Zakładka Running
│   │   ├── 🦶 biomech.py            ← Biomechanika
│   │   ├── 🩸 smo2.py               ← SmO2 z tempo
│   │   ├── 🫁 vent.py               ← Wentylacja z tempo
│   │   └── 🗺️ drift_maps_ui.py      ← Mapy driftu
│   │
│   ├── 🎭 frontend/                  ← Theme & layout
│   ├── 🏷️ domain/                    ← Modele typów
│   └── 🗄️ db/                        ← SQLite
│
├── 🔧 services/
│   ├── ⚡ session_orchestrator.py   ← Pipeline
│   └── ✅ data_validation.py        ← Walidacja
│
└── 🧪 tests/                         ← 31 testów
    ├── 📐 calculations/             ← Unit tests
    └── 🔗 integration/              ← Testy integracyjne
```

---

## 🧪 Testy

```bash
# Uruchom wszystkie testy
pytest tests/ -v

# Testy z pokryciem
pytest --cov=modules tests/
```

**Status:** `31/31 ✅`

| Kategoria | Testy | Status |
|-----------|-------|:------:|
| 📐 Obliczenia | 18 | ✅ |
| 🔗 Integracja | 5 | ✅ |
| 🔄 Repeatability | 2 | ✅ |
| ⚙️ Settings | 3 | ✅ |
| 🗺️ State Machine | 1 | ✅ |
| 🩸 SmO2 | 2 | ✅ |

---

## 📥 Wymagane Dane CSV

### Minimalne (podstawowa analiza)

```
┌──────────────────────────────────────────────────────┐
│  ✅ WYMAGANE                                         │
│  • pace              [s/km]  ← Tempo                 │
│                                                      │
│  ⚡ OPCJONALNE                                       │
│  • distance          [m]     ← Dystans               │
│  • heartrate         [bpm]   ← Tętno                 │
│  • cadence           [SPM]   ← Kadencja              │
└──────────────────────────────────────────────────────┘
```

### Zaawansowane (pełna analiza)

| Kolumna | Opis | Urządzenie | Ikona |
|---------|------|------------|-------|
| `tymeventilation` | Wentylacja [L/min] | Tymewear | 🫁 |
| `tymebreathrate` | Częstość oddechów [/min] | Tymewear | 🌬️ |
| `smo2` | Saturacja mięśniowa [%] | TrainRed / Moxy | 🩸 |
| `thb` | Hemoglobina całkowita [g/dL] | TrainRed / Moxy | 🩸 |
| `verticaloscillation` | Oscylacja pionowa [cm] | Garmin HRM-Run, Stryd | 📊 |
| `core_temperature` | Temperatura ciała [°C] | Core | 🌡️ |
| `skin_temperature` | Temperatura skóry [°C] | Core | 🌡️ |

### Garmin FIT (automatycznie z MergeCSV)

| Kolumna | Opis | Źródło |
|---------|------|--------|
| `stance_time` | Ground Contact Time [ms] | Garmin HRM-Run / Watch |
| `stance_time_balance` | Balans L/P kontaktu [%] | Garmin HRM-Run |
| `stance_time_percent` | Duty cycle [%] | Garmin HRM-Run |
| `vertical_ratio` | Oscylacja / krok [%] | Garmin HRM-Run |
| `step_length` | Długość kroku [m] | Garmin HRM-Run |
| `temperature` | Temperatura [°C] | Garmin Watch |
| `o2hb` | Oksyhemoglobina [a.u.] | TrainRed via CIQ |
| `hhb` | Deoksyhemoglobina [a.u.] | TrainRed via CIQ |
| `hrv` | HRV RMSSD per sekundę [ms] | Garmin Watch |
| `speed_m_s` | Prędkość [m/s] | Garmin Watch |

---

## ⚙️ Konfiguracja (Sidebar)

```
┌─────────────────────────────────────────────────────┐
│  ⚙️  PARAMETRY BIEGACZA                            │
├─────────────────────────────────────────────────────┤
│                                                     │
│  🏃 PODSTAWOWE                                      │
│  ├── Waga:      [ 75 ] kg                          │
│  ├── Wzrost:    [180 ] cm                          │
│  ├── Wiek:      [ 30 ] lat                         │
│  └── Płeć:      [ M / K ]                          │
│                                                     │
│  🎯 PROGOWE                                         │
│  ├── Tempo:     [300 ] s/km  (5:00 min/km)         │
│  ├── LTHR:      [170 ] bpm                         │
│  └── MaxHR:     [185 ] bpm                         │
│                                                     │
│  🫁 WENTYLACJA                                      │
│  ├── VT1:       [ 35 ] L/min                       │
│  └── VT2:       [ 65 ] L/min                       │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## 🚀 Optymalizacje Wydajności

| Optymalizacja | Przed | Po | Przyspieszenie |
|--------------|-------|-----|----------------|
| **Cache Streamlit** | Brak | `@st.cache_data` TTL=1h | ~10x |
| **Numba JIT** | Tylko W' | PDC + pace.py | ~5-10x |
| **Polars** | Pandas | Polars first | ~10-100x |
| **Indeksy DB** | Brak | 4 indeksy | Szybsze query |

---

## 🔬 Raport Jakości Danych

```
┌─────────────────────────────────────────────────────┐
│  📊 RAPORT JAKOŚCI DANYCH                          │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ✅ DOSTĘPNE METRYKI (67%)                          │
│  ├─ ⏱️ pace                                         │
│  ├─ 📏 distance                                     │
│  ├─ ❤️ heartrate                                    │
│  ├─ 👟 cadence                                      │
│  └─ 📊 verticaloscillation                          │
│                                                     │
│  ❌ BRAKUJĄCE                                       │
│  ├─ 🫁 tymeventilation  → Ventilation tab          │
│  ├─ 🩸 smo2            → SmO2 tab                  │
│  └─ 🌡️ core_temperature → Thermal tab              │
│                                                     │
│  💡 REKOMENDACJE                                    │
│  └─ Rozważ czujnik VO2 Master dla pełnej analizy   │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## 🛠️ Technologie

| Technologia | Zastosowanie | Wersja | Ikona |
|-------------|--------------|--------|-------|
| **Python** | Backend | 3.10+ | 🐍 |
| **Streamlit** | UI Framework | 1.30+ | 🎈 |
| **Pandas** | Data processing | 2.0+ | 📊 |
| **Polars** | Fast I/O | 0.20+ | ⚡ |
| **NumPy** | Numerical computing | 1.26+ | 🔢 |
| **SciPy** | Scientific computing | 1.11+ | 🧮 |
| **Plotly** | Interactive charts | 5.18+ | 📈 |
| **Numba** | JIT compilation | 0.59+ | ⚡ |
| **pytest** | Testing | 8.0+ | 🧪 |

---

## 🤝 Jak Wspierać

```bash
# 1. Fork repozytorium
git fork https://github.com/WielkiKrzych/Analiza_Biegowa.git

# 2. Utwórz branch
git checkout -b feature/TwojaFunkcja

# 3. Commit zmiany
git commit -m "Dodaj: TwojaFunkcja"

# 4. Push do branch
git push origin feature/TwojaFunkcja

# 5. Otwórz Pull Request
```

---

## 📄 Licencja

MIT License - zobacz plik `LICENSE` dla szczegółów.

---

## 👤 Autor

**WielkiKrzych**

<p align="center">
  <a href="https://github.com/WielkiKrzych">
    <img src="https://img.shields.io/badge/GitHub-WielkiKrzych-black?style=for-the-badge&logo=github" alt="GitHub">
  </a>
</p>

---

<p align="center">
  <sub>🏃 Zbudowane dla biegaczy | ⚡ Powered by Python | 📅 2026</sub>
</p>
