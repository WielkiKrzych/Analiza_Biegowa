# Próg jako Przedział Intensywności

## 1. Dlaczego Punktowy Próg jest Uproszczeniem

### 1.1 Tradycyjne Podejście

```
"VT1 = 185 W"
```

To stwierdzenie sugeruje, że:
- Istnieje **jeden konkretny moment**, w którym następuje zmiana
- Poniżej 185 W organizm jest w jednym stanie, powyżej — w innym
- Pomiar jest **absolutnie dokładny**

### 1.2 Rzeczywistość Fizjologiczna

Rzeczywistość jest inna:

1. **Przejście jest gradientowe**
   - Organizm nie ma "przełącznika" metabolicznego
   - Zmiana charakteru odpowiedzi rozciąga się na 10–30 W
   - Różne systemy reagują w różnym tempie

2. **Sygnały mają opóźnienia**
   - HR reaguje 30–90 s po zmianie Power
   - SmO₂ reaguje 15–45 s
   - DFA-a1 wymaga okna 60–180 s
   - Punkt "detekcji" zależy od opóźnienia sygnału

3. **Pomiar ma niepewność**
   - Power meter: ±1–2% błędu
   - Detekcja załamania: subiektywna
   - Szum sygnałów: naturalna zmienność

4. **Dzień-do-dnia zmienność**
   - Ten sam zawodnik, ten sam protokół
   - VT1 może różnić się o 5–15 W między testami
   - To nie błąd — to fizjologia

### 1.3 Konsekwencje Punktowego Podejścia

| Problem | Skutek |
|---------|--------|
| Fałszywa precyzja | Trener ustawia strefy z dokładnością ±1 W |
| Nadinterpretacja zmian | "VT1 wzrosło o 3 W" traktowane jako postęp |
| Ignorowanie niepewności | Decyzje treningowe bez uwzględnienia marginesu błędu |

---

## 2. Koncepcja Progu jako Przedziału

### 2.1 Model Strefy Przejściowej

```
         STREFA VT1
    ┌────────────────────┐
    │                    │
    │   Dolna   Środek   Górna
    │   granica          granica
    │     │       │       │
────┼─────┼───────┼───────┼─────────→ Power
    │    180 W   190 W   200 W
    │                    │
    └────────────────────┘
         szerokość: 20 W
```

### 2.2 Trzy Komponenty

Każdy próg opisujemy jako:

1. **Dolna granica** (lower bound)
   - Najniższa moc, przy której obserwujemy zmianę w którymkolwiek sygnale
   - "Punkt, od którego coś się zaczyna dziać"

2. **Wartość centralna** (midpoint)
   - Środek przedziału LUB wartość o najwyższej zgodności sygnałów
   - To jest "VT1" w tradycyjnym sensie — ale z kontekstem

3. **Górna granica** (upper bound)
   - Moc, przy której zmiana jest już jednoznaczna we wszystkich sygnałach
   - "Punkt, od którego na pewno jesteśmy powyżej progu"

### 2.3 Dlaczego Przedział?

| Aspekt | Punkt | Przedział |
|--------|-------|-----------|
| Reprezentacja fizjologii | ❌ Sztuczna | ✅ Realistyczna |
| Uwzględnienie opóźnień | ❌ Nie | ✅ Tak |
| Margines błędu | ❌ Ukryty | ✅ Jawny |
| Decyzje treningowe | ⚠️ Fałszywa precyzja | ✅ Świadoma niepewność |

---

## 3. Confidence Score — Pewność Detekcji

### 3.1 Idea

Nie wszystkie progi są wykryte z jednakową pewnością. Confidence Score wyraża:
- **Jak wiele sygnałów potwierdza detekcję**
- **Jak spójne są te sygnały**
- **Jak wąski jest przedział**

### 3.2 Składniki Confidence Score

| Czynnik | Wpływ na pewność |
|---------|-----------------|
| Liczba zgodnych sygnałów | Więcej = wyższa pewność |
| Szerokość przedziału | Węższy = wyższa pewność |
| Jakość sygnałów | Mniej artefaktów = wyższa pewność |
| Wyrazistość zmiany | Ostrzejsze załamanie = wyższa pewność |

