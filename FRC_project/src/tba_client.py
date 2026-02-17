"""
The Blue Alliance (TBA) API v3 Client

This module provides a client for interacting with The Blue Alliance API.
Documentation: https://www.thebluealliance.com/apidocs/v3
"""

from typing import Optional, List, Dict, Any
import requests
from functools import lru_cache


class TBAError(Exception):
    """Custom exception for TBA API errors."""
    pass


class TBAClient:
    """
    Client for The Blue Alliance API v3.
    
    Example Usage:
        client = TBAClient(api_key="your_key_here")
        team = client.get_team(254)
        print(team['nickname'])  # "The Cheesy Poofs"
    """
    
    BASE_URL = "https://www.thebluealliance.com/api/v3"
    
    def __init__(self, api_key: str):
        """
        Initialize TBA client with API key.
        
        Args:
            api_key: Your TBA API key from https://www.thebluealliance.com/account
        """
        if not api_key:
            raise ValueError("API key cannot be empty")
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'X-TBA-Auth-Key': self.api_key,
            'Accept': 'application/json'
        })
    
    def _make_request(self, endpoint: str) -> Optional[Any]:
        """
        Make an HTTP GET request to TBA API.
        
        Args:
            endpoint: API endpoint path (e.g., "/team/frc254")
            
        Returns:
            Parsed JSON response or None if error
            
        Raises:
            TBAError: If HTTP error occurs
        """
        url = f"{self.BASE_URL}{endpoint}"
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 404:
                return None  # Not found is acceptable
            raise TBAError(f"TBA API error ({response.status_code}): {e}")
        except requests.exceptions.RequestException as e:
            raise TBAError(f"Network error: {e}")
        except ValueError as e:
            raise TBAError(f"Invalid JSON response: {e}")
    
    def get_team(self, team_number: int) -> Optional[Dict[str, Any]]:
        """
        Get team information.
        
        Args:
            team_number: FRC team number (e.g., 254)
            
        Returns:
            Team data dict with keys: team_number, nickname, name, city, state_prov, country
            Example: {'team_number': 254, 'nickname': 'The Cheesy Poofs', ...}
        """
        return self._make_request(f"/team/frc{team_number}")
    
    def get_team_events(self, team_number: int, year: int) -> Optional[List[Dict[str, Any]]]:
        """
        Get all events a team attended in a year.
        
        Args:
            team_number: FRC team number
            year: Competition year (e.g., 2024)
            
        Returns:
            List of event dicts with keys: key, name, event_code, event_type, start_date, end_date
        """
        return self._make_request(f"/team/frc{team_number}/events/{year}")
    
    def get_event_teams(self, event_key: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get all teams at an event.
        
        Args:
            event_key: TBA event key (e.g., "2024casj")
            
        Returns:
            List of team dicts
        """
        return self._make_request(f"/event/{event_key}/teams")
    
    def get_event_matches(self, event_key: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get all matches at an event.
        
        Args:
            event_key: TBA event key
            
        Returns:
            List of match dicts with keys: key, comp_level, match_number, alliances, score_breakdown, time
            Example alliance structure: {'red': {'team_keys': ['frc254', ...], 'score': 120}, ...}
        """
        return self._make_request(f"/event/{event_key}/matches")
    
    def get_event_oprs(self, event_key: str) -> Optional[Dict[str, Dict[str, float]]]:
        """
        Get OPR, DPR, and CCWM for all teams at an event.
        
        Args:
            event_key: TBA event key
            
        Returns:
            Dict with keys: 'oprs', 'dprs', 'ccwms'
            Each maps team keys to floats: {'frc254': 87.3, 'frc1678': 82.1, ...}
        """
        return self._make_request(f"/event/{event_key}/oprs")
    
    def get_event_rankings(self, event_key: str) -> Optional[Dict[str, Any]]:
        """
        Get rankings for an event.
        
        Args:
            event_key: TBA event key
            
        Returns:
            Dict with keys: 'rankings' (list of dicts with rank, team_key, record, etc.)
            Example ranking: {'rank': 1, 'team_key': 'frc254', 'record': {'wins': 10, 'losses': 0, 'ties': 0}, ...}
        """
        return self._make_request(f"/event/{event_key}/rankings")
    
    def get_event_alliances(self, event_key: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get alliance selections for an event.
        
        Args:
            event_key: TBA event key
            
        Returns:
            List of alliance dicts with keys: name, picks (list of team keys)
            Example: [{'name': 'Alliance 1', 'picks': ['frc254', 'frc1678', 'frc118']}, ...]
        """
        return self._make_request(f"/event/{event_key}/alliances")
    
    def get_events_by_year(self, year: int) -> Optional[List[Dict[str, Any]]]:
        """
        Get all FRC events in a given year.
        
        Args:
            year: Competition year (e.g., 2024)
            
        Returns:
            List of event dicts
        """
        return self._make_request(f"/events/{year}")
    
    def get_team_matches_at_event(self, team_number: int, event_key: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get all matches for a specific team at an event.
        
        Args:
            team_number: FRC team number
            event_key: TBA event key
            
        Returns:
            List of match dicts for this team
        """
        return self._make_request(f"/team/frc{team_number}/event/{event_key}/matches")


# Cached wrapper functions for Streamlit compatibility
@lru_cache(maxsize=128)
def cached_get_team(api_key: str, team_number: int) -> Optional[Dict[str, Any]]:
    """Cached version of get_team for use with st.cache_data."""
    client = TBAClient(api_key)
    return client.get_team(team_number)


@lru_cache(maxsize=128)
def cached_get_event_oprs(api_key: str, event_key: str) -> Optional[Dict[str, Dict[str, float]]]:
    """Cached version of get_event_oprs for use with st.cache_data."""
    client = TBAClient(api_key)
    return client.get_event_oprs(event_key)


@lru_cache(maxsize=128)
def cached_get_event_rankings(api_key: str, event_key: str) -> Optional[Dict[str, Any]]:
    """Cached version of get_event_rankings for use with st.cache_data."""
    client = TBAClient(api_key)
    return client.get_event_rankings(event_key)


@lru_cache(maxsize=128)
def cached_get_events_by_year(api_key: str, year: int) -> Optional[List[Dict[str, Any]]]:
    """Cached version of get_events_by_year for use with st.cache_data."""
    client = TBAClient(api_key)
    return client.get_events_by_year(year)


@lru_cache(maxsize=128)
def cached_get_event_matches(api_key: str, event_key: str) -> Optional[List[Dict[str, Any]]]:
    """Cached version of get_event_matches for use with st.cache_data."""
    client = TBAClient(api_key)
    return client.get_event_matches(event_key)


@lru_cache(maxsize=128)
def cached_get_event_alliances(api_key: str, event_key: str) -> Optional[List[Dict[str, Any]]]:
    """Cached version of get_event_alliances for use with st.cache_data."""
    client = TBAClient(api_key)
    return client.get_event_alliances(event_key)


@lru_cache(maxsize=128)
def cached_get_event_teams(api_key: str, event_key: str) -> Optional[List[Dict[str, Any]]]:
    """Cached version of get_event_teams for use with st.cache_data."""
    client = TBAClient(api_key)
    return client.get_event_teams(event_key)
