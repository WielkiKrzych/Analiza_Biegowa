# Inwentarz osieroconego kodu

> **UWAGA — dokument ma dwie warstwy.** Sekcje ponizej opisuja stan **sprzed**
> decyzji (inwentaryzacja). To, co faktycznie usunieto i wyrejestrowano, jest w sekcji
> **„Stan po rundzie domykajacej (2026-09-29)" na koncu pliku** — ona ma pierwszenstwo.


Data: 2026-09-29. Metoda: analiza statyczna + weryfikacja importow dynamicznych.
**Ta czesc to inwentarz, nie plan usuwania** — powstala, zanim cokolwiek usunieto.
Cztery moduly zostaly pozniej skasowane na podstawie osobnej decyzji; patrz sekcja koncowa.

---

## Podsumowanie

| status | liczba modulow | lacznie linii |
|---|---:|---:|
| ZYWY | 0 | 0 |
| TYLKO-TESTY | 1 | 341 |
| **OSIEROCONY** | **24** | **5 915** |
| NIEROZSTRZYGNIETY | 0 | 0 |

Razem 25 kandydatow, 6 256 linii.

### Uwaga o rownoleglych zmianach w repo

Ten inwentarz mierzono na commicie `10330b6`. **W trakcie analizy inni wykonawcy pracowali
rownolegle w tym samym repo** i zmodyfikowali m.in. trzy pliki z listy kandydatow:

| plik | linie na `10330b6` | linie w chwili weryfikacji |
|---|---:|---:|
| `modules/calculations/smo2_breakpoints.py` | 322 | 341 |
| `modules/calculations/trend_engine.py` | 387 | 392 |
| `modules/ui/kpi.py` | 398 | 401 |

**Jeden status sie przez to zmienil:** `modules/calculations/smo2_breakpoints.py` przeszedl
z OSIEROCONY na **TYLKO-TESTY**, bo pojawil sie test, ktory go importuje (szczegoly w sekcji
"TYLKO-TESTY"). Wszystkie pozostale statusy zostaly ponownie zweryfikowane na biezacym drzewie
i sa niezmienione. Numery linii symboli w pozostalych wpisach odnosza sie do commit `10330b6`.

Dodatkowo, poza lista kandydatow, weryfikacja wykazala:

- **4 moduly UI zarejestrowane w `TabRegistry._tabs`, ale nigdy nie wywolane** — 928 linii (sekcja nizej).
- **3 moduly osierocone drugiego rzedu** — 115 + 120 + 83 linii (sekcja nizej).

Dwie sciezki z listy kandydatow byly bledne — pliki istnieja, ale gdzie indziej:

| podana sciezka | rzeczywista sciezka |
|---|---|
| `modules/calculations/intervals.py` | `modules/intervals.py` |
| `modules/utils/time_formatting.py` | `modules/time_formatting.py` |

Katalog `modules/utils/` nie istnieje; `modules/utils.py` jest modulem, nie pakietem.

---

## Metoda i uzyte sondy

Wszystkie sondy uruchomione z katalogu glownego repo, **z wykluczeniem `.claude/`**.
To wazne: `.claude/worktrees/` zawiera dwie pelne kopie tego repo
(`compassionate-shaw/`, `romantic-elbakyan/`, razem 384 pliki `.py`, kazda z wlasnym `app.py`).
Bez wykluczenia `.claude/` kazdy modul wyglada na zywy, bo "importuje go" kopia worktree.

| # | sonda | po co |
|---|---|---|
| S1 | `grep -rnE '^\s*(from\|import)\s+(modules\|services\|models)[\w\.]*' --include=*.py .` | pelny graf importow statycznych (234 trafienia) |
| S2 | `grep -rnE '^\s*from\s+\.+[\w\.]*\s+import' --include=*.py .` | importy **wzgledne** — niewidoczne dla S1; krytyczne, bo `modules/calculations/__init__.py` jest hubem re-eksportu |
| S3 | `grep -rnE 'importlib\|__import__\|getattr\(' --include=*.py .` | import dynamiczny |
| S4 | `grep -rn "modules.<pkg>.<modul>" --include=*.py .` | import po pelnej sciezce kropkowej |
| S5 | `grep -rn "\b<Symbol>\b" --include=*.py\|*.md .` | uzycie na poziomie **symbolu** (nie tylko importu modulu) |
| S6 | `grep -rn "<nazwa>" tests/` | kategoria TYLKO-TESTY |
| S7 | `grep -rn "<nazwa>" --include=*.toml --include=*.cfg --include=*.txt --include=*.sh --include=*.yaml --include=*.yml .` | entry pointy, CI, launcher |
| S8 | odczyt `app.py` | slownik `TabRegistry._tabs` (import dynamiczny) |
| S9 | odczyt `pyproject.toml`, `.github/workflows/test.yml`, `launcher.sh` | punkty wejscia |

### Zrodla zywotnosci sprawdzone osobno (zaden kandydat sie w nich nie pojawil)

1. **`app.py::TabRegistry._tabs`** — 22 wpisy, wartosci to krotki `(sciezka_modulu, nazwa_funkcji)`
   importowane przez `importlib.import_module`, wiec `grep` po imporcie ich nie widzi.
   Klucze: `report, running, biomech, model, hrv, smo2, hemo, vent, thermal, nutrition, limiters,
   thresholds, history, community, import, heart_rate, summary, drift_maps, training_load,
   banister, durability, tte`. **Zaden kandydat nie wystepuje jako wartosc.**
2. **Entry pointy** — `pyproject.toml` **nie ma** sekcji `[project.scripts]` ani `entry_points`.
   Jedyne wystapienie `scripts` to `exclude = ["scripts/"]` w konfiguracji mypy (linia 100).
3. **CI** — `.github/workflows/test.yml` uruchamia `ruff check .`, `pytest -q`, `mypy modules/ services/ models/`.
   Mypy tylko typuje katalogi, nie importuje ich w runtime.
4. **`launcher.sh`** — wykonuje wylacznie `streamlit run app.py` (linia 153).
5. **`tests/**`** — sonda S6 dla wszystkich 25 kandydatow zwrocila **zero trafien**.
6. **Stringi jako nazwy modulow/atrybutow** — jedyne miejsca z `importlib` to `app.py:68-69`
   (dyspozytor `TabRegistry`) i `tests/ui/test_review_ui.py:246-253`, ktory importuje dynamicznie
   `modules.ui.vent_tab`, `modules.ui.smo2`, `modules.ui.vent_charts` — zadnego kandydata.
   `modules/ui/registry.py:142` uzywa `importlib` na wlasny uzytek, ale sam nie ma wolajacego.
7. **Brak `pages/`** — katalog nie istnieje, wiec nie ma wielostronicowego mechanizmu Streamlita,
   ktory omijalby `app.py`.
8. **Brak `sys.path` hackow** — jedyne `sys.path` w repo to `tests/conftest.py:5`.
9. **Pakietowe `__init__.py`** — `modules/` nie ma `__init__.py` (namespace package);
   `modules/ui/__init__.py` jest **pusty**; `modules/export/__init__.py` i `modules/ai/__init__.py`
   zawieraja tylko docstring; `modules/reporting/__init__.py` nie re-eksportuje zadnego kandydata.
   Zaden kandydat nie jest wiec osiagalny przez re-eksport pakietu.

### Czego ta analiza nie obejmuje

- Wolajacych spoza repo (notebooki, skrypty poza drzewem, inne klony).
- Uruchomien runtime — nie bylo testu "odpal aplikacje i sprawdz, czy modul sie zaladuje";
  status wynika z analizy statycznej grafow importow.
- Dynamicznego `getattr` po nazwie spoza `TabRegistry` — takiego wzorca w repo nie ma (S3).

---

## OSIEROCONE

Kazdy wpis: symbol definiujacy zycie modulu, dowod braku wolajacego, ocena ryzyka usuniecia.
Wspolny dowod negatywny dla wszystkich (nie powtarzany w kazdym wpisie):
brak w `TabRegistry._tabs`, brak w `pyproject.toml`, **zero trafien w `tests/**`**
(sonda S6 dla calego zestawu zwrocila pusty wynik).

---

### `modules/export/fit_exporter.py` — 436 linii

- **Status:** OSIEROCONY
- **Publiczne symbole:** `FitExporter` (l.41), `PlatformSync` (l.381)
- **Dowod:** `grep -rn "modules.export.fit_exporter" --include=*.py .` → **0 trafien** poza wlasnym plikiem;
  S5 dla `FitExporter|PlatformSync` → trafienia wylacznie w l.41, 381, 385, 391 wlasnego pliku
  (`PlatformSync` tworzy `FitExporter` sam dla siebie, l.385).
