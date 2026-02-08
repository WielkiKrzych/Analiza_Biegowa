import pytest
from modules.settings import SettingsManager

def test_default_settings_running():
    """Test that default settings are running-oriented."""
    sm = SettingsManager()
    defaults = sm.default_settings
    
    # Should have runner_ prefix, not rider_
    assert "runner_weight" in defaults
    assert "runner_height" in defaults
    assert "runner_age" in defaults
    
    # Should have running-specific params
    assert "threshold_pace" in defaults  # min/km
    assert "critical_speed" in defaults  # m/s or min/km
    assert "d_prime" in defaults  # meters
    
    # Should NOT have cycling-specific params (removed)
    assert "crank_length" not in defaults
    
    # Default threshold pace should be realistic (4:00-6:00 min/km = 240-360s)
    assert 240 <= defaults["threshold_pace"] <= 360  # seconds per km

def test_load_settings_returns_defaults():
    """Test that load_settings returns default settings."""
    sm = SettingsManager()
    settings = sm.load_settings()
    assert settings["runner_weight"] == sm.default_settings["runner_weight"]

def test_legacy_params_present_for_compatibility():
    """Test that legacy cycling params exist for backward compatibility."""
    sm = SettingsManager()
    defaults = sm.default_settings
    
    # Legacy params should exist during transition
    assert "cp" in defaults
    assert "w_prime" in defaults
