"""
Unit tests for TBA Client

These tests use mocked HTTP responses to avoid making real API calls.
Run with: pytest tests/test_tba_client.py
"""

import pytest
import requests
from unittest.mock import patch, MagicMock
from src.tba_client import TBAClient, TBAError


class TestTBAClient:
    """Test suite for TBA API client."""
    
    def test_init_with_valid_key(self):
        """Test client initialization with valid API key."""
        client = TBAClient("test_api_key_123")
        assert client.api_key == "test_api_key_123"
        assert client.session.headers['X-TBA-Auth-Key'] == "test_api_key_123"
    
    def test_init_with_empty_key(self):
        """Test client initialization fails with empty API key."""
        with pytest.raises(ValueError, match="API key cannot be empty"):
            TBAClient("")
    
    @patch('src.tba_client.requests.Session.get')
    def test_get_team_success(self, mock_get):
        """Test successful team data retrieval."""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'team_number': 254,
            'nickname': 'The Cheesy Poofs',
            'city': 'San Jose',
            'state_prov': 'California',
            'country': 'USA'
        }
        mock_get.return_value = mock_response
        
        # Test
        client = TBAClient("test_key")
        team = client.get_team(254)
        
        assert team['team_number'] == 254
        assert team['nickname'] == 'The Cheesy Poofs'
        mock_get.assert_called_once()
    
    @patch('src.tba_client.requests.Session.get')
    def test_get_team_not_found(self, mock_get):
        """Test team retrieval returns None for 404."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
        mock_get.return_value = mock_response
        
        client = TBAClient("test_key")
        team = client.get_team(99999)
        
        assert team is None
    
    @patch('src.tba_client.requests.Session.get')
    def test_get_event_oprs_success(self, mock_get):
        """Test successful OPR data retrieval."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'oprs': {'frc254': 87.3, 'frc1678': 82.1},
            'dprs': {'frc254': 12.5, 'frc1678': 15.2},
            'ccwms': {'frc254': 45.2, 'frc1678': 38.7}
        }
        mock_get.return_value = mock_response
        
        client = TBAClient("test_key")
        oprs = client.get_event_oprs("2024casj")
        
        assert oprs['oprs']['frc254'] == 87.3
        assert oprs['dprs']['frc254'] == 12.5
        assert oprs['ccwms']['frc254'] == 45.2
    
    @patch('src.tba_client.requests.Session.get')
    def test_get_event_rankings_success(self, mock_get):
        """Test successful rankings retrieval."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'rankings': [
                {
                    'rank': 1,
                    'team_key': 'frc254',
                    'record': {'wins': 10, 'losses': 0, 'ties': 0}
                }
            ]
        }
        mock_get.return_value = mock_response
        
        client = TBAClient("test_key")
        rankings = client.get_event_rankings("2024casj")
        
        assert rankings['rankings'][0]['rank'] == 1
        assert rankings['rankings'][0]['team_key'] == 'frc254'
    
    @patch('src.tba_client.requests.Session.get')
    def test_get_events_by_year_success(self, mock_get):
        """Test successful events retrieval."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                'key': '2024casj',
                'name': 'Silicon Valley Regional',
                'event_code': 'casj',
                'start_date': '2024-03-15',
                'end_date': '2024-03-17'
            }
        ]
        mock_get.return_value = mock_response
        
        client = TBAClient("test_key")
        events = client.get_events_by_year(2024)
        
        assert len(events) == 1
        assert events[0]['key'] == '2024casj'
        assert events[0]['name'] == 'Silicon Valley Regional'
    
    @patch('src.tba_client.requests.Session.get')
    def test_http_error_raises_tba_error(self, mock_get):
        """Test that HTTP errors (non-404) raise TBAError."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
        mock_get.return_value = mock_response
        
        client = TBAClient("test_key")
        
        with pytest.raises(TBAError):
            client.get_team(254)
