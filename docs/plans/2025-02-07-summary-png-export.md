# Eksport wykresów PNG z zakładki Podsumowanie - Plan Implementacji

> **⚠️ UWAGA:** Funkcjonalność eksportu wykresów PNG została usunięta z tej uproszczonej wersji aplikacji Analiza_Kolarska. Ten dokument pozostaje jako dokumentacja historyczna.

> **Goal:** Dodać funkcję generowania wykresów PNG z zakładki Podsumowanie do pobrania jako ZIP, z opcjami rozmiaru i watermarkiem.

**Architektura:** Stworzymy dedykowany serwis `summary_export.py` w `modules/reporting/` który będzie generował wykresy w wybranych rozmiarach z watermarkiem, oraz dodamy UI w sidebar do wyboru rozmiaru i przycisku eksportu.

**Tech Stack:** Plotly (do generowania wykresów), Pillow (do watermarków), io/zipfile (do ZIP), Streamlit (UI)

---

## Task 1: Utworzenie serwisu eksportu wykresów

**Files:**
- Create: `modules/reporting/summary_export.py`

**Step 1: Utwórz plik serwisu**

```python
"""
Serwis eksportu wykresów z zakładki Podsumowanie do PNG.
"""

import io
import zipfile
from typing import Optional, Tuple, List
import pandas as pd
import plotly.graph_objects as go
from PIL import Image, ImageDraw, ImageFont
import plotly.io as pio


# Dostępne rozmiary wykresów
CHART_SIZES = {
    "standard": (1200, 800),
    "large": (1600, 1200),
    "full_hd": (1920, 1080),
    "macbook_pro": (3024, 1964),  # MacBook Pro M4 Pro 14"
}


def add_watermark(image_bytes: bytes, text: str = "TriDashboard") -> bytes:
    """
    Dodaje watermark do obrazu PNG.
    
    Args:
        image_bytes: Raw PNG bytes
        text: Tekst watermarka
        
    Returns:
        PNG bytes z watermarkiem
    """
    img = Image.open(io.BytesIO(image_bytes))
    draw = ImageDraw.Draw(img)
    
    # Użyj domyślnej czcionki (brak zewnętrznych zależności)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
    except:
        font = ImageFont.load_default()
    
    # Oblicz pozycję (prawy dolny róg z marginesem)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = img.width - text_width - 30
    y = img.height - text_height - 30
    
    # Narysuj watermark z przezroczystością (10% opacity = 25/255)
    draw.text((x, y), text, fill=(255, 255, 255, 25), font=font)
    
    # Zapisz do bytes
    output = io.BytesIO()
    img.save(output, format='PNG')
    return output.getvalue()


def export_chart_to_png(
    fig: go.Figure,
    filename: str,
    size: Tuple[int, int] = (1200, 800),
    add_watermark_flag: bool = True
) -> Tuple[str, bytes]:
    """
    Eksportuje wykres Plotly do PNG z opcjonalnym watermarkiem.
    
    Args:
        fig: Obiekt wykresu Plotly
        filename: Nazwa pliku (bez rozszerzenia)
        size: Rozmiar wykresu (szerokość, wysokość)
        add_watermark_flag: Czy dodać watermark
        
    Returns:
        Tuple (nazwa_pliku.png, bytes)
    """
    # Ustaw rozmiar wykresu
    fig.update_layout(
        width=size[0],
        height=size[1],
        autosize=False,
    )
    
    # Eksportuj do PNG
    img_bytes = pio.to_image(fig, format='png', scale=1)
    
    # Dodaj watermark jeśli wymagany
    if add_watermark_flag:
        img_bytes = add_watermark(img_bytes)
    
    return f"{filename}.png", img_bytes


def generate_summary_charts_zip(
    df_plot: pd.DataFrame,
    size_key: str = "large",
    add_watermark_flag: bool = True
) -> bytes:
    """
    Generuje ZIP z wykresami z zakładki Podsumowanie.
    
    Args:
        df_plot: DataFrame z danymi treningu
        size_key: Klucz rozmiaru (standard/large/full_hd/macbook_pro)
        add_watermark_flag: Czy dodać watermark
        
    Returns:
        ZIP file jako bytes
    """
    size = CHART_SIZES.get(size_key, CHART_SIZES["large"])
    
    # Utwórz ZIP w pamięci
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # 1. Przebieg treningu (Moc, HR, SmO2, VE)
        fig1 = _build_training_timeline_chart(df_plot)
        if fig1:
            name, bytes_data = export_chart_to_png(
                fig1, "01_przebieg_treningu", size, add_watermark_flag
            )
            zip_file.writestr(name, bytes_data)
        
        # 2. Wentylacja (VE) i Oddechy (BR)
        fig2 = _build_ventilation_chart(df_plot)
        if fig2:
            name, bytes_data = export_chart_to_png(
                fig2, "02_wentylacja_oddechy", size, add_watermark_flag
            )
            zip_file.writestr(name, bytes_data)
        
        # 3. SmO2 vs THb
        fig3 = _build_smo2_thb_chart(df_plot)
        if fig3:
            name, bytes_data = export_chart_to_png(
                fig3, "03_smo2_vs_thb", size, add_watermark_flag
            )
            zip_file.writestr(name, bytes_data)
    
    zip_buffer.seek(0)
    return zip_buffer.getvalue()


def _build_training_timeline_chart(df_plot: pd.DataFrame) -> Optional[go.Figure]:
    """Buduje wykres przebiegu treningu (kopia z summary.py)."""
    from modules.config import Config
    
    fig = go.Figure()
    time_x = (
        df_plot["time_min"]
        if "time_min" in df_plot.columns
        else df_plot["time"] / 60
        if "time" in df_plot.columns
        else None
    )
    
    if time_x is None:
        return None
    
    # Moc
    if "watts_smooth" in df_plot.columns:
        fig.add_trace(go.Scatter(
            x=time_x, y=df_plot["watts_smooth"],
            name="Moc", fill="tozeroy",
            line=dict(color=Config.COLOR_POWER, width=1),
        ))
    elif "watts" in df_plot.columns:
        fig.add_trace(go.Scatter(
            x=time_x, y=df_plot["watts"].rolling(5, center=True).mean(),
            name="Moc", fill="tozeroy",
            line=dict(color=Config.COLOR_POWER, width=1),
        ))
    
    # HR
    if "heartrate_smooth" in df_plot.columns:
        fig.add_trace(go.Scatter(
            x=time_x, y=df_plot["heartrate_smooth"],
            name="HR", line=dict(color=Config.COLOR_HR, width=2),
            yaxis="y2",
        ))
    elif "heartrate" in df_plot.columns:
        fig.add_trace(go.Scatter(
            x=time_x, y=df_plot["heartrate"],
            name="HR", line=dict(color=Config.COLOR_HR, width=2),
            yaxis="y2",
        ))
    
    # SmO2
    if "smo2_smooth" in df_plot.columns:
        fig.add_trace(go.Scatter(
            x=time_x, y=df_plot["smo2_smooth"],
            name="SmO2", line=dict(color=Config.COLOR_SMO2, width=2, dash="dot"),
            yaxis="y3",
        ))
    elif "smo2" in df_plot.columns:
        fig.add_trace(go.Scatter(
            x=time_x, y=df_plot["smo2"].rolling(5, center=True).mean(),
            name="SmO2", line=dict(color=Config.COLOR_SMO2, width=2, dash="dot"),
            yaxis="y3",
        ))
    
    # VE
    if "tymeventilation_smooth" in df_plot.columns:
        fig.add_trace(go.Scatter(
            x=time_x, y=df_plot["tymeventilation_smooth"],
            name="VE", line=dict(color=Config.COLOR_VE, width=2, dash="dash"),
            yaxis="y4",
        ))
    elif "tymeventilation" in df_plot.columns:
        fig.add_trace(go.Scatter(
            x=time_x, y=df_plot["tymeventilation"].rolling(10, center=True).mean(),
            name="VE", line=dict(color=Config.COLOR_VE, width=2, dash="dash"),
            yaxis="y4",
        ))
    
    fig.update_layout(
        template="plotly_dark",
        title="Przebieg Treningu (Moc, HR, SmO2, VE)",
        hovermode="x unified",
        xaxis=dict(title="Czas [min]"),
        yaxis=dict(title="Moc [W]", side="left"),
        yaxis2=dict(title="HR [bpm]", overlaying="y", side="right", showgrid=False),
        yaxis3=dict(title="SmO2 [%]", overlaying="y", side="right", position=0.95, showgrid=False),
        yaxis4=dict(title="VE [L/min]", overlaying="y", side="right", position=0.98, showgrid=False),
        legend=dict(orientation="h", y=-0.15),
        margin=dict(l=60, r=60, t=60, b=60),
    )
    
    return fig


def _build_ventilation_chart(df_plot: pd.DataFrame) -> Optional[go.Figure]:
    """Buduje wykres wentylacji i oddechów."""
    from plotly.subplots import make_subplots
    
    if "tymeventilation" not in df_plot.columns:
        return None
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    time_x = df_plot["time"] if "time" in df_plot.columns else range(len(df_plot))
    
    # VE
    ve_data = df_plot["tymeventilation"].rolling(10, center=True).mean()
    fig.add_trace(
        go.Scatter(
            x=time_x, y=ve_data,
            name="VE (L/min)",
            line=dict(color="#ffa15a", width=2),
        ),
        secondary_y=False,
    )
    
    # BR
    if "tymebreathrate" in df_plot.columns:
        br_data = df_plot["tymebreathrate"].rolling(10, center=True).mean()
        fig.add_trace(
            go.Scatter(
                x=time_x, y=br_data,
                name="BR (oddech/min)",
                line=dict(color="#00cc96", width=2),
            ),
            secondary_y=True,
        )
    
    fig.update_layout(
        template="plotly_dark",
        title="Wentylacja (VE) i Oddechy (BR)",
        legend=dict(orientation="h", y=1.05, x=0),
        hovermode="x unified",
        margin=dict(l=60, r=60, t=80, b=60),
    )
    fig.update_yaxes(title_text="VE (L/min)", secondary_y=False)
    fig.update_yaxes(title_text="BR (/min)", secondary_y=True)
    
    return fig


def _build_smo2_thb_chart(df_plot: pd.DataFrame) -> Optional[go.Figure]:
    """Buduje wykres SmO2 vs THb."""
    from plotly.subplots import make_subplots
    
    if "smo2" not in df_plot.columns:
        return None
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    time_x = df_plot["time"] if "time" in df_plot.columns else range(len(df_plot))
    
    # SmO2
    smo2_smooth = df_plot["smo2"].rolling(5, center=True).mean()
    fig.add_trace(
        go.Scatter(
            x=time_x, y=smo2_smooth,
            name="SmO2 (%)",
            line=dict(color="#2ca02c", width=2),
        ),
        secondary_y=False,
    )
    
    # THb
    if "thb" in df_plot.columns:
        thb_smooth = df_plot["thb"].rolling(5, center=True).mean()
        fig.add_trace(
            go.Scatter(
                x=time_x, y=thb_smooth,
                name="THb (g/dL)",
                line=dict(color="#9467bd", width=2),
            ),
            secondary_y=True,
        )
    
    fig.update_layout(
        template="plotly_dark",
        title="SmO2 vs THb w czasie",
        legend=dict(orientation="h", y=1.05, x=0),
        hovermode="x unified",
        margin=dict(l=60, r=60, t=80, b=60),
    )
    fig.update_yaxes(title_text="SmO2 (%)", secondary_y=False)
    fig.update_yaxes(title_text="THb (g/dL)", secondary_y=True)
    
    return fig
```

