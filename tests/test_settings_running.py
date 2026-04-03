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
    assert "threshold_power" in defaults  # Watts
    assert "lthr" in defaults  # Lactate Threshold HR
    assert "max_hr" in defaults  # Maximum HR

    # Should NOT have old params (removed)
    assert "d_prime" not in defaults
    assert "cp" not in defaults
    assert "w_prime" not in defaults

    # Default threshold pace should be realistic (3:30-6:00 min/km = 210-360s)
    assert 210 <= defaults["threshold_pace"] <= 360  # seconds per km


def test_load_settings_returns_defaults():
    """Test that load_settings returns default settings."""
    sm = SettingsManager()
    settings = sm.load_settings()
    assert settings["runner_weight"] == sm.default_settings["runner_weight"]


def test_new_running_params():
    """Test that new running params are present."""
    sm = SettingsManager()
    defaults = sm.default_settings

    # New running params should exist
    assert "threshold_power" in defaults
    assert "lthr" in defaults
    assert "max_hr" in defaults
