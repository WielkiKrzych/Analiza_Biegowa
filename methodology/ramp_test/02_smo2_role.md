# Rola SmO₂ w Ramp Test

## 1. Co SmO₂ Realnie Mierzy

### 1.1 Definicja Techniczna

SmO₂ (Muscle Oxygen Saturation) mierzy **względne nasycenie hemoglobiny tlenem** w tkance mięśniowej pod sensorem, wyrażone jako procent.

```
SmO₂ = (HbO₂) / (HbO₂ + Hb) × 100%
```

### 1.2 Co Sensor "Widzi"

Sensor NIRS (Near-Infrared Spectroscopy) penetruje tkankę na głębokość **10–15 mm** i mierzy:
- Hemoglobinę w **kapilarach, arteriuszach i żyłkach** pod sensorem
- Mieszankę krwi tętniczej i żylnej (proporcja ~25:75)
- Tylko **jeden mięsień** (np. vastus lateralis)

### 1.3 Interpretacja Fizjologiczna

SmO₂ odzwierciedla **bilans lokalny** między:
- **Dostawą O₂** (perfuzja, cardiac output, Hb)
- **Ekstrakcją O₂** (aktywność metaboliczna mięśnia)

Spadek SmO₂ = lokalne zużycie > lokalna dostawa

---

## 2. SmO₂ jako Sygnał LOKALNY

### 2.1 Fundamentalne Ograniczenie

> **SmO₂ mierzy JEDEN mięsień, nie cały organizm.**

| Pomiar | Zakres |
|--------|--------|
| SmO₂ | 1 mięsień (np. vastus lateralis) |
| VO₂ | Całe ciało |
| VE | Całe ciało |
| HR | Całe ciało |

### 2.2 Konsekwencje

1. **Różne mięśnie reagują inaczej**
   - Vastus lateralis ≠ rectus femoris ≠ gastrocnemius
   - Każdy mięsień ma inną proporcję włókien, kapilaryzację, rekrutację

2. **Pozycja sensora ma krytyczne znaczenie**
   - Przesunięcie o 2 cm może zmienić odczyt o 10–15%
   - Grubość tkanki tłuszczowej wpływa na sygnał

3. **SmO₂ nie reprezentuje "wydolności"**
   - Wysokie SmO₂ ≠ lepsza wydolność
   - Niskie SmO₂ ≠ gorsza wydolność
   - To sygnał o lokalnym bilansie O₂

---

## 3. Dlaczego SmO₂ LT1/2 ≠ VT1/2

### 3.1 Różnica Źródeł Sygnału

| VT1/VT2 | SmO₂ LT1/LT2 |
|---------|--------------|
| Odpowiedź **systemowa** (całe ciało) | Odpowiedź **lokalna** (1 mięsień) |
| Oparta na wentylacji (VE/VO₂, VE/VCO₂) | Oparta na ekstrakcji O₂ w tkance |
| Regulacja przez chemoreceptory | Regulacja przez perfuzję lokalną |

### 3.2 Źródła Rozbieżności

1. **Niejednorodna rekrutacja mięśni**
   - Podczas rampy rekrutacja jednostek motorycznych przesuwa się
   - Mięsień pod sensorem może być rekrutowany wcześniej/później niż dominujący

2. **Lokalna perfuzja ≠ globalny cardiac output**
   - Regionalna redystrybucja krwi zmienia lokalną SmO₂ niezależnie od VT

3. **Opóźnienia**
   - SmO₂ reaguje z opóźnieniem 15–45 s
   - VT wykrywa zmianę wentylacyjną z opóźnieniem 5–15 s

### 3.3 Typowe Rozbieżności

| Scenariusz | SmO₂ LT vs VT |
|------------|---------------|
| Wytrenowany mięsień | SmO₂ LT **później** niż VT (lepsza kapilaryzacja) |
| Niewytrenowany/nowy | SmO₂ LT **wcześniej** niż VT |
| Niska perfuzja | SmO₂ LT znacząco **wcześniej** |

