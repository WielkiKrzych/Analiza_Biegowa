# Analiza_Biegowa

Aplikacja do analizy danych treningowych biegowych. W pełni poświęcona biegaczom - od amatorów po zawodowców.

## Nowości (Luty 2026) 🎉

### ✅ Poprawki obliczeń (luty 2026)
- **Poprawiony dystans** — aplikacja teraz używa rzeczywistego dystansu z pliku CSV zamiast wyliczać go z tempa
- **Poprawione tempo średnie** — obliczane jako `czas_całkowity / dystans` zamiast średniej arytmetycznej
- **PDC (Pace Duration Curve)** — wykres dostępny z poprawnym tytułem
- **RSS (Running Stress Score)** — w pełni zaimplementowany dla metryki obciążenia treningowego

### 📊 Training Load (PMC)
- **CTL (Chronic Training Load)** — 42-dniowa średnia EWMA formy
- **ATL (Acute Training Load)** — 7-dniowa średnia zmęczenia  
- **TSB (Training Stress Balance)** — forma = CTL - ATL
- **Ramp Rate** — monitorowanie wzrostu obciążenia
- **Predykcja formy** — symulacja wpływu planowanych treningów

### 🏃 Analiza Biegowa
Wszystkie zakładki analityczne dedykowane dla biegania:

- **🏃 Running tab** — analiza tempa, strefy pace, RSS, Normalized Pace, GAP, Pace Duration Curve, Durability Index
- **📐 Model tab** — Critical Speed + D' z regresją liniową i oceną R²
- **🦶 Biomechanika** — kadencja SPM, GCT, długość kroku, Running Effectiveness, Vertical Oscillation
- **🍎 Nutrition** — model metaboliczny biegu (kcal/kg/km)
- **🚧 Limiters** — profile biegaczy (Maratończyk, Średniak, Sprinter)

### 🌐 Integracje
- **Strava OAuth** — bezpośrednia synchronizacja aktywności ze Stravą
- **Import CSV** — obsługa plików z Garmin Connect, Strava, Coros i innych

### 📱 Mobile & Responsive
- **Responsywny design** — aplikacja działa na telefonie
- **Własny Dashboard** — konfigurowalne widżety

### 🎯 Nowe Funkcje
- **Własny Dashboard** — dostosuj widoki do swoich potrzeb
- **Wykres Stref** — wizualizacja stref treningowych
- **Raport Tygodniowy** — podsumowanie tygodnia z trendami
- **Rekomendacje AI** — inteligentne sugestie treningowe na podstawie formy
- **Smart Intervals** — automatyczna detekcja interwałów (wkrótce)

### ✅ Ulepszona obsługa danych
- **Raport Jakości Danych** — automatyczna walidacja kompletności danych przy imporcie
- **Lepsze komunikaty** — szczegółowe wyjaśnienia gdy brakuje danych (wentylacja, SmO2, itp.)
- **Auto-doubling kadencji** — Garmin eksportuje kadencję jako half-steps (RPM), automatyczna konwersja na SPM
- **Estymacja GCT z kadencji** — Ground Contact Time szacowany z kadencji (duty cycle ~65%) gdy brak czujnika
- **Derivacja stride length** — automatyczne obliczanie długości kroku z prędkości i kadencji

### 📈 Wykresy Garmin Connect-style
- **Tempo (pace)** — czytelne wykresy z osią Y w formacie mm:ss, osią X w HH:MM:SS
- **Outlier capping** — ograniczenie ekstremalnych wartości tempa do 10:00/km
- **Area fill** — wypełnienie wykresu tempa w stylu Garmin Connect
- **PDC** — Pace Duration Curve z formatowaną osią Y

### 📊 Vertical Oscillation (VO)
- Analiza oscylacji pionowej z czujników biegowych (Garmin HRM-Run, Stryd)
- Wykres VO w czasie z linią trendu
- Analiza VO vs kadencja
- Wskaźnik optymalnej kadencji (najniższa oscylacja)
- Nowy wskaźnik **Running Effectiveness z VO**

