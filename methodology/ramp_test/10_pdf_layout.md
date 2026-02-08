# Ramp Test PDF Report – Layout Specification

> **Dokument:** Specyfikacja layoutu raportu PDF dla Ramp Testu  
> **Wersja:** 1.0.0  
> **Ostatnia aktualizacja:** 2026-01-03

---

## Zasady ogólne

| Zasada | Opis |
|--------|------|
| **Język** | Niemedyczny, dla zawodnika (kolarza). Unikaj terminologii klinicznej. |
| **Progi VT1/VT2** | Prezentowane jako **zakresy**, nie pojedyncze punkty. |
| **SmO₂ LT1/LT2** | Sygnał **wspierający**, nie decyzyjny. Wyraźnie to komunikuj. |
| **Confidence Score** | Wyświetlany jawnie na okładce (strona 1). |
| **Tryb warunkowy** | Jeśli `RAMP_TEST_CONDITIONAL`, wymagana wyraźna adnotacja. |
| **Ograniczenia** | Dedykowana sekcja informująca o granicach interpretacji. |

---

## Strona 1: Okładka / Podsumowanie

### Tytuł strony
**„Raport z Testu Ramp"**

### Cel strony
Przedstawić kluczowe wyniki w sposób natychmiast czytelny. Zawodnik powinien w 10 sekund zrozumieć swoje główne progi i poziom pewności wyników.

### Elementy OBOWIĄZKOWE