**Wniosek**: SmO₂ LT to **inny próg** niż VT — mogą korelować, ale nie są tożsame.

---

## 4. Warunki Utraty Wartości Interpretacyjnej SmO₂

### 4.1 Problemy Techniczne

| Problem | Skutek |
|---------|--------|
| Przemieszczenie sensora | Szum, nagłe skoki |
| Pocenie | Utrata kontaktu optycznego |
| Światło zewnętrzne | Zakłócenia NIRS |
| Zbyt mocne/słabe mocowanie | Kompresja naczyń / luźny kontakt |

### 4.2 Problemy Fizjologiczne

| Warunek | Skutek dla SmO₂ |
|---------|-----------------|
| Wysoka tkanka tłuszczowa (> 15 mm) | Sygnał z tłuszczu, nie mięśnia |
| Niska Hb (anemia) | Osłabiony sygnał NIRS |
| Zimno (wazokonstrykcja) | Obniżona perfuzja → fałszywie niskie SmO₂ |
| Hipotensja | Zmniejszona perfuzja globalna |

### 4.3 Problemy Protokołu

| Warunek | Problem |
|---------|---------|
| Zbyt szybka rampa (> 35 W/min) | SmO₂ nie nadąża za zmianami |
| Zbyt krótki test (< 8 min) | Niewystarczająca dynamika |
| Brak rozgrzewki | Niestabilna baseline SmO₂ |
| Przerwy w pedałowaniu | Artefakty reperfuzji |

### 4.4 Sygnały Ostrzegawcze

Dane SmO₂ tracą wartość interpretacyjną gdy:
- ⚠️ Sygnał jest płaski (brak zmian mimo wzrostu obciążenia)
- ⚠️ Nagłe skoki > 5% bez zmiany obciążenia
- ⚠️ Wartość baseline > 85% lub < 40%
- ⚠️ Brak korelacji z Power (r < 0.3)

---

## 5. SmO₂ jako Sygnał Modulujący

### 5.1 Rola w Metodologii

SmO₂ **NIE jest** głównym sygnałem do detekcji progów.

SmO₂ **JEST** sygnałem modulującym, który:
- **Potwierdza** lokalizację VT (gdy zgadza się z VE/HR)
- **Podważa** pewność VT (gdy znacząco się różni)
- **Dostarcza kontekst** o lokalnej odpowiedzi mięśnia

### 5.2 Hierarchia Sygnałów

```
1. VE (wentylacja)     → Główne źródło VT1/VT2
2. HR (tętno)          → Potwierdzenie systemowe
3. DFA-a1              → Potwierdzenie autonomiczne
4. SmO₂                → Modulacja lokalna (±)
```

### 5.3 Zasady Użycia SmO₂

1. **Nigdy jako jedyne źródło progu**
   - SmO₂ LT może różnić się od VT o 10–30 W

2. **Jako potwierdzenie**
   - Jeśli SmO₂ LT ≈ VT (±15 W) → zwiększ pewność VT
   - Jeśli SmO₂ LT ≠ VT (> 20 W różnicy) → zanotuj rozbieżność

3. **Jako źródło informacji lokalnej**
   - Szybki spadek SmO₂ → możliwy limit dostawy O₂
   - Płaski SmO₂ do końca → dobra kapilaryzacja i ekstrakcja
   - SmO₂ plateau przed spadkiem → rezerwowa zdolność ekstrakcji

---

## 6. Podsumowanie

| Aspekt | SmO₂ |
|--------|------|
| Typ sygnału | LOKALNY, nie systemowy |
| Rola w VT | Modulująca, nie decyzyjna |
| SmO₂ LT = VT? | NIE, korelacja ≠ tożsamość |
| Kiedy użyteczny | Potwierdzenie, kontekst lokalny |
| Kiedy tracił wartość | Artefakty, płaski sygnał, brak korelacji |

---

*Dokument koncepcyjny v1.0 — 2026-01-02*
