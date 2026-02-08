"""
Social Comparison Module - Anonymization & Community Features.

Enables anonymous comparison with other athletes:
- Data anonymization for privacy
- Percentile calculations
- Community leaderboards
"""
from dataclasses import dataclass
from typing import List
import hashlib
import pandas as pd


@dataclass
class AnonymizedProfile:
    """Anonymized athlete profile for comparison."""
    anonymous_id: str  # Hash of user identifier
    age_bracket: str   # e.g., "30-35"
    weight_bracket: str  # e.g., "70-75"
    gender: str        # "M" or "F"
    
    # Relative metrics only
    ftp_wkg: float     # W/kg
    vo2max_estimate: float
    
    # MMP percentiles (not absolute values)
    mmp_5s_wkg: float
    mmp_1m_wkg: float
    mmp_5m_wkg: float
    mmp_20m_wkg: float


@dataclass
class PercentileRanking:
    """Ranking within a comparison group."""
    metric: str
    value: float
    percentile: float  # 0-100
    category: str      # e.g., "Amateur", "Cat 3", "Elite"
    sample_size: int


class DataAnonymizer:
    """Anonymizes training data for safe sharing."""
    
    AGE_BRACKETS = [(18, 25), (25, 30), (30, 35), (35, 40), (40, 45), 
                    (45, 50), (50, 55), (55, 60), (60, 100)]
    WEIGHT_BRACKETS = [(45, 50), (50, 55), (55, 60), (60, 65), (65, 70),
                       (70, 75), (75, 80), (80, 85), (85, 90), (90, 100)]
    
    def __init__(self, salt: str = "tri_dashboard_2024"):
        self.salt = salt
    
    def create_anonymous_id(self, identifier: str) -> str:
        """Create anonymous, non-reversible ID.
        
        Args:
            identifier: User email or unique ID
            
        Returns:
            Hashed anonymous ID
        """
        salted = f"{self.salt}:{identifier}"
        return hashlib.sha256(salted.encode()).hexdigest()[:16]
    
    def get_bracket(
        self, 
        value: float, 
        brackets: List[tuple]
    ) -> str:
        """Get bracket label for a value."""
        for low, high in brackets:
            if low <= value < high:
                return f"{low}-{high}"
        return "unknown"
    
    def anonymize_session(
        self,
        df: pd.DataFrame,
        metrics: dict,
        age: int,
        weight: float,
        gender: str
    ) -> dict:
        """Anonymize session data for sharing.
        
        Removes:
        - Exact timestamps
        - Absolute power values
        - Location data
        
        Keeps:
        - Relative metrics (W/kg)
        - Zone distributions
        - Performance percentiles
        
        Args:
            df: Session DataFrame
            metrics: Calculated metrics
            age: Athlete age
            weight: Athlete weight in kg
            gender: 'M' or 'F'
            
        Returns:
            Anonymized data dict
        """
        if weight <= 0:
            weight = 70  # Default
        
        # Calculate W/kg values
        avg_watts = metrics.get('avg_watts', 0)
        np_val = metrics.get('np', avg_watts)
        
        # MMP in W/kg
        mmp_data = {}
        if 'watts' in df.columns:
            for window, label in [(5, '5s'), (60, '1m'), (300, '5m'), (1200, '20m')]:
                if len(df) >= window:
                    mmp = df['watts'].rolling(window).mean().max()
                    if not pd.isna(mmp):
                        mmp_data[f'mmp_{label}_wkg'] = mmp / weight
        
        # Zone distribution (no absolute values)
        zone_dist = {}
        if 'Zone' in df.columns:
            zone_counts = df['Zone'].value_counts(normalize=True)
            zone_dist = zone_counts.to_dict()
        
        return {
            'age_bracket': self.get_bracket(age, self.AGE_BRACKETS),
            'weight_bracket': self.get_bracket(weight, self.WEIGHT_BRACKETS),
            'gender': gender,
            'ftp_wkg': np_val / weight,
            'duration_min': len(df) // 60,
            'tss': metrics.get('tss', 0),
            'zone_distribution': zone_dist,
            **mmp_data
        }
    
    def anonymize_profile(
        self,
        user_id: str,
        age: int,
        weight: float,
        gender: str,
        ftp: float,
        mmp_data: dict
    ) -> AnonymizedProfile:
        """Create anonymized profile for community comparison.
        
        Args:
            user_id: User identifier (will be hashed)
            age: Current age
            weight: Weight in kg
            gender: 'M' or 'F'
            ftp: Functional Threshold Power
            mmp_data: Dict with MMP values for various durations
            
        Returns:
            AnonymizedProfile
        """
        return AnonymizedProfile(
            anonymous_id=self.create_anonymous_id(user_id),
            age_bracket=self.get_bracket(age, self.AGE_BRACKETS),
            weight_bracket=self.get_bracket(weight, self.WEIGHT_BRACKETS),
            gender=gender,
            ftp_wkg=ftp / weight if weight > 0 else 0,
            vo2max_estimate=mmp_data.get('vo2max', 0),
            mmp_5s_wkg=mmp_data.get('5s', 0) / weight if weight > 0 else 0,
            mmp_1m_wkg=mmp_data.get('1m', 0) / weight if weight > 0 else 0,
            mmp_5m_wkg=mmp_data.get('5m', 0) / weight if weight > 0 else 0,
            mmp_20m_wkg=mmp_data.get('20m', 0) / weight if weight > 0 else 0,
        )


