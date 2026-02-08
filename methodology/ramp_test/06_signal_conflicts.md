# Konflikty Między Sygnałami w Ramp Test

## 1. Wprowadzenie

Konflikty między sygnałami są **naturalne i informacyjne**. Nie oznaczają błędu — wskazują na złożoność odpowiedzi fizjologicznej lub ograniczenia pomiarowe.

```
Konflikt ≠ Błąd
Konflikt = Dodatkowa informacja
```

---

## 2. Konflikt HR vs Power

### 2.1 Typy Konfliktów

#### A. Cardiac Drift (HR rośnie przy stałej Power)

```
HR →
     ╭──────────
    ╱         ← HR rośnie
   ╱
──────────────────→ Time

Power →
─────────────────── ← Power stała
```

**Znaczenie fizjologiczne:**
- Przegrzanie (termoregulacja)
- Odwodnienie (zmniejszona objętość krwi)
- Zmęczenie mięśnia sercowego
- Deplecja glikogenu

**Wpływ na raport:**
> ⚠️ Wykryto cardiac drift (+X bpm przy stałej mocy)
> 
> Interpretacja progów HR może być przesunięta.
> Zalecenie: Używać zakresów Power, nie HR, do stref treningowych.

---

#### B. HR Plateau (HR przestaje rosnąć mimo wzrostu Power)

```
HR →
         ╭────────── ← Plateau
        ╱
       ╱
──────╱───────────────→ Power
```

**Znaczenie fizjologiczne:**
- Osiągnięcie HR max (limit chronotropowy)
- Sygnał zbliżania się do wyczerpania
- Możliwe osiągnięcie VT2

**Wpływ na raport:**
> ✅ Plateau HR wykryte przy X W
> 
> Potwierdza osiągnięcie limitu sercowo-naczyniowego.
> Interpretacja: Prawdopodobne VT2 w okolicach początku plateau.

---

#### C. HR Opóźniony (HR nie nadąża za Power)

**Znaczenie fizjologiczne:**
- Zbyt szybka rampa dla regulacji autonomicznej
- Wolna kinetyka sercowa (typowa u mniej wytrenowanych)

**Wpływ na raport:**
> ⚠️ HR opóźnione o ~X sekund względem Power
> 
> Detekcja VT oparta na HR może być przesunięta o Y W.
> Zastosowano korektę czasową.

---

### 2.2 Tabela Podsumowująca

| Konflikt | Fizjologia | Wpływ na VT | Wpływ na raport |
|----------|------------|-------------|-----------------|
| Cardiac drift | Termoregulacja/odwodnienie | Przeszacowanie VT (HR wyższe) | Ostrzeżenie + używaj Power |
| HR plateau | Limit chronotropowy | Wskazuje VT2 | Potwierdza maksimum |
| HR opóźniony | Wolna regulacja | Przesunięcie czasowe | Korekta czasowa |

---

## 3. Konflikt SmO₂ vs Power

### 3.1 Typy Konfliktów

#### A. SmO₂ Płaskie (brak spadku mimo wzrostu Power)

```
SmO₂ →
─────────────────── ← Brak zmiany

Power →
        ╱
       ╱
      ╱
─────╱────────────────→ Time
```

**Znaczenie fizjologiczne:**
- Bardzo dobra kapilaryzacja mięśnia (wytrenowanie lokalne)
- Perfuzja przewyższa ekstrakcję
- Możliwe: sensor nie na aktywnym mięśniu
- Możliwe: artefakt (utrata kontaktu)

**Wpływ na raport:**
> ⚠️ SmO₂ nie wykazuje typowego spadku
> 
> Możliwe przyczyny: wysoki poziom wytrenowania lub problem z sensorem.
> SmO₂ nie będzie używane do potwierdzenia VT.
> Pewność VT: obniżona (brak potwierdzenia lokalnego)

---

#### B. SmO₂ Spadek Wyprzedzający (spadek przed oczekiwanym VT)

**Znaczenie fizjologiczne:**
- Niska kapilaryzacja mięśnia pod sensorem
- Niedopasowanie perfuzji do metabolizmu
- Mięsień pod sensorem rekrutowany wcześniej

**Wpływ na raport:**
> ℹ️ SmO₂ sugeruje LT wcześniej (X W) niż VT (Y W)
> 
> Rozbieżność: Z W
> Interpretacja: Lokalny limit ekstrakcji O₂ występuje przed progiem systemowym.
> Sugestia: Praca nad kapilaryzacją mięśnia.

---

#### C. SmO₂ Spadek Opóźniony (spadek po oczekiwanym VT)

**Znaczenie fizjologiczne:**
- Wysoka rezerwa ekstrakcyjna mięśnia
- Bardzo dobra perfuzja lokalna
- Mięsień pod sensorem rekrutowany później

**Wpływ na raport:**
> ℹ️ SmO₂ sugeruje LT później (X W) niż VT (Y W)
> 
> Interpretacja: Mięsień dobrze wytrenowany, wysoka rezerwa tlenowa.

