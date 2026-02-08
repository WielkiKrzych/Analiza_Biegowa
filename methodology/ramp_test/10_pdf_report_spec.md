# Ramp Test PDF Report Specification

> **Status:** Draft v1.0  
> **Autor:** System  
> **Data:** 2026-01-03

## 1. Cel dokumentu

Definicja struktury i zawartości raportu PDF generowanego po analizie Ramp Testu. Raport przeznaczony dla **kolarza-amatora** – język niemedyczny, defensywny, zrozumiały.

---

## 2. Struktura raportu

```
┌─────────────────────────────────────────────────┐
│ STRONA 1: Podsumowanie + Wizualizacja           │
├─────────────────────────────────────────────────┤
│ STRONA 2: Szczegóły progów + Wsparcie SmO₂     │
├─────────────────────────────────────────────────┤
│ STRONA 3: Power-Duration Curve + CP            │
├─────────────────────────────────────────────────┤
│ STRONA 4: Ograniczenia + Rekomendacje          │
└─────────────────────────────────────────────────┘
```

---

## 3. Sekcje szczegółowe

### 3.1 Strona 1: Podsumowanie wyników

#### Nagłówek
- Logo / Nazwa aplikacji
- **Tytuł:** „Raport z testu Ramp – [DATA]"
- **Zawodnik:** (opcjonalne, jeśli podane)
- **Confidence Score:** `[0.XX]` z opisem słownym

#### Sekcja: Kluczowe wyniki

| Metryka | Wartość | Zakres / Interpretacja |
|---------|---------|------------------------|
| **VT1 (Próg tlenowy)** | `XXX W` | Strefa komfortowa |
| **VT2 (Próg beztlenowy)** | `XXX W` | Strefa wysiłku |
| **Zakres VT1–VT2** | `XXX–XXX W` | Strefa tempo/threshold |
| **Moc maksymalna (Pmax)** | `XXX W` | Szczyt testu |
| **VO₂max (est.)** | `XX.X ml/kg/min` | Szacunek wydolności |

#### Wykres: Przebieg testu
- **Typ:** Liniowy, czas vs moc + HR
- **Osie:**
  - X: Czas [min:sek]
  - Y1: Moc [W]
  - Y2: HR [bpm]
- **Znaczniki:** Pionowe linie VT1 / VT2

---

### 3.2 Strona 2: Szczegóły progów

#### Sekcja: Progi wentylacyjne (VT1 / VT2)

**Tekst wprowadzający:**
> „Progi zostały wykryte na podstawie zmian w wentylacji (oddychaniu) podczas testu. VT1 oznacza moment, gdy organizm zaczyna intensywniej pracować. VT2 to punkt, powyżej którego wysiłek staje się bardzo ciężki."

| Próg | Moc [W] | HR [bpm] | VE [L/min] | % Pmax |
|------|---------|----------|------------|--------|
| VT1  | XXX     | XXX      | XX.X       | XX%    |
| VT2  | XXX     | XXX      | XX.X       | XX%    |

#### Wykres: VE vs Power
- **Typ:** Scatter + trend
- **Osie:**
  - X: Moc [W]
  - Y: Wentylacja [L/min]
- **Znaczniki:** Punkty VT1 / VT2 z etykietami

#### Sekcja: Wsparcie SmO₂ (sygnał pomocniczy)

**Tekst wprowadzający:**
> „SmO₂ (saturacja mięśniowa) to dodatkowy wskaźnik potwierdzający progi. Spadek SmO₂ sugeruje rosnące zapotrzebowanie mięśni na tlen."

| Próg SmO₂ | Moc [W] | SmO₂ [%] | Korelacja z VT |
|-----------|---------|----------|----------------|
| LT1       | XXX     | XX.X     | ± X W vs VT1   |
| LT2       | XXX     | XX.X     | ± X W vs VT2   |

#### Wykres: SmO₂ vs Power
- **Typ:** Liniowy
- **Osie:**
  - X: Moc [W]
  - Y: SmO₂ [%]
- **Znaczniki:** LT1 / LT2

---

### 3.3 Strona 3: Power-Duration Curve + CP

#### Sekcja: Krzywa mocy (PDC)

**Tekst wprowadzający:**
> „Krzywa mocy pokazuje, jak długo możesz utrzymać dany poziom wysiłku. Im dłużej, tym niższa moc – to normalne."

#### Wykres: Power-Duration Curve
- **Typ:** Log-log lub lin-lin
- **Osie:**
  - X: Czas [min] (1, 5, 10, 20, 60)
  - Y: Moc [W]
- **Krzywe:**
  - Twoje MMP (punkty)
  - Model CP (linia)

#### Sekcja: Critical Power (CP) i W'

