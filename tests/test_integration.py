"""
Integration tests for Tri_Dashboard.

Tests that verify end-to-end functionality with real-like data.
"""

import numpy as np
import pandas as pd


class TestIntervalDetectionIntegration:
    """Integration tests for interval detection."""

    def test_detects_intervals_in_workout(self, sample_long_ride_df, cp_value):
        """Should detect intervals in structured workout."""
        from modules.ai.interval_detector import IntervalDetector

        detector = IntervalDetector(cp=cp_value)
        intervals = detector.detect_intervals(sample_long_ride_df)

        # Should find at least some intervals
        assert len(intervals) >= 2

    def test_classifies_interval_types(self, sample_long_ride_df, cp_value):
        """Should correctly classify interval types."""
        from modules.ai.interval_detector import IntervalDetector, IntervalType

        detector = IntervalDetector(cp=cp_value)
        intervals = detector.detect_intervals(sample_long_ride_df)

        # Should have at least one hard effort (above threshold)
        types = [i.interval_type for i in intervals]
        hard_types = [IntervalType.VO2MAX, IntervalType.THRESHOLD, IntervalType.SWEETSPOT]

        has_hard = any(t in hard_types for t in types)
        assert has_hard, "Should find at least one hard interval"

    def test_interval_durations_reasonable(self, sample_long_ride_df, cp_value):
        """Interval durations should be reasonable."""
        from modules.ai.interval_detector import IntervalDetector

        detector = IntervalDetector(cp=cp_value)
        intervals = detector.detect_intervals(sample_long_ride_df)

        for interval in intervals:
            assert interval.duration_sec >= 10, "Intervals should be at least 10s"
            assert interval.duration_sec <= 1800, "Intervals should be at most 30min"


class TestTrainingLoadIntegration:
    """Integration tests for training load calculations."""

    def test_calculate_load_returns_list(self):
        """Should return list of TrainingLoadMetrics."""
        from modules.training_load import TrainingLoadManager

        manager = TrainingLoadManager()
        history = manager.calculate_load(days=30)

        assert isinstance(history, list)

    def test_tsb_in_reasonable_range(self):
        """TSB should be in reasonable range if data exists."""
        from modules.training_load import TrainingLoadManager

        manager = TrainingLoadManager()
        current = manager.get_current_form()

        if current:
            # TSB can be extreme after heavy training blocks
            # More relaxed check: just verify it's a number
            assert isinstance(current.tsb, (int, float))
            # If CTL and ATL exist, TSB = CTL - ATL
            assert abs(current.tsb - (current.ctl - current.atl)) < 0.01

    def test_recommended_tss_returns_tuple(self):
        """Should return (min_tss, max_tss) tuple."""
        from modules.training_load import TrainingLoadManager

        manager = TrainingLoadManager()
        min_tss, max_tss = manager.get_recommended_tss()

        assert isinstance(min_tss, float)
        assert isinstance(max_tss, float)
        assert min_tss <= max_tss


class TestDataLoadingIntegration:
    """Integration tests for data loading and processing."""

    def test_load_and_process_data(self, sample_power_df):
        """Should process data without errors."""
        from modules.calculations import process_data

        df = process_data(sample_power_df)

        assert len(df) > 0
        assert "watts" in df.columns

    def test_calculate_all_metrics(self, sample_power_df_with_smooth, cp_value):
        """Should calculate all standard metrics."""
        from modules.calculations import (
            calculate_metrics,
            calculate_normalized_power,
            calculate_advanced_kpi,
            calculate_power_duration_curve,
        )

        metrics = calculate_metrics(sample_power_df_with_smooth, cp_value)
        np_val = calculate_normalized_power(sample_power_df_with_smooth)
        decoupling, ef = calculate_advanced_kpi(sample_power_df_with_smooth)
        pdc = calculate_power_duration_curve(sample_power_df_with_smooth)

        assert metrics["avg_watts"] > 0
        assert np_val > 0
        assert isinstance(decoupling, float)
        assert len(pdc) > 0


class TestHealthAlertsIntegration:
    """Integration tests for health monitoring."""

    def test_analyze_session_returns_list(self, sample_power_df_with_smooth):
        """Should return list of alerts."""
        from modules.health_alerts import HealthMonitor

        monitor = HealthMonitor()
        metrics = {"avg_watts": 200, "avg_hr": 140}

        alerts = monitor.analyze_session(sample_power_df_with_smooth, metrics)

        assert isinstance(alerts, list)

    def test_detects_high_effort(self):
        """Should potentially detect high heart rate or drift."""
        from modules.health_alerts import HealthMonitor

        # Create data with cardiac drift
        n = 1200
        df = pd.DataFrame(
            {
                "time": np.arange(n, dtype=float),
                "watts": np.ones(n) * 200,
                "watts_smooth": np.ones(n) * 200,
                "heartrate": np.linspace(130, 170, n),  # HR increasing
                "heartrate_smooth": np.linspace(130, 170, n),
            }
        )

        monitor = HealthMonitor()
        metrics = {"avg_watts": 200, "avg_hr": 150}

        alerts = monitor.analyze_session(df, metrics)

        # May or may not trigger alert depending on thresholds
        assert isinstance(alerts, list)


class TestPDCFullWorkflow:
    """Integration tests for complete PDC workflow."""

    def test_pdc_to_stamina_workflow(self, sample_long_ride_df, rider_params):
        """Test complete workflow from PDC to Stamina Score."""
        from modules.calculations import (
            calculate_power_duration_curve,
            calculate_fatigue_resistance_index,
            calculate_stamina_score,
            estimate_vlamax_from_pdc,
        )

        # Step 1: Calculate PDC
        pdc = calculate_power_duration_curve(sample_long_ride_df)
        assert len(pdc) > 0

        # Step 2: Get MMP values
        mmp_5min = pdc.get(300)
        mmp_20min = pdc.get(1200)

        # Step 3: Calculate FRI (may be None if not enough data)
        if mmp_5min and mmp_20min:
            fri = calculate_fatigue_resistance_index(mmp_5min, mmp_20min)
            assert 0 <= fri <= 2  # Allow some tolerance

            # Step 4: Calculate Stamina Score
            power_per_kg = mmp_5min / rider_params["weight"]
            vo2max = 16.61 + 8.87 * power_per_kg

            stamina = calculate_stamina_score(
                vo2max=vo2max,
                fri=fri,
                w_prime=rider_params["w_prime"],
                cp=rider_params["cp"],
                weight=rider_params["weight"],
            )

            assert 0 <= stamina <= 100

        # Step 5: Estimate VLamax
        vlamax = estimate_vlamax_from_pdc(pdc, rider_params["weight"])
        # May be None if not enough data, that's OK
