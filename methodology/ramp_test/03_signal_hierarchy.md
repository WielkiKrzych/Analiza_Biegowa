# Hierarchia Wiarygodności Sygnałów w Ramp Test

## 1. Podział Funkcjonalny

### 1.1 Oś Wymuszenia vs Obserwatorzy

```
┌─────────────────────────────────────────────────────────────┐
│                    OŚ WYMUSZENIA                            │
│                                                             │
│    POWER (W) ──────────────────────────────────────────→    │
│    Kontrolowana zmienna niezależna                          │
│    Jedyny sygnał, który WYMUSZAMY                           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    OBSERWATORZY                             │
│                                                             │
│    HR, SmO₂, DFA-a1 ────────────────────────────────────→   │
│    Zmienne zależne, które OBSERWUJEMY                       │
│    Reagują na oś wymuszenia z różnym opóźnieniem            │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Hierarchia Wiarygodności

```
Poziom 1: WYMUSZENIE    │ Power
Poziom 2: SYSTEMOWE     │ HR
Poziom 3: AUTONOMICZNE  │ DFA-a1 (HRV)
Poziom 4: LOKALNE       │ SmO₂
```

---

## 2. Power (Moc) — Oś Wymuszenia

### 2.1 Rola w Hierarchii

| Aspekt | Opis |
|--------|------|
| **Typ** | Zmienna niezależna (WYMUSZENIE) |
| **Poziom** | 1 (najwyższy) |
| **Funkcja** | Definiuje obciążenie, względem którego oceniamy odpowiedzi |

### 2.2 Co Wnosi

- **Jedyna kontrolowana zmienna** — wszystko inne jest reakcją na Power
- **Bezpośredni pomiar** — bez opóźnienia, bez przetwarzania
- **Podstawa stref** — VT1/VT2 wyrażane w Watach
- **Powtarzalność** — umożliwia porównywanie testów

### 2.3 Co Go Psuje

| Problem | Skutek |
|---------|--------|
| Błąd kalibracji power metera | Systematyczne przesunięcie wszystkich progów |
| Dryft power metera w trakcie testu | Fałszywa zmiana odpowiedzi |
| Nieregularna kadencja | Zmienność chwilowej mocy |
| Zmiana pozycji na rowerze | Zmiana rekrutacji mięśni przy tej samej mocy |

### 2.4 Jak Reaguje na Rampę

```
Power nie "reaguje" — Power DEFINIUJE rampę.

Czas →
        ╱
       ╱   ← Liniowy wzrost (np. 25 W/min)
      ╱
     ╱
────╱
   Start
```

---

## 3. HR (Tętno) — Obserwator Systemowy

### 3.1 Rola w Hierarchii

| Aspekt | Opis |
|--------|------|
| **Typ** | Zmienna zależna (OBSERWATOR) |
| **Poziom** | 2 (główny obserwator systemowy) |
| **Funkcja** | Odzwierciedla odpowiedź sercowo-naczyniową na obciążenie |

### 3.2 Co Wnosi

- **Odpowiedź całego ciała** — integruje wszystkie mięśnie
- **Dostępność** — każdy ma czujnik HR
- **Trend liniowy → nieliniowy** — zmiana charakteru wskazuje VT1
- **Plateau/dryft** — wskazuje zbliżanie się do VT2/maksimum

### 3.3 Co Go Psuje

| Problem | Skutek |
|---------|--------|
| Artefakty (pocenie, przesunięcie pasa) | Szum, fałszywe skoki |
| Kofeina, stres, niedospanie | Podwyższona baseline |
| Odwodnienie | Przesunięty HR przy danej mocy |
| Gorąco | Cardiac drift (HR rośnie przy stałej mocy) |
| Leki beta-blokerowe | Ograniczony zakres HR |
| Zbyt szybka rampa | HR nie nadąża (opóźnienie > 60 s) |

### 3.4 Jak Reaguje na Rampę

```
HR →
        ╭──────── Plateau/max
       ╱
      ╱    ← Przyspieszenie (VT2)
     ╱
    ╱ ← Zmiana nachylenia (VT1)
   ╱
  ╱ ← Liniowa odpowiedź
 ╱
────
   Power →