class ComparisonService:
    """Local comparison service (no cloud required).
    
    Uses embedded percentile data from published studies.
    """
    
    # FTP/kg percentiles by gender (from various sources)
    FTP_PERCENTILES_MALE = {
        # W/kg: percentile
        2.0: 10, 2.5: 25, 3.0: 40, 3.5: 55, 4.0: 70,
        4.5: 82, 5.0: 90, 5.5: 95, 6.0: 98, 6.5: 99
    }
    
    FTP_PERCENTILES_FEMALE = {
        1.5: 10, 2.0: 25, 2.5: 40, 3.0: 55, 3.5: 70,
        4.0: 85, 4.5: 93, 5.0: 97, 5.5: 99
    }
    
    # VO2max percentiles by age and gender
    VO2MAX_PERCENTILES = {
        'M': {
            '20-29': [(25, 10), (35, 25), (42, 50), (48, 75), (55, 90)],
            '30-39': [(23, 10), (32, 25), (39, 50), (45, 75), (52, 90)],
            '40-49': [(20, 10), (28, 25), (35, 50), (42, 75), (48, 90)],
            '50-59': [(18, 10), (25, 25), (32, 50), (38, 75), (44, 90)],
        },
        'F': {
            '20-29': [(20, 10), (28, 25), (35, 50), (42, 75), (48, 90)],
            '30-39': [(18, 10), (26, 25), (32, 50), (38, 75), (44, 90)],
            '40-49': [(16, 10), (24, 25), (30, 50), (35, 75), (40, 90)],
            '50-59': [(14, 10), (22, 25), (28, 50), (32, 75), (37, 90)],
        }
    }
    
    # Cycling categories by FTP/kg (men)
    CYCLING_CATEGORIES = [
        (7.0, "World Tour Pro"),
        (5.8, "Cat 1 / Elite"),
        (5.0, "Cat 2"),
        (4.2, "Cat 3"),
        (3.5, "Cat 4"),
        (3.0, "Cat 5"),
        (2.5, "Recreational"),
        (0.0, "Beginner"),
    ]
    
    def __init__(self):
        self.anonymizer = DataAnonymizer()
    
    def get_ftp_percentile(
        self,
        ftp_wkg: float,
        gender: str = 'M'
    ) -> PercentileRanking:
        """Get FTP/kg percentile ranking.
        
        Args:
            ftp_wkg: FTP in W/kg
            gender: 'M' or 'F'
            
        Returns:
            PercentileRanking
        """
        percentiles = (self.FTP_PERCENTILES_MALE if gender == 'M' 
                      else self.FTP_PERCENTILES_FEMALE)
        
        # Interpolate percentile
        last_pct = 0
        for wkg, pct in sorted(percentiles.items()):
            if ftp_wkg < wkg:
                # Interpolate between last and current
                ratio = ftp_wkg / wkg
                return PercentileRanking(
                    metric="FTP/kg",
                    value=ftp_wkg,
                    percentile=last_pct + (pct - last_pct) * ratio,
                    category=self._get_cycling_category(ftp_wkg),
                    sample_size=10000  # Approximate based on published data
                )
            last_pct = pct
        
        return PercentileRanking(
            metric="FTP/kg",
            value=ftp_wkg,
            percentile=99,
            category=self._get_cycling_category(ftp_wkg),
            sample_size=10000
        )
    
    def _get_cycling_category(self, ftp_wkg: float) -> str:
        """Get cycling racing category based on FTP/kg."""
        for threshold, category in self.CYCLING_CATEGORIES:
            if ftp_wkg >= threshold:
                return category
        return "Beginner"
    
    def get_vo2max_percentile(
        self,
        vo2max: float,
        age: int,
        gender: str = 'M'
    ) -> PercentileRanking:
        """Get VO2max percentile for age and gender.
        
        Args:
            vo2max: VO2max in ml/kg/min
            age: Athlete age
            gender: 'M' or 'F'
            
        Returns:
            PercentileRanking
        """
        # Find age bracket
        age_bracket = '20-29'
        for bracket in ['20-29', '30-39', '40-49', '50-59']:
            low, high = map(int, bracket.split('-'))
            if low <= age <= high:
                age_bracket = bracket
                break
        
        data = self.VO2MAX_PERCENTILES.get(gender, self.VO2MAX_PERCENTILES['M'])
        brackets = data.get(age_bracket, data['30-39'])
        
        # Interpolate
        last_pct = 0
        for vo2_threshold, pct in brackets:
            if vo2max < vo2_threshold:
                return PercentileRanking(
                    metric="VO2max",
                    value=vo2max,
                    percentile=last_pct + (pct - last_pct) * (vo2max / vo2_threshold),
                    category=self._get_fitness_level(pct),
                    sample_size=5000
                )
            last_pct = pct
        
        return PercentileRanking(
            metric="VO2max",
            value=vo2max,
            percentile=95,
            category="Elite",
            sample_size=5000
        )
    
    def _get_fitness_level(self, percentile: float) -> str:
        """Get fitness level description from percentile."""
        if percentile >= 90:
            return "Elite"
        elif percentile >= 75:
            return "Excellent"
        elif percentile >= 50:
            return "Good"
        elif percentile >= 25:
            return "Average"
        else:
            return "Below Average"
    
    def get_summary_rankings(
        self,
        ftp: float,
        weight: float,
        vo2max: float,
        age: int,
        gender: str
    ) -> List[PercentileRanking]:
        """Get all percentile rankings for an athlete.
        
        Args:
            ftp: FTP in watts
            weight: Weight in kg
            vo2max: VO2max estimate
            age: Athlete age
            gender: 'M' or 'F'
            
        Returns:
            List of PercentileRanking objects
        """
        rankings = []
        
        if weight > 0:
            ftp_wkg = ftp / weight
            rankings.append(self.get_ftp_percentile(ftp_wkg, gender))
        
        if vo2max > 0:
            rankings.append(self.get_vo2max_percentile(vo2max, age, gender))
        
        return rankings
