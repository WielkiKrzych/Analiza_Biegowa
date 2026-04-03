# tests/db/test_session_store.py
"""Comprehensive tests for SessionStore CRUD, migration, idempotency, and data preservation.

Uses in-memory SQLite via tmp_path (no production database touched).
"""

import sqlite3
from pathlib import Path
from typing import List

import pytest

from modules.db.session_store import SessionRecord, SessionStore

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Return a temporary database path."""
    return tmp_path / "test_sessions.db"


@pytest.fixture
def store(db_path: Path) -> SessionStore:
    """Return a SessionStore backed by a temporary DB."""
    return SessionStore(db_path=db_path)


@pytest.fixture
def sample_record() -> SessionRecord:
    """Return a sample SessionRecord with realistic values."""
    return SessionRecord(
        date="2026-03-15",
        filename="run_2026-03-15.fit",
        duration_sec=3600,
        tss=85.0,
        np=250.0,
        if_factor=0.85,
        avg_watts=240.0,
        avg_hr=155.0,
        max_hr=175.0,
        work_kj=900.0,
        avg_cadence=170.0,
        mmp_5s=520.0,
        mmp_1m=450.0,
        mmp_5m=350.0,
        mmp_20m=300.0,
        avg_rmssd=45.0,
        alerts_count=2,
        extra_metrics='{"vo2max": 55.0}',
    )


@pytest.fixture
def populated_store(store: SessionStore, sample_record: SessionRecord) -> SessionStore:
    """Return a store with one pre-inserted record."""
    store.add_session(sample_record)
    return store


@pytest.fixture
def multi_record_store(store: SessionStore) -> SessionStore:
    """Return a store with 5 records spanning different dates."""
    records = [
        SessionRecord(date=f"2026-03-{10 + i:02d}", filename=f"run_{i}.fit", tss=float(70 + i * 5))
        for i in range(5)
    ]
    for r in records:
        store.add_session(r)
    return store


# ============================================================
# Initialization & Schema Tests
# ============================================================


class TestSessionStoreInit:
    """Tests for database initialization and schema creation."""

    def test_creates_database_file(self, db_path: Path) -> None:
        """SessionStore should create the database file on disk."""
        assert not db_path.exists()
        SessionStore(db_path=db_path)
        assert db_path.exists()

    def test_creates_sessions_table(self, store: SessionStore) -> None:
        """The sessions table should exist after init."""
        with sqlite3.connect(store.db_path) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'"
            ).fetchall()
            assert len(tables) == 1

    def test_creates_four_indexes(self, store: SessionStore) -> None:
        """Four indexes should be created on the sessions table."""
        with sqlite3.connect(store.db_path) as conn:
            indexes = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_sessions_%'"
            ).fetchall()
            names = {row[0] for row in indexes}
            assert "idx_sessions_date" in names
            assert "idx_sessions_tss" in names
            assert "idx_sessions_np" in names
            assert "idx_sessions_created_at" in names

    def test_idempotent_init(self, store: SessionStore) -> None:
        """Re-initializing should not raise or duplicate tables/indexes."""
        SessionStore(db_path=store.db_path)  # second init
        with sqlite3.connect(store.db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='sessions'"
            ).fetchone()[0]
            assert count == 1
            # Indexes should still be exactly 4
            idx_count = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name LIKE 'idx_sessions_%'"
            ).fetchone()[0]
            assert idx_count == 4

    def test_auto_creates_parent_directory(self, tmp_path: Path) -> None:
        """SessionStore should create parent directories if they don't exist."""
        nested = tmp_path / "a" / "b" / "c" / "test.db"
        assert not nested.parent.exists()
        SessionStore(db_path=nested)
        assert nested.exists()

    def test_unique_constraint_on_date_filename(self, store: SessionStore) -> None:
        """The UNIQUE(date, filename) constraint should be enforced."""
        first_id = store.add_session(SessionRecord(date="2026-01-01", filename="a.fit"))
        assert first_id > 0
        # UPSERT on conflict: lastrowid returns 0 for UPDATE (no new row inserted)
        store.add_session(SessionRecord(date="2026-01-01", filename="a.fit", tss=99.0))
        assert store.get_session_count() == 1


