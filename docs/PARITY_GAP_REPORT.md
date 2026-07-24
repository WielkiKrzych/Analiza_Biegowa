# Raport parytetu funkcji — Analiza_Biegowa vs Analiza_Kolarska / Tri_Dashboard

**Data:** 2026-07-24
**Kontekst:** Analiza_Biegowa jest biegowym odpowiednikiem Analizy_Kolarskiej. Ten dokument
zestawia moduły obecne w Kolarskiej/Tri, a nieobecne w Biegowej, i rekomenduje działania.

## Zasada nadrzędna

Modułów kolarskich **nie kopiujemy 1:1**. Każdy port musi być przełożony na jednostki biegowe
(tempo/GAP zamiast W, spm zamiast rpm, D'/Critical Speed zamiast W'/CP-mocy), inaczej wróci
dokładnie ten dług techniczny, który usunięto w tej rundzie (rpm/W/„na rowerze").

## Co JUŻ jest w Biegowej (parytet osiągnięty)

Rdzeń biegowy istnieje i działa: `pace.py`, `pace_utils.py`, `gap.py`, `d_prime.py`,
`race_predictor.py` (surfaced w zakładce Summary), `running_dynamics.py`,
`running_effectiveness.py`, `dual_mode.py`, `hr_zones.py`, `smo2_phases.py`,
`ventilatory_cpet.py`, `ventilatory_step.py`, `br_analysis.py`. Zakładki: report, running,
biomech, model, hrv, hemo, vent, thermal, nutrition, limiters, thresholds, history,
community, import, heart_rate, summary, drift_maps.

## Braki — priorytetyzacja

### P1 — sport-agnostyczne, wysoka wartość dla biegacza (rekomendowany port)

| Moduł (calc / ui) | Funkcja | Uwaga do portu |
|---|---|---|
| `pmc.py` | Performance Management Chart (CTL/ATL/TSB) | Zamień TSS→RSS (Running Stress Score, już zdefiniowany w migracji) |
| `banister.py` + `banister_ui.py` | Model Banister fitness-fatigue | Wejście: RSS zamiast TSS; reszta bez zmian |
| `periodization.py` + `periodization_ui.py` | Periodyzacja / bloki | Sport-agnostyczne |
| `training_distribution.py` + ui | Rozkład intensywności (polaryzacja) | Strefy = strefy tempa (`pace.py`), nie strefy mocy |
| `training_impact.py` + ui | Wpływ treningu / adaptacje | Sport-agnostyczne |
| `plateau_detector.py` | Detekcja plateau formy | Sport-agnostyczne |
| `aerobic_efficiency.py` + ui | Efektywność tlenowa (EF) | EF = pace/HR lub power/HR; użyć tempa |
| `durability_ui.py` | Durability (spadek na dystansie) | Calc `calculate_durability_index` już jest w `metrics.py` — brakuje tylko UI |
| `tte_ui.py` | Time-to-Exhaustion UI | Calc `tte.py` istnieje; UI opisane w kategoriach %CP/tempa |

### P2 — sport-agnostyczne, średnia wartość

| Moduł | Funkcja | Uwaga |
|---|---|---|
| `heat_strain.py` + ui | Heat Strain Index | Fizjologia, sport-agnostyczna |
| `alert_engine.py` + `alerts.py` | Silnik alertów zdrowotnych | Progi w jednostkach biegowych |
| `test_validator.py` | Walidacja jakości testu | Dostosować kryteria do progresywnego biegu |
| `column_aliases.py` | Aliasy kolumn CSV | Dodać aliasy biegowe (pace/speed/stance_time) |

### P3 — specyficzne dla kolarstwa (NIE portować bez odpowiednika biegowego)

| Moduł | Powód |
|---|---|
| `mpa.py` + `mpa_ui.py` | Maximal Power Available — koncept mocy; biegowy odpowiednik to D'/Critical Speed (już jest) |
| `vlamax_profile.py` + `vlamax_ui.py` | VLaMax z profilu mocy — wymaga modelu biegowego |
| `w_prime_reconstitution.py` + ui | Rekonstytucja W' (dżule mocy) — w biegu odpowiednik to rekonstytucja D' (metry); `d_prime.py` już jest, ale bez modułu rekonstytucji |
| `power.py` (ui) | Zakładka mocy kolarskiej — zastąpiona przez `running.py` (tempo) |

### Infrastruktura do sprawdzenia

`sidebar.py`, `shared.py`, `utils.py` (ui) istnieją w Kolarskiej, brak w Biegowej — Biegowa
prawdopodobnie inline'uje te elementy w `app.py`. Do potwierdzenia przy okazji portu P1.

## Rekomendacja

Zrealizować P1 w osobnej, dedykowanej rundzie (każdy moduł: port + przełożenie jednostek +
test). P3 pominąć lub zaprojektować od zera jako biegowe (D'-reconstitution zamiast
W'-reconstitution). Nie wykonywać hurtowego `cp` z Kolarskiej.
