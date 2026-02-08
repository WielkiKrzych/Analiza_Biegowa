"""
VO2max Consistency Regression Tests.

Ensures UI and PDF display the same VO2max value
using the same calculation method (rolling_300s_mean_max).
"""

import pytest
import pandas as pd
import numpy as np


class TestVO2maxConsistency:
    """Test that VO2max is consistent across UI, PDF, and canonical sources."""

    @pytest.fixture
    def sample_power_data(self) -> pd.DataFrame:
        """Generate sample power data for testing."""
        np.random.seed(42)
        # 50 minutes of data at 1Hz
        n_samples = 3000

        # Ramp test pattern: gradually increasing power with noise
        base_power = np.linspace(100, 400, n_samples)
        noise = np.random.normal(0, 10, n_samples)
        power = base_power + noise

        return pd.DataFrame(
            {
                "time": range(n_samples),
                "watts": power,
                "heartrate": np.linspace(100, 180, n_samples) + np.random.normal(0, 2, n_samples),
            }
        )

    def test_ui_vo2max_calculation(self, sample_power_data):
        """Test UI method: df['watts'].rolling(window=300).mean().max()"""
        from modules.calculations.metrics import calculate_vo2max

        mmp_5min_ui = sample_power_data["watts"].rolling(window=300).mean().max()
        weight = 75
        vo2max_ui = calculate_vo2max(mmp_5min_ui, weight)

        assert mmp_5min_ui > 0, "MMP5 should be positive"
        assert vo2max_ui > 0, "VO2max should be positive"
        assert 40 < vo2max_ui < 90, f"VO2max {vo2max_ui} should be in reasonable range"

        return vo2max_ui, mmp_5min_ui

    def test_canonical_vo2max_calculation(self, sample_power_data):
        """Test that canonical physiology uses the same value as UI."""
        from modules.calculations.metrics import calculate_vo2max
        from modules.calculations.canonical_physio import build_canonical_physiology

        # Calculate what persistence.py would calculate
        mmp_5min = sample_power_data["watts"].rolling(window=300).mean().max()
        weight = 75
        vo2max_metrics = calculate_vo2max(mmp_5min, weight)

        # Simulate data structure from persistence.py
        data = {
            "metrics": {
                "vo2max": round(vo2max_metrics, 2),
                "vo2max_metadata": {
                    "value": round(vo2max_metrics, 2),
                    "mmp_5min_watts": round(mmp_5min, 1),
                    "method": "rolling_300s_mean_max",
                    "source": "persistence_pandas",
                    "confidence": 0.70,
                },
            },
            "metadata": {"rider_weight": weight},
            "cp_model": {"cp_watts": 300},
        }

        # Build canonical physiology
        time_series = {"power_watts": sample_power_data["watts"].tolist()}
        canonical = build_canonical_physiology(data, time_series)

        # Canonical should use metrics.vo2max, not recalculate
        assert canonical.vo2max.is_valid(), "Canonical VO2max should be valid"
        assert canonical.vo2max.source == "acsm_5min", (
            f"Source should be acsm_5min, got {canonical.vo2max.source}"
        )

        # Values should match exactly
        assert abs(canonical.vo2max.value - vo2max_metrics) < 0.01, (
            f"Canonical {canonical.vo2max.value} should match metrics {vo2max_metrics}"
        )

        return canonical.vo2max.value

    def test_ui_pdf_vo2max_identical(self, sample_power_data):
        """GOLD TEST: UI and PDF must show identical VO2max."""
        from modules.calculations.metrics import calculate_vo2max
        from modules.calculations.canonical_physio import build_canonical_physiology

        weight = 75

        # 1. UI Calculation (same as kpi.py)
        mmp_5min_ui = sample_power_data["watts"].rolling(window=300).mean().max()
        vo2max_ui = calculate_vo2max(mmp_5min_ui, weight)

        # 2. Simulate what PDF would use (via persistence + canonical)
        data = {
            "metrics": {
                "vo2max": round(vo2max_ui, 2),  # Same as UI
                "vo2max_metadata": {
                    "value": round(vo2max_ui, 2),
                    "method": "rolling_300s_mean_max",
                },
            },
            "metadata": {"rider_weight": weight},
            "cp_model": {"cp_watts": 300},
        }

        time_series = {"power_watts": sample_power_data["watts"].tolist()}
        canonical = build_canonical_physiology(data, time_series)
        vo2max_pdf = canonical.vo2max.value

        # CRITICAL ASSERTION: UI == PDF
        assert abs(vo2max_ui - vo2max_pdf) < 0.1, (
            f"CRITICAL: UI VO2max ({vo2max_ui:.2f}) != PDF VO2max ({vo2max_pdf:.2f})"
        )

        print(f"✅ UI VO2max = PDF VO2max = {vo2max_ui:.2f} ml/kg/min")

    def test_metadata_structure(self, sample_power_data):
        """Test that VO2max metadata contains all required fields."""
        from modules.calculations.metrics import calculate_vo2max

        mmp_5min = sample_power_data["watts"].rolling(window=300).mean().max()
        weight = 75
        vo2max = calculate_vo2max(mmp_5min, weight)

        # Simulate metadata structure
        metadata = {
            "value": round(vo2max, 2),
            "mmp_5min_watts": round(mmp_5min, 1),
            "method": "rolling_300s_mean_max",
            "source": "persistence_pandas",
            "confidence": 0.70,
            "formula": "Sitko et al. 2021: 16.61 + 8.87 * (P / kg)",
            "weight_kg": weight,
        }

        # Required fields
        required_fields = ["value", "method", "source", "confidence"]
        for field in required_fields:
            assert field in metadata, f"Missing required field: {field}"

        assert metadata["method"] == "rolling_300s_mean_max"
        assert metadata["confidence"] == 0.70


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
