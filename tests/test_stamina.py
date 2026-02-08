"""
Unit tests for Stamina Score and VLamax estimation.
"""
from modules.calculations import (
    calculate_stamina_score,
    estimate_vlamax_from_pdc,
    get_stamina_interpretation,
    get_vlamax_interpretation,
    calculate_aerobic_contribution,
)


class TestStaminaScore:
    """Tests for calculate_stamina_score."""
    
    def test_returns_valid_score(self, rider_params):
        """Should return score in 0-100 range."""
        score = calculate_stamina_score(
            vo2max=rider_params['vo2max'],
            fri=0.85,
            w_prime=rider_params['w_prime'],
            cp=rider_params['cp'],
            weight=rider_params['weight']
        )
        
        assert 0 <= score <= 100
    
    def test_higher_fitness_higher_score(self, rider_params):
        """Better metrics should give higher score."""
        low_score = calculate_stamina_score(
            vo2max=45,
            fri=0.75,
            w_prime=15000,
            cp=220,
            weight=80
        )
        
        high_score = calculate_stamina_score(
            vo2max=70,
            fri=0.95,
            w_prime=25000,
            cp=350,
            weight=70
        )
        
        assert high_score > low_score
    
    def test_zero_weight_safe(self, rider_params):
        """Should handle zero weight."""
        score = calculate_stamina_score(
            vo2max=55,
            fri=0.85,
            w_prime=20000,
            cp=280,
            weight=0
        )
        assert score == 0.0
    
    def test_zero_cp_safe(self, rider_params):
        """Should handle zero CP."""
        score = calculate_stamina_score(
            vo2max=55,
            fri=0.85,
            w_prime=20000,
            cp=0,
            weight=75
        )
        assert score == 0.0


class TestVlamaxEstimation:
    """Tests for estimate_vlamax_from_pdc."""
    
    def test_returns_valid_vlamax(self, rider_params):
        """Should return VLamax in reasonable range."""
        pdc = {30: 500, 300: 320}  # Typical sprinter profile
        
        vlamax = estimate_vlamax_from_pdc(pdc, rider_params['weight'])
        
        assert vlamax is not None
        assert 0.2 <= vlamax <= 1.2
    
    def test_sprinter_higher_vlamax(self, rider_params):
        """Sprinter profile should have higher VLamax."""
        weight = rider_params['weight']
        
        # Sprinter: big drop from 30s to 5min
        sprinter_pdc = {30: 600, 300: 280}
        sprinter_vlamax = estimate_vlamax_from_pdc(sprinter_pdc, weight)
        
        # Diesel: small drop from 30s to 5min
        diesel_pdc = {30: 400, 300: 320}
        diesel_vlamax = estimate_vlamax_from_pdc(diesel_pdc, weight)
        
        assert sprinter_vlamax > diesel_vlamax
    
    def test_missing_durations(self, rider_params):
        """Should return None if required durations missing."""
        pdc = {60: 350}  # Missing both 30s and 5min
        
        vlamax = estimate_vlamax_from_pdc(pdc, rider_params['weight'])
        assert vlamax is None
    
    def test_zero_weight(self, rider_params):
        """Should handle zero weight."""
        pdc = {30: 500, 300: 320}
        vlamax = estimate_vlamax_from_pdc(pdc, 0)
        assert vlamax is None


class TestStaminaInterpretation:
    """Tests for get_stamina_interpretation."""
    
    def test_world_tour_level(self):
        """Score >= 80 should indicate World Tour."""
        result = get_stamina_interpretation(85)
        assert "world tour" in result.lower() or "tour" in result.lower()
    
    def test_amateur_level(self):
        """Score 35-50 should indicate amateur."""
        result = get_stamina_interpretation(42)
        assert "amator" in result.lower()
    
    def test_beginner_level(self):
        """Score < 35 should indicate beginner."""
        result = get_stamina_interpretation(25)
        assert "początkujący" in result.lower() or "rozwojowy" in result.lower()


class TestVlamaxInterpretation:
    """Tests for get_vlamax_interpretation."""
    
    def test_sprinter(self):
        """High VLamax should indicate sprinter."""
        result = get_vlamax_interpretation(1.0)
        assert "sprinter" in result.lower()
    
    def test_climber(self):
        """Low VLamax should indicate climber."""
        result = get_vlamax_interpretation(0.35)
        assert "climber" in result.lower() or "tt" in result.lower()


class TestAerobicContribution:
    """Tests for calculate_aerobic_contribution."""
    
    def test_returns_dict(self, rider_params):
        """Should return dict with duration -> aerobic % mapping."""
        pdc = {5: 600, 60: 400, 300: 320, 1200: 280}
        
        result = calculate_aerobic_contribution(
            pdc, 
            rider_params['vo2max'], 
            rider_params['weight']
        )
        
        assert isinstance(result, dict)
    
    def test_longer_duration_more_aerobic(self, rider_params):
        """Longer durations should have higher aerobic %."""
        pdc = {5: 600, 60: 400, 300: 320, 1200: 280}
        
        result = calculate_aerobic_contribution(
            pdc, 
            rider_params['vo2max'], 
            rider_params['weight']
        )
        
        # Generally, aerobic % increases with duration
        if 5 in result and 1200 in result:
            assert result[1200] > result[5]
    
    def test_empty_pdc(self, rider_params):
        """Should handle empty PDC."""
        result = calculate_aerobic_contribution(
            {}, 
            rider_params['vo2max'], 
            rider_params['weight']
        )
        assert result == {}
    
    def test_zero_vo2max(self, rider_params):
        """Should handle zero VO2max."""
        pdc = {60: 400}
        result = calculate_aerobic_contribution(pdc, 0, rider_params['weight'])
        assert result == {}
