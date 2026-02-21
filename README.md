# 🏃‍♂️ Analiza_Biegowa

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Streamlit-1.30+-red?style=for-the-badge&logo=streamlit" alt="Streamlit">
  <img src="https://img.shields.io/badge/Tests-31%2F31-green?style=for-the-badge" alt="Tests">
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" alt="License">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Performance-Optimized-brightgreen?style=flat-square">
  <img src="https://img.shields.io/badge/Numba-JIT-orange?style=flat-square">
  <img src="https://img.shields.io/badge/Polars-Fast-blueviolet?style=flat-square">
</p>

---

## 🚀 Szybki Start

```bash
# Klonowanie repozytorium
git clone https://github.com/WielkiKrzych/Analiza_Biegowa.git
cd Analiza_Biegowa

# Uruchomienie aplikacji
streamlit run app.py
```

---

## 🎯 Co Nowego? (Luty 2026)

### ⚡ Optymalizacje Wydajności

| Funkcja | Przed | Po | Zysk |
|---------|-------|-----|------|
| **Cache'owanie** | Brak | `@st.cache_data` TTL=1h | ~10x szybciej |
| **Numba JIT** | Tylko W' | PDC + pace.py | ~5-10x szybciej |
| **Polars** | Pandas | Polars first | ~10-100x szybciej |
| **Indeksy DB** | Brak | 4 indeksy | Szybsze query |

### ✅ Poprawki Obliczeń
- **Poprawiony dystans** — używa rzeczywistego dystansu z CSV
- **Poprawione tempo średnie** — `czas / dystans` (eliminuje błąd)
- **PDC (Pace Duration Curve)** — wykres z poprawnym tytułem

---

## 🏗️ Architektura Systemu

