# Technical Stack for Ramp Test PDF Generation

> **⚠️ UWAGA:** Funkcjonalność generowania PDF została usunięta z tej uproszczonej wersji aplikacji Analiza_Kolarska. Ten dokument pozostaje jako dokumentacja historyczna.

> **Dokument:** Architektura stacku technicznego do generowania raportów PDF  
> **Wersja:** 1.0.0  
> **Ostatnia aktualizacja:** 2026-01-03

---

## 1. Wymagania architektoniczne

| Wymaganie | Opis |
|-----------|------|
| **Źródło danych** | Wyłącznie kanoniczny raport JSON (`ramp_test_{date}_{uuid}.json`) |
| **Niezależność** | Brak zależności od Streamlit ani żadnego frameworka UI |
| **Wykresy** | Statyczne obrazy (PNG lub SVG), nie interaktywne |
| **Jakość** | Gotowość do druku (print-ready) |
| **Powtarzalność** | Identyczne dane wejściowe → identyczny PDF |

---

## 2. Wybrane biblioteki Python

### 2.1 Generator wykresów: **Matplotlib**

| Aspekt | Wartość |
|--------|---------|
| **Biblioteka** | `matplotlib` (>=3.7) |
| **Format wyjściowy** | PNG (300 DPI) lub SVG |
| **Backend** | `Agg` (non-interactive, thread-safe) |

#### Uzasadnienie wyboru

| Alternatywa | Dlaczego NIE |
|-------------|--------------|
| **Plotly** | Generuje HTML/JS, wymaga konwersji do statycznych obrazów przez `kaleido`, dodatkowa zależność i wolniejsze |
| **Seaborn** | Wrapper na Matplotlib, dodaje overhead bez korzyści dla prostych wykresów |
| **Bokeh** | Zorientowany na interaktywność, słaby eksport statyczny |
| **Altair** | Deklaratywny, wymaga Vega do renderowania statycznego |

**Matplotlib** jest standardem de facto dla publikacji naukowych, zapewnia pełną kontrolę nad każdym pikselem, natywnie eksportuje do PNG/SVG bez dodatkowych zależności.

---

### 2.2 Generator PDF: **ReportLab**

| Aspekt | Wartość |
|--------|---------|
| **Biblioteka** | `reportlab` (>=4.0) |
| **Wariant** | Open Source (nie Plus) |
| **Licencja** | BSD |

#### Uzasadnienie wyboru

| Alternatywa | Dlaczego NIE |
|-------------|--------------|
| **WeasyPrint** | Wymaga HTML/CSS jako input, ciężki (cairo, pango), wolniejszy |
| **FPDF2** | Prostszy, ale mniej elastyczny, słabsze wsparcie dla tabel |
| **PyMuPDF** | Głównie do odczytu PDF, nie do generowania |
| **xhtml2pdf** | Konwersja HTML→PDF, niespójna obsługa CSS |
| **pdfkit/wkhtmltopdf** | Zewnętrzna zależność binarna, problemy z instalacją |

**ReportLab** to najbardziej dojrzała biblioteka do programatycznego tworzenia PDF w Pythonie. Oferuje:
- Pełną kontrolę nad layoutem (Platypus framework)
- Natywne wsparcie dla tabel, obrazów, stylów
- Brak zależności zewnętrznych (pure Python)
- Używany przez banki i instytucje do generowania dokumentów

---

## 3. Zalecenia techniczne

### 3.1 Parametry PDF

| Parametr | Wartość | Uzasadnienie |
|----------|---------|--------------|
| **Format strony** | A4 (210 × 297 mm) | Standardowy format europejski, łatwy druk |
| **Orientacja** | Pionowa (portrait) | Lepsza czytelność tabel i wykresów |
| **Marginesy** | 15 mm (wszystkie strony) | Bezpieczny obszar dla drukarek |
| **DPI wykresów** | 300 | Standard druku, balans jakość/rozmiar |

### 3.2 Typografia

| Element | Czcionka | Uzasadnienie |
|---------|----------|--------------|
| **Główna** | Helvetica (built-in) | Uniwersalna, czytelna, nie wymaga embedowania |
| **Alternatywa** | Liberation Sans / DejaVu Sans | Jeśli potrzebne znaki Unicode (PL) |
| **Nagłówki** | Helvetica-Bold | Hierarchia wizualna |
| **Kod/liczby** | Courier | Monospace dla wartości liczbowych |

> **Uwaga:** Helvetica jest wbudowana w ReportLab i każdy czytnik PDF. Unikaj TTF/OTF, jeśli nie są konieczne (polskie znaki).

