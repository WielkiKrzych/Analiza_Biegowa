# Analiza_Kolarska

Uproszczona wersja aplikacji Tri_Dashboard do analizy danych treningowych kolarskich.

## Funkcjonalności

Aplikacja oferuje analizę podstawowych parametrów treningowych poprzez cztery główne sekcje:

### 📊 Overview
- **Raport z KPI** - szczegółowy raport z kluczowymi wskaźnikami wydajności
- **Podsumowanie** - przegląd podstawowych metryk sesji treningowej

### ⚡ Performance
- **Power** - analiza mocy, CP, W', oraz zaawansowane metryki mocy
- **Biomech** - analiza biomechaniczna (kadencja, balans nóg, Pulse Power, Gross Efficiency)
- **Model** - model wydolnościowy i wycena W'
- **HR** - analiza tętna i strefy treningowe
- **Hematology** - parametry hematologiczne
- **Drift Maps** - mapy dryfu fizjologicznego

### 🧠 Intelligence
- **Nutrition** - analiza spalania i zapotrzebowania energetycznego
- **Limiters** - identyfikacja ograniczników wydolnościowych

### 🫀 Physiology
- **HRV** - analiza zmienności rytmu serca
- **SmO2** - monitorowanie saturacji mięśniowej
- **Ventilation** - analiza wentylacji i parametrów oddechowych
- **Thermal** - analiza termoregulacji

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
Analiza_Kolarska/
├── app.py                    # Główny plik aplikacji
├── modules/
│   ├── calculations/         # Moduły obliczeniowe
│   ├── ui/                   # Komponenty UI
│   ├── db/                   # Baza danych sesji
│   ├── frontend/             # Frontend helpers
│   └── export/               # Eksport danych
├── services/                 # Serwisy aplikacji
├── tests/                    # Testy
└── data/                     # Baza danych
```

## Uwagi

Ta wersja jest uproszczoną wersją Tri_Dashboard, z której usunięto:
- Zakładki związane z progami wentylacyjnymi (Vent - Progi, Vent - Progi Manuals)
- Zakładki związane z progami SmO2 (SmO2 - Progi, SmO2 - Progi Manuals)
- Archiwum testów rampowych (Ramp Archive)
- AI Coach
- Generowanie raportów PDF/PNG z sidebar
- Zakładka Intervals (funkcjonalność przeniesiona do Biomech)
- Zakładka TTE (Time To Exhaustion)

**Z zakładki Podsumowanie usunięto:**
- Model Matematyczny CP
- Progi Wentylacyjne VT1/VT2
- Progi SmO2 LT1/LT2

Pozostałe sekcje w Podsumowaniu:
1. Przebieg Treningu
2. Wentylacja (VE) i Oddechy (BR)
3. SmO2 vs THb w czasie
4. Threshold Discordance Index (TDI)
5. Estymacja VO2max z Niepewnością (CI95%)

Aplikacja koncentruje się na podstawowej analizie danych treningowych (PWR, HR, SmO2, VT).