# ============================================================
# add_session Tests
# ============================================================


class TestAddSession:
    """Tests for the add_session (INSERT/UPSERT) operation."""

    def test_insert_returns_positive_id(
        self, store: SessionStore, sample_record: SessionRecord
    ) -> None:
        """add_session should return a positive integer ID."""
        session_id = store.add_session(sample_record)
        assert isinstance(session_id, int)
        assert session_id > 0

    def test_insert_stores_all_fields(
        self, store: SessionStore, sample_record: SessionRecord
    ) -> None:
        """All fields of SessionRecord should be persisted correctly."""
        sid = store.add_session(sample_record)
        with sqlite3.connect(store.db_path) as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
        assert row is not None
        assert row[1] == sample_record.date
        assert row[2] == sample_record.filename
        assert row[3] == sample_record.duration_sec
        assert row[4] == pytest.approx(sample_record.tss)
        assert row[5] == pytest.approx(sample_record.np)
        assert row[6] == pytest.approx(sample_record.if_factor)
        assert row[7] == pytest.approx(sample_record.avg_watts)
        assert row[8] == pytest.approx(sample_record.avg_hr)
        assert row[9] == pytest.approx(sample_record.max_hr)
        assert row[10] == pytest.approx(sample_record.work_kj)
        assert row[11] == pytest.approx(sample_record.avg_cadence)
        assert row[12] == pytest.approx(sample_record.mmp_5s)
        assert row[13] == pytest.approx(sample_record.mmp_1m)
        assert row[14] == pytest.approx(sample_record.mmp_5m)
        assert row[15] == pytest.approx(sample_record.mmp_20m)
        assert row[16] == pytest.approx(sample_record.avg_rmssd)
        assert row[17] == sample_record.alerts_count
        assert row[18] == sample_record.extra_metrics

    def test_upsert_updates_existing_record(
        self, store: SessionStore, sample_record: SessionRecord
    ) -> None:
        """Inserting the same (date, filename) should update, not duplicate."""
        store.add_session(sample_record)
        sample_record.tss = 99.0
        store.add_session(sample_record)
        assert store.get_session_count() == 1

    def test_upsert_preserves_id(self, store: SessionStore, sample_record: SessionRecord) -> None:
        """UPSERT should not create a duplicate row."""
        store.add_session(sample_record)
        sample_record.tss = 99.0
        store.add_session(sample_record)
        assert store.get_session_count() == 1
        sessions = store.get_sessions(days=365)
        assert sessions[0].tss == pytest.approx(99.0)

    def test_returns_negative_on_db_error(self, store: SessionStore) -> None:
        """If the DB somehow fails, add_session returns -1."""
        record = SessionRecord()
        with sqlite3.connect(store.db_path) as conn:
            conn.execute("DROP TABLE sessions")
            conn.commit()
        result = store.add_session(record)
        assert result == -1

    def test_default_values_on_minimal_record(self, store: SessionStore) -> None:
        """SessionRecord defaults should be used for missing columns."""
        record = SessionRecord(date="2026-04-01", filename="minimal.fit")
        sid = store.add_session(record)
        assert sid > 0
        with sqlite3.connect(store.db_path) as conn:
            row = conn.execute(
                "SELECT tss, np, if_factor, avg_watts, avg_hr, max_hr, work_kj, "
                "avg_cadence, mmp_5s, mmp_1m, mmp_5m, mmp_20m, avg_rmssd, "
                "alerts_count, extra_metrics FROM sessions WHERE id = ?",
                (sid,),
            ).fetchone()
            assert row[0] == 0.0  # tss
            assert row[1] == 0.0  # np
            assert row[2] == 0.0  # if_factor
            assert row[3] == 0.0  # avg_watts
            assert row[4] == 0.0  # avg_hr
            assert row[5] == 0.0  # max_hr
            assert row[6] == 0.0  # work_kj
            assert row[7] == 0.0  # avg_cadence
            assert row[8] is None  # mmp_5s
            assert row[9] is None  # mmp_1m
            assert row[10] is None  # mmp_5m
            assert row[11] is None  # mmp_20m
            assert row[12] is None  # avg_rmssd
            assert row[13] == 0  # alerts_count
            assert row[14] == "{}"  # extra_metrics

    def test_multiple_sequential_inserts(self, store: SessionStore) -> None:
        """Multiple inserts should return incrementing IDs."""
        ids: List[int] = []
        for i in range(5):
            sid = store.add_session(
                SessionRecord(date=f"2026-01-{i + 1:02d}", filename=f"run_{i}.fit")
            )
            ids.append(sid)
        assert ids == sorted(ids)
        assert len(set(ids)) == 5  # all unique


