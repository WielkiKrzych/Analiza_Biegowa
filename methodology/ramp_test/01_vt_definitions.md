# Definicje VT1 i VT2 w Kontekście Ramp Testu

## 1. Czym jest VT1 (Próg Wentylacyjny 1)

### 1.1 Definicja Fizjologiczna

VT1 to **strefa przejściowa**, w której organizm zaczyna zwiększać wentylację **nieproporcjonalnie** do wzrostu obciążenia, aby utrzymać homeostazę metaboliczną.

Mechanizm:
- Wzrost produkcji CO₂ → stymulacja chemoreceptorów → wzrost częstości oddechów
- Początek akumulacji mleczanu powyżej poziomu spoczynkowego
- Przesunięcie od dominacji tlenowej do mieszanej

### 1.2 Manifestacja w Sygnałach

| Sygnał | Obserwacja w strefie VT1 |
|--------|--------------------------|
| VE (wentylacja) | Pierwszy punkt nieliniowego wzrostu VE/VO₂ |
| HR (tętno) | Początek odchylenia od liniowej odpowiedzi HR-Power |
| SmO₂ | Początek systematycznego spadku (nie pojedynczy skok) |
| DFA-a1 | Zbliżanie się do wartości ~0.75 (utrata korelacji fraktalnej) |

### 1.3 Charakterystyka Strefy

VT1 **nie jest punktem** — jest **obszarem przejścia** o szerokości typowo 10–30 W, w którym:
- Sygnały zaczynają reagować z różnym opóźnieniem
- HR może "dogonić" zmianę metabolizmu z opóźnieniem 30–90 s
- SmO₂ reaguje lokalnie, z opóźnieniem zależnym od perfuzji

---

## 2. Czym jest VT2 (Próg Wentylacyjny 2)

### 2.1 Definicja Fizjologiczna

VT2 to **strefa przejściowa**, powyżej której organizm **nie jest w stanie utrzymać stanu ustalonego** — akumulacja mleczanu przewyższa jego utylizację.

Mechanizm:
- Kompensacja kwasicy przez hiperwentylację (wzrost VE/VCO₂)
- Gwałtowny wzrost częstości oddechów kosztem głębokości
- Wejście w fazę nieodwracalnego zmęczenia metabolicznego

### 2.2 Manifestacja w Sygnałach

| Sygnał | Obserwacja w strefie VT2 |
|--------|--------------------------|
| VE (wentylacja) | Drugi punkt załamania — hiperwentylacja kompensacyjna |
| HR (tętno) | Spłaszczenie lub niestabilność (HR plateau / cardiac drift) |
| SmO₂ | Głęboki, przyspieszony spadek (desaturacja) |
| DFA-a1 | Wartość < 0.50 (całkowita utrata złożoności HRV) |

### 2.3 Charakterystyka Strefy

VT2 również jest **obszarem**, nie punktem:
- Szerokość strefy typowo 5–20 W
- Opóźnienie HR względem rzeczywistej zmiany: 45–120 s
- SmO₂ może wykazywać "plateau" przed gwałtownym spadkiem

---

## 3. Czym VT1 i VT2 NIE SĄ

### 3.1 Nie są punktami matematycznymi

> ❌ "VT1 = 185 W"

> ✅ "VT1 znajduje się w strefie 180–195 W"

Fizjologia nie działa jak przełącznik — przejście między stanami metabolicznymi jest **gradientowe**.

### 3.2 Nie są wartościami absolutnymi

VT1 i VT2:
- ❌ Nie są stałe dla danego zawodnika
- ❌ Nie można ich przenosić między testami bez weryfikacji
- ❌ Nie wynikają z norm populacyjnych ("65% VO₂max")

Każdy test musi identyfikować progi **de novo** na podstawie aktualnej odpowiedzi fizjologicznej.

### 3.3 Nie są progami laktatowymi

| Próg wentylacyjny | Próg laktatowy |
|-------------------|----------------|
| VT1 | LT1 (≈ 2 mmol/L) |
| VT2 | LT2 / MLSS (≈ 4 mmol/L) |

Korelacja istnieje, ale **nie są tożsame**:
- VT wykrywa odpowiedź wentylacyjną
- LT wymaga pomiaru mleczanu we krwi
- Rozbieżność może wynosić 5–15 W

### 3.4 Nie są progami FTP

- FTP (Functional Threshold Power) to **koncept treningowy**, nie fizjologiczny
- FTP ≈ VT2 to **przybliżenie**, nie definicja
- Używanie FTP zamiast VT2 wprowadza błąd systematyczny

---

## 4. Nieliniowość Odpowiedzi Fizjologicznej

### 4.1 Model Trzech Faz

```
Intensywność →

Faza I          │ Faza II        │ Faza III
(Aerobowa)      │ (Mieszana)     │ (Anaerobowa)
                │                │
Linearna        │ VT1           │ VT2
odpowiedź       │ (pierwszy     │ (drugi
HR, VE          │ punkt         │ punkt
                │ załamania)    │ załamania)
```

### 4.2 Charakterystyka Nieliniowości

- **Przed VT1**: VE rośnie proporcjonalnie do obciążenia
- **VT1–VT2**: VE rośnie szybciej niż obciążenie (kompensacja CO₂)
- **Powyżej VT2**: VE rośnie gwałtownie (kompensacja kwasicy)

---

## 5. Opóźnienia Sygnałów

### 5.1 Źródła Opóźnień

| Sygnał | Typowe opóźnienie | Przyczyna |
|--------|-------------------|-----------|
| Power | 0 s | Bezpośredni pomiar |
| VE | 5–15 s | Czas reakcji chemoreceptorów |
| HR | 30–90 s | Regulacja autonomiczna |
| SmO₂ | 15–45 s | Czas transportu O₂, perfuzja lokalna |
| DFA-a1 | 60–180 s | Wymaga okna czasowego do obliczeń |

### 5.2 Konsekwencje dla Detekcji

1. **Sygnały nie są zsynchronizowane** — każdy reaguje z inną dynamiką
2. **HR "goni" obciążenie** — przy szybkim rampie (30 W/min) opóźnienie jest większe
3. **SmO₂ jest lokalny** — odzwierciedla jeden mięsień, nie całe ciało
4. **DFA-a1 wymaga czasu** — okno 2–5 min jest minimum dla stabilnych odczytów

### 5.3 Implikacje Praktyczne

> Detekta VT1/VT2 powinna uwzględniać opóźnienia poprzez:
> - Analizę wsteczną (retrospective detection)
> - Korekty czasowe dla różnych sygnałów
> - Szersze strefy zamiast punktów

---

## 6. Próg jako Obszar, Nie Punkt

### 6.1 Model Strefy Przejściowej

```
         ┌─────────────────┐
         │   STREFA VT1    │
         │  (10–30 W)      │
         │                 │
   ──────┼─────────────────┼──────→ Power
         │                 │
    Faza I        Faza II
```

### 6.2 Parametry Strefy

Każdy próg powinien być opisany jako:
- **Dolna granica** — najniższa moc, przy której obserwujemy zmianę
- **Górna granica** — moc, przy której zmiana jest jednoznaczna
- **Pewność detekcji** — ile sygnałów potwierdza lokalizację

### 6.3 Raportowanie

Zamiast:
> VT1 = 185 W

Należy raportować:
> VT1: 180–195 W (pewność: wysoka, 3/4 sygnały zgodne)

---

*Dokument koncepcyjny v1.0 — 2026-01-02*