### 3.3 Skala Confidence

```
WYSOKA (0.8–1.0)
├── ≥ 3 sygnały zgodne
├── Przedział ≤ 15 W
├── Wyraźne załamanie
└── < 5% artefaktów

ŚREDNIA (0.5–0.8)
├── 2 sygnały zgodne
├── Przedział 15–30 W
├── Umiarkowane załamanie
└── 5–15% artefaktów

NISKA (< 0.5)
├── 1 sygnał lub brak zgodności
├── Przedział > 30 W
├── Niewyraźne załamanie
└── > 15% artefaktów
```

### 3.4 Przykłady

**Wysoka pewność:**
> VT1: 180–195 W (środek: 188 W)
> Confidence: 0.92
> Sygnały: HR ✓, VE ✓, SmO₂ ✓

**Średnia pewność:**
> VT1: 170–205 W (środek: 188 W)
> Confidence: 0.65
> Sygnały: HR ✓, VE ✓, SmO₂ ✗ (konflikt)

**Niska pewność:**
> VT1: 160–210 W (środek: 185 W)
> Confidence: 0.35
> Sygnały: HR ?, VE ✓, SmO₂ ✗

---

## 4. Raportowanie Progów

### 4.1 Format Tradycyjny (unikamy)

```
VT1 = 185 W
VT2 = 245 W
```

### 4.2 Format Przedziałowy (zalecany)

```
┌──────────────────────────────────────────┐
│ VT1                                      │
├──────────────────────────────────────────┤
│ Przedział:    180 – 195 W                │
│ Środek:       188 W                      │
│ Pewność:      WYSOKA (0.88)              │
│ Źródła:       HR ✓, VE ✓, SmO₂ ✓         │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│ VT2                                      │
├──────────────────────────────────────────┤
│ Przedział:    240 – 260 W                │
│ Środek:       250 W                      │
│ Pewność:      ŚREDNIA (0.72)             │
│ Źródła:       HR ✓, VE ✓, SmO₂ ✗         │
│ Uwaga:        SmO₂ sugeruje LT2 = 235 W  │
└──────────────────────────────────────────┘
```

---

## 5. Implikacje dla Stref Treningowych

### 5.1 Strefy z Marginesem Niepewności

Zamiast:
> Z3: 186–220 W

Lepiej:
> Z3: ~185–~220 W (margines ±10 W przy niskiej pewności VT1)

### 5.2 Komunikacja z Zawodnikiem

> "Twój próg aerobowy (VT1) znajduje się w okolicach **185–195 W**.
> Możesz trenować strefę 2 do około **180–185 W**, aby mieć pewność,
> że pozostajesz poniżej progu."

---

## 6. Kiedy Przedział się Rozszerza?

| Czynnik | Wpływ na szerokość |
|---------|-------------------|
| Mniej sygnałów | Szerszy przedział |
| Więcej artefaktów | Szerszy przedział |
| Wolniejsza rampa | Węższy przedział |
| Brak rozgrzewki | Szerszy przedział (niestabilna baseline) |
| Konflikty między sygnałami | Szerszy przedział |

---

## 7. Podsumowanie Koncepcji

| Element | Definicja |
|---------|-----------|
| **Przedział** | Zakres mocy, w którym zachodzi przejście metaboliczne |
| **Dolna granica** | Pierwszy sygnał wykrywa zmianę |
| **Górna granica** | Zmiana potwierdzona we wszystkich sygnałach |
| **Wartość centralna** | Środek przedziału lub punkt najwyższej zgodności |
| **Confidence Score** | Miara pewności detekcji (0–1) |

> **Próg nie jest punktem — jest strefą przejściową.**
> Raportowanie przedziału z confidence score uczciwie komunikuje niepewność inherentną w pomiarze fizjologicznym.

---

*Dokument koncepcyjny v1.0 — 2026-01-02*
