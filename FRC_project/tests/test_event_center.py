"""
Integration tests for Event Center tab logic.

Tests use mocked TBA responses to validate data transformation
without making real API calls.

Run with: pytest tests/test_event_center.py -v
"""

import pytest
from unittest.mock import patch, MagicMock
from src.tba_client import TBAClient
from src.tba_mapper import map_team_to_archetype, get_team_summary, get_archetype_distribution


class TestEventCenterDataFlow:
    """Test that TBA data is properly transformed for display."""

    @patch('src.tba_client.requests.Session.get')
    def test_rankings_and_opr_merge(self, mock_get):
        """Rankings + OPR data merge produces correct table rows."""
        rankings_resp = MagicMock()
        rankings_resp.status_code = 200
        rankings_resp.json.return_value = {
            "rankings": [
                {"rank": 1, "team_key": "frc254", "record": {"wins": 8, "losses": 0, "ties": 0}, "sort_orders": [24.0]},
                {"rank": 2, "team_key": "frc1678", "record": {"wins": 7, "losses": 1, "ties": 0}, "sort_orders": [21.0]},
            ]
        }
        opr_resp = MagicMock()
        opr_resp.status_code = 200
        opr_resp.json.return_value = {
            "oprs": {"frc254": 87.3, "frc1678": 65.2},
            "dprs": {"frc254": 12.5, "frc1678": 18.1},
            "ccwms": {"frc254": 45.0, "frc1678": 30.5},
        }

        # Return different responses per URL
        def side_effect(url, **kwargs):
            if "rankings" in url:
                return rankings_resp
            elif "oprs" in url:
                return opr_resp
            return MagicMock(status_code=404)
        mock_get.side_effect = side_effect

        client = TBAClient("test_key")
        rankings = client.get_event_rankings("2024test")
        oprs = client.get_event_oprs("2024test")

        assert rankings["rankings"][0]["team_key"] == "frc254"
        assert oprs["oprs"]["frc254"] == 87.3

        # Verify archetype mapping from OPR
        assert map_team_to_archetype(87.3) == "elite_turret"
        assert map_team_to_archetype(65.2) == "elite_multishot"

    @patch('src.tba_client.requests.Session.get')
    def test_match_schedule_sorting(self, mock_get):
        """Matches are split into completed and upcoming correctly."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "key": "2024test_qm1", "comp_level": "qm", "match_number": 1, "set_number": 1,
                "alliances": {
                    "red": {"team_keys": ["frc254", "frc1678", "frc118"], "score": 150},
                    "blue": {"team_keys": ["frc971", "frc973", "frc5026"], "score": 120},
                }
            },
            {
                "key": "2024test_qm2", "comp_level": "qm", "match_number": 2, "set_number": 1,
                "alliances": {
                    "red": {"team_keys": ["frc254", "frc1678", "frc118"], "score": -1},
                    "blue": {"team_keys": ["frc971", "frc973", "frc5026"], "score": -1},
                }
            },
        ]
        mock_get.return_value = mock_response

        client = TBAClient("test_key")
        matches = client.get_event_matches("2024test")

        completed = [m for m in matches if m["alliances"]["red"]["score"] >= 0]
        upcoming = [m for m in matches if m["alliances"]["red"]["score"] < 0]

        assert len(completed) == 1
        assert len(upcoming) == 1
        assert completed[0]["match_number"] == 1

    @patch('src.tba_client.requests.Session.get')
    def test_alliance_bracket_available_teams(self, mock_get):
        """Available teams = all event teams minus picked teams."""
        alliance_resp = MagicMock()
        alliance_resp.status_code = 200
        alliance_resp.json.return_value = [
            {"name": "Alliance 1", "picks": ["frc254", "frc1678", "frc118"], "status": {"record": {"wins": 3, "losses": 0, "ties": 0}}},
            {"name": "Alliance 2", "picks": ["frc971", "frc973", "frc5026"], "status": {"record": {"wins": 2, "losses": 1, "ties": 0}}},
        ]
        teams_resp = MagicMock()
        teams_resp.status_code = 200
        teams_resp.json.return_value = [
            {"team_number": 254}, {"team_number": 1678}, {"team_number": 118},
            {"team_number": 971}, {"team_number": 973}, {"team_number": 5026},
            {"team_number": 7130}, {"team_number": 100},
        ]

        def side_effect(url, **kwargs):
            if "alliances" in url:
                return alliance_resp
            elif "teams" in url:
                return teams_resp
            return MagicMock(status_code=404)
        mock_get.side_effect = side_effect

        client = TBAClient("test_key")
        alliances = client.get_event_alliances("2024test")
        all_teams = client.get_event_teams("2024test")

        picked = set()
        for a in alliances:
            picked.update(t.replace("frc", "") for t in a["picks"])

        all_nums = {str(t["team_number"]) for t in all_teams}
        available = all_nums - picked

        assert "7130" in available
        assert "100" in available
        assert "254" not in available
        assert len(available) == 2


class TestTeamQuickLook:
    """Test team summary generation for the Quick-Look panel."""

    @patch('src.tba_client.requests.Session.get')
    def test_team_summary_full_data(self, mock_get):
        """Full team summary with OPR, ranking, and archetype."""
        def side_effect(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            if "/team/frc254" in url and "event" not in url:
                resp.json.return_value = {"team_number": 254, "nickname": "The Cheesy Poofs"}
            elif "oprs" in url:
                resp.json.return_value = {"oprs": {"frc254": 87.3}, "dprs": {"frc254": 12.5}, "ccwms": {"frc254": 45.0}}
            elif "rankings" in url:
                resp.json.return_value = {"rankings": [{"team_key": "frc254", "rank": 1, "record": {"wins": 8, "losses": 0, "ties": 0}}]}
            else:
                resp.status_code = 404
            return resp
        mock_get.side_effect = side_effect

        client = TBAClient("test_key")
        summary = get_team_summary(client, 254, "2024test")

        assert summary is not None
        assert summary["name"] == "The Cheesy Poofs"
        assert summary["opr"] == 87.3
        assert summary["rank"] == 1
        assert summary["archetype"] == "elite_turret"

    def test_archetype_distribution(self):
        """Archetype mapping covers all OPR ranges."""
        assert map_team_to_archetype(85) == "elite_turret"
        assert map_team_to_archetype(65) == "elite_multishot"
        assert map_team_to_archetype(50) == "strong_scorer"
        assert map_team_to_archetype(35) == "everybot"
        assert map_team_to_archetype(20) == "kitbot_plus"
        assert map_team_to_archetype(10) == "kitbot_base"
        assert map_team_to_archetype(0) == "kitbot_base"