### 3.3 Kolory

| Przeznaczenie | Kolor HEX | Nazwa |
|---------------|-----------|-------|
| Podstawowy (nagłówki) | `#1F77B4` | Niebieski |
| VT1 | `#FFA15A` | Pomarańczowy |
| VT2 | `#EF553B` | Czerwony |
| Confidence OK | `#2ECC71` | Zielony |
| Confidence Warning | `#F1C40F` | Żółty |
| Tekst drugorzędny | `#7F8C8D` | Szary |

---

## 4. Podział odpowiedzialności

### 4.1 Architektura modułów

```
modules/reporting/
├── figures/                 # Generator wykresów
│   ├── __init__.py
│   └── ramp_figures.py      # generate_ramp_profile_chart, generate_smo2_power_chart, generate_pdc_chart
├── pdf/                     # Generator PDF
│   ├── __init__.py
│   └── generator.py         # generate_ramp_pdf, PDFConfig
└── persistence.py           # Orkiestrator (save_ramp_test_report, _auto_generate_pdf)
```

### 4.2 Odpowiedzialności

| Moduł | Odpowiedzialność | Nie robi |
|-------|------------------|----------|
| **figures/** | Generowanie statycznych wykresów (PNG) z danych JSON | Nie zapisuje PDF, nie formatuje tekstu |
| **pdf/** | Składanie dokumentu PDF z wykresów i tekstu | Nie wykonuje obliczeń, nie czyta raw data |
| **persistence.py** | Orkiestracja: JSON → figures → PDF → index | Nie renderuje wykresów, nie formatuje PDF |

### 4.3 Przepływ danych

```
┌─────────────────┐
│ Canonical JSON  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│ figures/        │────▶│ temp/*.png      │
│ ramp_figures.py │     │ (statyczne)     │
└─────────────────┘     └────────┬────────┘
                                 │
         ┌───────────────────────┘
         ▼
┌─────────────────┐     ┌─────────────────┐
│ pdf/            │────▶│ *.pdf           │
│ generator.py    │     │ (final)         │
└─────────────────┘     └─────────────────┘
```

---

## 5. Powtarzalność raportów

### 5.1 Wymagania

Dwa wywołania generatora z tym samym JSON muszą dać **identyczne wizualnie** PDF (choć mogą różnić się metadanymi jak timestamp).

### 5.2 Mechanizmy zapewnienia powtarzalności

| Mechanizm | Implementacja |
|-----------|---------------|
| **Wersjonowanie metodologii** | Pole `method_version` w JSON i PDF footer |
| **Deterministic rendering** | Matplotlib: stały seed dla ewentualnych elementów losowych |
| **Brak side effects** | Generatory są pure functions (input → output) |
| **Canonical JSON** | Dane wejściowe są immutable po zapisie |
| **Pinned dependencies** | `requirements.txt` z dokładnymi wersjami bibliotek |

### 5.3 Wersjonowanie

| Wersja | Kiedy zmienić |
|--------|---------------|
| **Patch (1.0.X)** | Poprawki kosmetyczne, nie wpływające na wyniki |
| **Minor (1.X.0)** | Nowe sekcje/wykresy, bez zmian w istniejących |
| **Major (X.0.0)** | Zmiany w algorytmach wykrywania progów, nowa struktura JSON |

---

## 6. Zależności (requirements.txt)

```
matplotlib>=3.7.0,<4.0.0
reportlab>=4.0.0,<5.0.0
numpy>=1.24.0
```

> **Uwaga:** Nie dodawaj `streamlit`, `plotly`, ani żadnych bibliotek UI do modułu `reporting/`.

---

## 7. Testowanie

### 7.1 Testy jednostkowe

| Moduł | Co testować |
|-------|-------------|
| **figures/** | Czy wykresy generują się bez błędów, czy pliki PNG mają poprawne wymiary |
| **pdf/** | Czy PDF jest generowany, czy ma oczekiwaną liczbę stron |
| **persistence/** | Czy workflow JSON → PDF → index działa end-to-end |

### 7.2 Testy regresji wizualnej

- Porównanie wygenerowanego PDF z „golden" PDF dla znanego zestawu danych
- Narzędzie: `pdf-diff` lub manualna inspekcja dla major releases

---

## 8. Podsumowanie stacku

| Warstwa | Technologia | Wersja |
|---------|-------------|--------|
| Wykresy | Matplotlib (Agg backend) | >=3.7 |
| PDF | ReportLab (Platypus) | >=4.0 |
| Dane | Canonical JSON | v1.0.0 |
| Format | A4, 300 DPI, Helvetica | - |
