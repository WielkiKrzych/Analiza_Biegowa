"""
Common utilities for figure generation.
Independent of UI or FigureConfig class.
"""
import matplotlib.pyplot as plt
import os
from io import BytesIO
from typing import Optional

DPI = 150

# Static Color Palette (as requested)
COLORS = {
    "power": "#4CAF50",
    "vt1": "#FFA726",
    "vt2": "#EF5350",
    "smo2": "#42A5F5",
    "cp": "#AB47BC",
    "hr": "#EF5350",
    "ve": "#4CAF50",
    "grid": "#EEEEEE",
    "text": "#2C3E50",
    "secondary": "#999999"
}

def get_color(key: str) -> str:
    """Safely get color from palette with default fallback."""
    return COLORS.get(key, "#999999")

def apply_common_style(fig, ax, **kwargs):
    """Apply standard styling to a figure and primary axis."""
    ax.grid(True, linestyle='--', alpha=0.3, color=get_color("grid"))
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    title_size = kwargs.get('title_size', 14)
    font_size = kwargs.get('font_size', 10)
    
    ax.title.set_fontsize(title_size)
    ax.xaxis.label.set_fontsize(font_size)
    ax.yaxis.label.set_fontsize(font_size)

def save_figure(fig, output_path: Optional[str] = None, **kwargs) -> bytes:
    """Save figure to buffer and optionally to file."""
    fmt = kwargs.get('format', 'png')
    dpi = kwargs.get('dpi', 150)
    
    buf = BytesIO()
    fig.savefig(buf, format=fmt, dpi=dpi, bbox_inches='tight')
    plt.close(fig)
    
    data = buf.getvalue()
    
    if output_path:
        path = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(data)
            
    return data

def create_empty_figure(message: str, title: str, output_path: Optional[str] = None, **kwargs):
    """Create a figure with an error/empty message and optionally save it."""
    figsize = kwargs.get('figsize', (10, 6))
    dpi = kwargs.get('dpi', 150)
    
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    ax.text(0.5, 0.5, message, ha='center', va='center', fontsize=12, color='red')
    ax.set_title(title, fontsize=kwargs.get('title_size', 14), fontweight='bold')
    ax.axis('off')
    
    if output_path:
        return save_figure(fig, output_path, **kwargs)
    return fig