| Parametr | Wartość | Interpretacja |
|----------|---------|---------------|
| **CP (Critical Power)** | XXX W | Moc, którą możesz utrzymać „długo" |
| **W' (Rezerwa anaerobowa)** | XXX kJ | Zapas energii powyżej CP |
| **CP/kg** | X.XX W/kg | Względna wydolność |

**Info box:**
> „CP to przybliżenie Twojej mocy progowej. Nie jest to dokładny odpowiednik FTP, ale służy do planowania treningu."

---

### 3.4 Strona 4: Ograniczenia i rekomendacje

#### Sekcja: Confidence Score

**Wizualizacja:** Gauge (0–100%) lub pasek postępu

| Składnik | Wynik | Uwagi |
|----------|-------|-------|
| Klasyfikacja sesji | ✅/⚠️ | Ramp Test wykryty |
| Jakość danych mocy | ✅/⚠️ | Brak przerw |
| Jakość danych VE | ✅/⚠️ | Wystarczająca długość |
| Jakość danych SmO₂ | ✅/⚠️ | Opcjonalne |

**Łączny confidence:** `XX%`

#### Sekcja: Ograniczenia interpretacji

> [!WARNING]
> **Ważne informacje**

1. **To nie jest badanie medyczne.** Wyniki są szacunkami na podstawie algorytmów, nie pomiaru laboratoryjnego.

2. **Dokładność zależy od jakości danych.** Niepoprawne skalibrowanie czujników może wpłynąć na wyniki.

3. **Progi są przybliżeniami.** VT1/VT2 wykryte algorytmicznie mogą różnić się od wyników testu spirometrycznego.

4. **SmO₂ to sygnał wspierający.** Nie jest to niezależna metoda detekcji progów.

5. **Wyniki są jednorazowe.** Wydolność zmienia się w czasie – powtarzaj testy regularnie.

#### Sekcja: Rekomendacje treningowe

| Strefa | Zakres mocy | Opis | Cel treningowy |
|--------|-------------|------|----------------|
| Z1 (Recovery) | < VT1 - 20% | Bardzo łatwy | Regeneracja |
| Z2 (Endurance) | VT1 ± 10% | Komfortowy | Baza tlenowa |
| Z3 (Tempo) | VT1 – VT2 | Umiarkowanie ciężki | Próg |
| Z4 (Threshold) | VT2 ± 5% | Ciężki | Wytrzymałość |
| Z5 (VO2max) | > VT2 + 10% | Maksymalny | Kapacytacja |

---

## 4. Elementy wizualne

### 4.1 Paleta kolorów
- **VT1:** `#FFA15A` (pomarańczowy)
- **VT2:** `#EF553B` (czerwony)
- **SmO₂ LT1:** `#2CA02C` (zielony)
- **SmO₂ LT2:** `#D62728` (ciemnoczerwony)
- **CP:** `#1F77B4` (niebieski)
- **Confidence OK:** `#2ECC71`
- **Confidence Warning:** `#F1C40F`

### 4.2 Fonty
- **Nagłówki:** Inter Bold, 16-24pt
- **Tekst:** Inter Regular, 10-12pt
- **Metryki:** Inter SemiBold, 14pt

### 4.3 Ikonografia
- ⚡ Moc
- ❤️ Tętno
- 🫁 Wentylacja
- 🩸 SmO₂
- 📊 Wykresy
- ⚠️ Ostrzeżenia

---

## 5. Wymagania techniczne

### 5.1 Format
- PDF/A (archiwizacja)
- Rozmiar: A4 (210 × 297 mm)
- Marginesy: 15mm

### 5.2 Generacja
- Biblioteka: `reportlab` lub `weasyprint`
- Wykresy: `matplotlib` (export PNG) → embed w PDF
- Tabele: Natywne tabele PDF

### 5.3 Metadata
```json
{
  "title": "Raport Ramp Test",
  "author": "Tri_Dashboard",
  "subject": "Analiza wydolnościowa",
  "keywords": "ramp test, VT1, VT2, CP, cycling",
  "created": "ISO8601 timestamp",
  "session_id": "UUID",
  "method_version": "X.Y.Z"
}
```

---

## 6. Przykład narrative flow

```
1. „Cześć! Oto Twoje wyniki z testu Ramp." (podsumowanie)
2. „Wykryliśmy Twoje progi:" (VT1/VT2 tabela)
3. „Oto jak wyglądał Twój test:" (wykres przebiegu)
4. „SmO₂ potwierdza te wyniki:" (LT1/LT2)
5. „Twoja krzywa mocy:" (PDC + CP)
6. „Jak pewne są te wyniki?" (confidence)
7. „Pamiętaj, że..." (ograniczenia)
8. „Na tej podstawie możesz trenować:" (strefy)
```

---

## 7. Changelog

| Wersja | Data | Opis |
|--------|------|------|
| 1.0 | 2026-01-03 | Wersja inicjalna |
