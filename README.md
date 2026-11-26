# Analiza Biegowa

Lokalna aplikacja Streamlit do analizy pojedynczego biegu z pliku CSV lub TXT. Pokazuje tempo, GAP, strefy tempa, krzywą tempa (PDC), prędkość krytyczną i D′, a przy dostępnych pomiarach także biomechanikę, tętno, wentylację, SmO₂ i obciążenie cieplne. Wyniki sesji można pobrać jako PDF.

## Uruchomienie

Wymagania obejmują Python 3.10 lub nowszy oraz Streamlit 1.54 lub nowszy. Z katalogu repozytorium uruchom:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
```

Otwórz adres podany przez Streamlit, wgraj plik w panelu bocznym i ustaw masę, wzrost oraz tempo progowe w sekundach na kilometr. Jeżeli masz ręcznie wyznaczone wartości VT1 i VT2 w L/min, możesz dodać je do wykresu VE w raporcie.

Na macOS `bash build_biegowa_app.sh` tworzy aplikację z ikoną i skrótem w Docku. Do startu z Docka zainstaluj zależności z katalogu repozytorium w interpreterze wybieranym przez launcher. Samo środowisko `.venv` z powyższej instrukcji wystarcza do startu z terminala. `launcher.sh` obsługuje serwer na wolnym porcie z zakresu 8510-8519. Log trafia do `/tmp/analiza_biegowa_launch.log`.

## Format pliku

Wgraj CSV lub TXT z nagłówkami i separatorem przecinek lub średnik. Potrzebujesz co najmniej 10 wierszy, uporządkowanego liczbowego czasu `time` w sekundach oraz próbek ruchu zapisanych jako `pace` w s/km (obsługiwany jest też zapis `mm:ss`) lub `speed_m_s` w m/s. `speed` i `velocity` to aliasy `speed_m_s`. W danych eksportowanych jako `velocity_smooth` aplikacja rozpoznaje zapis w km/h na podstawie mediany dodatnich próbek powyżej 10. Tempo lub szybkość równe zero oznaczają postój.

```csv
time,pace,heartrate
0,300,145
1,301,145
2,299,146
3,298,146
4,300,146
5,301,146
6,300,147
7,299,147
8,300,147
9,301,147
```

| Opcjonalny pomiar | Kolumny i zastosowanie |
| --- | --- |
| Dystans i profil wysokości | `distance` w m, `altitude` lub `elevation` w m do GAP |
| Tętno i odstępy RR | `heartrate` lub `hr` w bpm, odstępy między uderzeniami w `rr_interval` lub `hrv` do analizy HRV i DFA α1 |
| Biomechanika | `cadence` w krokach/min, `stance_time` lub `gct` w ms, `vertical_oscillation` w cm, `stance_time_balance` i `vertical_ratio` w % |
| Wentylacja | `TymeVentilation` lub `VE` w L/min, `TymeBreathRate` lub `BR` w oddechach/min |
| Oksygenacja mięśni | `smo2` w %, `thb`, `o2hb` i `hhb` |
| Temperatura i CORE | `core_temperature`, `skin_temperature` i `temp` (otoczenie) w °C, `HeatStrainIndex` lub `hsi` w skali 0-10 |
| Opcjonalna moc z zegarka lub footpoda | `watts`, `power` lub `running_power` w W. Kanał dostępny na wykresie w Podsumowaniu, bez wpływu na metryki. |

## Zakładki

| Grupa | Analizy |
| --- | --- |
| Overview | **Raport z KPI** ze wskaźnikami oraz przebiegiem tętna, SmO₂ i wentylacji. **Podsumowanie** z osią czasu i eksportem PDF. |
| Performance | **Running** z tempem, GAP, strefami i PDC. **Biomechanika**, **CS i D′**, **HR**, **Drift Maps** z eksportem JSON oraz **TTE** wg tempa. |
| Intelligence | **Żywienie** z symulacją zużycia i podaży węglowodanów według tempa i masy. |
| Physiology | **HRV**, **SmO₂**, **Ventilation**, **Thermal**, **Hemodynamika** i **Efektywność tlenowa** (Pa:HR). |

W **Overview → Podsumowanie** otwórz **Raport PDF**, wybierz **Przygotuj PDF**, a następnie pobierz plik. Raport zawiera tempo, GAP, NP/RSS, strefy, dostępne sygnały i model CS/D′, jeśli zapis wystarcza do dopasowania. Brak pomiaru jest opisany jako „brak”. Zmiana pliku, masy lub tempa progowego wymaga ponownego przygotowania raportu.

Dane wgranego biegu pozostają w bieżącej sesji. Notatki SmO₂ i wentylacji zapisują się lokalnie w `training_notes/`, a PDF i JSON pobiera się na żądanie.

## Obliczenia i konfiguracja

- Średnie tempo ruchu i PDC są liczone w domenie prędkości. Postoje oraz dłuższe przerwy w nagraniu nie tworzą fikcyjnych odcinków PDC.
- GAP zależy od tempa i profilu wysokości. NP stosuje normalizację trzecią potęgą prędkości. RSS łączy NP z czasem i ustawionym tempem progowym.
- Model CS/D′ dopasowuje zależność dystansu od czasu do najlepszych odcinków z tej sesji. Pa:HR porównuje relację prędkości do tętna w aktywnych częściach biegu.
- Czasy w strefach HSI są liczone z odstępów między pomiarami CORE przed resamplingiem. Przerwy ponad 30 sekund są pomijane.
- W `.env` możesz zmienić domyślne wartości `DEFAULT_BODY_WEIGHT_KG`, `DEFAULT_RUNNER_HEIGHT_CM` i `DEFAULT_THRESHOLD_PACE_SEC_PER_KM`.

## Testy

```bash
python3 -m pip install -e '.[dev]'
python3 -m pytest -q --tb=short
ruff check .
mypy modules/ services/ --config-file pyproject.toml
```

`app.py` wybiera widok, `services/` waliduje i przetwarza sesję, `modules/calculations/` liczy metryki, a `modules/reporting/` tworzy PDF. Zasady pracy znajdują się w [CONTRIBUTING.md](CONTRIBUTING.md).

Licencja [MIT](LICENSE).