# ============================================================
# get_sessions Tests
# ============================================================


class TestGetSessions:
    """Tests for the get_sessions query operation."""

    def test_empty_db(self, store: SessionStore) -> None:
        """Empty database should return an empty list."""
        assert store.get_sessions() == []

    def test_returns_session_records(self, populated_store: SessionStore) -> None:
        """get_sessions should return a list of SessionRecord objects."""
        sessions = populated_store.get_sessions(days=365)
        assert len(sessions) == 1
        assert isinstance(sessions[0], SessionRecord)
        assert sessions[0].date == "2026-03-15"

    def test_date_filtering(self, store: SessionStore) -> None:
        """get_sessions should filter by date range."""
        store.add_session(SessionRecord(date="2020-01-01", filename="old.fit"))
        store.add_session(SessionRecord(date="2030-01-01", filename="future.fit"))
        sessions = store.get_sessions(days=1)
        # With days=1, only very recent sessions should appear
        assert len(sessions) <= 2

    def test_ordered_by_date_desc(self, store: SessionStore) -> None:
        """Results should be ordered by date descending."""
        store.add_session(SessionRecord(date="2026-03-10", filename="a.fit"))
        store.add_session(SessionRecord(date="2026-03-15", filename="b.fit"))
        store.add_session(SessionRecord(date="2026-03-12", filename="c.fit"))
        sessions = store.get_sessions(days=365)
        dates = [s.date for s in sessions]
        assert dates == sorted(dates, reverse=True)

    def test_returns_all_fields(self, populated_store: SessionStore) -> None:
        """All SessionRecord fields should be populated from DB."""
        sessions = populated_store.get_sessions(days=365)
        s = sessions[0]
        assert s.id is not None
        assert s.date == "2026-03-15"
        assert s.filename == "run_2026-03-15.fit"
        assert s.duration_sec == 3600
        assert s.tss == pytest.approx(85.0)
        assert s.np == pytest.approx(250.0)
        assert s.if_factor == pytest.approx(0.85)
        assert s.avg_watts == pytest.approx(240.0)
        assert s.avg_hr == pytest.approx(155.0)
        assert s.max_hr == pytest.approx(175.0)
        assert s.work_kj == pytest.approx(900.0)
        assert s.avg_cadence == pytest.approx(170.0)
        assert s.mmp_5s == pytest.approx(520.0)
        assert s.mmp_1m == pytest.approx(450.0)
        assert s.mmp_5m == pytest.approx(350.0)
        assert s.mmp_20m == pytest.approx(300.0)
        assert s.avg_rmssd == pytest.approx(45.0)
        assert s.alerts_count == 2
        assert s.extra_metrics == '{"vo2max": 55.0}'

    def test_returns_empty_on_error(self, store: SessionStore) -> None:
        """get_sessions should return [] on DB error."""
        with sqlite3.connect(store.db_path) as conn:
            conn.execute("DROP TABLE sessions")
            conn.commit()
        assert store.get_sessions() == []


# ============================================================
# get_session_count Tests
# ============================================================