- **Zaleznosci:** tylko `struct`, `datetime`, `io`, `pandas` — bez bibliotek zewnetrznych.
- **Ryzyko usuniecia: srednie.** Usuniecie niczego nie lamie technicznie, ale to **jedyna**
  implementacja eksportu FIT w repo i samodzielna funkcja uzytkowa (eksport sesji do zegarka).
  Kod nie jest niczym zastepczym pokryty.

---

### `modules/calculations/report_generator.py` — 408 linii

- **Status:** OSIEROCONY
- **Publiczne symbole:** `ReportSection` (l.57), `RampTestReport` (l.67), `generate_report` (l.86),
  `format_report_markdown` (l.348), `__all__` (l.402)
- **Dowod:** `grep -rn "modules.calculations.report_generator" --include=*.py .` → **0 trafien**;
  S5 dla `RampTestReport|format_report_markdown|generate_report` → tylko wlasny plik
  (plus wzmianki w `methodology/ramp_test/08_algorithm_map.md:264,308,342` i
  `methodology/ramp_test/09_code_audit_todo.md:111`, gdzie `ReportGenerator` jest opisany jako
  element architektury, a nie wywolany).
- **Uwaga:** `modules/calculations/__init__.py` (hub re-eksportu, 223 linie) **nie** importuje
  tego modulu — sprawdzone sonda S2.
- **Ryzyko usuniecia: srednie.** To rownolegly generator raportu w formacie Markdown obok zywego
  generatora PDF (`modules/reporting/pdf/builder.py`, `persistence_save.py`). Dokumentacja
  methodology opisuje `ReportGenerator` jako "DO IMPLEMENTACJI", wiec modul moze byc zamierzona
  przyszla sciezka, a nie przypadkowym odpadem.

---

### `modules/ui/kpi.py` — 401 linii (398 na commicie `10330b6`)

- **Status:** OSIEROCONY (zdublowana, porzucona wersja zywej zakladki)
- **Publiczne symbole:** `render_kpi_tab` (l.299), `_build_drift_chart` (l.9),
  `_render_smo2_panel` (l.93), `_render_hr_panel` (l.164), `_render_ventilation_chart` (l.215)
- **Dowod:** `grep -rn "modules.ui.kpi" --include=*.py .` → **0 trafien**;
  S5 dla `render_kpi_tab` → tylko wlasny plik l.299.
- **Kluczowy dowod nadmiarowosci:** zywa zakladka `"report"` w `app.py:37` to
  `modules.ui.report::render_report_tab`, a jej etykieta w UI brzmi wlasnie
  **"📋 Raport z KPI"** (`app.py:242`). `modules/ui/report.py` zawiera ten sam zestaw sekcji
  co `kpi.py`: `_render_kpi_section` (l.78), `_render_drift_chart` (l.314),
  `_render_smo2_column` (l.412), `_render_hr_column` (l.471), `_render_ventilation_section` (l.508).
  To funkcjonalnie ten sam ekran, zaimplementowany dwa razy.
- **Ryzyko usuniecia: niskie.** Uzytkownik nie traci zadnej widocznej funkcji — zakladka dziala
  z `report.py`. Przed usunieciem warto porownac pary `_build_drift_chart` (kpi) vs
  `_render_drift_chart` (report), bo to niezalezne implementacje i jedna z nich moze byc nowsza.

---

### `modules/reporting/summary_export.py` — 388 linii

- **Status:** OSIEROCONY (niedokonczona integracja — jest plan, nie ma wpiecia)
- **Publiczne symbole:** `CHART_SIZES` (l.15), `add_watermark` (l.23), `export_chart_to_png` (l.75),
  `generate_summary_charts_zip` (l.110)
- **Dowod:** `grep -rn "modules.reporting.summary_export" --include=*.py .` → **0 trafien**;
  S5 dla `generate_summary_charts_zip|CHART_SIZES|add_watermark` → trafienia wylacznie w
  wlasnym pliku oraz w `docs/plans/2025-02-07-summary-png-export.md` (l.381, 460-464, 494-501, 538-586),
  gdzie sa **testy i przyklad uzycia z planu**, ktore nigdy nie trafily do `tests/**`.
- **Uwaga metodologiczna:** plan `docs/plans/2025-02-07-summary-png-export.md` zaklada takze
  dodanie przycisku eksportu w sidebarze. Sidebar (`modules/frontend/layout.py`) nie zawiera
  wolania `generate_summary_charts_zip` — integracja nie zostala dokonczona.
- **Ryzyko usuniecia: srednie.** To jedyna implementacja eksportu wykresow do PNG/ZIP
  z watermarkiem, a jej brak jest efektem niedokonczonej pracy, nie porzucenia pomyslu.
  Usuniecie przekresla plan z `docs/plans/`.

---

### `modules/ai/interval_detector.py` — 387 linii

- **Status:** OSIEROCONY
- **Publiczne symbole:** `IntervalType` (l.19), `DetectedInterval` (l.61), `IntervalDetector` (l.97)
- **Dowod:** `grep -rn "modules.ai.interval_detector" --include=*.py .` → **0 trafien**
  (caly pakiet `modules/ai/` ma tylko `__init__.py` z docstringiem i ten plik);
  S5 dla `IntervalDetector|DetectedInterval|IntervalType` → tylko wlasny plik.
- **Kolizja nazw:** metoda `IntervalDetector.detect_intervals` (l.112) ma odpowiednik
  jako funkcja modulowa `modules/intervals.py::detect_intervals` (l.98) — **takze osierocony**.
  Dwie niezalezne implementacje tej samej rzeczy, obie martwe.
- **Ryzyko usuniecia: niskie.** Modul samodzielny, zaleznosci `numpy`/`pandas`/`scipy`,
  nic go nie importuje, nic nie dziedziczy po jego typach.

---

### `modules/calculations/trend_engine.py` — 392 linie (387 na commicie `10330b6`)

- **Status:** OSIEROCONY
- **Publiczne symbole:** `MetricTrend` (l.30), `TrendAnalysis` (l.42), `load_ramp_test_history` (l.65),
  `extract_metrics_from_report` (l.112), `calculate_rate_per_week` (l.151),
  `classify_direction` (l.191 w biezacym drzewie, l.186 na `10330b6`), `analyze_trends` (l.207)
- **Dowod:** `grep -rn "modules.calculations.trend_engine" --include=*.py .` → **0 trafien**;
  S5 dla `TrendAnalysis|analyze_trends|load_ramp_test_history|MetricTrend|classify_direction` →
  wylacznie wlasny plik. Brak w `modules/calculations/__init__.py`.
- **Uwaga:** modul uzywa `from modules.reporting.persistence import load_ramp_test_report`
  w ciele funkcji (l.74) — zaleznosc istnieje, ale tylko w jedna strone.
  Zywy odpowiednik analizy trendow to `modules/ui/trends_history.py` + `modules.ui.report`,
  ktore korzystaja z `calculate_trend` z `modules/calculations`.
- **Ryzyko usuniecia: srednie.** Modul liczy metryki trendu (rate/week, klasyfikacja kierunku,
  adaptation score) i jest jedynym miejscem z ta logika — usuniecie gubi gotowy, kompletny
  silnik analizy trendow z historii ramp testow.

---

### `modules/reports.py` — 367 linii

- **Status:** OSIEROCONY
- **Publiczne symbole:** `generate_docx_report` (l.233), `export_all_charts_as_png` (l.297)
  (+ 7 helperow `_add_*`, `_calculate_fallback_metrics`)
- **Dowod:** `grep -rnE "modules\.reports\b" --include=*.py .` → **0 trafien**;
  S5 dla `generate_docx_report|export_all_charts_as_png` → tylko wlasny plik.
- **Uwaga o wewnetrznej zaleznosci:** `modules/reports.py:322` importuje
  `from .chart_exporters import CHART_REGISTRY, ChartContext`. `modules/chart_exporters.py` (300 linii)
  jest importowany **takze** przez `modules/reports.py` jako jedynego wolajacego — sprawdzone
  sonda S1/S2. To czyni `chart_exporters.py` drugim w kolejce po usunieciu `reports.py`.