### 🫁 Ulepszona analiza wentylacji
- Szczegółowe komunikaty gdy brakuje danych wentylacyjnych
- Wskazówki jakie czujniki są potrzebne (VO2 Master, Cosmed)

### 📈 Ulepszone TDI (Threshold Discordance Index)
- Szczegółowe wyjaśnienie dlaczego nie można obliczyć TDI
- Instrukcje jak uzupełnić brakujące dane

## Funkcjonalności

Aplikacja oferuje analizę podstawowych parametrów treningowych poprzez cztery główne sekcje:

### 📊 Overview
- **Raport z KPI** - szczegółowy raport z kluczowymi wskaźnikami wydajności
- **Podsumowanie** - przegląd podstawowych metryk sesji treningowej

### ⚡ Performance
- **🏃 Running** - analiza tempa (pace), stref tempa, RSS (Running Stress Score)
- **🦶 Biomechanika** - analiza biomechaniczna (kadencja SPM, GCT, długość kroku, Running Effectiveness, **Vertical Oscillation**)
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
| **Tempo Normalizowane** | Algorytm 4-potęgowy (jak NP dla mocy) |
| **Critical Speed** | Prędkość krytyczna |
| **D'** | Pojemność anaerobowa w metrach |
| **RSS** | Running Stress Score |
| **GAP** | Grade-Adjusted Pace (tempo skorygowane o podbieg) |
| **Cadence SPM** | Kadencja w krokach na minutę |
| **GCT** | Ground Contact Time (czas kontaktu z podłożem) |
| **Stride Length** | Długość kroku |
| **Running Effectiveness** | Efektywność biegu |
| **Vertical Oscillation** | Oscylacja pionowa (cm) - efektywność biegu |

## Parametry w Sidebar

### ⚙️ Parametry Podstawowe (domyślne)
- Waga: **95 kg**
- Wzrost: **180 cm**
- Wiek: **30 lat**
- Płeć

### 🏃 Parametry Progowe
- **Tempo Progowe** [s/km]
- **LTHR** [bpm] - tętno progowe
- **MaxHR** [bpm] - maksymalne tętno

### 🫁 Wentylacja
- VT1 [L/min] - próg tlenowy
- VT2 [L/min] - próg beztlenowy

## Technologie

- Python 3.11+
- Streamlit - interfejs użytkownika
- Pandas/NumPy - przetwarzanie danych
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
│   │   └── dual_mode.py     # Normalized Pace, RSS
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

Wszystkie testy przechodzą: 31/31 ✅

Testy obejmują:
- Obliczenia biegowe (pace, GAP, strefy)
- Dynamikę biegu (cadence, GCT, VO)
- Progi VT1/VT2
- Model wydolnościowy (D')
- Integrację systemów
- Walidację danych

## Wymagane dane CSV

Aplikacja obsługuje pliki CSV z danych z:
- Garmin Connect
- Stryd
- Coros
- Innych aplikacji GPS

Wymagane kolumny (minimum):
- `pace` lub `speed` - tempo biegu
- `distance` - dystans (opcjonalnie, ale zalecane dla poprawnych metryk)
- `heartrate` lub `hr` - tętno (opcjonalnie)
- `cadence` - kadencja (opcjonalnie)

### Opcjonalne kolumny zaawansowane:
- `verticaloscillation` - oscylacja pionowa (cm)
- `tymeventilation` - wentylacja (L/min)
- `tymebreathrate` - częstość oddechów
- `smo2` - saturacja mięśniowa (%)
- `thb` - hemoglobina całkowita
- `core_temperature` - temperatura ciała
- `skin_temperature` - temperatura skóry

### Raport Jakości Danych
Po zaimportowaniu pliku CSV aplikacja automatycznie generuje **Raport Jakości Danych** który pokazuje:
- ✅ Dostępne metryki w Twoim pliku
- ❌ Brakujące metryki i ich wpływ na analizę
- 💡 Rekomendacje (np. "Brak wentylacji - zakładka Ventilation nieaktywna")
- 📊 Procent kompletności danych

## Autor

WielkiKrzych
