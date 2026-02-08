"""
Tests for Data Validation Rules.
"""
import pytest
import pandas as pd
from services.data_validation import validate_dataframe
from modules.config import Config

class TestValidationRules:

    @pytest.fixture
    def valid_df(self):
        return pd.DataFrame({
            'time': range(100),
            'watts': [200] * 100,
            'heartrate': [140] * 100,
            'cadence': [90] * 100,
            'smo2': [60] * 100
        })

    def test_valid_dataframe(self, valid_df):
        is_valid, msg = validate_dataframe(valid_df)
        assert is_valid
        assert msg == ""

    def test_missing_time_column(self, valid_df):
        df = valid_df.drop(columns=['time'])
        is_valid, msg = validate_dataframe(df)
        assert not is_valid
        assert "Brak wymaganej kolumny" in msg

    def test_missing_data_columns(self):
        df = pd.DataFrame({'time': range(50)})
        is_valid, msg = validate_dataframe(df)
        assert not is_valid
        assert "Brak wymaganych kolumn danych" in msg

    def test_insufficient_length(self, valid_df):
        df = valid_df.head(5)
        is_valid, msg = validate_dataframe(df)
        assert not is_valid
        assert "Za mało danych" in msg

    def test_non_numeric_time(self, valid_df):
        df = valid_df.copy()
        df['time'] = ["string"] * len(df)
        is_valid, msg = validate_dataframe(df)
        assert not is_valid
        assert "Kolumna 'time' musi być liczbowa" in msg

    def test_watts_exceeds_limit(self, valid_df):
        df = valid_df.copy()
        # Set one value extremely high
        df.loc[5, 'watts'] = Config.VALIDATION_MAX_WATTS + 100
        is_valid, msg = validate_dataframe(df)
        assert not is_valid
        assert "Moc maksymalna" in msg
        assert "przekracza limit" in msg

    def test_hr_exceeds_limit(self, valid_df):
        df = valid_df.copy()
        df.loc[5, 'heartrate'] = Config.VALIDATION_MAX_HR + 10
        is_valid, msg = validate_dataframe(df)
        assert not is_valid
        assert "Tętno maksymalne" in msg

    def test_multiple_failures(self, valid_df):
        df = valid_df.copy()
        df.loc[5, 'watts'] = 10000
        df.loc[5, 'heartrate'] = 500
        is_valid, msg = validate_dataframe(df)
        assert not is_valid
        assert "Moc maksymalna" in msg
        assert "Tętno maksymalne" in msg