- **Zaleznosc:** `python-docx` (`docx`, zadeklarowany w `pyproject.toml:29`) jest importowany
  w repo **wylacznie** przez ten plik (`modules/reports.py:9-11`). Po jego usunieciu
  `python-docx` staje sie nieuzywana zaleznoscia w `pyproject.toml`.
- **Ryzyko usuniecia: srednie.** To jedyny dzialajacy generator raportu DOCX w repo.
  W `persistence_pdf.py:76` i `l.244` istnieje proba importu `from .docx_builder import build_ramp_docx`,
  ale **plik
  `modules/reporting/docx_builder.py` nie istnieje** (sprawdzone: `ls` zwraca "No such file").
  Import jest w `try/except (ImportError, OSError, ValueError)` (l.75-82), wiec kazde generowanie
  PDF loguje `logger.error("DOCX generation failed: ...")` i idzie dalej — czyli sciezka DOCX jest
  zepsuta w dwoch miejscach naraz. Patrz sekcja "Znaleziska spoza listy kandydatow".

---

### `modules/calculations/smo2_breakpoints.py` — PRZEKLASYFIKOWANY (bylo OSIEROCONY, jest TYLKO-TESTY)

Na commicie `10330b6` ten modul nie mial zadnego wolajacego: 322 linie, zero trafien
`grep -rn "modules.calculations.smo2_breakpoints" --include=*.py .` poza wlasnym plikiem,
`detect_smo2_breakpoints_segmented` w linii 43. W trakcie analizy rownolegly wykonawca dodal
`tests/calculations/test_wave2_calculations.py:18`
(`from modules.calculations.smo2_breakpoints import detect_smo2_breakpoints_segmented`),
co zmienia status na **TYLKO-TESTY**. Plik ma teraz 341 linii, a
`detect_smo2_breakpoints_segmented` przesunelo sie na linie 59 (doszedl nowy helper
`_validate_breakpoint_input`, l.43). Pelny wpis — sekcja "TYLKO-TESTY" nizej.

---

### `modules/calculations/hr_zones.py` — 318 linii

- **Status:** OSIEROCONY
- **Publiczne symbole:** `HRZoneConfig` (l.24), `calculate_hr_zones_hrmax` (l.62),
  `calculate_hr_zones_karvonen` (l.84), `calculate_hr_zones_lthr` (l.115), `get_hr_zone` (l.140),
  `calculate_time_in_hr_zones` (l.223), `get_zone_boundaries` (l.270),
  `estimate_lthr_from_threshold_pace` (l.288), `__all__` (l.306)
- **Dowod:** `grep -rn "modules.calculations.hr_zones" --include=*.py .` → **0 trafien**;
  S5 dla `HRZoneConfig|get_hr_zone|calculate_hr_zones_hrmax|calculate_time_in_hr_zones` →
  wylacznie wlasny plik. Brak w `modules/calculations/__init__.py`.
