"""
UI Plugin Base Module.

Provides abstract base class for all UI tab modules.
Enables automatic discovery and registration of UI components.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Callable
import pandas as pd


@dataclass
class TabConfig:
    """Configuration for a UI tab."""
    id: str                         # Unique identifier
    name: str                       # Display name with emoji
    group: str                      # Parent group (Overview, Performance, etc.)
    order: int = 100                # Sort order within group
    requires_data: bool = True      # Needs uploaded data?
    requires_smo2: bool = False     # Needs SmO2 data?
    requires_vent: bool = False     # Needs ventilation data?
    icon: str = "📊"                # Tab icon
    description: str = ""           # Tooltip/description


class UITabPlugin(ABC):
    """Abstract base class for UI tab plugins.
    
    All UI modules should inherit from this class to be
    automatically discovered and registered.
    
    Example:
        class PowerTab(UITabPlugin):
            @property
            def config(self) -> TabConfig:
                return TabConfig(
                    id="power",
                    name="🔋 Power",
                    group="Performance",
                    order=10
                )
            
            def render(self, df, **kwargs):
                st.header("Power Analysis")
                # ... render logic
    """
    
    @property
    @abstractmethod
    def config(self) -> TabConfig:
        """Return tab configuration."""
        pass
    
    @abstractmethod
    def render(self, df: Optional[pd.DataFrame] = None, **kwargs) -> None:
        """Render the tab content.
        
        Args:
            df: Main DataFrame (may be None if requires_data=False)
            **kwargs: Additional context (rider_weight, cp, etc.)
        """
        pass
    
    def is_available(self, df: Optional[pd.DataFrame] = None) -> bool:
        """Check if tab should be shown based on available data.
        
        Override for custom availability logic.
        """
        config = self.config
        
        if config.requires_data and df is None:
            return False
        
        if df is not None:
            if config.requires_smo2 and 'smo2' not in df.columns:
                return False
            if config.requires_vent and 'tymeventilation' not in df.columns:
                return False
        
        return True
    
    def get_lazy_loader(self) -> Callable:
        """Return a lazy-loading wrapper for this tab's render function."""
        def lazy_render(*args, **kwargs):
            return self.render(*args, **kwargs)
        return lazy_render


class UIGroupConfig:
    """Configuration for a tab group."""
    
    def __init__(self, id: str, name: str, icon: str = "📊", order: int = 100):
        self.id = id
        self.name = name
        self.icon = icon
        self.order = order
    
    @property
    def display_name(self) -> str:
        return f"{self.icon} {self.name}"


# Predefined tab groups
TAB_GROUPS = {
    'overview': UIGroupConfig('overview', 'Overview', '📊', 10),
    'performance': UIGroupConfig('performance', 'Performance', '⚡', 20),
    'physiology': UIGroupConfig('physiology', 'Physiology', '❤️', 30),
    'analysis': UIGroupConfig('analysis', 'Analysis', '🔬', 40),
}