```

**Opóźnienie**: 30–90 s względem zmiany Power

---

## 4. DFA-a1 (HRV) — Obserwator Autonomiczny

### 4.1 Rola w Hierarchii

| Aspekt | Opis |
|--------|------|
| **Typ** | Zmienna zależna (OBSERWATOR) |
| **Poziom** | 3 (obserwator autonomiczny) |
| **Funkcja** | Odzwierciedla stan układu autonomicznego |

### 4.2 Co Wnosi

- **Złożoność fraktalna** — mierzy "chaos" w rytmie serca
- **Niezależny od absolutnego HR** — inna informacja niż sam HR
- **Korelacja z progami**:
  - α1 ≈ 1.0 → strefa aerobowa
  - α1 ≈ 0.75 → okolice VT1
  - α1 < 0.5 → powyżej VT2
- **Marker stresu autonomicznego** — reaguje na zmęczenie

### 4.3 Co Go Psuje

| Problem | Skutek |
|---------|--------|
| Arytmie (AF, ektopie) | DFA-a1 traci sens |
| Artefakty RR (brakujące uderzenia) | Fałszywe wartości |
| Za krótkie okno (< 120 s) | Niestabilne oszacowanie |
| Za mało punktów RR (< 100 w oknie) | Błąd statystyczny |
| Zbyt szybka rampa | Brak czasu na stabilizację |

### 4.4 Jak Reaguje na Rampę

```
DFA-a1 →
  1.2 │────╮
      │    ╲
  1.0 │     ╲
      │      ╲ ← VT1 (α1 ≈ 0.75)
  0.75│───────╲──────
      │        ╲
  0.5 │─────────╲──── ← VT2 (α1 < 0.5)
      │          ╲
  0.3 │           ╲___
      └──────────────────
         Power →
```

**Opóźnienie**: 60–180 s (wymaga okna czasowego)

---

## 5. SmO₂ — Obserwator Lokalny

### 5.1 Rola w Hierarchii

| Aspekt | Opis |
|--------|------|
| **Typ** | Zmienna zależna (OBSERWATOR LOKALNY) |
| **Poziom** | 4 (najniższy w hierarchii) |
| **Funkcja** | Odzwierciedla lokalny bilans O₂ w jednym mięśniu |

### 5.2 Co Wnosi

- **Informacja lokalna** — co dzieje się w konkretnym mięśniu
- **Dynamika ekstrakcji** — jak szybko mięsień "zużywa" tlen
- **Modulacja VT** — potwierdza lub podważa detekcję
- **Kinetyka** — szybkość zmian informuje o zdolnościach oksydacyjnych

### 5.3 Co Go Psuje

| Problem | Skutek |
|---------|--------|
| Przemieszczenie sensora | Nagły skok, utrata kontaktu |
| Pocenie | Zakłócenie optyczne |
| Gruba tkanka tłuszczowa (> 15 mm) | Sygnał z tłuszczu, nie mięśnia |
| Ucisk sensorem | Ograniczona perfuzja |
| Pozycja (inny mięsień) | Zupełnie inny profil |
| Zbyt szybka rampa | SmO₂ nie nadąża |

### 5.4 Jak Reaguje na Rampę

```
SmO₂ (%) →
  80 │───╮
     │   ╲
  70 │    ╲
     │     ╲ ← Początek spadku (LT1?)
  60 │──────╲──────
     │       ╲
  50 │────────╲──── ← Przyspieszony spadek (LT2?)
     │         ╲
  40 │          ╲___
     └──────────────────
         Power →
```

**Opóźnienie**: 15–45 s (perfuzja lokalna)

---

## 6. Podsumowanie Hierarchii

| Sygnał | Poziom | Typ | Opóźnienie | Wnosi | Najczęstszy problem |
|--------|--------|-----|------------|-------|---------------------|
| **Power** | 1 | WYMUSZENIE | 0 s | Definiuje oś X | Kalibracja |
| **HR** | 2 | Systemowy | 30–90 s | Odpowiedź całego ciała | Artefakty, dryft |
| **DFA-a1** | 3 | Autonomiczny | 60–180 s | Złożoność fraktalna | Za krótkie okno, arytmie |
| **SmO₂** | 4 | Lokalny | 15–45 s | Bilans O₂ w mięśniu | Pozycja sensora |

---

## 7. Zasady Interpretacji

### 7.1 Power jest Osią, Reszta to Obserwatorzy

- Wszystkie progi wyrażamy względem Power
- Sygnały obserwujemy jako reakcję na Power
- Nigdy nie "wymuszamy" HR ani SmO₂

### 7.2 Hierarchia Wiarygodności

Przy sprzecznych sygnałach:
1. Ufaj temu, co wyżej w hierarchii
2. Sygnał niższy może modulować pewność, nie decyzję
3. Konflikt między poziomami → zmniejsz pewność

### 7.3 Przykład Konfliktu

> VT oparte na HR wskazuje 200 W.
> SmO₂ sugeruje 180 W.

**Decyzja**: VT = 200 W (HR wyżej w hierarchii), ale pewność: **średnia** (SmO₂ nie potwierdza)

---

*Dokument koncepcyjny v1.0 — 2026-01-02*