**Step 2: Dodaj Pillow do zależności**

Sprawdź czy Pillow jest w pyproject.toml:
```bash
grep -i pillow /Users/wielkikrzychmbp/Documents/Tri_Dashboard/pyproject.toml
```

Jeśli nie ma, dodaj:
```toml
pillow = "^10.0.0"
```

**Step 3: Commit**

```bash
git add modules/reporting/summary_export.py pyproject.toml
git commit -m "feat: add summary charts PNG export service

- Create summary_export.py with watermark support
- Support multiple sizes: standard, large, full_hd, macbook_pro
- Export 3 charts: training timeline, ventilation, smo2 vs thb
- Add TriDashboard watermark at 10% opacity"
```

---

## Task 2: Dodanie UI w sidebar do eksportu

**Files:**
- Modify: `app.py` (dodaj sekcję eksportu w sidebar)

**Step 1: Dodaj import na górze app.py**

```python
from modules.reporting.summary_export import generate_summary_charts_zip, CHART_SIZES
```

**Step 2: Dodaj UI eksportu w sidebar (po sekcji export raportu)**

W `app.py`, w sekcji sidebar (około linii 384), dodaj:

```python
    # PNG Export - Wykresy z Podsumowania
    st.sidebar.markdown("---")
    st.sidebar.header("📊 Export Wykresów (Podsumowanie)")
    
    # Checkboxy z rozmiarami
    st.sidebar.markdown("**Rozmiar wykresów:**")
    size_options = {
        "standard": "Standard (1200x800)",
        "large": "Duży (1600x1200)",
        "full_hd": "Full HD (1920x1080)",
        "macbook_pro": "MacBook Pro M4 (3024x1964)",
    }
    
    selected_size = st.sidebar.radio(
        "Wybierz rozmiar:",
        options=list(size_options.keys()),
        format_func=lambda x: size_options[x],
        key="summary_chart_size"
    )
    
    # Przycisk generowania
    if st.sidebar.button("🖼️ Generuj wykresy PNG", key="generate_summary_charts"):
        with st.sidebar.spinner("Generowanie wykresów..."):
            try:
                zip_bytes = generate_summary_charts_zip(
                    df_plot,
                    size_key=selected_size,
                    add_watermark_flag=True
                )
                
                st.sidebar.download_button(
                    label="⬇️ Pobierz ZIP z wykresami",
                    data=zip_bytes,
                    file_name=f"wykresy_podsumowanie_{uploaded_file.name.split('.')[0]}.zip",
                    mime="application/zip",
                    key="download_summary_charts"
                )
                st.sidebar.success("✅ Wykresy gotowe do pobrania!")
            except Exception as e:
                st.sidebar.error(f"❌ Błąd generowania: {e}")
```

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add PNG export UI for summary charts in sidebar