class TestGetSessionCount:
    """Tests for the get_session_count operation."""

    def test_empty_db(self, store: SessionStore) -> None:
        """Empty database should return 0."""
        assert store.get_session_count() == 0

    def test_count_increments(self, store: SessionStore) -> None:
        """Count should increment with each insert."""
        store.add_session(SessionRecord(date="2026-01-01", filename="a.fit"))
        assert store.get_session_count() == 1
        store.add_session(SessionRecord(date="2026-01-02", filename="b.fit"))
        assert store.get_session_count() == 2

    def test_count_after_upsert(self, store: SessionStore) -> None:
        """Count should not increase on duplicate upsert."""
        store.add_session(SessionRecord(date="2026-01-01", filename="a.fit"))
        store.add_session(SessionRecord(date="2026-01-01", filename="a.fit", tss=99.0))
        assert store.get_session_count() == 1

    def test_count_after_delete(self, populated_store: SessionStore) -> None:
        """Count should decrease after delete."""
        sessions = populated_store.get_sessions(days=365)
        populated_store.delete_session(sessions[0].id)
        assert populated_store.get_session_count() == 0

    def test_count_returns_zero_on_error(self, store: SessionStore) -> None:
        """get_session_count should return 0 on DB error."""
        with sqlite3.connect(store.db_path) as conn:
            conn.execute("DROP TABLE sessions")
            conn.commit()
        assert store.get_session_count() == 0


# ============================================================
# delete_session Tests
# ============================================================


class TestDeleteSession:
    """Tests for the delete_session operation."""

    def test_delete_existing(self, populated_store: SessionStore) -> None:
        """Deleting an existing session should return True and reduce count."""
        sessions = populated_store.get_sessions(days=365)
        sid = sessions[0].id
        assert populated_store.delete_session(sid) is True
        assert populated_store.get_session_count() == 0

    def test_delete_nonexistent(self, store: SessionStore) -> None:
        """Deleting a non-existent ID should return False."""
        assert store.delete_session(9999) is False

    def test_delete_negative_id(self, store: SessionStore) -> None:
        """Deleting with a negative ID should return False."""
        assert store.delete_session(-1) is False

    def test_delete_zero_id(self, store: SessionStore) -> None:
        """Deleting with ID 0 should return False."""
        assert store.delete_session(0) is False

    def test_delete_returns_false_on_error(self, store: SessionStore) -> None:
        """delete_session should return False on DB error."""
        with sqlite3.connect(store.db_path) as conn:
            conn.execute("DROP TABLE sessions")
            conn.commit()
        assert store.delete_session(1) is False


# ============================================================
# get_all_tss Tests
# ============================================================


class TestGetAllTss:
    """Tests for the get_all_tss aggregation query."""

    def test_empty_db(self, store: SessionStore) -> None:
        """Empty database should return empty list."""
        assert store.get_all_tss() == []

    def test_returns_date_tss_tuples(self, store: SessionStore) -> None:
        """Should return (date, tss) tuples with daily aggregation."""
        store.add_session(SessionRecord(date="2026-03-15", filename="a.fit", tss=80.0))
        store.add_session(SessionRecord(date="2026-03-15", filename="b.fit", tss=20.0))
        result = store.get_all_tss(days=365)
        assert len(result) == 1  # same date grouped
        assert result[0][1] == pytest.approx(100.0)

    def test_multiple_dates(self, store: SessionStore) -> None:
        """Should return separate entries for different dates."""
        store.add_session(SessionRecord(date="2026-03-14", filename="a.fit", tss=50.0))
        store.add_session(SessionRecord(date="2026-03-15", filename="b.fit", tss=80.0))
        result = store.get_all_tss(days=365)
        assert len(result) == 2

    def test_ordered_by_date_asc(self, store: SessionStore) -> None:
        """Results should be ordered by date ascending."""
        store.add_session(SessionRecord(date="2026-03-15", filename="b.fit", tss=80.0))
        store.add_session(SessionRecord(date="2026-03-14", filename="a.fit", tss=50.0))
        result = store.get_all_tss(days=365)
        dates = [r[0] for r in result]
        assert dates == sorted(dates)

    def test_returns_empty_on_error(self, store: SessionStore) -> None:
        """get_all_tss should return [] on DB error."""
        with sqlite3.connect(store.db_path) as conn:
            conn.execute("DROP TABLE sessions")
            conn.commit()
        assert store.get_all_tss() == []


