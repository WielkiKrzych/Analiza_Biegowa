"""
Strava API Integration Module.

Provides OAuth authentication and activity synchronization with Strava.
"""

import os
import json
import requests
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import streamlit as st

# Strava API configuration
STRAVA_CLIENT_ID = os.environ.get("STRAVA_CLIENT_ID", "")
STRAVA_CLIENT_SECRET = os.environ.get("STRAVA_CLIENT_SECRET", "")
STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API_URL = "https://www.stacexternal.com/api/v3"


@dataclass
class StravaActivity:
    """Represents a Strava activity."""
    id: int
    name: str
    type: str
    start_date: str
    distance: float  # meters
    moving_time: int  # seconds
    elapsed_time: int  # seconds
    total_elevation_gain: float
    average_speed: float  # m/s
    max_speed: float  # m/s
    average_heartrate: Optional[float] = None
    max_heartrate: Optional[float] = None
    average_cadence: Optional[float] = None
    calories: Optional[float] = None
    average_watts: Optional[float] = None


class StravaAuth:
    """Handles Strava OAuth authentication."""
    
    def __init__(self, client_id: str = None, client_secret: str = None):
        self.client_id = client_id or STRAVA_CLIENT_ID
        self.client_secret = client_secret or STRAVA_CLIENT_SECRET
        self.token_file = ".strava_tokens"
    
    def get_authorization_url(self, redirect_uri: str) -> str:
        """Generate Strava authorization URL."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "read,activity:read_all",
        }
        return f"{STRAVA_AUTH_URL}?" + "&".join(f"{k}={v}" for k, v in params.items())
    
    def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access token."""
        response = requests.post(
            STRAVA_TOKEN_URL,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "grant_type": "authorization_code",
            }
        )
        response.raise_for_status()
        return response.json()
    
    def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token."""
        response = requests.post(
            STRAVA_TOKEN_URL,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }
        )
        response.raise_for_status()
        return response.json()
    
    def save_tokens(self, tokens: Dict[str, Any]) -> None:
        """Save tokens to file."""
        with open(self.token_file, "w") as f:
            json.dump(tokens, f)
    
    def load_tokens(self) -> Optional[Dict[str, Any]]:
        """Load tokens from file."""
        try:
            with open(self.token_file, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return None
    
    def get_valid_token(self) -> Optional[str]:
        """Get valid access token, refreshing if needed."""
        tokens = self.load_tokens()
        if not tokens:
            return None
        
        # Check if token needs refresh
        expires_at = tokens.get("expires_at", 0)
        if datetime.now().timestamp() > expires_at:
            # Refresh token
            new_tokens = self.refresh_token(tokens["refresh_token"])
            self.save_tokens(new_tokens)
            return new_tokens.get("access_token")
        
        return tokens.get("access_token")


class StravaClient:
    """Strava API client for fetching activities."""
    
    def __init__(self, access_token: str):
        self.access_token = access_token
    
    def get_activities(
        self, 
        after: Optional[datetime] = None,
        before: Optional[datetime] = None,
        per_page: int = 100
    ) -> List[StravaActivity]:
        """Fetch activities from Strava."""
        params = {"per_page": per_page}
        
        if after:
            params["after"] = int(after.timestamp())
        if before:
            params["before"] = int(before.timestamp())
        
        response = requests.get(
            "https://www.strava.com/api/v3/athlete/activities",
            headers={"Authorization": f"Bearer {self.access_token}"},
            params=params
        )
        response.raise_for_status()
        
        activities = []
        for data in response.json():
            try:
                activity = StravaActivity(
                    id=data["id"],
                    name=data["name"],
                    type=data["type"],
                    start_date=data["start_date"],
                    distance=data.get("distance", 0),
                    moving_time=data.get("moving_time", 0),
                    elapsed_time=data.get("elapsed_time", 0),
                    total_elevation_gain=data.get("total_elevation_gain", 0),
                    average_speed=data.get("average_speed", 0),
                    max_speed=data.get("max_speed", 0),
                    average_heartrate=data.get("average_heartrate"),
                    max_heartrate=data.get("max_heartrate"),
                    average_cadence=data.get("average_cadence"),
                    calories=data.get("calories"),
                    average_watts=data.get("average_watts"),
                )
                activities.append(activity)
            except (KeyError, TypeError):
                continue
        
        return activities
    
    def export_to_csv(self, activities: List[StravaActivity]) -> str:
        """Export activities to CSV format."""
        import pandas as pd
        
        data = []
        for a in activities:
            data.append({
                "date": a.start_date,
                "name": a.name,
                "type": a.type,
                "distance_km": a.distance / 1000,
                "duration_sec": a.moving_time,
                "avg_pace": a.moving_time / (a.distance / 1000) if a.distance > 0 else 0,
                "avg_hr": a.average_heartrate or 0,
                "max_hr": a.max_heartrate or 0,
                "cadence": a.average_cadence or 0,
                "calories": a.calories or 0,
                "elevation_gain": a.total_elevation_gain,
            })
        
        df = pd.DataFrame(data)
        return df.to_csv(index=False)


def render_strava_tab():
    """Render Strava integration UI tab."""
    st.header("🏃 Integracja ze Stravą")
    
    auth = StravaAuth()
    
    # Check if tokens exist
    tokens = auth.load_tokens()
    
    if not tokens:
        st.info("""
        **Połącz ze Stravą** aby automatycznie synchronizować swoje treningi.
        
        Aby połączyć aplikację ze Stravą:
        1. Utwórz aplikację na [Strava Developers](https://www.strava.com/settings/api)
        2. Ustaw redirect URI: `http://localhost:8501/strava`
        3. Dodaj zmienne środowiskowe:
           - `STRAVA_CLIENT_ID`
           - `STRAVA_CLIENT_SECRET`
        """)
        
        if STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET:
            redirect_uri = "http://localhost:8501/strava"
            auth_url = auth.get_authorization_url(redirect_uri)
            st.markdown(f"[🔗 Połącz ze Stravą]({auth_url})")
        else:
            st.warning("⚠️ Skonfiguruj STRAVA_CLIENT_ID i STRAVA_CLIENT_SECRET aby włączyć integrację.")
        return
    
    # Show connected status
    token = auth.get_valid_token()
    if token:
        st.success("✅ Połączono ze Stravą")
        
        # Fetch activities
        client = StravaClient(token)
        
        col1, col2 = st.columns(2)
        with col1:
            days = st.selectbox("Okres", [7, 14, 30, 60, 90], format_func=lambda x: f"{x} dni")
        with col2:
            if st.button("🔄 Synchronizuj"):
                with st.spinner("Pobieranie aktywności..."):
                    after = datetime.now() - timedelta(days=days)
                    activities = client.get_activities(after=after)
                    st.session_state["strava_activities"] = activities
                    st.session_state["strava_sync_time"] = datetime.now()
        
        # Show activities
        if "strava_activities" in st.session_state:
            activities = st.session_state["strava_activities"]
            st.write(f"**Znaleziono {len(activities)} aktywności**")
            
            # Summary metrics
            total_distance = sum(a.distance for a in activities) / 1000
            total_time = sum(a.moving_time for a in activities) / 3600
            total_calories = sum(a.calories or 0 for a in activities)
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Treningi", len(activities))
            m2.metric("Dystans", f"{total_distance:.1f} km")
            m3.metric("Czas", f"{total_time:.1f} h")
            m4.metric("Kalorie", f"{total_calories:.0f}")
            
            # Export button
            csv = client.export_to_csv(activities)
            st.download_button(
                "📥 Eksportuj do CSV",
                csv,
                "strava_activities.csv",
                "text/csv"
            )
            
            # Activity list
            with st.expander("📋 Lista aktywności", expanded=False):
                for a in activities[:20]:
                    st.write(f"**{a.start_date[:10]}** - {a.name} ({a.distance/1000:.1f} km)")
    else:
        st.error("❌ Problem z autoryzacją. Spróbuj ponownie.")
        if st.button("🔓 Wyloguj"):
            try:
                os.remove(auth.token_file)
                st.rerun()
            except:
                pass


def handle_strava_callback(code: str) -> bool:
    """Handle OAuth callback from Strava."""
    try:
        auth = StravaAuth()
        tokens = auth.exchange_code_for_token(code)
        auth.save_tokens(tokens)
        return True
    except Exception as e:
        st.error(f"Błąd autoryzacji: {e}")
        return False