- Add size selection radio buttons (4 options)
- Add generate and download buttons
- Integrate with summary_export service"
```

---

## Task 3: Testowanie

**Files:**
- Create: `tests/test_summary_export.py`

**Step 1: Utwórz testy**

```python
"""Testy dla modułu eksportu wykresów z Podsumowania."""

import pytest
import pandas as pd
import numpy as np
from io import BytesIO
import zipfile

from modules.reporting.summary_export import (
    add_watermark,
    export_chart_to_png,
    generate_summary_charts_zip,
    CHART_SIZES,
    _build_training_timeline_chart,
    _build_ventilation_chart,
    _build_smo2_thb_chart,
)


def create_sample_df():
    """Tworzy przykładowy DataFrame z danymi treningu."""
    time = np.arange(0, 3600, 1)  # 1 godzina
    watts = np.full_like(time, 200.0) + np.random.normal(0, 10, len(time))
    hr = np.full_like(time, 140.0) + np.random.normal(0, 3, len(time))
    smo2 = np.full_like(time, 65.0) + np.random.normal(0, 2, len(time))
    ve = np.full_like(time, 60.0) + np.random.normal(0, 5, len(time))
    br = np.full_like(time, 35.0) + np.random.normal(0, 2, len(time))
    thb = np.full_like(time, 12.0) + np.random.normal(0, 0.5, len(time))
    
    return pd.DataFrame({
        'time': time,
        'watts': watts,
        'heartrate': hr,
        'smo2': smo2,
        'tymeventilation': ve,
        'tymebreathrate': br,
        'thb': thb,
    })


