# tests/reporting/test_persistence.py
"""Comprehensive tests for the persistence module.

Tests cover:
- Constants and schema validation
- NumpyEncoder (JSON serialization of numpy types)
- Helper functions (limiter interpretation, source file dedup)
- Save/load roundtrip
- Error handling (missing files, corrupt data)
- PDF index management
"""

import json
import csv
from pathlib import Path

import numpy as np
import pytest

from modules.reporting.persistence_constants import (
    CANONICAL_SCHEMA,
    CANONICAL_VERSION,
    INDEX_COLUMNS,
    METHOD_VERSION,
)
from modules.reporting.persistence_helpers import (
    NumpyEncoder,
    _check_source_file_exists,
    _get_limiter_interpretation,
)
from modules.reporting.persistence_load import load_ramp_test_report


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_report_data():
    """Minimal valid canonical report data."""
    return {
        "$schema": CANONICAL_SCHEMA,
        "version": CANONICAL_VERSION,
        "metadata": {
            "session_id": "test-uuid-1234",
            "test_date": "2026-01-15",
            "method_version": METHOD_VERSION,
            "athlete_id": "athlete-001",
            "notes": "Integration test report",
            "analyzer": "test",
        },
        "thresholds": {
            "vt1": {"midpoint_watts": 150},
            "vt2": {"midpoint_watts": 250},
        },
    }


@pytest.fixture
def saved_report(tmp_path, sample_report_data):
    """Write sample_report_data to a JSON file and return its path."""
    report_file = tmp_path / "report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(sample_report_data, f, ensure_ascii=False, indent=2)
    return report_file


# ---------------------------------------------------------------------------
# Constants & Schema Validation
# ---------------------------------------------------------------------------


class TestPersistenceConstants:
    """Tests for persistence_constants module."""

    def test_canonical_schema_is_string(self):
        assert isinstance(CANONICAL_SCHEMA, str)

    def test_canonical_schema_ends_with_json(self):
        assert CANONICAL_SCHEMA.endswith(".json")

    def test_canonical_version_is_semver(self):
        parts = CANONICAL_VERSION.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_method_version_matches_ramp_method_version(self):
        from modules.calculations.version import RAMP_METHOD_VERSION

        assert METHOD_VERSION == RAMP_METHOD_VERSION

    def test_index_columns_expected_list(self):
        assert isinstance(INDEX_COLUMNS, list)

    def test_index_columns_contain_required_fields(self):
        required = {"session_id", "test_date", "json_path"}
        assert required.issubset(set(INDEX_COLUMNS))


# ---------------------------------------------------------------------------
# NumpyEncoder
# ---------------------------------------------------------------------------


class TestNumpyEncoder:
    """Tests for NumpyEncoder JSON serialization."""

    def test_encode_numpy_int(self):
        data = {"value": np.int64(42)}
        result = json.dumps(data, cls=NumpyEncoder)
        parsed = json.loads(result)
        assert parsed["value"] == 42
        assert isinstance(parsed["value"], int)

    def test_encode_numpy_float(self):
        data = {"value": np.float64(3.14)}
        result = json.dumps(data, cls=NumpyEncoder)
        parsed = json.loads(result)
        assert parsed["value"] == pytest.approx(3.14)

    def test_encode_numpy_bool(self):
        data = {"flag": np.bool_(True)}
        result = json.dumps(data, cls=NumpyEncoder)
        parsed = json.loads(result)
        assert parsed["flag"] is True

    def test_encode_numpy_ndarray(self):
        data = {"arr": np.array([1.0, 2.0, 3.0])}
        result = json.dumps(data, cls=NumpyEncoder)
        parsed = json.loads(result)
        assert parsed["arr"] == [1.0, 2.0, 3.0]

    def test_encode_mixed_types(self):
        data = {
            "int": np.int32(10),
            "float": np.float32(2.5),
            "bool": np.bool_(False),
            "arr": np.array([1, 2, 3]),
            "str": "plain string",
        }
        result = json.dumps(data, cls=NumpyEncoder)
        parsed = json.loads(result)
        assert parsed["int"] == 10
        assert parsed["float"] == pytest.approx(2.5)
        assert parsed["bool"] is False
        assert parsed["arr"] == [1, 2, 3]
        assert parsed["str"] == "plain string"

    def test_encode_falls_through_for_unknown_types(self):
        """Non-numpy unknown types should raise TypeError via default encoder."""
        with pytest.raises(TypeError):
            json.dumps({"obj": object()}, cls=NumpyEncoder)


# ---------------------------------------------------------------------------
# Helper: _get_limiter_interpretation
# ---------------------------------------------------------------------------


class TestGetLimiterInterpretation:
    """Tests for limiter interpretation helper."""

    def test_returns_dict_for_known_limiter(self):
        result = _get_limiter_interpretation("Serce")
        assert isinstance(result, dict)
        assert "title" in result
        assert "description" in result
        assert "suggestions" in result

    def test_pluca_limiter(self):
        result = _get_limiter_interpretation("Płuca")
        assert "Ograniczenie Oddechowe" in result["title"]

    def test_miesnie_limiter(self):
        result = _get_limiter_interpretation("Mięśnie")
        assert "Peryferyjne" in result["title"]

    def test_unknown_limiter_defaults_to_serce(self):
        result = _get_limiter_interpretation("UnknownFactor")
        serce = _get_limiter_interpretation("Serce")
        assert result == serce

    def test_empty_string_defaults_to_serce(self):
        result = _get_limiter_interpretation("")
        serce = _get_limiter_interpretation("Serce")
        assert result == serce


