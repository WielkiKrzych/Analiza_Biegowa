# Plan Zmian - Audyt Analiza_Biegowa

**Data opracowania:** 08.02.2026  
**Autor:** Sisyphus AI Agent  
**Status:** Wersja robocza - do weryfikacji

---

## Spis treści
1. [Podsumowanie zmian](#1-podsumowanie-zmian)
2. [Priorytetyzacja](#2-priorytetyzacja)
3. [Szczegółowe zadania](#3-szczegółowe-zadania)
4. [Zmiany w kodzie](#4-zmiany-w-kodzie)
5. [Testy](#5-testy)
6. [Timeline](#6-timeline)

---

## 1. Podsumowanie zmian

### 1.1 Zidentyfikowane problemy
| Problem | Severity | Wpływ na UX |
|---------|----------|-------------|
| Brak obsługi Vertical Oscillation | Medium | Średni - dane w CSV nieużywane |
| Niejasne komunikaty o braku VT | Medium | Wysoki - użytkownik nie wie dlaczego nie ma danych |
| Brak auto-detekcji typu sportu | Low | Średni - aplikacja pokazuje wskaźniki nieadekwatne do danych |
| Brak walidacji danych przy imporcie | Medium | Wysoki - niekompletne analizy |
| TDI nie obsługuje braku VT1 | Low | Niski - tylko dla zaawansowanych użytkowników |

### 1.2 Oczekiwane rezultaty
- ✅ Pełne wykorzystanie dostępnych danych z CSV
- ✅ Jasne komunikaty o brakujących czujnikach
- ✅ Automatyczne dostosowanie UI do typu sportu
- ✅ Walidacja jakości danych przy imporcie
- ✅ Lepsza obsługa brakujących danych w analizach zaawansowanych

---

## 2. Priorytetyzacja

### Priorytet 1: KRYTYCZNE (MVP)
Zadania, które muszą być wykonane aby poprawić podstawowe doświadczenie użytkownika.

1. **Zmiana 3:** Ulepszone komunikaty o braku VT
2. **Zmiana 2:** Obsługa Vertical Oscillation
3. **Zmiana 5:** Walidacja kompletności danych

### Priorytet 2: WAŻNE
Zadania, które znacząco poprawiają UX ale nie są krytyczne.

4. **Zmiana 4:** Auto-detekcja typu sportu
5. **Zmiana 6:** Ulepszenie TDI

### Priorytet 3: NICE-TO-HAVE
Funkcjonalności dodatkowe, wartościowe ale niepilne.

6. **Zmiana 7:** Nowy wskaźnik Running Effectiveness z VO
7. **Zmiana 8:** Testy integracyjne

---

## 3. Szczegółowe zadania

### Zadanie 1: Ulepszone komunikaty o braku danych wentylacyjnych
**Priorytet:** P1 - Krytyczny  
**Czas:** 30 min  
**Pliki:** `modules/ui/vent.py`

#### Obecny stan:
```python
if "tymeventilation" not in target_df.columns:
    st.info("ℹ️ Brak danych wentylacji (tymeventilation) w tym pliku.")
    return
```

#### Docelowy stan:
```python
if "tymeventilation" not in target_df.columns:
    st.info("""
    ℹ️ **Brak danych wentylacji**
    
    Aby uzyskać analizę wentylacyjną, potrzebujesz czujnika wentylacji 
    (np. VO2 Master, Cosmed, lub inny metabolimeter).
    
    **Brakujące kolumny:**
    - `tymeventilation` (VE - wentylacja w L/min)
    - `tymebreathrate` (BR - częstość oddechów)
    
    **Twoje dane zawierają:** Moc, HR, SmO2 - analiza fizjologii mięśniowej 
    jest dostępna w zakładce 🩸 SmO2.
    """)
    return
```

#### Kroki implementacji:
1. Zlokalizować sprawdzenie kolumny `tymeventilation` w `vent.py`
2. Zamienić komunikat `st.info()` na rozszerzony HTML/Markdown
3. Dodać linki do dokumentacji (opcjonalnie)
4. Przetestować z plikiem CSV bez VT

---

### Zadanie 2: Obsługa Vertical Oscillation
**Priorytet:** P1 - Krytyczny  
**Czas:** 1-2h  
**Pliki:** 
- `modules/calculations/running_dynamics.py` (nowe funkcje)
- `modules/ui/biomech.py` (nowe wykresy)

#### Nowe funkcje do dodania:

**A) W modules/calculations/running_dynamics.py:**
```python
def calculate_vo_stats(vo_cm: np.ndarray) -> Dict:
    """Calculate Vertical Oscillation statistics."""
    valid_vo = vo_cm[~np.isnan(vo_cm)]
    if len(valid_vo) == 0:
        return {}
    
    return {
        "mean_vo": float(np.mean(valid_vo)),
        "min_vo": float(np.min(valid_vo)),
        "max_vo": float(np.max(valid_vo)),
        "std_vo": float(np.std(valid_vo)),
        "cv_vo": float(np.std(valid_vo) / np.mean(valid_vo) * 100) if np.mean(valid_vo) > 0 else 0,
    }

def analyze_vo_efficiency(vo_cm: np.ndarray, cadence_spm: np.ndarray) -> Dict:
    """
    Analyze running efficiency based on VO and cadence.
    
    Lower VO at same cadence = better efficiency (less bouncing).
    """
    # Filter valid data
    mask = (~np.isnan(vo_cm)) & (~np.isnan(cadence_spm)) & (cadence_spm > 0)
    if mask.sum() < 10:
        return {}
    
    vo_valid = vo_cm[mask]
    cad_valid = cadence_spm[mask]
    
    # Calculate VO per cadence bin
    cad_bins = np.arange(140, 200, 10)  # 140-200 SPM
    vo_by_cadence = {}
    
    for i, cad_start in enumerate(cad_bins[:-1]):
        cad_end = cad_bins[i+1]
        mask_bin = (cad_valid >= cad_start) & (cad_valid < cad_end)
        if mask_bin.sum() > 5:
            vo_by_cadence[f"{cad_start}-{cad_end}"] = float(np.mean(vo_valid[mask_bin]))
    
    return {
        "vo_by_cadence": vo_by_cadence,
        "optimal_cadence": find_optimal_cadence(vo_by_cadence),
    }

def find_optimal_cadence(vo_by_cadence: Dict) -> Optional[str]:
    """Find cadence range with lowest VO."""
    if not vo_by_cadence:
        return None
    return min(vo_by_cadence.items(), key=lambda x: x[1])[0]
```

**B) W modules/ui/biomech.py (nowa sekcja):**
```python
def render_vertical_oscillation_analysis(df_plot):
    """Render Vertical Oscillation analysis section."""
    st.divider()
    st.subheader("📊 Vertical Oscillation (Oscylacja Pionowa)")
    
    # Sprawdź czy mamy dane VO
    vo_col = None
    for col in ["verticaloscillation", "VerticalOscillation", "vo", "oscillation"]:
        if col in df_plot.columns:
            vo_col = col
            break
    
    if vo_col is None:
        st.info("ℹ️ Brak danych Vertical Oscillation w tym pliku.")
        return
    
    # Oblicz statystyki
    from modules.calculations.running_dynamics import calculate_vo_stats, analyze_vo_efficiency
    
    vo_data = df_plot[vo_col].values
    vo_stats = calculate_vo_stats(vo_data)
    
    # Wyświetl metryki
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Średnie VO", f"{vo_stats.get('mean_vo', 0):.1f} cm")
    col2.metric("Min VO", f"{vo_stats.get('min_vo', 0):.1f} cm")
    col3.metric("Max VO", f"{vo_stats.get('max_vo', 0):.1f} cm")
    col4.metric("CV", f"{vo_stats.get('cv_vo', 0):.1f}%")
    
    # Wykres VO w czasie
    fig_vo = go.Figure()
    fig_vo.add_trace(go.Scatter(
        x=df_plot['time_min'],
        y=df_plot[vo_col].rolling(5, center=True).mean(),
        name='VO',
        line=dict(color='#ff6b6b', width=2),
    ))
    
    # Dodaj linię trendu
    if len(df_plot) > 100:
        from scipy import stats
        mask = ~np.isnan(df_plot[vo_col])
        if mask.sum() > 100:
            slope, intercept, _, _, _ = stats.linregress(
                df_plot.loc[mask, 'time_min'], 
                df_plot.loc[mask, vo_col]
            )
            trend = intercept + slope * df_plot['time_min']
            fig_vo.add_trace(go.Scatter(
                x=df_plot['time_min'],
                y=trend,
                name='Trend',
                line=dict(color='white', dash='dash')
            ))
    
    fig_vo.update_layout(
        template="plotly_dark",
        title="Vertical Oscillation w czasie",
        yaxis_title="VO [cm]",
        xaxis_title="Czas [min]",
        height=400
    )
    st.plotly_chart(fig_vo, use_container_width=True)
    
    # Analiza efektywności z kadencją
    if 'cadence' in df_plot.columns or 'cadence_smooth' in df_plot.columns:
        cad_col = 'cadence_smooth' if 'cadence_smooth' in df_plot.columns else 'cadence'
        efficiency = analyze_vo_efficiency(vo_data, df_plot[cad_col].values)
        
        if efficiency.get('optimal_cadence'):
            st.success(f"🎯 **Optymalna kadencja:** {efficiency['optimal_cadence']} SPM "
                      f"(najniższa oscylacja)")
        
        # Wykres VO vs Cadence
        fig_scatter = go.Figure()
        fig_scatter.add_trace(go.Scatter(
            x=df_plot[cad_col],
            y=df_plot[vo_col],
            mode='markers',
            marker=dict(size=4, opacity=0.5, color='#ff6b6b'),
            name='VO vs Cadence'
        ))
        fig_scatter.update_layout(
            template="plotly_dark",
            title="VO vs Kadencja",
            xaxis_title="Cadence [SPM/RPM]",
            yaxis_title="VO [cm]",
            height=400
        )
        st.plotly_chart(fig_scatter, use_container_width=True)
    
    # Interpretacja
    st.info("""
    **💡 Interpretacja Vertical Oscillation:**
    
    **Co to jest?**
    VO to odległość o jaką centrum masy podnosi się i opuszcza podczas biegu.
    
    **Normy (dla biegaczy):**
    - **< 6 cm:** Bardzo efektywny bieg (elite)
    - **6-8 cm:** Dobra efektywność
    - **8-10 cm:** Średnia efektywność
    - **> 10 cm:** Wysoka oscylacja - "bouncing"
    
    **Dla rowerzystów:**
    VO jest naturalnie niższa (siedzenie). Wartości > 3 cm przy pedałowaniu 
    mogą wskazywać na "podskakiwanie" na siodełku.
    
    **Korelacja z kadencją:**
    Wyższa kadencja zazwyczaj = niższa VO (mniej "bouncing").
    Szukaj optymalnego punktu gdzie VO jest minimalna przy komfortowej kadencji.
    """)
```

#### Kroki implementacji:
1. Dodać funkcje w `running_dynamics.py`
2. Dodać sekcję w `biomech.py`
3. Wywołać funkcję w `render_biomech_tab()`
4. Przetestować z plikiem CSV zawierającym VerticalOscillation

---

### Zadanie 3: Walidacja kompletności danych przy imporcie
**Priorytet:** P1 - Krytyczny  
**Czas:** 1h  
**Pliki:** 
- `modules/utils.py` (walidacja)
- `app.py` (wyświetlanie)

#### Nowa klasa validatora:

**A) W modules/utils.py:**
```python
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class DataQualityReport:
    """Report on data quality and completeness."""
    available_metrics: List[str]
    missing_metrics: List[str]
    recommendations: List[str]
    quality_score: float  # 0-100
    sport_type: str  # "cycling", "running", "mixed", "unknown"
    
    def to_dict(self) -> Dict:
        return {
            "available": self.available_metrics,
            "missing": self.missing_metrics,
            "recommendations": self.recommendations,
            "quality_score": self.quality_score,
            "sport_type": self.sport_type,
        }

def validate_data_completeness(df: pd.DataFrame) -> DataQualityReport:
    """
    Validate data completeness and provide recommendations.
    
    Returns a report with available/missing metrics and suggestions.
    """
    available = []
    missing = []
    recommendations = []
    
    # Define required and optional metrics
    metric_definitions = {
        "core": {
            "watts": ["watts", "power"],
            "heartrate": ["heartrate", "hr", "heart_rate"],
        },
        "advanced": {
            "cadence": ["cadence", "cad"],
            "smo2": ["smo2"],
            "thb": ["thb", "total_hemoglobin"],
        },
        "ventilation": {
            "ve": ["tymeventilation", "ve", "ventilation"],
            "br": ["tymebreathrate", "br", "breath_rate"],
        },
        "thermal": {
            "core_temp": ["core_temperature", "core_temp"],
            "skin_temp": ["skin_temperature", "skin_temp"],
        },
        "biomechanics": {
            "vo": ["verticaloscillation", "VerticalOscillation", "vo"],
        },
        "running": {
            "pace": ["pace", "speed"],
            "gct": ["ground_contact", "gct"],
        },
    }
    
    columns_lower = [c.lower() for c in df.columns]
    
    # Check each metric group
    for group, metrics in metric_definitions.items():
        for metric_name, aliases in metrics.items():
            found = any(a.lower() in columns_lower for a in aliases)
            if found:
                available.append(f"{group}.{metric_name}")
            else:
                missing.append(f"{group}.{metric_name}")
    
    # Generate recommendations
    if "core.watts" not in available and "running.pace" not in available:
        recommendations.append("⚠️ Brak danych mocy lub tempa - analiza ograniczona")
    
    if "ventilation.ve" not in available:
        recommendations.append("ℹ️ Brak wentylacji - zakładka Ventilation nieaktywna")
    
    if "biomechanics.vo" not in available:
        recommendations.append("ℹ️ Brak Vertical Oscillation - analiza biomechaniczna ograniczona")
    
    if "advanced.smo2" in available and "ventilation.ve" in available:
        recommendations.append("✅ Pełna analiza fizjologiczna dostępna (SmO2 + VE)")
    
    # Determine sport type
    sport_type = detect_sport_type(df)
    
    # Calculate quality score
    total_metrics = len(available) + len(missing)
    quality_score = (len(available) / total_metrics * 100) if total_metrics > 0 else 0
    
    return DataQualityReport(
        available_metrics=available,
        missing_metrics=missing,
        recommendations=recommendations,
        quality_score=quality_score,
        sport_type=sport_type,
    )

def detect_sport_type(df: pd.DataFrame) -> str:
    """Detect sport type based on available columns."""
    has_power = any(c in df.columns for c in ["watts", "power", "Watts"])
    has_pace = any(c in df.columns for c in ["pace", "speed", "gap"])
    has_cadence = "cadence" in df.columns
    
    if has_power and not has_pace:
        return "cycling"
    elif has_pace and not has_power:
        return "running"
    elif has_power and has_pace:
        return "mixed"
    else:
        return "unknown"
```

**B) W app.py (po załadowaniu danych):**
```python
# Po załadowaniu df_raw
from modules.utils import validate_data_completeness

quality_report = validate_data_completeness(df_raw)
st.session_state["data_quality_report"] = quality_report

# Wyświetl raport jako expander
with st.expander("📋 Raport jakości danych", expanded=False):
    st.write(f"**Typ sportu:** {quality_report.sport_type}")
    st.write(f"**Jakość danych:** {quality_report.quality_score:.0f}%")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Dostępne metryki:**")
        for m in quality_report.available_metrics[:10]:  # Limit display
            st.write(f"  ✅ {m}")
        if len(quality_report.available_metrics) > 10:
            st.write(f"  ... i {len(quality_report.available_metrics) - 10} więcej")
    
    with col2:
        st.write("**Brakujące metryki:**")
        for m in quality_report.missing_metrics[:5]:
            st.write(f"  ❌ {m}")
    
    if quality_report.recommendations:
        st.write("**Rekomendacje:**")
        for rec in quality_report.recommendations:
            st.write(rec)
```

#### Kroki implementacji:
1. Dodać klasę `DataQualityReport` w `utils.py`
2. Zaimplementować `validate_data_completeness()`
3. Dodać `detect_sport_type()`
4. Wywołać walidację w `app.py`
5. Wyświetlić raport w UI

---

### Zadanie 4: Auto-detekcja typu sportu
**Priorytet:** P2 - Ważne  
**Czas:** 1h  
**Pliki:** 
- `app.py` (główna logika)
- `modules/ui/power.py` (warunkowe wyświetlanie)
- `modules/ui/running.py` (warunkowe wyświetlanie)

#### Logika w app.py:
```python
# Po walidacji danych
sport_type = quality_report.sport_type

# Dostosuj UI do typu sportu
if sport_type == "cycling":
    st.info("🚴 Wykryto dane kolarskie - wyświetlanie wskaźników mocy")
    show_power_ui = True
    show_running_ui = False
elif sport_type == "running":
    st.info("🏃 Wykryto dane biegowe - wyświetlanie wskaźników tempa")
    show_power_ui = False
    show_running_ui = True
elif sport_type == "mixed":
    st.info("🚴🏃 Wykryto dane hybrydowe - dostępne oba tryby")
    show_power_ui = True
    show_running_ui = True
else:
    st.warning("❓ Nie można określić typu sportu - wyświetlanie wszystkich metryk")
    show_power_ui = True
    show_running_ui = True

# Przekaż do zakładek
st.session_state["show_power_ui"] = show_power_ui
st.session_state["show_running_ui"] = show_running_ui
```

#### Modyfikacja zakładek:
W każdej zakładce sprawdzać `st.session_state.get("show_power_ui", True)` przed wyświetlaniem.

---

### Zadanie 5: Ulepszenie TDI (Threshold Discordance Index)
**Priorytet:** P2 - Ważne  
**Czas:** 30 min  
**Pliki:** `modules/ui/summary.py`

#### Zmiana w funkcji `_render_tdi_analysis`:
```python
def _render_tdi_analysis(vt1_watts: int, lt1_watts: int):
    """
    Renderowanie analizy TDI z lepszą obsługą brakujących danych.
    """
    # Walidacja danych z bardziej szczegółowymi komunikatami
    if not vt1_watts or vt1_watts <= 0:
        st.warning("""
        ⚠️ **Brak danych VT1 (wentylacyjny)**
        
        Aby obliczyć TDI, potrzebujesz:
        1. Progu wentylacyjnego VT1 (z czujnika wentylacji lub testu progowego)
        2. Progu metabolicznego LT1 (z czujnika SmO2)
        
        **Twoje dane zawierają:** 
        - {} ✅ (SmO2 dostępne)
        - {} ❌ (brak wentylacji)
        
        TDI porównuje zgodność progu wentylacyjnego z progiem metabolicznym.
        Bez danych wentylacyjnych nie można wykonać tej analizy.
        """.format("LT1 (SmO2)" if lt1_watts > 0 else "LT1", "VT1"))
        return
    
    if not lt1_watts or lt1_watts <= 0:
        st.warning("⚠️ **Brak danych LT1 (SmO2)** — nie można obliczyć TDI.")
        return
    
    # ... reszta kodu bez zmian
```

---

### Zadanie 6: Nowy wskaźnik - Running Effectiveness z VO
**Priorytet:** P3 - Nice to have  
**Czas:** 1-2h  
**Pliki:** 
- `modules/calculations/running_dynamics.py`
- `modules/ui/biomech.py`

#### Nowa funkcja:
```python
def calculate_running_effectiveness_from_vo(
    pace_sec_per_km: float,
    vo_cm: float,
    runner_height_cm: float
) -> Dict:
    """
    Calculate running effectiveness using Vertical Oscillation.
    
    Lower VO relative to height = better efficiency.
    """
    if pace_sec_per_km <= 0 or vo_cm <= 0 or runner_height_cm <= 0:
        return {}
    
    # VO as percentage of height
    vo_percent_height = (vo_cm / runner_height_cm) * 100
    
    # Calculate effectiveness score (0-100)
    # Elite runners: VO < 5% of height
    # Average: VO 7-8% of height
    # Poor: VO > 10% of height
    if vo_percent_height < 5:
        score = 100
    elif vo_percent_height < 10:
        score = 100 - (vo_percent_height - 5) * 10
    else:
        score = max(0, 50 - (vo_percent_height - 10) * 5)
    
    return {
        "vo_percent_height": vo_percent_height,
        "effectiveness_score": score,
        "classification": classify_vo_efficiency(vo_percent_height),
    }

def classify_vo_efficiency(vo_percent_height: float) -> str:
    if vo_percent_height < 5:
        return "🟢 Elite - wyjątkowa efektywność"
    elif vo_percent_height < 6.5:
        return "🟢 Bardzo dobra efektywność"
    elif vo_percent_height < 8:
        return "🟡 Dobra efektywność"
    elif vo_percent_height < 10:
        return "🟠 Średnia efektywność"
    else:
        return "🔴 Wymaga poprawy - za dużo bouncing"
```

---

## 4. Zmiany w kodzie

### Lista plików do modyfikacji:

| Plik | Zmiany | Linie |
|------|--------|-------|
| `modules/ui/vent.py` | Ulepszone komunikaty o braku VT | ~25 |
| `modules/calculations/running_dynamics.py` | Nowe funkcje VO | +80 |
| `modules/ui/biomech.py` | Sekcja VO + wykresy | +120 |
| `modules/utils.py` | Walidacja + detekcja sportu | +100 |
| `app.py` | Wywołanie walidacji + raport | +40 |
| `modules/ui/summary.py` | Ulepszone TDI | ~15 |

### Nowe pliki do utworzenia:
- Brak (wszystkie zmiany w istniejących plikach)

---

## 5. Testy

### 5.1 Testy jednostkowe
```python
# tests/test_data_validation.py
def test_detect_sport_type():
    # Test cycling
    df_cycling = pd.DataFrame({"watts": [100, 200], "heartrate": [120, 140]})
    assert detect_sport_type(df_cycling) == "cycling"
    
    # Test running
    df_running = pd.DataFrame({"pace": [300, 320], "heartrate": [120, 140]})
    assert detect_sport_type(df_running) == "running"
    
    # Test mixed
    df_mixed = pd.DataFrame({"watts": [100], "pace": [300]})
    assert detect_sport_type(df_mixed) == "mixed"

def test_vo_stats_calculation():
    vo = np.array([6.5, 7.0, 6.8, 7.2, 6.9])
    stats = calculate_vo_stats(vo)
    assert "mean_vo" in stats
    assert stats["mean_vo"] == pytest.approx(6.88, 0.1)
```

### 5.2 Testy integracyjne
```python
# tests/integration/test_csv_import.py
def test_csv_without_ventilation():
    """Test that app handles CSV without ventilation data gracefully."""
    df = load_data("test_data/no_ventilation.csv")
    report = validate_data_completeness(df)
    assert "ventilation.ve" in report.missing_metrics
    assert any("wentylacji" in rec for rec in report.recommendations)

def test_csv_with_vertical_oscillation():
    """Test that VO data is properly detected and used."""
    df = load_data("test_data/with_vo.csv")
    report = validate_data_completeness(df)
    assert "biomechanics.vo" in report.available_metrics
```

### 5.3 Testy manualne
- [ ] Wgraj CSV bez VT - sprawdź komunikat
- [ ] Wgraj CSV z VO - sprawdź nową sekcję w Biomechanice
- [ ] Wgraj CSV kolarski - sprawdź detekcję
- [ ] Wgraj CSV biegowy - sprawdź detekcję
- [ ] Sprawdź TDI bez VT1

---

## 6. Timeline

### Sprint 1: Podstawowe poprawy (1-2 dni)
- [ ] Zadanie 1: Komunikaty VT (30 min)
- [ ] Zadanie 2: Obsługa VO (2h)
- [ ] Zadanie 3: Walidacja danych (1h)
- [ ] Testy manualne (1h)

### Sprint 2: Usprawnienia (2-3 dni)
- [ ] Zadanie 4: Auto-detekcja sportu (1h)
- [ ] Zadanie 5: Ulepszone TDI (30 min)
- [ ] Zadanie 6: Running Effectiveness z VO (2h)
- [ ] Testy jednostkowe (2h)

### Sprint 3: Finalizacja (1 dzień)
- [ ] Refaktoryzacja i czyszczenie (2h)
- [ ] Dokumentacja (1h)
- [ ] Code review (1h)

**Całkowity czas szacunkowy:** 3-5 dni roboczych

---

## 7. Checklist implementacji

### Przed rozpoczęciem:
- [ ] Utworzyć branch `feature/data-quality-improvements`
- [ ] Upewnić się, że wszystkie testy przechodzą na `main`
- [ ] Przygotować testowe pliki CSV (z VO, bez VT, kolarski, biegowy)

### Podczas implementacji:
- [ ] Regularnie commitować zmiany
- [ ] Testować każdą zmianę osobno
- [ ] Aktualizować dokumentację

### Po implementacji:
- [ ] Uruchomić pełną suitę testów: `pytest tests/ -v`
- [ ] Sprawdzić typowanie: `mypy modules/`
- [ ] Przeprowadzić code review
- [ ] Zmergować do `main`
- [ ] Zaktualizować README.md (opcjonalnie)

---

**Uwagi końcowe:**
Ten plan zakłada stopniową implementację zmian z priorytetyzacją na podstawie wpływu na UX. Zaleca się rozpoczęcie od Zadania 1 i 3, które mają największy wpływ na użytkownika przy stosunkowo niskim nakładzie pracy.