- **Kontekst:** `README.md:312` opisuje ten modul jako funkcje dodana ("✅ `hr_zones.py`:
  Nowy modul stref HR"), a `docs/PARITY_GAP_REPORT.md:17` wymienia go wsrod brakujacych
  elementow parytetu — czyli modul jest **udokumentowany jako funkcja, ale nigdy nie wpiety**.
  Strefy HR w UI liczy `modules/ui/heart_rate.py` wlasna sciezka.
- **Ryzyko usuniecia: wysokie.** Usuniecie kasuje gotowa, kompletna implementacje trzech modeli
  stref HR (HRmax, Karvonen, LTHR), ktora dokumentacja projektu (README + PARITY_GAP_REPORT)
  traktuje jako czesc docelowego zestawu funkcji. To raczej kandydat do **wpiecia** niz do usuniecia.

---

### `modules/calculations/gas_exchange_estimation.py` — 314 linii

- **Status:** OSIEROCONY
- **Publiczne symbole:** `estimate_vo2_from_power` (l.16), `estimate_vo2_from_hr` (l.48),
  `estimate_vco2_from_vo2` (l.85), `add_estimated_gas_exchange` (l.125),
  `detect_vt_with_estimated_gas_exchange` (l.190), `detect_vt_percentile_based` (l.237)
- **Dowod:** `grep -rn "modules.calculations.gas_exchange_estimation" --include=*.py .` → **0 trafien**;
  S5 dla wszystkich szesciu symboli → trafienia wylacznie w liniach 16-237 wlasnego pliku
  (funkcje wolaja sie wzajemnie: l.164, 168, 178, 181, 220). Brak w `modules/calculations/__init__.py`.
- **Uwaga:** wewnetrznie uzywa `from .ventilatory import detect_vt_ramp_python` (l.217) —
  `modules/calculations/ventilatory.py` jest zywy (importowany przez `__init__.py`), wiec
  zaleznosc jest jednokierunkowa i bezpieczna.
- **Ryzyko usuniecia: niskie-srednie.** Samodzielny modul szacujacy wymiane gazowa z mocy/HR
  i wykrywajacy VT na danych szacowanych. Nic go nie uzywa, ale to jedyna taka implementacja
  (obejscie braku miernika gazow) — usuniecie gubi zdolnosc, nie poprawnosc.

---

### `modules/monitoring.py` — 302 linie

- **Status:** OSIEROCONY
- **Publiczne symbole:** `TimingRecord` (l.22), `PerformanceMonitor` (l.31), `monitor` (l.150),
  `timed` (l.153), `get_memory_usage` (l.168), `memory_tracker` (l.184), `CacheMetrics` (l.203),
  `cache_metrics` (l.229), `track_cache_hit` (l.232), `track_cache_miss` (l.237),
  `get_cache_stats` (l.242), `generate_performance_report` (l.250)
- **Dowod:** `grep -rn "modules.monitoring" --include=*.py .` → **0 trafien**;
  S5 dla `PerformanceMonitor|TimingRecord|memory_tracker|generate_performance_report|CacheMetrics|
  track_cache_hit|track_cache_miss|get_memory_usage` → wylacznie wlasny plik;
  `get_cache_stats` → **dwie** definicje, obie martwe: `modules/monitoring.py:242` i
  `modules/cache_utils.py:172` (kolizja nazw miedzy dwoma osieroconymi modulami).
- **Zaleznosci:** wylacznie standard library (`functools`, `logging`, `threading`, `time`,
  `collections`, `contextlib`, `dataclasses`, `datetime`, `typing`) — zero zaleznosci zewnetrznych.
- **Ryzyko usuniecia: niskie.** Nic go nie importuje, wiec dekoratory `@timed`/`@memory_tracker`
  nigdzie nie sa nalozone, a `monitor`/`cache_metrics` to nieuzywane singleton modulowe.
  Usuniecie nie zmienia zadnego zachowania runtime.

---

### `modules/task_queue.py` — 298 linii

- **Status:** OSIEROCONY
- **Publiczne symbole:** `TaskStatus` (l.21), `Task` (l.32), `BackgroundTaskManager` (l.47),
  `get_task_manager` (l.229), `submit_background_task` (l.237), `get_task_status` (l.253),
  `get_task_result` (l.260), `ProgressCallback` (l.277)
- **Dowod:** `grep -rn "modules.task_queue" --include=*.py .` → **0 trafien**;
  S5 dla `BackgroundTaskManager|get_task_manager|submit_background_task|get_task_status|
  get_task_result|ProgressCallback|TaskStatus` → wylacznie wlasny plik.
- **Kolizja architektoniczna:** rownolegle dziala `modules/calculations/async_runner.py`,
  ktory **jest** zywy (re-eksportowany przez `modules/calculations/__init__.py:29,212`
  jako `run_in_thread`) i realizuje to samo zadanie (pula watkow + asynchroniczne uruchamianie).
- **Zaleznosci:** wylacznie standard library (`threading`, `uuid`, `concurrent.futures`,
  `dataclasses`, `datetime`, `enum`, `typing`).
- **Ryzyko usuniecia: niskie.** Nic nie importuje, zero zaleznosci zewnetrznych, funkcjonalnie
  wyparte przez `async_runner.py`.

---

### `modules/health_alerts.py` — 287 linii

- **Status:** OSIEROCONY
- **Publiczne symbole:** `HealthAlert` (l.19), `HealthMonitor` (l.40)
  (metody: `check_cardiac_drift`, `check_thermal_stress`, `check_muscle_fatigue`,
  `check_overreaching`, `check_hydration_status`, l.96-271)
- **Dowod:** `grep -rn "modules.health_alerts" --include=*.py .` → **0 trafien**;
  S5 dla `HealthAlert|HealthMonitor` → wylacznie wlasny plik.
- **Uwaga:** modul monitoruje dokladnie te same zjawiska, ktore liczy zywy lancuch
  `modules/calculations/cardiac_drift.py`, `thermoregulation.py`, `canonical_physio.py`
  (wolane z `modules/reporting/persistence_save.py:134,230,283,408`) — ale jest od nich
  niezalezna, rownolegla implementacja o innym interfejsie (alerty zamiast metryk).
- **Ryzyko usuniecia: srednie.** Usuniecie gubi gotowa warstwe alertow zdrowotnych
  (drift sercowy, stres termiczny, przetrenowanie, nawodnienie) — 6 gotowych reguł,
  ktore nie maja odpowiednika w postaci alertow nigdzie indziej.

---

### `modules/cache_utils.py` — 223 linie

- **Status:** OSIEROCONY
- **Publiczne symbole:** `get_cache` (l.33), `cache_result` (l.49), `_generate_cache_key` (l.109),
  `_hash_arg` (l.124), `_invalidate_cache` (l.147), `clear_cache` (l.165), `get_cache_stats` (l.172),
  `cache_1h`/`cache_24h`/`cache_7d` (l.186-188), `cached_analyze_step_test` (l.195),
  `cached_detect_smo2_thresholds` (l.203), `cached_calculate_cp_wprime` (l.211),
  `cached_generate_summary_pdf` (l.219)
- **Dowod:** `grep -rn "modules.cache_utils" --include=*.py .` → **0 trafien**;
  S5 dla `cache_result|clear_cache|get_cache|cached_analyze_step_test|cached_detect_smo2_thresholds|
  cached_calculate_cp_wprime|cached_generate_summary_pdf` → trafienia wylacznie w liniach
  33-219 wlasnego pliku. `clear_cache` i `get_cache` nie maja zadnego wolajacego.
- **Niezalezne potwierdzenie w repo:** `docs/cleanup-candidates.md:31-34` juz stwierdza wprost,
  ze "kazda funkcja dekorowana `cache_result` w tym module (...) **obecnie nie ma call site w repo**".
  Moj audyt to potwierdza i rozszerza na caly modul.
- **Uwaga:** modul wymaga `streamlit` (poprzez `modules.config`) i uzywa `st.cache_data`.
  Ma znany, opisany defekt: `_hash_arg` (l.124) sprowadza listy i slowniki do `LIST:<len>`/`DICT:<len>`,
  wiec dwie rozne listy tej samej dlugosci daja ten sam klucz cache.
  Defekt jest **utajony** (nic nie wola), ale stanie sie realny, jesli modul zostanie wpiety bez naprawy.
- **Ryzyko usuniecia: niskie.** Caly modul jest nieosiagalny, a jego ewentualne wpiecie wymagaloby
  najpierw naprawy `_hash_arg`.

---

### `modules/ui/registry.py` — 191 linii — **[USUNIETY 2026-09-29]**

- **Status:** OSIEROCONY
- **Publiczne symbole:** `PluginRegistry` (l.21), `_registry` (l.176), `get_registry` (l.179),
  `register_plugin` (l.184), `discover_plugins` (l.189)
- **Dowod:** `grep -rn "PluginRegistry|get_registry|register_plugin|discover_plugins" --include=*.py .`
  → trafienia wylacznie w tym pliku (l.21, 28, 37, 176, 179, 184, 189);
  `grep -rn "UITabPlugin|TabConfig|UIGroupConfig|TAB_GROUPS|get_grouped_tabs|get_available_tabs"
  --include=*.py .` **poza** `registry.py` i `base.py` → **0 trafien**.
- **Werdykt przypadku imiennego:** patrz sekcja "Przypadki imienne" — to porzucona druga
  implementacja rejestru zakladek. Zywy dyspozytor jest w `app.py`.
- **Ryzyko usuniecia: niskie.** Nic nie importuje modulu, a jego usuniecie dodatkowo osieroca
  `modules/ui/base.py` (patrz "Osierocone drugiego rzedu").

---

### `modules/manual_overrides.py` — 171 linii

- **Status:** OSIEROCONY
- **Publiczne symbole:** `ManualOverrides` (l.21), `get_manual_overrides` (l.65),
  `resolve_value` (l.119), `to_dict` (l.139)
- **Dowod:** `grep -rn "get_manual_overrides|resolve_value" --include=*.py .` → trafienia wylacznie
  w tym pliku (l.8, 10, 11 — docstring z przykladem — oraz definicje l.65, 119);
  `grep -rn "modules.manual_overrides" --include=*.py .` → tylko wlasny docstring l.8.
- **Wazna pulapka nazewnicza:** identyfikator `manual_overrides` wystepuje **bardzo szeroko**
  w repo (`modules/reporting/pdf/builder.py`, `persistence_pdf.py`, `persistence_save.py`,
  `modules/reporting/figures/*`), ale **zawsze jako nazwa argumentu/zmiennej lokalnej**,
  nigdy jako import z tego modulu. To latwo pomylic przy powierzchownym `grep`.
- **Zywy odpowiednik:** `modules/canonical_values.py::resolve_all_thresholds` (zywy, wolany z
  `modules/reporting/persistence_save.py:576,591`) realizuje te sama role — scalanie recznych
  progow z automatycznymi. `manual_overrides.py` to rownolegla, wczesniejsza wersja.
- **Ryzyko usuniecia: niskie.** Rola jest pokryta przez zywy `canonical_values.py`.
  Warto jednak sprawdzic, czy `ManualOverrides` nie zawiera pol, ktorych `canonical_values` nie obsluguje.

---

### `modules/ui/compare.py` — 163 linie

- **Status:** OSIEROCONY
- **Publiczne symbole:** `render_comparison_tab` (l.97), `_build_history_entry` (l.10),
  `_build_display_rows` (l.29), `_comparison_status_emoji` (l.65), `_render_interpretation` (l.73)
- **Dowod:** `grep -rn "modules.ui.compare" --include=*.py .` → **0 trafien**;
  S5 dla `render_comparison_tab` → wylacznie wlasny plik l.97. Brak klucza `compare` w `_tabs`.
- **Uwaga:** modul importuje `modules.calculations.repeatability` (l.4). Ten modul jest **zywy**
  (ma wlasny test: `tests/test_repeatability.py:1`), wiec usuniecie `compare.py` nie osieroca niczego.
- **Ryzyko usuniecia: niskie.** Samodzielny, nieuzywany ekran UI; jedyna jego zaleznosc jest zywa
  i niezalezna.

---

### `modules/ui/genetics_ui.py` — 156 linii

- **Status:** OSIEROCONY
- **Publiczne symbole:** `render_genetics_tab` (l.13), `_display_profile` (l.79),
  `_create_score_gauge` (l.133)
- **Dowod:** `grep -rn "modules.ui.genetics_ui" --include=*.py .` → **0 trafien**;
  S5 dla `render_genetics_tab` → tylko wlasny plik l.13. Brak klucza w `_tabs`.
- **Konsekwencja:** jest **jedynym** importerem `modules/genetics.py`
  (`grep -rn "modules.genetics" --include=*.py .` → tylko `genetics_ui.py:10`).
  Usuniecie osieroca `modules/genetics.py` (120 linii) — patrz "Osierocone drugiego rzedu".
- **Ryzyko usuniecia: srednie.** Pociaga za soba drugi modul. `modules/genetics.py` liczy
  profile genetyczne (ACTN3, ACE) — to material ekspercki, ktory moze byc zamierzona funkcja
  na przyszlosc, a nie odpadem.

---

### `modules/ui/environment_ui.py` — 154 linie

- **Status:** OSIEROCONY
- **Publiczne symbole:** `render_environment_tab` (l.14), `_display_weather` (l.82)
- **Dowod:** `grep -rn "modules.ui.environment_ui" --include=*.py .` → **0 trafien**;
  S5 dla `render_environment_tab` → tylko wlasny plik l.14. Brak klucza w `_tabs`.
- **Konsekwencja:** jest **jedynym** importerem `modules/environment.py`
  (`grep -rn "modules.environment" --include=*.py .` → tylko `environment_ui.py:11`).
  Usuniecie osieroca `modules/environment.py` (83 linie) — patrz "Osierocone drugiego rzedu".
- **Ryzyko usuniecia: srednie.** Pociaga za soba drugi modul; `modules/environment.py` ma
  warstwe serwisowa (`EnvironmentService`, `WeatherData`) i prawdopodobnie wymaga sieci,
  wiec jest to raczej niedokonczona funkcja niz smiec.

---

### `modules/ui/header.py` — 143 linie

- **Status:** OSIEROCONY (modul oficjalnie oznaczony jako przestarzaly)
- **Publiczne symbole:** `render_sticky_header` (l.14), `render_metric_cards` (l.68),
  `show_breadcrumb` (l.83), `extract_header_data` (l.117)
- **Dowod:** `grep -rn "modules.ui.header" --include=*.py .` → **0 trafien**;
  S5 dla `render_sticky_header` → wlasny plik l.14 oraz **`modules/frontend/components.py:38`**
  (`UIComponents.render_sticky_header`), wolany realnie z `services/dashboard_renderer.py:164`.
  S5 dla `show_breadcrumb` → wlasny plik + `modules/frontend/components.py:18`, wolany z `app.py`
  jako `UIComponents.show_breadcrumb`.
- **Niezalezne potwierdzenie w repo:** `docs/cleanup-candidates.md:7` wymienia
  `modules/ui/header.py::extract_header_data` wsrod funkcji, ktorym dodano ostrzezenie
  o przestarzalosci. Sam modul potwierdza to w `l.132`, wskazujac nastepce:
  `services.session_orchestrator.prepare_sticky_header_data`.
- **Werdykt:** cztery funkcje, kazda ma zywego nastepce w `modules/frontend/components.py`
  albo `services/dashboard_renderer.py`. Modul jest w calosci wyparty.
- **Ryzyko usuniecia: niskie.** Podwojnie potwierdzone: brak wolajacych + jawna deprecjacja
  wraz ze wskazaniem nastepcy.

---

### `modules/async_utils.py` — 133 linie

- **Status:** OSIEROCONY
- **Publiczne symbole:** `run_in_thread` (l.20), `load_data_async` (l.42),
  `analyze_ramp_test_async` (l.54), `detect_smo2_thresholds_async` (l.68),
  `generate_pdf_async` (l.80), `AsyncProgressTracker` (l.94), `shutdown_executor` (l.131)
- **Dowod:** `grep -rn "modules.async_utils" --include=*.py .` → **0 trafien**;
  S5 dla `load_data_async|analyze_ramp_test_async|detect_smo2_thresholds_async|generate_pdf_async|
  AsyncProgressTracker` → wylacznie wlasny plik.
- **Wazna pulapka nazewnicza:** `run_in_thread` i `shutdown_executor` **wygladaja** na zywe, ale
  trafienia dotycza **innego modulu**: `modules/calculations/async_runner.py` (l.42, 51) ma wlasne
  funkcje o tych samych nazwach i to one sa re-eksportowane przez
  `modules/calculations/__init__.py:34,212`. Wersje z `async_utils.py` nie maja wolajacego.
- **Ryzyko usuniecia: niskie.** Funkcjonalnie wyparte przez zywy `async_runner.py`;
  brak wolajacych potwierdzony na poziomie symbolu, nie tylko importu.

---

### `modules/intervals.py` — 126 linii

- **Status:** OSIEROCONY
- **Publiczne symbole:** `detect_intervals` (l.98), `_resolve_watts_col` (l.4),
  `_find_raw_intervals` (l.9), `_merge_close_intervals` (l.40), `_build_interval_stats` (l.62)
- **Dowod:** `grep -rn "modules.intervals" --include=*.py .` → **0 trafien**;
  `grep -rnE "\bdetect_intervals\b" --include=*.py .` → dwa trafienia, oba definicyjne:
  `modules/intervals.py:98` (funkcja) i `modules/ai/interval_detector.py:112` (metoda tej samej nazwy).
  **Zadnego wywolania.**
- **Uwaga o sciezce:** lista kandydatow podawala `modules/calculations/intervals.py` — ten plik
  nie istnieje. Wlasciwa sciezka to `modules/intervals.py`.
- **Ryzyko usuniecia: niskie.** Zero wolajacych, zaleznosc tylko `pandas`.
  Uwaga na kolizje: `detect_intervals` z tego modulu i metoda w `ai/interval_detector.py`
  to dwie niezalezne implementacje — usuwajac jedna, nie zakladaj, ze druga jest ta sama.

---

### `modules/time_formatting.py` — 106 linii — **[USUNIETY 2026-09-29]**

- **Status:** OSIEROCONY
- **Publiczne symbole:** `format_time_hhmmss` (l.8), `format_time_axis` (l.31),
  `get_time_axis_config` (l.50), `pace_to_seconds` (l.83), `seconds_to_pace` (l.102)
- **Dowod:** `grep -rn "modules.time_formatting" --include=*.py .` → **0 trafien**;
  S5 dla `format_time_hhmmss|format_time_axis|get_time_axis_config|seconds_to_pace` →
  wylacznie wlasny plik.
- **Uwaga o sciezce:** lista kandydatow podawala `modules/utils/time_formatting.py`;
  katalog `modules/utils/` nie istnieje. Wlasciwa sciezka to `modules/time_formatting.py`.
- **Powazna pulapka nazewnicza i semantyczna:** `pace_to_seconds` wystepuje w dwoch miejscach
  o **odwrotnej semantyce**:
  - `modules/time_formatting.py:83` — `pace_to_seconds(pace: float) -> str` (liczby → string),
  - `modules/calculations/pace_utils.py:68` — `pace_to_seconds(pace_str: str) -> float` (string → liczby).
  Zywa jest wersja z `pace_utils.py` — ma testy (`tests/calculations/test_pace_utils.py:46-48`).
  Wersja z `time_formatting.py` jest martwa. To najniebezpieczniejszy wpis na tej liscie:
  przy przypadkowym imporcie "nie tego" `pace_to_seconds` kod dostanie funkcje o odwrotnym
  kierunku konwersji i to samo wyrazenie policzy cos innego.
- **Ryzyko usuniecia: niskie** (nic nie importuje), **ale usuniecie jest tu zalecane** wlasnie
  ze wzgledu na kolizje semantyczna.

---

### `modules/ui/callbacks.py` — 42 linie

- **Status:** OSIEROCONY
- **Publiczne symbole:** `StreamlitCallback` (l.13)
- **Dowod:** `grep -rn "modules.ui.callbacks" --include=*.py .` → **0 trafien**;
  S5 dla `StreamlitCallback` → tylko wlasny plik l.13.
- **Uwaga:** modul importuje `TrainingCallback` z `modules.ml_logic` (l.10). `modules.ml_logic`
  jest **zywy** (importowany z `app.py:12`), wiec usuniecie tego pliku nie osieroca niczego.
- **Ryzyko usuniecia: niskie.** Pojedyncza klasa, brak wolajacych, jedyna zaleznosc zywa
  i niezalezna. Warto tylko sprawdzic, czy `StreamlitCallback` nie mial byc podlaczony do
  `predict_only`/`train_model` w `ml_logic` — wtedy to niedokonczona integracja, nie smiec.

---

### `modules/reporting/pdf/layout_executive.py` — 9 linii — **[USUNIETY 2026-09-29]**

- **Status:** OSIEROCONY jako **fasada** (re-eksport); same symbole sa zywe
- **Publiczne symbole:** `__all__` (l.6) z `build_page_executive_summary`,
  `build_page_executive_verdict`
- **Dowod:** `grep -rn "modules.reporting.pdf.layout_executive" --include=*.py .` → **0 trafien**;
  `grep -rn "layout_executive\b" --include=*.py .` → trafienia w `builder.py:44-45` i `layout.py:24-25`,
  ale **wszystkie** wskazuja na `layout_executive_summary` i `layout_executive_verdict`
  (z sufiksem), nie na te fasade. `modules/reporting/pdf/__init__.py` (39 linii) nie importuje
  `layout_executive` — importuje `builder`, `styles`, `summary_pdf`.
  `README.md:175` opisuje te fasade jako "facade, 75 lines", co jest juz nieaktualne (plik ma 9 linii).
- **Rozroznienie:** **modul** jest osierocony, ale **symbole** nie sa —
  `build_page_executive_summary` i `build_page_executive_verdict` sa importowane bezposrednio
  z modulow zrodlowych i uzywane w zywym lancuchu generowania PDF.
  Usuniecie tego pliku **nie** usuwa funkcji executive summary.
- **Ryzyko usuniecia: niskie.** Plik nie zawiera logiki (tylko `import` + `__all__`),
  nikt go nie importuje, a jego zawartosc jest dostepna dwiema zywymi sciezkami obok.

---

## TYLKO-TESTY

Jeden modul. Uzywany **wylacznie** przez `tests/**` — nie ma wolajacego produkcyjnego,
wiec usuniecie go zepsuloby test, a nie aplikacje.

### `modules/calculations/smo2_breakpoints.py` — 341 linii

- **Status:** TYLKO-TESTY
- **Publiczne symbole:** `SmO2Breakpoints` (l.24), `detect_smo2_breakpoints_segmented` (l.59),
  `_validate_breakpoint_input` (l.43)
- **Dowod — jedyny wolajacy:**
  `tests/calculations/test_wave2_calculations.py:18`
  (`from modules.calculations.smo2_breakpoints import detect_smo2_breakpoints_segmented`),
  uzyty w `tests/calculations/test_wave2_calculations.py:150`
  (`test_smo2_breakpoints_all_nan_power_column_is_not_valid`, l.142).
  Poza tym plikiem: `grep -rn "modules.calculations.smo2_breakpoints" --include=*.py .`
  → **0 trafien**. Brak w `modules/calculations/__init__.py`, brak w `TabRegistry._tabs`.
- **Historia statusu:** na commicie `10330b6` modul byl **OSIEROCONY** (322 linie, zero wolajacych).
  Status zmienil sie w trakcie tej analizy, gdy rownolegly wykonawca dodal powyzszy test.
- **Kontekst:** zywe wykrywanie progow SmO2 idzie innymi sciezkami —
  `modules/calculations/smo2_thresholds.py` i `smo2_advanced.py`, eksportowane przez
  `modules/calculations/__init__.py` i wolane z `modules/ui/summary.py:20`.
  Ten modul jest wiec **rownolegla, nieuzywana produkcyjnie** implementacja segmentowej
  detekcji breakpointow, ktora wlasnie zyskala test regresyjny.
- **Ryzyko usuniecia: wysokie (nie usuwac).** Modul ma teraz test regresyjny,
  ktory zostal dodany swiadomie przez innego wykonawce — usuniecie modulu zepsuloby ten test
  i cofnelo swiezo wykonana prace. Do decyzji Krzyska nalezy raczej, czy modul **wpiac**
  do produkcyjnego lancucha SmO2, czy test i modul usunac razem.

Uzupelniajaco: pelny graf importow z `tests/**` (S1) zawiera 58 pozycji — poza powyzsza
wszystkie wskazuja na moduly zywe (`modules.calculations.*`, `modules.reporting.*`,
`modules.config`, `modules.frontend.state`, `modules.db`, `modules.utils`, `modules.settings`,
`services.*`, `models.results`) albo na dynamiczne importy `modules.ui.vent_tab` /
`modules.ui.smo2` / `modules.ui.vent_charts` z `tests/ui/test_review_ui.py:246-248`.

---

## NIEROZSTRZYGNIETE

**Brak.** Dla kazdego z 25 kandydatow (stan na `10330b6`) sonda S5 na poziomie **symbolu**
(nie tylko importu modulu) zwrocila trafienia wylacznie w jego wlasnym pliku (plus, dla trzech
przypadkow, w `docs/` i `methodology/` — jako opis planu lub architektury, nigdy jako wolanie).
Jedyny kandydat, ktory zmienil status w trakcie analizy, jest rozstrzygniety jako TYLKO-TESTY,
nie jako nierozstrzygniety.

Dwa przypadki wymagaly dodatkowego rozstrzygniecia, bo `grep` na poziomie importu byl mylacy;
oba sa rozstrzygniete, nie nierozstrzygniete:

| kandydat | zrodlo falszywego "zycia" | rozstrzygniecie |
|---|---|---|
| `modules/ui/header.py` | `render_sticky_header`, `show_breadcrumb` sa wolane — ale z `modules/frontend/components.py` (`UIComponents`) | OSIEROCONY — zweryfikowane `file:line` w obu miejscach |
| `modules/async_utils.py` | `run_in_thread`, `shutdown_executor` sa wolane — ale wersje z `modules/calculations/async_runner.py` | OSIEROCONY — zweryfikowane `file:line` w obu miejscach |
| `modules/manual_overrides.py` | `manual_overrides` wystepuje w kilkudziesieciu liniach `modules/reporting/**` | OSIEROCONY — tam zawsze jako argument/zmienna lokalna, nie import |

---

## ZYWE (odrzucone z listy kandydatow)

**Brak.** Zadnego kandydata nie trzeba bylo odrzucic — surowa heurystyka dala liste poprawna
merytorycznie. Uwaga: dwa wpisy mialy **bledna sciezke** (`modules/calculations/intervals.py`,
`modules/utils/time_formatting.py`), ale same moduly istnieja i sa osierocone pod poprawnymi
sciezkami (`modules/intervals.py`, `modules/time_formatting.py`).

| modul | wolajacy |
|---|---|
| — | (lista pusta) |

---

## Przypadki imienne

### 1. `modules/ui/registry.py` (191 linii) vs `app.py::TabRegistry` — **[USUNIETY 2026-09-29]**

**Werdykt: `PluginRegistry` to porzucona druga implementacja tego samego mechanizmu.
Zywy jest `TabRegistry` w `app.py`.**

**Czym sa oba:**

| | `app.py::TabRegistry` (l.26-92) | `modules/ui/registry.py::PluginRegistry` (l.21-172) |
|---|---|---|
| Rejestracja | statyczny slownik `_tabs`, 22 wpisy (l.29-52) | dynamiczne `discover()` skanujace `modules/ui/*.py` (l.112-167) |
| Kontrakt zakladki | krotka `(sciezka_modulu: str, nazwa_funkcji: str)` | klasa `UITabPlugin` z `config: TabConfig` i `render()` |
| Rozdzielenie | `importlib.import_module` + `getattr` (l.68-69) | instancje pluginow w slowniku (l.47) |
| Obsluga bledow | tak — granica `try/except` z 7 typami wyjatkow (l.71-92) | brak granicy; bledy tylko logowane w `discover()` (l.159-163) |
| Model danych | brak | `TabConfig`, `UIGroupConfig`, `TAB_GROUPS` w `modules/ui/base.py` |
| Wolajacy | `render_tab_content` (l.95-97), wolany 18 razy z `app.py` | **brak** |

**Dowody:**

```bash
grep -rn "PluginRegistry|get_registry|register_plugin|discover_plugins" --include="*.py" .
# -> trafienia wylacznie w modules/ui/registry.py (l.21, 28, 37, 176, 179, 184, 189)

grep -rn "UITabPlugin|TabConfig|UIGroupConfig|TAB_GROUPS|get_grouped_tabs|get_available_tabs" \
  --include="*.py" . | grep -v "modules/ui/registry.py" | grep -v "modules/ui/base.py"
# -> 0 trafien
```

**Dodatkowy dowod strukturalny:** `discover()` zaklada, ze w `modules/ui/` istnieja klasy
dziedziczace po `UITabPlugin`. **Nie istnieje ani jedna** — `modules/ui/` ma 40 plikow i zaden
nie dziedziczy po `UITabPlugin` (sonda S3/S5). Gdyby `discover()` zostal uruchomiony,
zwrocilby 0 pluginow.

**Konsekwencja:** usuniecie `registry.py` osieroca dodatkowo `modules/ui/base.py` (115 linii),
bo `registry.py:16` (`from .base import UITabPlugin`) jest **jedynym** importem `base.py` w repo.

**Ostrzezenie przed przedwczesnym usunieciem:** `discover()` jest jedynym miejscem w repo,
ktore implementuje automatyczne wykrywanie zakladek. `TabRegistry._tabs` wymaga recznej
rejestracji i **juz sie rozjechal z rzeczywistoscia** — 22 wpisy, ale tylko 18 jest wywolywanych
(patrz "Znaleziska spoza listy kandydatow"). To argument za tym, ze plugin system mial rozwiazac
realny problem — ale zostal porzucony w polowie, wiec jako kod jest martwy.

---

### 2. `modules/ui/vent.py` (26 linii) — ktore re-eksporty sa osiagalne

**Werdykt: osiagalna jest dokladnie jedna pozycja z `__all__` — `render_vent_tab`.
Pozostale siedem re-eksportow to martwy kod.**

`app.py:37` rejestruje zakladke jako `"vent": ("modules.ui.vent", "render_vent_tab")`,
a `app.py:339` wola `render_tab_content("vent", df_plot, training_notes, uploaded_file.name)`.
`TabRegistry.render` robi `importlib.import_module("modules.ui.vent")` i
`getattr(module, "render_vent_tab")` — to jedyna sciezka do tego modulu w calym repo:

```bash
grep -rn 'modules\.ui\.vent\b' --include="*.py" --include="*.toml" --include="*.md" .
# -> ./app.py:37  (jedyne trafienie)
```

| pozycja `__all__` | zywa? | kto ja faktycznie importuje |
|---|---|---|
| `render_vent_tab` | **TAK** | `app.py:37` przez `importlib` + `getattr` |
| `_render_br_only_section` | NIE | `modules/ui/vent_tab.py:11` — **bezposrednio** z `vent_br_only` |
| `_render_ve_section` | NIE | `modules/ui/vent_tab.py:13-15` — **bezposrednio** z `vent_charts` |
| `_render_br_section` | NIE | `modules/ui/vent_tab.py:13-15` — **bezposrednio** z `vent_charts` |
| `_render_tidal_volume_section` | NIE | `modules/ui/vent_tab.py:13-15` — **bezposrednio** z `vent_charts` |
| `_render_legacy_tools` | NIE | `modules/ui/vent_tab.py:17` — **bezposrednio** z `vent_legacy` |
| `_parse_time_to_seconds` | NIE | `vent_tab.py:18`, `vent_charts.py:11` — **bezposrednio** z `vent_utils` |
| `_format_time` | NIE | `vent_tab.py:18`, `vent_charts.py:11` — **bezposrednio** z `vent_utils` |

**Dowod:** `grep -rnE '_render_br_only_section|_render_br_section|_render_tidal_volume_section|
_render_ve_section|_render_legacy_tools|render_vent_tab|_parse_time_to_seconds|_format_time'
--include='*.py' .` → **zero** importow z `modules.ui.vent`. Wszystkie trafienia to definicje
w modulach zrodlowych i importy w `vent_tab.py` / `vent_charts.py`, ktore ida prosto do zrodla.

**Interpretacja:** docstring modulu (`l.1-5`) deklaruje "backward-compatible access to all
ventilation UI functions" po splicie na podmoduly. Konsumenci starej sciezki **juz nie istnieja** —
`vent_tab.py` zostal zaktualizowany, by importowac z nowych modulow bezposrednio.
Warstwa zgodnosci wstecznej przezyła swoich konsumentow.

**Ograniczenie:** `render_vent_tab` jest osiagalny tylko przez dynamiczny `getattr`
w `TabRegistry`. Sonda czysto statyczna (import graf) uznalaby **caly** modul `vent.py`
za osierocony — to bledny wynik. Wlasciwy status: **ZYWY, ale tylko 1 z 8 symboli**.
Jest to jedyny taki przypadek wsrod wszystkich analizowanych modulow.

**Uwaga o duplikatach:** `_format_time` i `_parse_time_to_seconds` maja **rownolegle,
niezalezne implementacje** w `modules/ui/smo2.py` (l.19, 34) i — dla `_format_time` —
w `modules/ui/heart_rate.py` (l.25). To samo dotyczy `_render_legacy_tools`
(`vent_legacy.py:10` vs `smo2.py:527`). Przy sprzataniu warto rozstrzygnac, czy to celowe,
czy rozwidlona kopia.

---

## Znaleziska spoza listy kandydatow

Te moduly nie byly na liscie, ale wyszly w trakcie weryfikacji. **Nic z nimi nie zrobiono.**

### A. Moduly zarejestrowane w `TabRegistry._tabs`, ale nigdy nie wywolane (928 linii)

`TabRegistry._tabs` ma 22 wpisy, ale `render_tab_content(...)` jest wolane w `app.py`
tylko **18 razy**. Cztery zarejestrowane zakladki nie maja zadnego wywolania:

| klucz w `_tabs` | modul | linii | status |
|---|---|---:|---|
| `thresholds` (l.41) | `modules/ui/threshold_analysis_ui.py` | 465 | ZAREJESTROWANY, NIGDY NIE WYWOLANY |
| `history` (l.42) | `modules/ui/trends_history.py` | 212 | ZAREJESTROWANY, NIGDY NIE WYWOLANY |
| `import` (l.44) | `modules/ui/history_import_ui.py` | 127 | ZAREJESTROWANY, NIGDY NIE WYWOLANY |
| `community` (l.43) | `modules/ui/community.py` | 124 | ZAREJESTROWANY, NIGDY NIE WYWOLANY |

Dowod: `grep -rnE 'threshold_analysis_ui|trends_history|ui\.community|history_import_ui'
--include='*.py' .` → trafienia wylacznie w `app.py:41-44` (same stringi rejestru),
w ich wlasnych plikach oraz w `docs/coverage-report.md:138` i `README.md:158,311,492`.

To **inna kategoria** niz OSIEROCONY: ktos te zakladki zamierzal pokazac (sa w rejestrze,
maja funkcje `render_*_tab`), ale nie podlaczyl ich do zadnego `st.tabs(...)`.
Do decyzji Krzyska: wpiac czy usunac. Nie usuwac automatycznie — to moze byc niedokonczona
praca, a nie smiec.

### B. Moduly osierocone drugiego rzedu (318 linii)

Istnieja moduly, ktore **nie sa** na liscie kandydatow, ale sa importowane **wylacznie**
przez moduly z listy. Po usunieciu kandydatow one tez stana sie osierocone:

| modul | linii | jedyny importer | importer jest kandydatem? |
|---|---:|---|---|
| `modules/ui/base.py` | 115 | `modules/ui/registry.py:16` | TAK (kandydat #15) |
| `modules/genetics.py` | 120 | `modules/ui/genetics_ui.py:10` | TAK (kandydat #18) |
| `modules/environment.py` | 83 | `modules/ui/environment_ui.py:11` | TAK (kandydat #19) |

Dodatkowo `modules/chart_exporters.py` (300 linii) ma dwa zrodla importu:
`modules/reports.py:322` (kandydat #7) i `modules/chart_exporters.py:8` (wlasny docstring).
Jesli `reports.py` zostanie usuniety, `chart_exporters.py` trzeba sprawdzic osobno.

### C. Zepsuty import DOCX (latent, nie kosmetyczny)

`modules/reporting/persistence_pdf.py:76` wykonuje `from .docx_builder import build_ramp_docx`,
ale **plik `modules/reporting/docx_builder.py` nie istnieje**:

```bash
ls modules/reporting/docx_builder.py
# -> No such file or directory
```

Wystapienie jest **drugie** — takze w `l.244`. Import jest owiniety w
`try/except (ImportError, OSError, ValueError)` (`l.75-82`, `l.243-247`), wiec nie wywala
aplikacji, ale **kazde** generowanie PDF loguje `logger.error("DOCX generation failed: ...")`
i cicho pomija DOCX. Rownolegle `modules/reports.py::generate_docx_report` (osierocony, 367 linii)
jest jedynym dzialajacym generatorem DOCX w repo, ale nic go nie wola.
Czyli: generowanie DOCX jest zepsute w dwoch miejscach jednoczesnie i zadne z nich nie jest uzywane.
Do decyzji Krzyska, nie do naprawy w tym kroku.

### D. Trzy pary rownoleglych implementacji tej samej funkcji

| temat | zywa | osierocona |
|---|---|---|
| `detect_intervals` | brak (obie martwe) | `modules/intervals.py:98` + `modules/ai/interval_detector.py:112` |
| `get_cache_stats` | brak (obie martwe) | `modules/monitoring.py:242` + `modules/cache_utils.py:172` |
| `pace_to_seconds` | `modules/calculations/pace_utils.py:68` | `modules/time_formatting.py:83` — **odwrotna semantyka** |
| `_format_time`, `_parse_time_to_seconds` | `modules/ui/vent_utils.py:6,21` (przez `vent_tab`) | `modules/ui/smo2.py:19,34`, `modules/ui/heart_rate.py:25` |

Najwazniejsza z tych par to `pace_to_seconds` — dwie funkcje o tej samej nazwie i
**przeciwnym kierunku konwersji**. Zywa jest wersja liczbowa-ze-stringa
(`pace_utils.py:68`, testowana). Martwa jest wersja string-z-liczb (`time_formatting.py:83`).
Przy usuwaniu `time_formatting.py` nie ma ryzyka; ryzyko pojawiloby sie, gdyby ktos
importowal "nie te" funkcje.

---

## Ograniczenia tego inwentarza

1. **Brak uruchomienia runtime.** Wnioski pochodza z analizy statycznej grafow importow
   (S1-S8). Nie bylo testu "uruchom aplikacje i sprawdz, czy modul sie zaladuje".
   Dla 25 kandydatow nie ma to znaczenia (zaden nie jest importowany), ale dla modulow
   z sekcji "Znaleziska spoza listy kandydatow" (A, B) warto potwierdzenie uruchomieniowe.
2. **`.claude/worktrees/` zawiera dwie pelne kopie repo** (384 pliki `.py`). Kazde polecenie
   weryfikacyjne z tego dokumentu wymaga wylaczenia `.claude/`, inaczej wyniki sa falszywie
   pozytywne.
3. **Nie sprawdzono wolajacych spoza drzewa repo** (notebooki, inne klony, skrypty uzytkownika).
   Jesli Krzysiek importuje ktorykolwiek z tych modulow recznie poza repo, status sie zmienia.
4. **`docs/coverage-report.md` jest nieaktualny** (data 2026-04-03, 321 testow; obecnie 241 testow).
   Uzyty jako dowod pomocniczy tylko dla wpisow z 0% pokrycia, nigdy jako dowod glowny.
5. **Statusy dotycza modulow i symboli w tym drzewie na commicie `10330b6`**, z ponowna
   weryfikacja na biezacym drzewie w dniu 2026-09-29. Trzy pliki kandydatow zostaly w miedzyczasie
   zmodyfikowane przez rownoleglych wykonawcow (patrz tabela w "Podsumowaniu"), a jeden kandydat
   zmienil status na TYLKO-TESTY.
6. **Drzewo repo bylo w trakcie analizy modyfikowane rownolegle.** W chwili weryfikacji
   `git status --porcelain` pokazywal 39 zmodyfikowanych plikow `.py` i 3 nowe pliki testowe
   nienalezace do tego zadania — dlatego `ruff` i `pytest` byly w tym momencie czerwone
   (F401 w `tests/ui/test_wave2_ui.py:429`, `ImportError: classify_ramp_test` w
   `services/dashboard_renderer.py:85`). Zaden z tych plikow nie zostal dotkniety przez to zadanie.
   Baseline zmierzony **przed** tymi zmianami: `ruff` czysty, `pytest` 241 testow zielonych.

---

## Co dalej (decyzja Krzyska, nie ten krok)

Nic nie zostalo usuniete. **Nie ma tu planu usuwania** — to inwentarz.
25 kandydatow w podziale na to, ile pracy wymaga decyzja, od najbezpieczniejszego:

**1. Do usuniecia bez zastrzezen — 6 modulow, 1 049 linii**
(zero wolajacych, zero unikalnej logiki, zywy odpowiednik istnieje):
`monitoring.py` (302), `task_queue.py` (298), `ui/registry.py` (191), `ui/header.py` (143),
`time_formatting.py` (106), `reporting/pdf/layout_executive.py` (9).
Po nich osierocony staje sie `ui/base.py` (115) — jedynym jego importerem jest `ui/registry.py`.

**2. Do usuniecia po porownaniu pary implementacji — 6 modulow, 1 441 linii**
(kazdy ma zywego konkurenta; trzeba sprawdzic, czy zywy nie jest ubozszy):
`ui/kpi.py` (401, vs `ui/report.py`), `ai/interval_detector.py` (387) + `intervals.py` (126)
(para dwoch martwych implementacji `detect_intervals`), `cache_utils.py` (223 —
**najpierw naprawic `_hash_arg`**, inaczej nie ma sensu wpinac),
`manual_overrides.py` (171, vs `canonical_values.py`), `async_utils.py` (133,
vs `calculations/async_runner.py`).

**3. Wymaga decyzji produktowej — 12 modulow, 3 425 linii**
(moze byc niedokonczona funkcja, nie smiec):
`export/fit_exporter.py` (436), `calculations/report_generator.py` (408),
`calculations/trend_engine.py` (392), `reporting/summary_export.py` (388), `reports.py` (367),
`calculations/hr_zones.py` (318 — **kandydat do wpiecia**, opisany w README jako funkcja),
`calculations/gas_exchange_estimation.py` (314), `health_alerts.py` (287),
`ui/compare.py` (163), `ui/genetics_ui.py` (156), `ui/environment_ui.py` (154),
`ui/callbacks.py` (42).
Po nich osierocone stana sie: `genetics.py` (120), `environment.py` (83), `chart_exporters.py` (300).

**4. Wymaga rozstrzygniecia "wpiac czy usunac" — poza lista kandydatow, 928 linii:**
4 zakladki zarejestrowane w `_tabs`, ale nigdy nie wywolane (sekcja A):
`threshold_analysis_ui.py`, `trends_history.py`, `history_import_ui.py`, `community.py`.

**5. Zmienil status w trakcie analizy — nie usuwac:**
`calculations/smo2_breakpoints.py` (341) — ma swiezy test regresyjny dodany przez innego
wykonawce. Decyzja: wpiac do produkcyjnego lancucha SmO2 albo usunac modul i test razem.

**6. Osobno do decyzji:** zepsuty import `docx_builder` (sekcja C) — naprawic czy usunac
osierocony `reports.py` i sciezke DOCX razem. Uwaga: po usunieciu `reports.py`
`python-docx` w `pyproject.toml:29` staje sie nieuzywana zaleznoscia.

---

# Stan po rundzie domykajacej (2026-09-29)

Inwentarz powyzej opisuje stan **sprzed** decyzji. Ponizej to, co faktycznie wykonano.
Wszystkie ponizsze zmiany weszly z zielonym `ruff check .` i pelnym pakietem testow.

## Usuniete (421 linii)

Zero wolajacych potwierdzone niezaleznie przed kazdym usunieciem: import statyczny, import
wzgledny, string w `importlib`, `TabRegistry._tabs`, `pyproject.toml`, `tests/**`.

| plik | linie | uzasadnienie |
|---|---|---|
| `modules/ui/registry.py` | 191 | `PluginRegistry` — porzucona druga implementacja `TabRegistry`; zadna klasa w repo nie dziedziczy po `UITabPlugin`, wiec `discover()` zwracal zero wtyczek |
| `modules/ui/base.py` | 115 | `UITabPlugin` — jedynym importerem byl `registry.py` |
| `modules/time_formatting.py` | 106 | zero wolajacych; `docs/coverage-report.md` pokazywal 0% pokrycia. Uwaga: jego `pace_to_seconds` mial **odwrotna semantyke** niz `calculations/pace_utils.py::pace_to_seconds`, ktory zostaje |
| `modules/reporting/pdf/layout_executive.py` | 9 | czysta fasada re-eksportujaca `build_page_executive_summary` / `build_page_executive_verdict`; oba symbole sa importowane wprost z modulow zrodlowych |

## Wyrejestrowane z `TabRegistry._tabs` (kod zostaje na dysku)

`_tabs` mialo 22 wpisy przy 18 renderowanych zakladkach. Cztery wpisy bez odpowiadajacego
wywolania `render_tab_content` zostaly usuniete z rejestru; **moduly zostaja nietkniete**:

- `threshold_analysis_ui.py`
- `trends_history.py`
- `history_import_ui.py`
- `community.py`

Test w `tests/ui/test_wave2_ui.py` porownuje teraz rejestr z wywolaniami przez `ast`, wiec ponowny
rozjazd `_tabs` i UI zostanie zlapany.

## Oczyszczone re-eksporty

`modules/ui/vent.py` — z 8 pozycji w `__all__` osiagalna byla tylko `render_vent_tab` (string w
`app.py` przez `importlib`); pozostale 7 importowano wprost z modulow zrodlowych. Plik zszedl
z 27 do 12 linii.

## Naprawione, nie usuniete

Zepsuty import `docx_builder` (`persistence_pdf.py`) — modul nie istnial nigdy, blad byl zjadany
przez `except`, a `docx_path` nie byl nigdzie konsumowany. Usunieto dwa martwe bloki (20 linii).
`modules/reports.py::generate_docx_report` to **inny** generator i zostaje.

## Nadal otwarte

Sekcje 3, 4 (czesciowo — moduly zostaly, tylko wyrejestrowane), 5 i 6 powyzej pozostaja bez
rozstrzygniecia. W szczegolnosci 12 modulow z sekcji 3 (3 425 linii) czeka na decyzje produktowa:
to moga byc niedokonczone funkcje, a nie smiec.