---

### 3.2 Tabela Podsumowująca

| Konflikt | Fizjologia | Wpływ na VT | Wpływ na raport |
|----------|------------|-------------|-----------------|
| SmO₂ płaskie | Wytrenowanie / artefakt | Brak potwierdzenia | Obniż pewność, zanotuj |
| SmO₂ wyprzedzający | Słaba kapilaryzacja | Konflikt lokalizacji | Zanotuj rozbieżność + sugestia |
| SmO₂ opóźniony | Wysoka rezerwa | Konflikt lokalizacji | Zanotuj jako pozytyw |

---

## 4. Konflikt DFA-a1 vs HR

### 4.1 Typy Konfliktów

#### A. DFA-a1 > 1.0 przy Wysokim HR

```
DFA-a1 = 1.2
HR = 175 bpm (wysokie)
```

**Znaczenie fizjologiczne:**
- Możliwe artefakty w sygnale RR
- Ektopie lub arytmia
- Problemy z detekcją R-peaks

**Wpływ na raport:**
> ⛔ DFA-a1 niefizjologiczne (α1 > 1.0 przy HR > 160)
> 
> Prawdopodobne artefakty w sygnale HRV.
> DFA-a1 wykluczone z analizy VT.

---

#### B. DFA-a1 Stabilne przy Rosnącym HR

```
DFA-a1 →
────────────────── ← Brak spadku (α1 ≈ 0.9)

HR →
        ╱
       ╱
      ╱
─────╱───────────────→ Power
```

**Znaczenie fizjologiczne:**
- Bardzo wysoki próg anaerobowy (wytrenowanie)
- Zbyt krótkie okno DFA (< 2 min)
- Możliwe: brak osiągnięcia VT podczas testu

**Wpływ na raport:**
> ⚠️ DFA-a1 nie wykazuje typowego spadku
> 
> Możliwe: wysoki poziom wytrenowania lub niewystarczające obciążenie.
> Pewność VT: obniżona (brak potwierdzenia autonomicznego)

---

#### C. DFA-a1 Szybki Spadek przy Wolnym Wzroście HR

**Znaczenie fizjologiczne:**
- Wysoka wrażliwość autonomiczna
- Szybka utrata złożoności HRV przy niskim obciążeniu
- Możliwe: niska tolerancja wysiłkowa

**Wpływ na raport:**
> ℹ️ DFA-a1 osiąga 0.75 wcześniej niż oczekiwano na podstawie HR
> 
> Interpretacja: Układ autonomiczny reaguje szybko na obciążenie.
> VT1 może być niższe niż sugeruje sam HR.

---

### 4.2 Tabela Podsumowująca

| Konflikt | Fizjologia | Wpływ na VT | Wpływ na raport |
|----------|------------|-------------|-----------------|
| α1 > 1.0 przy wysokim HR | Artefakty RR | Wyklucz DFA | Ostrzeżenie + wyklucz |
| α1 stabilne | Wytrenowanie / za krótki test | Brak potwierdzenia | Obniż pewność |
| α1 szybki spadek | Wysoka wrażliwość | VT potencjalnie niższe | Zanotuj + uwzględnij |

---

## 5. Ogólne Zasady Postępowania z Konfliktami

### 5.1 Hierarchia przy Konflikcie

Przy sprzecznych wskazaniach:
1. **Power** — zawsze pewna (oś wymuszenia)
2. **HR** — główny obserwator systemowy
3. **DFA-a1** — weryfikacja autonomiczna (jeśli wiarygodna)
4. **SmO₂** — modulacja (lokalny kontekst)

### 5.2 Wpływ na Confidence Score

| Typ konfliktu | Wpływ na pewność |
|---------------|------------------|
| Konflikt 2 sygnałów tego samego poziomu | −0.15 do −0.25 |
| Konflikt sygnału niższego z wyższym | −0.05 do −0.10 |
| Konflikt wszystkich sygnałów | ⛔ Wynik niepewny |

### 5.3 Raportowanie Konfliktów

Każdy konflikt powinien być:
1. **Wykryty** — automatycznie lub manualnie
2. **Nazwany** — typ konfliktu
3. **Wyjaśniony** — możliwe przyczyny fizjologiczne
4. **Uwzględniony** — wpływ na pewność i interpretację

---

## 6. Podsumowanie

| Para sygnałów | Typowe konflikty | Główny wpływ |
|---------------|------------------|--------------|
| HR vs Power | Drift, plateau, opóźnienie | Przesuwa/potwierdza VT |
| SmO₂ vs Power | Płaski, wyprzedza, opóźnia | Moduluje pewność VT |
| DFA-a1 vs HR | Niefizjologiczny, stabilny, szybki | Weryfikuje/podważa VT |

> **Konflikt to informacja, nie błąd.**
> Każdy konflikt powinien być jawnie zaraportowany z interpretacją fizjologiczną.

---

*Dokument koncepcyjny v1.0 — 2026-01-02*