def test_chart_sizes_defined():
    """Test czy wszystkie rozmiary są zdefiniowane."""
    assert "standard" in CHART_SIZES
    assert "large" in CHART_SIZES
    assert "full_hd" in CHART_SIZES
    assert "macbook_pro" in CHART_SIZES
    
    # Sprawdź czy rozmiary są poprawne
    assert CHART_SIZES["standard"] == (1200, 800)
    assert CHART_SIZES["large"] == (1600, 1200)


def test_build_training_timeline_chart():
    """Test budowania wykresu przebiegu treningu."""
    df = create_sample_df()
    fig = _build_training_timeline_chart(df)
    
    assert fig is not None
    assert len(fig.data) >= 1  # Przynajmniej moc


def test_build_ventilation_chart():
    """Test budowania wykresu wentylacji."""
    df = create_sample_df()
    fig = _build_ventilation_chart(df)
    
    assert fig is not None
    assert len(fig.data) >= 1  # VE


def test_build_smo2_thb_chart():
    """Test budowania wykresu SmO2 vs THb."""
    df = create_sample_df()
    fig = _build_smo2_thb_chart(df)
    
    assert fig is not None
    assert len(fig.data) >= 1  # SmO2


def test_export_chart_to_png():
    """Test eksportu pojedynczego wykresu."""
    import plotly.graph_objects as go
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[1, 2, 3], y=[1, 2, 3]))
    
    filename, img_bytes = export_chart_to_png(
        fig, "test_chart", (800, 600), add_watermark_flag=False
    )
    
    assert filename == "test_chart.png"
    assert len(img_bytes) > 0
    assert img_bytes[:4] == b'\\x89PNG'  # PNG magic bytes


