# Architektura systemu

> Wyciągnięte z README.md. README pozostaje historycznym changelogiem; ten plik jest kanonicznym opisem architektury.

## 🏗️ Architektura Systemu

> Ten dokument jest wyciągnięty z README dla wygody nawigacji. Główny README nadal jest historycznym changelogiem projektu.

```
┌─────────────────────────────────────────────────────────────┐
│                    🚀 STREAMLIT APP                          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ 📋 Tabs     │  │ 🎨 Theme    │  │ 💾 Cache    │         │
│  │ (29 mod)    │  │ Manager     │  │ Manager     │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    🔧 SERVICES LAYER                         │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐  ┌─────────────────────┐          │
│  │ ⚡ Orchestrator     │  │ ✅ Validation       │          │
│  │ (Numba JIT +       │  │ (Schema Check)      │          │
│  │  Polars)            │  │                     │          │
│  └─────────────────────┘  └─────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    📦 MODULES LAYER                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  🧮 CALCULATIONS          🎨 UI            💾 DATABASE      │
│  ───────────────          ─────            ──────────       │
│  • ⏱️ pace.py            • 📊 charts      • 🗄️ SQLite      │
│  • 🔋 d_prime.py         • 📈 reports     • 📂 sessions    │
│  • 🫁 ventilatory.py     • 🎯 metrics    • 📝 notes       │
│  • 💪 power.py           • 🗺️ maps       • ⚙️ settings    │
│  • ❤️ hrv.py             • 📱 mobile                        │
│  • 🩸 smo2_advanced.py                                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Główne Zakładki

```
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│   📊 OVERVIEW    │   ⚡ PERFORMANCE   │   🫀 PHYSIOLOGY   │   🧠 AI      │
│   ────────────   │   ─────────────    │   ─────────────    │   ─────     │
│                                                                          │
│   • 📈 Report      • 🏃 Running         • ❤️ HRV           • 🤖 ML       │
│   • 📋 Summary     • 🦶 Biomechanics    • 🩸 SmO2          • 🍽️ Nutrition│
│   • 🎯 KPIs        • 📐 Model           • 🫁 Ventilation   • 🔍 Limiters │
│   • 📊 Charts      • ❤️ HR Zones        • 🌡️ Thermal                      │
│   • 🗺️ Maps        • 🩸 Hematology      • 💧 Hydration                    │
│   • 📝 Notes       • 📉 Drift Maps                                        │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Pipeline Przetwarzania

```
    📁 CSV Input
       │
       ▼
┌─────────────────────┐
│  ⚡ Polars Loader   │  ← Szybkie I/O (10-100x)
│  (TTL Cache 1h)     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  🔄 Normalize       │  ← Mapowanie kolumn
│     Columns         │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  🧹 Clean &         │  ← Walidacja danych
│     Validate        │
└──────────┬──────────┘
           │
      ┌────┴────┐
      ▼         ▼
┌─────────┐ ┌─────────┐
│ 📊 Pandas│ │ ⚡ Numba │  ← Równoległe przetwarzanie
│ Standard│ │   JIT   │
└────┬────┘ └────┬────┘
     │           │
     └─────┬─────┘
           ▼
┌─────────────────────┐
│  🎯 Metrics Calc    │  ← W', NP, HR, Tempo
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  💾 Cache Results   │  ← @st.cache_data
└─────────────────────┘
```

---
