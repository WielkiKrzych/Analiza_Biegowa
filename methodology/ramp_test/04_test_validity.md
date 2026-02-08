# Kryteria Ważności Ramp Testu

## 1. Klasyfikacja Ważności

```
┌─────────────────────────────────────────────────────────────┐
│  🔴 NIEWAŻNY         │ Test odrzucony, powtórzyć           │
├─────────────────────────────────────────────────────────────┤
│  🟡 WAŻNY WARUNKOWO  │ Interpretacja z zastrzeżeniami      │
├─────────────────────────────────────────────────────────────┤
│  🟢 W PEŁNI WIARYGODNY│ Pełna interpretacja możliwa        │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Test NIEWAŻNY 🔴

Test jest **metodologicznie nieważny** gdy spełniony jest **KTÓRYKOLWIEK** z poniższych warunków:

### 2.1 Długość Rampy

| Kryterium | Granica |
|-----------|---------|
| Czas trwania rampy | < 6 minut |
| Liczba stopni/etapów rozpoznawalnych | < 4 |
| Brak osiągnięcia plateau/maksimum | Przerwanie przed wyczerpaniem |

### 2.2 Jakość Sygnałów

| Sygnał | Kryterium nieważności |
|--------|----------------------|
| Power | Brak danych > 30 s ciągłych |
| Power | Różnica chwilowa > 50% między próbkami |
| HR | Brak danych > 60 s ciągłych |
| HR | > 20% próbek to artefakty (< 40 bpm lub > 220 bpm) |

### 2.3 Artefakty

| Typ | Kryterium nieważności |
|-----|----------------------|
| Przerwy w pedałowaniu | > 3 przerwy po > 10 s każda |
| Zatrzymanie | Całkowite zatrzymanie > 20 s w fazie rampy |
| Nagłe skoki Power | > 3 skoki o amplitudzie > 100 W |

### 2.4 Zachowanie Badanego

| Problem | Kryterium nieważności |
|---------|----------------------|
| Przedwczesne przerwanie | "Stop" przed osiągnięciem minimum 8/10 RPE |
| Zmiana protokołu | Zmiana tempa rampy w trakcie testu |
| Brak rozgrzewki | Test rozpoczęty bez rozgrzewki (HR baseline niestabilny) |
| Problemy zdrowotne | Zgłoszenie bólu, zawrotów głowy, dyskomfortu |

---

## 3. Test WAŻNY WARUNKOWO 🟡

Test jest **ważny z zastrzeżeniami** gdy:
- NIE spełnia kryteriów nieważności (sekcja 2)
- ALE spełnia **KTÓRYKOLWIEK** z poniższych warunków:

### 3.1 Długość Rampy

| Kryterium | Granica |
|-----------|---------|
| Czas trwania rampy | 6–8 minut (krótki, ale akceptowalny) |
| Zakres intensywności | < 150 W różnicy między startem a maksimum |

### 3.2 Jakość Sygnałów

| Sygnał | Kryterium warunkowe |
|--------|---------------------|
| HR | 5–20% próbek to artefakty |
| SmO₂ | Brak danych > 30 s ciągłych |
| SmO₂ | Sygnał płaski (brak zmian mimo wzrostu Power) |
| DFA-a1 | Okno < 180 s (ograniczona wiarygodność) |

### 3.3 Artefakty

| Typ | Kryterium warunkowe |
|-----|---------------------|
| Przerwy w pedałowaniu | 1–3 przerwy po 5–10 s |
| Niestabilna kadencja | Odchylenie > 15 rpm od średniej |
| Szum HR | Odchylenie > 10 bpm między kolejnymi próbkami |

### 3.4 Zachowanie Badanego

| Problem | Kryterium warunkowe |
|---------|---------------------|
| Subiektywne wyczerpanie | RPE 8–9/10 przy przerwaniu (nie pełne maximum) |
| Nieoptymalna rozgrzewka | Rozgrzewka < 5 minut |
| Zmienna pozycja | Zmiana pozycji siodła/kierownicy w trakcie |

### 3.5 Implikacje Warunkowej Ważności

> **Interpretacja możliwa, ale:**
> - Pewność progów: **obniżona**
> - Raport zawiera: **zastrzeżenia**
> - Porównanie z poprzednimi testami: **ograniczone**

---

## 4. Test W PEŁNI WIARYGODNY 🟢

Test jest **w pełni wiarygodny** gdy spełnione są **WSZYSTKIE** poniższe kryteria:

### 4.1 Długość Rampy

| Kryterium | Wymaganie |
|-----------|-----------|
| Czas trwania rampy | ≥ 8 minut |
| Zakres intensywności | ≥ 150 W różnicy |
| Osiągnięcie maksimum | Subiektywne wyczerpanie (RPE 10/10) LUB plateau HR |

### 4.2 Jakość Sygnałów

| Sygnał | Wymaganie |
|--------|-----------|
| Power | Ciągłe dane, brak przerw > 5 s |
| Power | Odchylenie chwilowe < 20% od trendu |
| HR | < 5% próbek to artefakty |
| HR | Ciągłe dane, brak przerw > 15 s |
| SmO₂ (jeśli używane) | Ciągłe dane, widoczny trend spadkowy |
| DFA-a1 (jeśli używane) | Okno ≥ 180 s, ≥ 100 punktów RR w oknie |

### 4.3 Brak Artefaktów

| Typ | Wymaganie |
|-----|-----------|
| Przerwy | Brak przerw w pedałowaniu > 5 s |
| Kadencja | Stabilna (odchylenie < 10 rpm) |
| Power | Płynny wzrost zgodny z protokołem |

### 4.4 Zachowanie Badanego

| Aspekt | Wymaganie |
|--------|-----------|
| Rozgrzewka | ≥ 5 minut, HR ustabilizowany przed rampą |
| Wyczerpanie | Pełne subiektywne wyczerpanie LUB plateau HR |
| Pozycja | Stała pozycja przez cały test |
| Stan zdrowia | Brak zgłoszonych dolegliwości |

---

## 5. Tabela Podsumowująca

| Kryterium | 🔴 Nieważny | 🟡 Warunkowy | 🟢 Wiarygodny |
|-----------|-------------|--------------|----------------|
| **Czas rampy** | < 6 min | 6–8 min | ≥ 8 min |
| **Przerwy** | > 3 × 10 s | 1–3 × 5–10 s | Brak > 5 s |
| **Artefakty HR** | > 20% | 5–20% | < 5% |
| **Zatrzymania** | > 20 s | — | Brak |
| **Wyczerpanie** | Przedwczesne (RPE < 8) | RPE 8–9 | RPE 10 / plateau |
| **Rozgrzewka** | Brak | < 5 min | ≥ 5 min |

---

## 6. Procedura Weryfikacji

### 6.1 Automatyczna

1. Sprawdź długość rampy (czas, zakres W)
2. Policz artefakty w każdym sygnale
3. Wykryj przerwy i zatrzymania
4. Oceń stabilność kadencji

### 6.2 Manualna (wymagana dla przypadków granicznych)

1. Przegląd wykresu Power vs Time
2. Ocena zachowania badanego (notatki)
3. Potwierdzenie subiektywnego wyczerpania
4. Decyzja: nieważny / warunkowy / wiarygodny

---

## 7. Komunikacja Wyników

### 7.1 Test Nieważny

> ⛔ **Test metodologicznie nieważny**
> 
> Powód: [konkretny powód]
> 
> Zalecenie: Powtórzyć test po [minimalna przerwa]

### 7.2 Test Warunkowy

> ⚠️ **Test ważny z zastrzeżeniami**
> 
> Zastrzeżenia: [lista problemów]
> 
> Wyniki należy interpretować z ostrożnością.
> Pewność progów: ŚREDNIA

### 7.3 Test Wiarygodny

> ✅ **Test w pełni wiarygodny**
> 
> Wszystkie kryteria jakości spełnione.
> Pewność progów: WYSOKA

---

*Dokument koncepcyjny v1.0 — 2026-01-02*
