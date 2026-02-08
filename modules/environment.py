"""
Environmental Factors Module.

Fetches weather data and calculates TSS corrections based on:
- Temperature
- Humidity
- Altitude
- Wind
"""
from dataclasses import dataclass
from typing import Optional, Tuple
from datetime import datetime
import os


@dataclass
class WeatherData:
    """Weather conditions for a training session."""
    temperature: float  # °C
    humidity: float     # %
    wind_speed: float   # km/h
    feels_like: float   # °C
    description: str
    location: str
    timestamp: datetime
    altitude: float = 0  # meters (manual or GPS)
    
    @property
    def is_hot(self) -> bool:
        return self.temperature > 30 or self.feels_like > 32
    
    @property
    def is_humid(self) -> bool:
        return self.humidity > 80
    
    @property
    def is_windy(self) -> bool:
        return self.wind_speed > 20
    
    @property
    def is_high_altitude(self) -> bool:
        return self.altitude > 1500


class EnvironmentService:
    """Fetches weather data and calculates environmental corrections."""
    
    # TSS correction factors
    TEMP_CORRECTION = {
        # (min_temp, max_temp): correction_factor
        (35, 50): 0.15,   # Very hot: +15%
        (30, 35): 0.10,   # Hot: +10%
        (25, 30): 0.05,   # Warm: +5%
        (-5, 5): 0.05,    # Cold: +5%
        (-20, -5): 0.10,  # Very cold: +10%
    }
    
    HUMIDITY_CORRECTION = {
        (90, 100): 0.08,  # Extreme humidity: +8%
        (80, 90): 0.05,   # High humidity: +5%
    }
    
    ALTITUDE_CORRECTION = {
        (3000, 5000): 0.20,  # Very high: +20%
        (2500, 3000): 0.15,  # High: +15%
        (2000, 2500): 0.10,  # Moderate high: +10%
        (1500, 2000): 0.05,  # Mild high: +5%
    }
    
    WIND_CORRECTION = {
        (30, 100): 0.10,  # Strong wind: +10%
        (20, 30): 0.05,   # Moderate wind: +5%
    }
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: OpenWeatherMap API key
        """
        self.api_key = api_key or os.environ.get('OPENWEATHER_API_KEY')
    
    def get_conditions(
        self,
        date: datetime,
        lat: float,
        lon: float
    ) -> Optional[WeatherData]:
        """Fetch weather conditions for location and date.
        
        Args:
            date: Date of training
            lat: Latitude
            lon: Longitude
            
        Returns:
            WeatherData or None if unavailable
        """
        if not self.api_key:
            return self._get_mock_data(lat, lon)
        
        try:
            import requests
            
            # Use current weather API (historical requires paid plan)
            url = f"https://api.openweathermap.org/data/2.5/weather"
            params = {
                'lat': lat,
                'lon': lon,
                'appid': self.api_key,
                'units': 'metric'
            }
            
            response = requests.get(url, params=params, timeout=5)
            data = response.json()
            
            if response.status_code != 200:
                return None
            
            return WeatherData(
                temperature=data['main']['temp'],
                humidity=data['main']['humidity'],
                wind_speed=data['wind']['speed'] * 3.6,  # m/s to km/h
                feels_like=data['main']['feels_like'],
                description=data['weather'][0]['description'],
                location=data.get('name', 'Unknown'),
                timestamp=datetime.now()
            )
            
        except Exception as e:
            print(f"Weather API error: {e}")
            return None
    
    def _get_mock_data(self, lat: float, lon: float) -> WeatherData:
        """Return mock weather data when API is unavailable."""
        return WeatherData(
            temperature=20.0,
            humidity=60.0,
            wind_speed=10.0,
            feels_like=20.0,
            description="Brak danych pogodowych (ustaw OPENWEATHER_API_KEY)",
            location="Unknown",
            timestamp=datetime.now()
        )
    
    def calculate_tss_correction(
        self,
        weather: WeatherData
    ) -> Tuple[float, str]:
        """Calculate TSS correction factor based on conditions.
        
        Args:
            weather: Weather data
            
        Returns:
            Tuple of (correction_factor, explanation)
        """
        corrections = []
        explanations = []
        
        # Temperature correction
        for (min_t, max_t), factor in self.TEMP_CORRECTION.items():
            if min_t <= weather.temperature < max_t:
                corrections.append(factor)
                explanations.append(f"Temperatura {weather.temperature:.0f}°C: +{factor*100:.0f}%")
                break
        
        # Humidity correction
        for (min_h, max_h), factor in self.HUMIDITY_CORRECTION.items():
            if min_h <= weather.humidity < max_h:
                corrections.append(factor)
                explanations.append(f"Wilgotność {weather.humidity:.0f}%: +{factor*100:.0f}%")
                break
        
        # Altitude correction
        for (min_a, max_a), factor in self.ALTITUDE_CORRECTION.items():
            if min_a <= weather.altitude < max_a:
                corrections.append(factor)
                explanations.append(f"Wysokość {weather.altitude:.0f}m: +{factor*100:.0f}%")
                break
        
        # Wind correction
        for (min_w, max_w), factor in self.WIND_CORRECTION.items():
            if min_w <= weather.wind_speed < max_w:
                corrections.append(factor)
                explanations.append(f"Wiatr {weather.wind_speed:.0f} km/h: +{factor*100:.0f}%")
                break
        
        total_correction = sum(corrections)
        explanation = " | ".join(explanations) if explanations else "Brak korekt"
        
        return total_correction, explanation
    
    def adjust_tss(
        self,
        base_tss: float,
        weather: WeatherData
    ) -> Tuple[float, str]:
        """Adjust TSS based on environmental conditions.
        
        Args:
            base_tss: Original TSS value
            weather: Weather conditions
            
        Returns:
            Tuple of (adjusted_tss, explanation)
        """
        correction, explanation = self.calculate_tss_correction(weather)
        adjusted_tss = base_tss * (1 + correction)
        
        return adjusted_tss, explanation
    
    def get_heat_acclimation_status(
        self,
        recent_hot_sessions: int
    ) -> str:
        """Estimate heat acclimation status.
        
        Args:
            recent_hot_sessions: Number of hot sessions in last 14 days
            
        Returns:
            Acclimation status description
        """
        if recent_hot_sessions >= 10:
            return "🟢 Pełna aklimatyzacja cieplna (10+ sesji)"
        elif recent_hot_sessions >= 5:
            return "🟡 Częściowa aklimatyzacja (5-9 sesji)"
        elif recent_hot_sessions >= 2:
            return "🟠 Początek aklimatyzacji (2-4 sesje)"
        else:
            return "🔴 Brak aklimatyzacji (<2 sesje)"
