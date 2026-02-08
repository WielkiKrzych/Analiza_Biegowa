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
    
    # Konwertuj do RGBA jeśli potrzeba
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    # Utwórz warstwę przezroczystą dla watermarka
    watermark_layer = Image.new('RGBA', img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(watermark_layer)
    
    # Użyj domyślnej czcionki (brak zewnętrznych zależności)
    try:
        # Próba użycia czcionki systemowej na macOS
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
    except:
        try:
            # Fallback na inne systemowe czcionki
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 48)
        except:
            font = ImageFont.load_default()
    
    # Oblicz pozycję (prawy dolny róg z marginesem)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = img.width - text_width - 40
    y = img.height - text_height - 40
    
    # Narysuj watermark z przezroczystością (10% opacity = 25/255)
    draw.text((x, y), text, fill=(255, 255, 255, 25), font=font)
    
    # Połącz oryginalny obraz z warstwą watermarka
    result = Image.alpha_composite(img, watermark_layer)
    
    # Zapisz do bytes
    output = io.BytesIO()
    result.save(output, format='PNG')
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
