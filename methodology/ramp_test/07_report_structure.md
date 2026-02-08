# Struktura Raportu z Ramp Testu

## 1. Zasady Ogólne

### 1.1 Język

| Unikaj | Używaj |
|--------|--------|
| "Twoje VT1 wynosi dokładnie 185 W" | "VT1 znajduje się w okolicach 180–190 W" |
| "Próg laktatowy" | "Próg aerobowy (VT1)" |
| "Diagnoza" | "Obserwacja" |
| "Musisz trenować" | "Sugeruję rozważyć" |
| "Jesteś słaby/silny" | "Profil wskazuje na..." |

### 1.2 Defensywność Metodologiczna

Każdy raport zawiera:
- Poziom pewności dla każdego progu
- Ograniczenia metodologiczne
- Zastrzeżenie o charakterze niemedycznym

---

## 2. Struktura Raportu

```
┌──────────────────────────────────────────────────────────────┐
│ 1. PODSUMOWANIE WYKONAWCZE                                   │
├──────────────────────────────────────────────────────────────┤
│ 2. INFORMACJE O TEŚCIE                                       │
├──────────────────────────────────────────────────────────────┤
│ 3. WAŻNOŚĆ TESTU                                             │
├──────────────────────────────────────────────────────────────┤
│ 4. WYNIKI — PROGI WENTYLACYJNE                               │
├──────────────────────────────────────────────────────────────┤
│ 5. WYNIKI — SmO₂ (SYGNAŁ LOKALNY)                            │
├──────────────────────────────────────────────────────────────┤
│ 6. KONFLIKTY I ZASTRZEŻENIA                                  │
├──────────────────────────────────────────────────────────────┤
│ 7. PROPONOWANE STREFY TRENINGOWE                             │
├──────────────────────────────────────────────────────────────┤
│ 8. SUGESTIE TRENINGOWE                                       │
├──────────────────────────────────────────────────────────────┤
│ 9. NOTA METODOLOGICZNA                                       │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Sekcje Szczegółowo

### 3.1 Podsumowanie Wykonawcze

**Cel:** Kluczowe wnioski w 3–5 zdaniach.

**Wzór:**
> Test przeprowadzony [data]. Zidentyfikowano próg aerobowy (VT1) w okolicach **X–Y W** oraz próg anaerobowy (VT2) w okolicach **A–B W**. Pewność detekcji: [wysoka/średnia/niska]. [Opcjonalnie: główna obserwacja, np. "Profil wskazuje na silną bazę aerobową."]

---

### 3.2 Informacje o Teście

| Pole | Wartość |
|------|---------|
| Data testu | [data] |
| Protokół | Rampa [X W/min] |
| Czas rozgrzewki | [min] |
| Czas rampy | [min] |
| Moc początkowa | [W] |
| Moc maksymalna | [W] |
| HR maksymalne | [bpm] |
| RPE końcowe | [/10] |

---

### 3.3 Ważność Testu

**Wzór dla testu wiarygodnego:**
> ✅ **Test metodologicznie wiarygodny**
> Wszystkie kryteria jakości spełnione.

**Wzór dla testu warunkowego:**
> ⚠️ **Test ważny z zastrzeżeniami**
> - [lista zastrzeżeń]
> Wyniki należy interpretować z ostrożnością.

**Wzór dla testu nieważnego:**
> ⛔ **Test metodologicznie nieważny**
> Powód: [...]
> Zalecenie: Powtórzyć test.

---

### 3.4 Wyniki — Progi Wentylacyjne

**Format prezentacji VT1/VT2:**

```
┌──────────────────────────────────────────────────────────┐
│ PRÓG AEROBOWY (VT1)                                      │
├──────────────────────────────────────────────────────────┤
│ Przedział mocy:     175 – 190 W                          │
│ Wartość centralna:  ~183 W                               │
│ Przedział HR:       ~138 – 145 bpm                       │
│                                                          │
│ Pewność detekcji:   ████████░░ WYSOKA (0.85)             │
│ Źródła zgodne:      HR ✓  VE ✓  SmO₂ ✓                   │
└──────────────────────────────────────────────────────────┘
```

**Język:**
- Zawsze "~" lub "w okolicach" przed wartością centralną
- Zawsze podawać przedział, nie punkt
- Zawsze podawać poziom pewności

---

### 3.5 Wyniki — SmO₂ (Sygnał Lokalny)

**Nagłówek sekcji:**
> ℹ️ **Uwaga:** SmO₂ jest sygnałem lokalnym mierzącym jeden mięsień. 
> Wyniki tej sekcji stanowią dodatkowy kontekst, nie główną diagnozę.

**Format:**

```
┌──────────────────────────────────────────────────────────┐
│ SmO₂ — ANALIZA LOKALNA (vastus lateralis)                │
├──────────────────────────────────────────────────────────┤
│ Punkt spadku SmO₂:  ~170 W                               │
│ Różnica vs VT1:     -13 W (SmO₂ reaguje wcześniej)       │
│                                                          │
│ Interpretacja:                                           │
│ Mięsień pod sensorem osiąga limit ekstrakcji O₂          │
│ przed ogólnym progiem wentylacyjnym. Może wskazywać      │
│ na potencjał do poprawy kapilaryzacji mięśnia.           │
└──────────────────────────────────────────────────────────┘
```

**Zasady:**
- Nigdy nie prezentować SmO₂ jako równoważnego VT
- Zawsze wyjaśniać różnicę (jeśli istnieje)
- Zawsze przypominać o lokalnym charakterze

---

### 3.6 Konflikty i Zastrzeżenia

**Cel:** Transparentność — co nie zgadzało się i dlaczego.

**Wzór:**
> **Zaobserwowane rozbieżności:**
> 
> 1. SmO₂ sugeruje LT1 przy ~170 W, podczas gdy VT1 na podstawie 
>    HR/VE znajduje się przy ~183 W. Różnica: 13 W.
>    *Interpretacja: Lokalna odpowiedź mięśnia różni się od systemowej.*
> 
> 2. Cardiac drift: HR wzrosło o +5 bpm w ostatnich 3 minutach 
>    przy stałej mocy podczas rozgrzewki.
>    *Uwzględniono w analizie.*

---

### 3.7 Proponowane Strefy Treningowe

**Format:**

| Strefa | Nazwa | Zakres mocy | Zakres HR | Uwagi |
|--------|-------|-------------|-----------|-------|
| Z1 | Regeneracja | < 130 W | < 115 bpm | |
| Z2 | Wytrzymałość | 130–165 W | 115–135 bpm | Główna strefa bazowa |
| Z3 | Tempo | 165–185 W | 135–145 bpm | Pod VT1 |
| Z4 | Próg | 185–220 W | 145–165 bpm | VT1–VT2 |
| Z5 | VO2max | > 220 W | > 165 bpm | Powyżej VT2 |

**Disclaimer:**
> *Strefy obliczone na podstawie wykrytych progów. 
> Przy pewności ŚREDNIEJ lub NISKIEJ rozważ margines ±5–10 W.*

---

### 3.8 Sugestie Treningowe

**Zasady:**
- Używaj "sugeruję", "rozważ", "może być korzystne"
- Nigdy "musisz", "powinieneś", "nakaz"
- Przy niskiej pewności: "Dane nie są wystarczająco pewne, aby formułować konkretne zalecenia"

**Wzór:**
> **Obserwacja:** Stosunek VT1/VT2 wynosi 0.72, co sugeruje zrównoważony profil aerobowy.
> 
> **Sugestia:** Rozważ utrzymanie mieszanego programu z przewagą strefy Z2 
> (60–70% objętości) uzupełnionego pracą w strefie Z4 (15–20%).

---

### 3.9 Nota Metodologiczna

**Obowiązkowa sekcja końcowa:**

> **Ograniczenia i zastrzeżenia**
> 
> 1. Niniejszy raport nie stanowi diagnozy medycznej. 
>    Test wykonano w warunkach niemedycznych.
> 
> 2. Progi wentylacyjne (VT1, VT2) są szacowane na podstawie 
>    dostępnych sygnałów bez bezpośredniej analizy gazowej (VO₂/VCO₂).
>    Dokładność jest ograniczona w porównaniu do badań laboratoryjnych.
> 
> 3. SmO₂ jest sygnałem lokalnym i nie zastępuje pomiarów systemowych.
> 
> 4. Wyniki mogą różnić się między testami o 5–15 W z powodu 
>    naturalnej zmienności fizjologicznej.
> 
> 5. Przed wprowadzeniem zmian w treningu skonsultuj się z trenerem.

---

## 4. Komunikowanie Niepewności

### 4.1 Słownictwo

| Pewność | Słownictwo |
|---------|------------|
| Wysoka (> 0.8) | "znajduje się w", "wynosi około" |
| Średnia (0.5–0.8) | "prawdopodobnie w okolicach", "szacujemy na" |
| Niska (< 0.5) | "może znajdować się", "dane sugerują, ale niepewnie" |

### 4.2 Wizualizacja

```
Pewność: ████████░░ 0.85 (wysoka)
Pewność: █████░░░░░ 0.52 (średnia)  
Pewność: ██░░░░░░░░ 0.25 (niska)
```

### 4.3 Przy Niskiej Pewności

> ⚠️ **Uwaga:** Pewność detekcji VT2 jest NISKA (0.42).
> Przedział 210–250 W jest szeroki i wymaga ostrożnej interpretacji.
> Zalecamy weryfikację w kolejnym teście.

---

## 5. Czego NIE Zawiera Raport

- ❌ Jednoznacznych wartości punktowych bez przedziału
- ❌ Sformułowań typu "diagnoza", "wynik badania"
- ❌ Porównań do norm populacyjnych ("jesteś powyżej średniej")
- ❌ Nakazowych zaleceń treningowych
- ❌ Prognoz wyników zawodów

---

*Dokument koncepcyjny v1.0 — 2026-01-02*
