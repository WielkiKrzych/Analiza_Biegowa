# Analiza_Biegowa

Aplikacja do analizy danych treningowych biegowych i kolarskich. Rozwinięcie koncepcji Analiza_Kolarska, z pełnym wsparciem dla biegania, kolarstwa i treningów hybrydowych.

## Nowości (Luty 2026) 🎉

### ✅ Ulepszona obsługa danych
- **Raport Jakości Danych** - automatyczna walidacja kompletności danych przy imporcie
- **Auto-detekcja typu sportu** - automatyczne rozpoznawanie czy to rower, bieg czy trening hybrydowy
- **Lepsze komunikaty** - szczegółowe wyjaśnienia gdy brakuje danych (wentylacja, SmO2, itp.)

### 📊 Vertical Oscillation (VO)
- Analiza oscylacji pionowej z czujników biegowych (Garmin HRM-Run, Stryd)
- Wykres VO w czasie z linią trendu
- Analiza VO vs kadencja
- Wskaźnik optymalnej kadencji (najniższa oscylacja)
- Nowy wskaźnik **Running Effectiveness z VO** - efektywność biegu na podstawie oscylacji

### 🫁 Ulepszona analiza wentylacji
- Szczegółowe komunikaty gdy brakuje danych wentylacyjnych
- Wskazówki jakie czujniki są potrzebne (VO2 Master, Cosmed)
- Sugestie alternatywnych analiz (np. przejście do zakładki SmO2)

### 📈 Ulepszone TDI (Threshold Discordance Index)
- Szczegółowe wyjaśnienie dlaczego nie można obliczyć TDI
- Instrukcje jak uzupełnić brakujące dane
- Sugestie rozwiązań (ręczne wprowadzenie progów)

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
| **Critical Speed** | Prędkość krytyczna (biegowy odpowiednik CP) |
| **D'** | Pojemność anaerobowa w metrach (biegowy odpowiednik W') |
| **RSS** | Running Stress Score (biegowy odpowiednik TSS) |
| **GAP** | Grade-Adjusted Pace (tempo skorygowane o podbieg) |
| **Cadence SPM** | Kadencja w krokach na minutę |
| **GCT** | Ground Contact Time (czas kontaktu z podłożem) |
| **Running Effectiveness** | Efektywność biegu (speed/power) |
| **Vertical Oscillation** | Oscylacja pionowa (cm) - efektywność biegu |
| **VO Efficiency** | Efektywność na podstawie oscylacji vs wzrost |

## Parametry w Sidebar

### ⚙️ Parametry Podstawowe
- Waga [kg]
- Wzrost [cm]
- Wiek [lata]
- Płeć

### 🏃 Parametry Progowe
- **Tempo Progowe** [s/km]
- **LTHR** [bpm] - tętno progowe
- **Threshold Power** [W] - dla biegaczy z czujnikiem mocy (opcjonalnie)
- **MaxHR** [bpm] - maksymalne tętno

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

Wszystkie testy przechodzą: 163/164 ✅

Testy obejmują:
- Obliczenia biegowe (pace, GAP, strefy)
- Obliczenia kolarskie (power, NP, TSS)
- Dynamikę biegu (cadence, GCT, VO)
- Progi VT1/VT2
- Model wydolnościowy (D', W')
- Integrację systemów
- Walidację danych

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
- VO2 Master / Cosmed
- Innych aplikacji GPS

Wymagane kolumny (minimum):
- `pace` lub `speed` - tempo biegu (dla biegania)
- `watts` lub `power` - moc (dla kolarstwa)
- `heartrate` lub `hr` - tętno (opcjonalnie)
- `cadence` - kadencja (opcjonalnie)

### Opcjonalne kolumny zaawansowane:
- `tymeventilation` - wentylacja (L/min) - dla analizy wentylacyjnej
- `tymebreathrate` - częstość oddechów - dla analizy wentylacyjnej
- `smo2` - saturacja mięśniowa (%) - dla analizy NIRS
- `thb` - hemoglobina całkowita - dla analizy NIRS
- `VerticalOscillation` - oscylacja pionowa (cm) - dla analizy biomechanicznej
- `core_temperature` - temperatura ciała - dla analizy termicznej
- `skin_temperature` - temperatura skóry - dla analizy termicznej

### Raport Jakości Danych
Po zaimportowaniu pliku CSV aplikacja automatycznie generuje **Raport Jakości Danych** który pokazuje:
- ✅ Dostępne metryki w Twoim pliku
- ❌ Brakujące metryki i ich wpływ na analizę
- 💡 Rekomendacje (np. "Brak wentylacji - zakładka Ventilation nieaktywna")
- 📊 Procent kompletności danych

## Autor

WielkiKrzych