```
┌─────────────────────────────────────────────────────────────────┐
│                         APP.PY                                   │
│                    (Streamlit Entry)                            │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  TabRegistry │  │  ThemeManager│  │ StateManager│          │
│  │  (Lazy Load) │  │  (UI Theme)  │  │ (Session)   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SERVICES LAYER                             │
│  ┌─────────────────────┐  ┌─────────────────────┐             │
│  │ SessionOrchestrator │  │  DataValidation    │             │
│  │ (Cache + Numba)    │  │  (Schema Check)    │             │
│  └─────────────────────┘  └─────────────────────┘             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MODULES LAYER                                │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ │
│  │Calculations│ │    UI      │ │   Domain   │ │    DB      │ │
│  │  (43 mod)  │ │  (29 tabs) │ │   (Type)   │ │ (SQLite)   │ │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 Moduły Obliczeniowe

| Moduł | Funkcja | Status |
|-------|---------|--------|
| `pace.py` | Strefy tempa, PDC, fenotyp | ⚡ Numba JIT |
| `d_prime.py` | Model D' (anaerobic distance) | ✅ |
| `running_dynamics.py` | Kadencja, GCT, VO | ✅ |
| `gap.py` | Grade-Adjusted Pace | ✅ |
| `dual_mode.py` | Normalized Pace, RSS | ✅ |
| `ventilatory.py` | VT1/VT2 detection (67KB) | ✅ |
| `power.py` | Power metrics, PDC | ✅ |
| `w_prime.py` | W' balance | ⚡ Numba JIT |
| `hrv.py` | HRV analysis (DFA α1) | ⚡ Numba JIT |
| `smo2_advanced.py` | SmO2 kinetics | ⚡ Numba JIT |

---

## 🎨 Interfejs Użytkownika

### Główne Zakładki

```
┌──────────────────────────────────────────────────────────────┐
│  📊 OVERVIEW  │  ⚡ PERFORMANCE  │  🧠 INTELLIGENCE  │  🫀 PHYSIOLOGY  │
├──────────────────────────────────────────────────────────────┤
│  • Report     │  • Running        │  • Nutrition      │  • HRV           │
│  • Summary    │  • Biomechanics   │  • Limiters       │  • SmO2          │
│               │  • Model          │                   │  • Ventilation   │
│               │  • HR             │                   │  • Thermal       │
│               │  • Hematology     │                   │                  │
│               │  • Drift Maps    │                   │                  │
└──────────────────────────────────────────────────────────────┘
```

### Funkcje UI

- ✅ **Error Boundaries** - zakładki nie crashują aplikacji
- ✅ **Structured Logging** - JSON format dla debugging
- ✅ **Graceful Degradation** - częściowe wyniki przy błędzie

---

## 🏃 Kluczowe Metryki Biegowe

| Metryka | Ikona | Opis |
|---------|-------|------|
| **Tempo (Pace)** | ⏱️ | min/km - główny wskaźnik intensywności |
| **Normalized Pace** | 📈 | Algorytm 4-potęgowy (jak NP dla mocy) |
| **Critical Speed** | 🎯 | Prędkość krytyczna |
| **D'** | 🔋 | Pojemność anaerobowa [m] |
| **RSS** | ⚖️ | Running Stress Score |
| **GAP** | 🏔️ | Grade-Adjusted Pace |
| **Cadence SPM** | 👟 | Kadencja kroków/min |
| **GCT** | 🦶 | Ground Contact Time [ms] |
| **Stride Length** | 📏 | Długość kroku [m] |
| **Vertical Oscillation** | 📊 | Oscylacja pionowa [cm] |
| **Running Effectiveness** | 💪 | Efektywność biegu |

---

## 🔧 Konfiguracja (Sidebar)

```
┌─────────────────────────────────┐
│  ⚙️ PARAMETRY BIEGACZA         │
├─────────────────────────────────┤
│  🏃 PODSTAWOWE                 │
│  ├── Waga: [75] kg             │
│  ├── Wzrost: [180] cm          │
│  ├── Wiek: [30] lat            │
│  └── Płeć: [M/K]               │
│                                 │
│  🎯 PROGOWE                    │
│  ├── Tempo: [300] s/km         │
│  ├── LTHR: [170] bpm          │
│  └── MaxHR: [185] bpm          │
│                                 │
│  🫁 WENTYLACJA                 │
│  ├── VT1: [0] L/min            │
│  └── VT2: [0] L/min            │
└─────────────────────────────────┘
```

---

## 📁 Struktura Projektu

```
Analiza_Biegowa/
├── app.py                          🚀 Main entry point
├── pyproject.toml                  📦 Dependencies & config
├── README.md                       📖 Documentation
│
├── modules/                        🧮 Core modules
│   ├── calculations/               ⚡ 43 calculation modules
│   │   ├── pace.py               ⏱️ Pace zones, PDC
│   │   ├── d_prime.py            🔋 D' model
│   │   ├── running_dynamics.py    👟 Biomechanics
│   │   ├── ventilatory.py         🫁 VT1/VT2
│   │   └── polars_adapter.py      ⚡ Polars fast I/O
│   │
│   ├── ui/                        🎨 29 UI components
│   │   ├── running.py             🏃 Running tab
│   │   ├── biomech.py             🦶 Biomech tab
│   │   ├── model.py               📐 Model tab
│   │   └── ...
│   │
│   ├── frontend/                  💅 Theme & layout
│   ├── domain/                    🏷️ Type models
│   ├── db/                        💾 SQLite storage
│   └── constants.py               📝 Magic numbers
│
├── services/                       🔌 Business logic
│   ├── session_orchestrator.py    ⚡ Processing pipeline
│   ├── session_analysis.py         📊 Metrics
│   └── data_validation.py          ✅ Validation
│
└── tests/                         🧪 31 tests
    ├── calculations/              📐 Unit tests
    └── integration/               🔗 Pipeline tests
```

---

## 🧪 Testy

```bash
# Uruchom wszystkie testy
pytest tests/ -v

