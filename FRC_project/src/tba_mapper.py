"""
TBA Data to Simulation Archetype Mapper

Maps real team data from The Blue Alliance (OPR, rankings, etc.) to simulation archetypes
defined in config.py.
"""

from typing import Optional, Dict, Any


def map_team_to_archetype(opr: float, climb_data: Optional[Dict] = None) -> str:
    """
    Map a real team's OPR + climb stats to the closest archetype key.
    
    Heuristic tiers (adjust as needed based on 2026 game data):
      OPR >= 80  → "elite_turret"
      OPR >= 60  → "elite_multishot"
      OPR >= 45  → "strong_scorer"
      OPR >= 30  → "everybot"
      OPR >= 15  → "kitbot_plus"
      OPR < 15   → "kitbot_base"
    
    If climb_data shows no climb capability and OPR > 30, consider "defense_bot".
    
    Args:
        opr: Team's Offensive Power Rating
        climb_data: Optional dict with climb stats (not used yet for 2026, reserved for future)
        
    Returns:
        Archetype key string (e.g., "elite_turret")
    """
    # Check for defense specialization (high DPR, low OPR ratio)
    # For now, we'll use a simple OPR-based heuristic
    # TODO: Incorporate climb_data when 2026 climb mechanics are defined
    
    if opr >= 80:
        return "elite_turret"
    elif opr >= 60:
        return "elite_multishot"
    elif opr >= 45:
        return "strong_scorer"
    elif opr >= 30:
        return "everybot"
    elif opr >= 15:
        return "kitbot_plus"
    else:
        return "kitbot_base"


def get_team_summary(tba_client, team_number: int, event_key: str) -> Optional[Dict[str, Any]]:
    """
    Fetch team info + OPR + ranking from TBA for a given event.
    
    Args:
        tba_client: Instance of TBAClient
        team_number: FRC team number
        event_key: TBA event key (e.g., "2024casj")
        
    Returns:
        Dict with keys: name, number, opr, ccwm, dpr, rank, record, archetype
        Example:
        {
            'name': 'The Cheesy Poofs',
            'number': 254,
            'opr': 87.3,
            'dpr': 12.5,
            'ccwm': 45.2,
            'rank': 1,
            'record': {'wins': 10, 'losses': 0, 'ties': 0},
            'archetype': 'elite_turret'
        }
        
        Returns None if team is not found at event or data is incomplete.
    """
    try:
        # Get team info
        team_info = tba_client.get_team(team_number)
        if not team_info:
            return None
        
        # Get OPR data
        opr_data = tba_client.get_event_oprs(event_key)
        team_key = f"frc{team_number}"
        
        opr = None
        dpr = None
        ccwm = None
        
        if opr_data:
            opr = opr_data.get('oprs', {}).get(team_key)
            dpr = opr_data.get('dprs', {}).get(team_key)
            ccwm = opr_data.get('ccwms', {}).get(team_key)
        
        # Get ranking data
        rankings_data = tba_client.get_event_rankings(event_key)
        rank = None
        record = None
        
        if rankings_data and 'rankings' in rankings_data:
            for ranking in rankings_data['rankings']:
                if ranking.get('team_key') == team_key:
                    rank = ranking.get('rank')
                    record = ranking.get('record')
                    break
        
        # Map to archetype if OPR is available
        archetype = None
        if opr is not None:
            archetype = map_team_to_archetype(opr)
        
        return {
            'name': team_info.get('nickname', 'Unknown'),
            'number': team_number,
            'opr': opr,
            'dpr': dpr,
            'ccwm': ccwm,
            'rank': rank,
            'record': record,
            'archetype': archetype
        }
        
    except Exception as e:
        print(f"Error fetching team summary for {team_number} at {event_key}: {e}")
        return None


def get_archetype_distribution(tba_client, event_key: str) -> Dict[str, int]:
    """
    Analyze the distribution of archetypes at an event.
    
    Args:
        tba_client: Instance of TBAClient
        event_key: TBA event key
        
    Returns:
        Dict mapping archetype names to counts
        Example: {'elite_turret': 3, 'strong_scorer': 12, 'everybot': 20, ...}
    """
    distribution = {}
    
    try:
        opr_data = tba_client.get_event_oprs(event_key)
        if not opr_data or 'oprs' not in opr_data:
            return distribution
        
        for team_key, opr in opr_data['oprs'].items():
            archetype = map_team_to_archetype(opr)
            distribution[archetype] = distribution.get(archetype, 0) + 1
        
        return distribution
        
    except Exception as e:
        print(f"Error getting archetype distribution for {event_key}: {e}")
        return distribution