| Element | Opis | Położenie |
|---------|------|-----------|
| **Tytuł raportu** | „Raport z Testu Ramp" | Górna część, wyśrodkowany |
| **Data testu** | Format: YYYY-MM-DD | Pod tytułem |
| **ID sesji** | Pierwsze 8 znaków UUID | Pod datą, mniejsza czcionka |
| **Wersja metodologii** | np. `v1.0.0` | Obok ID sesji |
| **Confidence Score** | Wartość procentowa (np. 75%) + etykieta słowna („Wysoka pewność" / „Umiarkowana" / „Niska") | Wyróżniony badge, poniżej nagłówka |
| **Adnotacja warunkowa** | ⚠️ „Test rozpoznany warunkowo – interpretacja obarczona zwiększoną niepewnością" | Żółty box, tylko gdy `is_conditional=True` |

### Tabela kluczowych wyników

| Parametr | Wartość | Interpretacja |
|----------|---------|---------------|
| VT1 (Próg tlenowy) | `XXX W` | Strefa komfortowa |
| VT2 (Próg beztlenowy) | `XXX W` | Strefa wysiłku |
| Zakres VT1–VT2 | `XXX–YYY W` | Strefa tempo/threshold |
| Moc maksymalna (Pmax) | `XXX W` | Szczyt testu |
| VO₂max (szacowany) | `XX.X ml/kg/min` | Wydolność tlenowa |
| CP (Critical Power) | `XXX W` | Moc progowa |

### Wykres
**Ramp Profile Chart** – przebieg mocy w czasie z zaznaczonymi VT1/VT2 jako pionowe linie.

---

## Strona 2: Szczegóły Progów Wentylacyjnych

### Tytuł strony
**„Szczegóły Progów VT1 / VT2"**

### Cel strony
Wyjaśnić, czym są progi wentylacyjne i jak zostały wykryte. Pokazać dane wspierające (HR, VE).

### Informacje tekstowe
- Krótki opis: „Progi zostały wykryte na podstawie zmian w wentylacji (oddychaniu) podczas testu."
- Wyjaśnienie VT1: „Moment, gdy organizm zaczyna intensywniej pracować."
- Wyjaśnienie VT2: „Punkt, powyżej którego wysiłek staje się bardzo ciężki."

### Tabela progów

| Próg | Moc [W] | HR [bpm] | VE [L/min] |
|------|---------|----------|------------|
| VT1 | `XXX` | `XXX` | `XX.X` |
| VT2 | `XXX` | `XXX` | `XX.X` |

### Wykres
**SmO₂ vs Power Chart** – SmO₂ na osi Y, moc na osi X, z zaznaczonymi LT1/LT2.

### Adnotacja SmO₂
> ℹ️ „SmO₂ LT1/LT2 są sygnałem wspierającym. Nie zastępują progów wentylacyjnych, ale pomagają je potwierdzić."

---

## Strona 3: Power-Duration Curve (PDC) i Critical Power

### Tytuł strony
**„Krzywa Mocy i Critical Power"**

### Cel strony
Przedstawić model CP/W' i krzywą mocy. Wyjaśnić, co oznacza Critical Power w praktyce treningowej.

### Informacje tekstowe
- „Krzywa mocy pokazuje, jak długo możesz utrzymać dany poziom wysiłku."
- „**CP** to moc, którą teoretycznie możesz utrzymać bardzo długo."
- „**W'** to Twoja rezerwa energetyczna powyżej CP."

### Tabela CP/W'

| Parametr | Wartość | Znaczenie |
|----------|---------|-----------|
| CP | `XXX W` | Moc „długotrwała" |
| CP/kg | `X.XX W/kg` | Względna wydolność |
| W' | `XX.X kJ` | Rezerwa anaerobowa |

### Wykres
**Power-Duration Curve** – krzywa mocy od 1s do 60min, z zaznaczonym CP jako pozioma linia asymptotyczna.

---

## Strona 4: Interpretacja Wyników

### Tytuł strony
**„Co oznaczają te wyniki?"**

### Cel strony
Przetłumaczyć liczby na język zrozumiały dla zawodnika. Wyjaśnić, jak wykorzystać wyniki w treningu.

### Informacje tekstowe (pełne akapity)

1. **Próg tlenowy (VT1)**  
   „Twój próg tlenowy wynosi {VT1} W. To moc, przy której możesz jechać komfortowo przez wiele godzin. Oddychasz spokojnie, możesz rozmawiać."

2. **Próg beztlenowy (VT2)**  
   „Twój próg beztlenowy wynosi {VT2} W. Powyżej tej mocy wysiłek staje się bardzo wymagający. Oddychasz ciężko, nie możesz swobodnie mówić."

3. **Strefa Tempo**  
   „Strefa między {VT1} a {VT2} W to Twoja strefa „tempo" – idealna do treningu wytrzymałościowego i poprawy progu."

4. **Critical Power**  
   „CP ({CP} W) to matematyczne przybliżenie Twojej mocy progowej. Możesz używać tej wartości do planowania interwałów i wyznaczania stref treningowych."

---

## Strona 5: Strefy Treningowe

### Tytuł strony
**„Rekomendowane Strefy Treningowe"**

### Cel strony
Przełożyć wyniki na konkretne strefy treningowe, które zawodnik może natychmiast zastosować.

### Tabela stref

| Strefa | Zakres [W] | Opis | Cel treningowy |
|--------|-----------|------|----------------|
| Z1 Recovery | `< X` | Bardzo łatwy | Regeneracja |
| Z2 Endurance | `X–Y` | Komfortowy | Baza tlenowa |
| Z3 Tempo | `Y–Z` | Umiarkowany | Próg |
| Z4 Threshold | `Z–A` | Ciężki | Wytrzymałość |
| Z5 VO₂max | `> A` | Maksymalny | Kapacytacja |

### Formuły obliczania stref
- Z1: `< VT1 × 0.8`
- Z2: `VT1 × 0.8 – VT1`
- Z3: `VT1 – VT2`
- Z4: `VT2 – VT2 × 1.05`
- Z5: `> VT2 × 1.05`

---

## Strona 6: Ograniczenia Interpretacji

### Tytuł strony
**„⚠️ Ograniczenia interpretacji"**

### Cel strony
Chronić zawodnika i trenera przed nadinterpretacją wyników. Jasno komunikować, czym raport NIE JEST.

### Treść sekcji (OBOWIĄZKOWA)

> **1. To nie jest badanie medyczne.**  
> Wyniki są szacunkami algorytmicznymi, nie pomiarami laboratoryjnymi. Nie służą do diagnozowania stanów zdrowotnych.

> **2. Dokładność zależy od jakości danych.**  
> Niepoprawna kalibracja czujników, artefakty ruchu lub niestabilność sygnału mogą wpłynąć na wyniki.

> **3. Progi są przybliżeniami.**  
> VT1/VT2 wykryte algorytmicznie mogą się różnić od wyników testu spirometrycznego w laboratorium.

> **4. Wyniki są jednorazowe.**  
> Wydolność zmienia się w czasie – powtarzaj testy co 6-8 tygodni, aby śledzić postępy.

> **5. SmO₂ to sygnał wspierający.**  
> LT1/LT2 z SmO₂ nie zastępują progów wentylacyjnych. Służą do dodatkowej walidacji.

> **6. Skonsultuj się z trenerem.**  
> Przed wprowadzeniem zmian w treningu skonsultuj wyniki z wykwalifikowanym specjalistą.

### Adnotacja dla trybu warunkowego (jeśli dotyczy)
> ⚠️ **Ten raport został wygenerowany dla testu rozpoznanego warunkowo.**  
> Profil mocy lub czas kroków wykazują odchylenia od standardowego protokołu Ramp Test.  
> Interpretacja jest obarczona zwiększoną niepewnością.

---

## Stopka (każda strona)

| Element | Opis |
|---------|------|
| Numer strony | „Strona X" |
| Data wygenerowania | Format: YYYY-MM-DD HH:MM |
| Źródło | „Tri_Dashboard" |

---

## Oznaczenia specjalne

### Tryb warunkowy (`RAMP_TEST_CONDITIONAL`)
- **Strona 1:** Żółty box z tekstem: „⚠️ Test rozpoznany warunkowo – interpretacja obarczona zwiększoną niepewnością."
- **Strona 6:** Dodatkowy akapit w sekcji ograniczeń.

### Confidence Score
- **Strona 1:** Badge z wartością procentową i etykietą słowną.
- **Kolory:**
  - `>= 75%`: Zielony (Wysoka pewność)
  - `50-74%`: Żółty (Umiarkowana pewność)
  - `< 50%`: Czerwony (Niska pewność)

### Wersja metodologii
- **Strona 1:** W nagłówku, obok ID sesji: `v1.0.0`
- **Stopka:** Opcjonalnie powtórzona.

---

## Podsumowanie struktury

| Strona | Tytuł | Główna zawartość |
|--------|-------|------------------|
| 1 | Okładka | Kluczowe wyniki, confidence, wykres profilu |
| 2 | Progi VT1/VT2 | Tabela progów, wykres SmO₂ |
| 3 | PDC / CP | Tabela CP/W', wykres krzywej mocy |
| 4 | Interpretacja | Tekstowe wyjaśnienie wyników |
| 5 | Strefy | Tabela stref treningowych |
| 6 | Ograniczenia | Disclaimery i ostrzeżenia |