# Testy z pokryciem
pytest --cov=modules tests/
```

**Wyniki:** `31/31 ✅`

| Kategoria | Testy | Status |
|-----------|-------|--------|
| Obliczenia | 18 | ✅ |
| Integracja | 5 | ✅ |
| Repeatability | 2 | ✅ |
| Settings | 3 | ✅ |
| State Machine | 1 | ✅ |
| SmO2 | 2 | ✅ |

---

## 📥 Wymagane Dane CSV

### Minimalne (do podstawowej analizy)

| Kolumna | Opis | Wymagane |
|---------|------|----------|
| `pace` | Tempo [s/km] | ✅ |
| `distance` | Dystans [m] | Opcjonalne |
| `heartrate` | Tętno [bpm] | Opcjonalne |
| `cadence` | Kadencja [SPM] | Opcjonalne |

### Zaawansowane (pełna analiza)

| Kolumna | Opis | Urządzenie |
|---------|------|------------|
| `verticaloscillation` | Oscylacja pionowa [cm] | Garmin HRM-Run, Stryd |
| `tymeventilation` | Wentylacja [L/min] | VO2 Master, Cosmed |
| `smo2` | Saturacja mięśniowa [%] | Moxy |
| `thb` | Hemoglobina całkowita [g/dL] | Moxy |
| `core_temperature` | Temp. ciała [°C] | Core |
| `skin_temperature` | Temp. skóry [°C] | Core |

### Źródła Danych

```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   Garmin    │  │    Stryd   │  │    Coros   │  │   Inne     │
│  Connect    │  │   Power    │  │    Apex    │  │   GPS      │
└─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘
```

---

## 🔬 Raport Jakości Danych

Aplikacja automatycznie analizuje jakość danych:

```
┌─────────────────────────────────────────────────────┐
│  📊 RAPORT JAKOŚCI DANYCH                         │
├─────────────────────────────────────────────────────┤
│  ✅ DOSTĘPNE METRYKI                              │
│  ├── pace, distance, heartrate, cadence           │
│  └── verticaloscillation                          │
│                                                  │
│  ❌ BRAKUJĄCE                                    │
│  ├── tymeventilation (wpływ: Ventilation)        │
│  ├── smo2 (wpływ: SmO2, Kinetics)               │
│  └── core_temperature (wpływ: Thermal)           │
│                                                  │
│  📈 KOMPLETNOŚĆ: 67%                            │
│  💡 REKOMENDACJE                                 │
│  └── Rozważ użycie czujnika VO2 Master          │
└─────────────────────────────────────────────────────┘
```

---

## ⚙️ Technologie

| Technologia | Zastosowanie | Wersja |
|-------------|--------------|--------|
| **Python** | Backend | 3.10+ |
| **Streamlit** | UI Framework | 1.30+ |
| **Pandas** | Data processing | 2.0+ |
| **Polars** | Fast I/O | 0.20+ |
| **NumPy** | Numerical computing | 1.26+ |
| **SciPy** | Scientific computing | 1.11+ |
| **Plotly** | Interactive charts | 5.18+ |
| **Numba** | JIT compilation | 0.59+ |
| **pytest** | Testing | 8.0+ |

---

## 📈 Pipeline Obliczeniowy

```
CSV Input
    │
    ▼
┌─────────────────┐
│  load_data()    │  ← Polars fast read
│  (cached)       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  normalize_cols │  ← Column mapping
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ process_data()  │  ← Cleaning & validation
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌───────┐ ┌───────┐
│Pandas │ │ Numba │  ← Parallel processing
│  std  │ │  JIT  │
└───┬───┘ └───┬───┘
    │         │
    └────┬────┘
         ▼
┌─────────────────┐
│ Metrics Calc    │  ← W', NP, HR, etc.
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Cache Output   │  ← @st.cache_data
└─────────────────┘
```

---

## 🏆 Funkcje Premium

- ✅ **AI Interval Detection** - automatyczna detekcja interwałów
- ✅ **MLX Neural Network** - predykcja HR (Apple Silicon)
- ✅ **OpenWeatherMap** - korekta TSS dla warunków
- ✅ **FIT Export** - kompatybilność z TrainingPeaks/Strava

---

## 🤝 Jak Wspierać

1. Fork repozytorium
2. Utwórz branch (`git checkout -b feature/AmazingFeature`)
3. Commit zmiany (`git commit -m 'Add AmazingFeature'`)
4. Push do branch (`git push origin feature/AmazingFeature`)
5. Otwórz Pull Request

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
  <sub>Built with 🚀 and Python | 2026</sub>
</p>