# ============================================================
# Schema Migration Tests
# ============================================================


class TestSchemaMigration:
    """Tests for backward compatibility with legacy database schemas."""

    def test_works_with_legacy_table(self, tmp_path: Path) -> None:
        """SessionStore should work with a legacy table missing MMP/HRV columns."""
        db_path = tmp_path / "legacy.db"
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    duration_sec INTEGER DEFAULT 0,
                    tss REAL DEFAULT 0,
                    np REAL DEFAULT 0,
                    if_factor REAL DEFAULT 0,
                    avg_watts REAL DEFAULT 0,
                    avg_hr REAL DEFAULT 0,
                    max_hr REAL DEFAULT 0,
                    work_kj REAL DEFAULT 0,
                    avg_cadence REAL DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(date, filename)
                )
                """
            )
            conn.commit()

        store = SessionStore(db_path=db_path)
        # Existing data from legacy table should still be accessible
        count = store.get_session_count()
        assert count == 0  # no data inserted yet, but no error either

    def test_preserves_legacy_data(self, tmp_path: Path) -> None:
        """Data in a legacy table should remain after SessionStore init."""
        db_path = tmp_path / "legacy_data.db"
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    duration_sec INTEGER DEFAULT 0,
                    tss REAL DEFAULT 0,
                    np REAL DEFAULT 0,
                    if_factor REAL DEFAULT 0,
                    avg_watts REAL DEFAULT 0,
                    avg_hr REAL DEFAULT 0,
                    max_hr REAL DEFAULT 0,
                    work_kj REAL DEFAULT 0,
                    avg_cadence REAL DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(date, filename)
                )
                """
            )
            conn.execute(
                "INSERT INTO sessions (date, filename, duration_sec, tss) VALUES (?, ?, ?, ?)",
                ("2026-01-01", "legacy.fit", 1800, 50.0),
            )
            conn.commit()

        store = SessionStore(db_path=db_path)
        # get_session_count works even with legacy schema (no missing columns)
        count = store.get_session_count()
        assert count == 1


# ============================================================
# Data Preservation Tests
# ============================================================


class TestDataPreservation:
    """Tests for data integrity across operations."""

    def test_extra_metrics_json_preserved(
        self, store: SessionStore, sample_record: SessionRecord
    ) -> None:
        """Extra metrics JSON string should be stored and retrieved exactly."""
        store.add_session(sample_record)
        sessions = store.get_sessions(days=365)
        assert sessions[0].extra_metrics == '{"vo2max": 55.0}'

    def test_null_mmp_fields_preserved(self, store: SessionStore) -> None:
        """None MMP values should be stored as NULL."""
        record = SessionRecord(
            date="2026-01-01",
            filename="no_mmp.fit",
            mmp_5s=None,
            mmp_1m=None,
            mmp_5m=None,
            mmp_20m=None,
        )
        store.add_session(record)
        sessions = store.get_sessions(days=365)
        assert sessions[0].mmp_5s is None
        assert sessions[0].mmp_1m is None

    def test_float_precision_preserved(self, store: SessionStore) -> None:
        """Float values should maintain reasonable precision."""
        record = SessionRecord(
            date="2026-01-01",
            filename="precision.fit",
            tss=85.123456,
            np=250.987654,
            if_factor=0.854321,
        )
        store.add_session(record)
        sessions = store.get_sessions(days=365)
        assert sessions[0].tss == pytest.approx(85.123456, abs=1e-4)
        assert sessions[0].np == pytest.approx(250.987654, abs=1e-4)

    def test_upsert_preserves_correct_values(
        self, store: SessionStore, sample_record: SessionRecord
    ) -> None:
        """After upsert, all fields should reflect the latest values."""
        store.add_session(sample_record)
        sample_record.tss = 120.0
        sample_record.avg_hr = 170.0
        store.add_session(sample_record)
        sessions = store.get_sessions(days=365)
        assert sessions[0].tss == pytest.approx(120.0)
        assert sessions[0].avg_hr == pytest.approx(170.0)

    def test_multiple_records_different_dates(self, store: SessionStore) -> None:
        """Multiple records with different dates should all be stored."""
        for i in range(5):
            store.add_session(
                SessionRecord(
                    date=f"2026-03-{10 + i:02d}",
                    filename=f"run_{i}.fit",
                    tss=float(70 + i * 5),
                )
            )
        assert store.get_session_count() == 5
        sessions = store.get_sessions(days=365)
        tss_values = [s.tss for s in sessions]
        assert set(tss_values) == {70.0, 75.0, 80.0, 85.0, 90.0}

    def test_created_at_auto_populated(self, store: SessionStore) -> None:
        """created_at should be automatically populated."""
        store.add_session(SessionRecord(date="2026-01-01", filename="a.fit"))
        with sqlite3.connect(store.db_path) as conn:
            row = conn.execute("SELECT created_at FROM sessions WHERE id = 1").fetchone()
            assert row[0] is not None
            assert len(row[0]) > 0