# ---------------------------------------------------------------------------
# Helper: _check_source_file_exists
# ---------------------------------------------------------------------------


class TestCheckSourceFileExists:
    """Tests for source file deduplication helper."""

    def test_returns_false_when_no_index(self, tmp_path):
        assert _check_source_file_exists(str(tmp_path), "test.csv") is False

    def test_returns_false_when_index_empty(self, tmp_path):
        index_file = tmp_path / "index.csv"
        index_file.write_text("session_id,test_date\n", encoding="utf-8")
        assert _check_source_file_exists(str(tmp_path), "test.csv") is False

    def test_returns_false_when_source_not_in_index(self, tmp_path):
        index_file = tmp_path / "index.csv"
        with open(index_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["session_id", "test_date", "source_file"])
            writer.writeheader()
            writer.writerow(
                {"session_id": "abc", "test_date": "2026-01-01", "source_file": "other.csv"}
            )
        assert _check_source_file_exists(str(tmp_path), "test.csv") is False

    def test_returns_true_when_source_in_index(self, tmp_path):
        index_file = tmp_path / "index.csv"
        with open(index_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["session_id", "test_date", "source_file"])
            writer.writeheader()
            writer.writerow(
                {"session_id": "abc", "test_date": "2026-01-01", "source_file": "test.csv"}
            )
        assert _check_source_file_exists(str(tmp_path), "test.csv") is True

    def test_returns_false_on_corrupt_index(self, tmp_path):
        index_file = tmp_path / "index.csv"
        index_file.write_bytes(b"\x00\x01\x02 corrupt binary")
        assert _check_source_file_exists(str(tmp_path), "test.csv") is False


# ---------------------------------------------------------------------------
# Load: load_ramp_test_report
# ---------------------------------------------------------------------------


class TestLoadRampTestReport:
    """Tests for report loading."""

    def test_load_valid_report(self, saved_report, sample_report_data):
        result = load_ramp_test_report(saved_report)
        assert result["metadata"]["session_id"] == "test-uuid-1234"
        assert result["version"] == CANONICAL_VERSION

    def test_load_preserves_all_fields(self, saved_report, sample_report_data):
        result = load_ramp_test_report(saved_report)
        assert set(result.keys()) == set(sample_report_data.keys())

    def test_load_missing_file_raises(self, tmp_path):
        missing = tmp_path / "nonexistent.json"
        with pytest.raises(FileNotFoundError):
            load_ramp_test_report(missing)

    def test_load_corrupt_json_raises(self, tmp_path):
        corrupt = tmp_path / "bad.json"
        corrupt.write_text("{invalid json}", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_ramp_test_report(corrupt)

    def test_load_with_unicode_content(self, tmp_path):
        data = {"metadata": {"notes": "Test polski: ąęćłńóźż"}}
        report_file = tmp_path / "unicode.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        result = load_ramp_test_report(report_file)
        assert "ąęćłńóźż" in result["metadata"]["notes"]


# ---------------------------------------------------------------------------
# Save/Load Roundtrip
# ---------------------------------------------------------------------------


class TestSaveLoadRoundtrip:
    """Tests that save→load preserves data integrity."""

    def test_roundtrip_preserves_metadata(self, tmp_path, sample_report_data):
        report_file = tmp_path / "roundtrip.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(sample_report_data, f, cls=NumpyEncoder, ensure_ascii=False)

        loaded = load_ramp_test_report(report_file)
        assert loaded["metadata"]["session_id"] == sample_report_data["metadata"]["session_id"]
        assert loaded["metadata"]["test_date"] == sample_report_data["metadata"]["test_date"]

    def test_roundtrip_with_numpy_values(self, tmp_path):
        data = {
            "values": np.array([1.5, 2.5, 3.5]),
            "count": np.int64(42),
            "score": np.float64(0.95),
        }
        report_file = tmp_path / "numpy_rt.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(data, f, cls=NumpyEncoder, ensure_ascii=False)

        loaded = load_ramp_test_report(report_file)
        assert loaded["values"] == [1.5, 2.5, 3.5]
        assert loaded["count"] == 42
        assert loaded["score"] == pytest.approx(0.95)


# ---------------------------------------------------------------------------
# Persistence wrapper __all__ exports
# ---------------------------------------------------------------------------


class TestPersistenceWrapper:
    """Tests for the persistence.py re-export wrapper."""

    def test_all_exports_defined(self):
        from modules.reporting.persistence import __all__

        expected = {
            "CANONICAL_SCHEMA",
            "CANONICAL_VERSION",
            "INDEX_COLUMNS",
            "METHOD_VERSION",
            "NumpyEncoder",
            "check_git_tracking",
            "generate_and_save_pdf",
            "generate_ramp_test_pdf",
            "load_ramp_test_report",
            "save_ramp_test_report",
            "update_index_pdf_path",
        }
        assert set(__all__) == expected

    def test_import_from_wrapper_matches_direct_import(self):
        from modules.reporting.persistence import NumpyEncoder as Wrapped
        from modules.reporting.persistence_helpers import NumpyEncoder as Direct

        assert Wrapped is Direct

    def test_load_ramp_test_report_importable_from_wrapper(self):
        from modules.reporting.persistence import load_ramp_test_report

        assert callable(load_ramp_test_report)
