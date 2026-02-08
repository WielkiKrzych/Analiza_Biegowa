"""
UI Plugin Registry.

Automatically discovers and registers UI tab plugins.
Provides centralized access to all available tabs.
"""
import importlib
import logging
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd

from .base import UITabPlugin

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Central registry for UI tab plugins.
    
    Handles discovery, registration, and retrieval of UI modules.
    
    Usage:
        registry = PluginRegistry()
        registry.discover()  # Auto-find all plugins
        
        for group, tabs in registry.get_grouped_tabs():
            # Create tab group
            for tab in tabs:
                tab.render(df, **context)
    """
    
    _instance: Optional['PluginRegistry'] = None
    
    def __new__(cls):
        """Singleton pattern for global registry access."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._plugins: Dict[str, UITabPlugin] = {}
            cls._instance._initialized = False
        return cls._instance
    
    @property
    def plugins(self) -> Dict[str, UITabPlugin]:
        return self._plugins
    
    def register(self, plugin: UITabPlugin) -> None:
        """Register a plugin instance.
        
        Args:
            plugin: Instance of UITabPlugin subclass
        """
        config = plugin.config
        if config.id in self._plugins:
            logger.warning(f"Plugin '{config.id}' already registered, overwriting")
        self._plugins[config.id] = plugin
        logger.debug(f"Registered plugin: {config.id} ({config.name})")
    
    def unregister(self, plugin_id: str) -> None:
        """Remove a plugin from registry."""
        if plugin_id in self._plugins:
            del self._plugins[plugin_id]
    
    def get(self, plugin_id: str) -> Optional[UITabPlugin]:
        """Get plugin by ID."""
        return self._plugins.get(plugin_id)
    
    def get_available_tabs(
        self, 
        df: Optional[pd.DataFrame] = None
    ) -> List[UITabPlugin]:
        """Get list of tabs available for current data.
        
        Args:
            df: Current DataFrame to check requirements against
            
        Returns:
            List of available UITabPlugin instances, sorted by order
        """
        available = [
            plugin for plugin in self._plugins.values()
            if plugin.is_available(df)
        ]
        return sorted(available, key=lambda p: p.config.order)
    
    def get_grouped_tabs(
        self, 
        df: Optional[pd.DataFrame] = None
    ) -> Dict[str, List[UITabPlugin]]:
        """Get tabs grouped by their group configuration.
        
        Args:
            df: Current DataFrame
            
        Returns:
            Dict mapping group_id to list of plugins
        """
        available = self.get_available_tabs(df)
        
        groups: Dict[str, List[UITabPlugin]] = {}
        for plugin in available:
            group_id = plugin.config.group.lower()
            if group_id not in groups:
                groups[group_id] = []
            groups[group_id].append(plugin)
        
        # Sort each group's tabs by order
        for group_id in groups:
            groups[group_id].sort(key=lambda p: p.config.order)
        
        return groups
    
    def discover(self, package_path: str = "modules.ui") -> int:
        """Auto-discover plugins in a package.
        
        Scans the package for UITabPlugin subclasses and registers them.
        
        Args:
            package_path: Dotted path to package (e.g., "modules.ui")
            
        Returns:
            Number of plugins discovered
        """
        if self._initialized:
            return len(self._plugins)
        
        count = 0
        try:
            # Get the ui module directory
            import modules.ui as ui_module
            ui_path = Path(ui_module.__file__).parent
            
            # Scan for Python files
            for py_file in ui_path.glob("*.py"):
                if py_file.name.startswith("_"):
                    continue
                if py_file.name in ("base.py", "registry.py"):
                    continue
                
                module_name = py_file.stem
                try:
                    module = importlib.import_module(f"{package_path}.{module_name}")
                    
                    # Look for UITabPlugin subclasses
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and 
                            issubclass(attr, UITabPlugin) and 
                            attr is not UITabPlugin):
                            try:
                                plugin_instance = attr()
                                self.register(plugin_instance)
                                count += 1
                            except Exception as e:
                                logger.debug(f"Could not instantiate {attr_name}: {e}")
                                
                except Exception as e:
                    logger.debug(f"Could not import {module_name}: {e}")
                    
        except Exception as e:
            logger.warning(f"Plugin discovery failed: {e}")
        
        self._initialized = True
        logger.info(f"Discovered {count} UI plugins")
        return count
    
    def clear(self) -> None:
        """Clear all registered plugins."""
        self._plugins.clear()
        self._initialized = False


# Global registry instance
_registry = PluginRegistry()


def get_registry() -> PluginRegistry:
    """Get the global plugin registry."""
    return _registry


def register_plugin(plugin: UITabPlugin) -> None:
    """Register a plugin with the global registry."""
    _registry.register(plugin)


def discover_plugins() -> int:
    """Run plugin discovery."""
    return _registry.discover()
