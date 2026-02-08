# Analiza_Biegowa

Aplikacja do analizy danych treningowych biegowych. Rozwinięcie koncepcji Analiza_Kolarska, dostosowane do specyfiki biegania.

## Funkcjonalności

Aplikacja oferuje analizę podstawowych parametrów treningowych poprzez cztery główne sekcje:

### 📊 Overview
- **Raport z KPI** - szczegółowy raport z kluczowymi wskaźnikami wydajności
- **Podsumowanie** - przegląd podstawowych metryk sesji treningowej

### ⚡ Performance
- **🏃 Running** - analiza tempa (pace), stref tempa, RSS (Running Stress Score)
- **🦶 Biomechanika** - analiza biomechaniczna (kadencja SPM, GCT, długość kroku, Running Effectiveness)
- **📐 Model** - model wydolnościowy (Critical Speed, D')
- **❤️ HR** - analiza tętna i strefy treningowe
- **🧬 Hematology** - parametry hematologiczne
- **📈 Drift Maps** - mapy dryfu fizjologicznego

### 🧠 Intelligence
- **🍎 Nutrition** - analiza spalania i zapotrzebowania energetycznego
- **🚧 Limiters** - identyfikacja ograniczników wydolnościowych

### 🫀 Physiology
- **💓 HRV** - analiza zmienności rytmu serca
- **🩸 SmO2** - monitorowanie saturacji mięśniowej
- **🫁 Ventilation** - analiza wentylacji i parametrów oddechowych
- **🌡️ Thermal** - analiza termoregulacji

## Kluczowe Metryki Biegowe

| Metryka | Opis |
|---------|------|
| **Tempo (Pace)** | min/km - główny wskaźnik intensywności |
| **Critical Speed** | Prędkość krytyczna (biegowy odpowiednik CP) |
| **D'** | Pojemność anaerobowa w metrach (biegowy odpowiednik W') |
| **RSS** | Running Stress Score (biegowy odpowiednik TSS) |
| **GAP** | Grade-Adjusted Pace (tempo skorygowane o podbieg) |
| **Cadence SPM** | Kadencja w krokach na minutę |
| **GCT** | Ground Contact Time (czas kontaktu z podłożem) |
| **Running Effectiveness** | Efektywność biegu (speed/power) |

## Parametry w Sidebar

### ⚙️ Parametry Podstawowe
- Waga [kg] - domyślnie 95kg
- Wzrost [cm] - domyślnie 180cm
- Wiek [lata] - domyślnie 30
- Płeć

### 🏃 Parametry Progowe
- **Tempo Progowe** [s/km] - domyślnie 230s (3:50 min/km)
- **LTHR** [bpm] - tętno progowe, domyślnie 170
- **Threshold Power** [W] - dla biegaczy z czujnikiem mocy (opcjonalnie)
- **MaxHR** [bpm] - maksymalne tętno, domyślnie 185

### 🫁 Wentylacja
- VT1 [L/min] - próg tlenowy
- VT2 [L/min] - próg beztlenowy

## Technologie

- Python 3.11+
- Streamlit - interfejs użytkownika
- Pandas/NumPy/Polars - przetwarzanie danych
- Plotly - wizualizacja danych

## Uruchomienie

```bash
streamlit run app.py
```

## Struktura projektu

```
Analiza_Biegowa/
├── app.py                    # Główny plik aplikacji
├── modules/
│   ├── calculations/         # Moduły obliczeniowe
│   │   ├── pace.py          # Strefy tempa, PDC, phenotype
│   │   ├── pace_utils.py    # Konwersje pace ↔ speed
│   │   ├── d_prime.py       # Model D' (anaerobic distance)
│   │   ├── running_dynamics.py  # Cadence, GCT, stride
│   │   ├── gap.py           # Grade-Adjusted Pace
│   │   ├── race_predictor.py    # Predykcja czasów (Riegel)
│   │   └── dual_mode.py     # Wsparcie pace + power
│   ├── ui/                   # Komponenty UI
│   ├── domain/               # Modele domenowe
│   ├── db/                   # Baza danych sesji
│   ├── frontend/             # Frontend helpers
│   └── export/               # Eksport danych
├── services/                 # Serwisy aplikacji
├── tests/                    # Testy
└── data/                     # Baza danych
```

## Testy

```bash
pytest tests/ -v
```

Wszystkie testy przechodzą: 26/26 ✅

## Transformacja z Kolarskiej

Aplikacja została przekształcona z analizy kolarskiej (power-based) na analizę biegową (pace-based):

| Kolarstwo | → | Bieganie |
|-----------|---|----------|
| Power [W] | → | **Pace [min/km]** |
| Critical Power | → | **Critical Speed + Threshold Pace** |
| W' [J] | → | **D' [m]** |
| Normalized Power | → | **Normalized Pace** |
| TSS | → | **RSS** |
| Cadence [RPM] | → | **Cadence [SPM]** |
| Ramp Test | → | **Progressive Run** |

## Wymagane dane CSV

Aplikacja obsługuje pliki CSV z danymi z:
- Garmin Connect
- Stryd
- Innych aplikacji GPS

Wymagane kolumny (minimum):
- `pace` lub `speed` - tempo biegu
- `heartrate` lub `hr` - tętno (opcjonalnie)
- `cadence` - kadencja (opcjonalnie)
- `power` - moc biegowa (opcjonalnie, dla użytkowników Stryd)

## Autor

WielkiKrzych