# ============================================================
# SessionRecord Dataclass Tests
# ============================================================


class TestSessionRecord:
    """Tests for the SessionRecord dataclass."""

    def test_default_values(self) -> None:
        """SessionRecord should have sensible defaults."""
        record = SessionRecord()
        assert record.id is None
        assert record.date == ""
        assert record.filename == ""
        assert record.duration_sec == 0
        assert record.tss == 0.0
        assert record.np == 0.0
        assert record.if_factor == 0.0
        assert record.avg_watts == 0.0
        assert record.avg_hr == 0.0
        assert record.max_hr == 0.0
        assert record.work_kj == 0.0
        assert record.avg_cadence == 0.0
        assert record.mmp_5s is None
        assert record.mmp_1m is None
        assert record.mmp_5m is None
        assert record.mmp_20m is None
        assert record.avg_rmssd is None
        assert record.alerts_count == 0
        assert record.extra_metrics == "{}"

    def test_custom_values(self) -> None:
        """SessionRecord should accept custom values."""
        record = SessionRecord(
            date="2026-01-01",
            filename="test.fit",
            tss=100.0,
            mmp_5s=600.0,
        )
        assert record.date == "2026-01-01"
        assert record.filename == "test.fit"
        assert record.tss == 100.0
        assert record.mmp_5s == 600.0


# ============================================================
# Edge Cases
# ============================================================


class TestEdgeCases:
    """Edge case tests for SessionStore."""

    def test_empty_string_date(self, store: SessionStore) -> None:
        """Empty string date should still insert."""
        record = SessionRecord(date="", filename="empty_date.fit")
        sid = store.add_session(record)
        assert sid > 0

    def test_special_characters_in_filename(self, store: SessionStore) -> None:
        """Filenames with special characters should be stored correctly."""
        record = SessionRecord(
            date="2026-01-01",
            filename="run (2026-01-01) [test].fit",
        )
        store.add_session(record)
        sessions = store.get_sessions(days=365)
        assert sessions[0].filename == "run (2026-01-01) [test].fit"

    def test_large_tss_value(self, store: SessionStore) -> None:
        """Large TSS values should be stored without overflow."""
        record = SessionRecord(date="2026-01-01", filename="big.fit", tss=9999.99)
        store.add_session(record)
        sessions = store.get_sessions(days=365)
        assert sessions[0].tss == pytest.approx(9999.99)

    def test_negative_duration(self, store: SessionStore) -> None:
        """Negative duration should be stored as-is (data issue, not DB issue)."""
        record = SessionRecord(date="2026-01-01", filename="neg.fit", duration_sec=-1)
        store.add_session(record)
        sessions = store.get_sessions(days=365)
        assert sessions[0].duration_sec == -1

    def test_delete_all_records(self, multi_record_store: SessionStore) -> None:
        """Deleting all records should leave the table empty."""
        sessions = multi_record_store.get_sessions(days=365)
        for s in sessions:
            multi_record_store.delete_session(s.id)
        assert multi_record_store.get_session_count() == 0
        assert multi_record_store.get_sessions(days=365) == []