def test_add_watermark():
    """Test dodawania watermarka."""
    # Utwórz prosty obrazek PNG
    from PIL import Image
    img = Image.new('RGBA', (400, 300), color='blue')
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    img_bytes = buffer.getvalue()
    
    # Dodaj watermark
    watermarked = add_watermark(img_bytes, "Test")
    
    assert len(watermarked) > 0
    assert watermarked[:4] == b'\\x89PNG'


def test_generate_summary_charts_zip():
    """Test generowania ZIP z wykresami."""
    df = create_sample_df()
    
    zip_bytes = generate_summary_charts_zip(
        df,
        size_key="standard",
        add_watermark_flag=False
    )
    
    assert len(zip_bytes) > 0
    
    # Sprawdź zawartość ZIP
    with zipfile.ZipFile(BytesIO(zip_bytes), 'r') as zf:
        files = zf.namelist()
        assert len(files) >= 1
        assert any('przebieg' in f for f in files)


def test_generate_summary_charts_zip_with_watermark():
    """Test generowania ZIP z watermarkiem."""
    df = create_sample_df()
    
    zip_bytes = generate_summary_charts_zip(
        df,
        size_key="large",
        add_watermark_flag=True
    )
    
    assert len(zip_bytes) > 0
    
    with zipfile.ZipFile(BytesIO(zip_bytes), 'r') as zf:
        files = zf.namelist()
        assert len(files) >= 1
```

**Step 2: Uruchom testy**

```bash
cd /Users/wielkikrzychmbp/Documents/Tri_Dashboard
python3 -m pytest tests/test_summary_export.py -v
```

**Step 3: Commit**

```bash
git add tests/test_summary_export.py
git commit -m "test: add tests for summary charts export

- Test chart building functions
- Test watermark functionality
- Test ZIP generation
- Test all chart sizes"
```

---

## Task 4: Finalny commit i push

**Step 1: Sprawdź wszystkie zmiany**

```bash
git status
git log --oneline -5
```

**Step 2: Push do GitHub**

```bash
git push origin main
```

---

## Podsumowanie zmian

**Nowe pliki:**
- `modules/reporting/summary_export.py` - Serwis eksportu wykresów
- `tests/test_summary_export.py` - Testy

**Zmodyfikowane pliki:**
- `app.py` - Dodanie UI w sidebar
- `pyproject.toml` - Dodanie Pillow (opcjonalnie)

**Funkcjonalność:**
- 3 wykresy eksportowane do PNG: Przebieg treningu, Wentylacja/BR, SmO2 vs THb
- 4 rozmiary do wyboru: Standard, Large, Full HD, MacBook Pro M4
- Watermark "TriDashboard" na każdym wykresie (10% opacity)
- Wszystkie wykresy w jednym ZIP
- Dostępne w sidebar po wygenerowaniu podsumowania

**Użycie:**
1. Wgraj plik CSV
2. Przejdź do zakładki "Podsumowanie"
3. W sidebar wybierz rozmiar wykresów
4. Kliknij "Generuj wykresy PNG"
5. Pobierz ZIP z wykresami
6. Wybierz odpowiedni wykres i wrzuć na Stravę
