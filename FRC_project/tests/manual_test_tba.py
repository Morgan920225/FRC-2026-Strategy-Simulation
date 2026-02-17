"""
Quick manual test script for TBA client.
This is not a unit test - it makes real API calls to verify the client works.

Usage: python tests/manual_test_tba.py
"""

from src.tba_client import TBAClient
from src.tba_mapper import map_team_to_archetype, get_team_summary

# NOTE: Replace with a real TBA API key to test
# Get one from: https://www.thebluealliance.com/account
TEST_API_KEY = "YOUR_API_KEY_HERE"

def test_basic_client():
    """Test basic TBA client functionality."""
    if TEST_API_KEY == "YOUR_API_KEY_HERE":
        print("⚠️  Please set a real API key in tests/manual_test_tba.py")
        return
    
    print("Creating TBA client...")
    client = TBAClient(TEST_API_KEY)
    
    print("\n1. Testing get_team(254)...")
    team = client.get_team(254)
    if team:
        print(f"   ✓ Team 254: {team.get('nickname')}")
    else:
        print("   ✗ Failed to get team data")
    
    print("\n2. Testing get_event_oprs('2024casj')...")
    oprs = client.get_event_oprs("2024casj")
    if oprs and 'oprs' in oprs:
        sample_teams = list(oprs['oprs'].items())[:3]
        print(f"   ✓ Got OPR data for {len(oprs['oprs'])} teams")
        for team_key, opr in sample_teams:
            print(f"      {team_key}: {opr:.2f}")
    else:
        print("   ✗ Failed to get OPR data")
    
    print("\n3. Testing map_team_to_archetype()...")
    test_oprs = [85.0, 65.0, 48.0, 35.0, 18.0, 10.0]
    for opr in test_oprs:
        archetype = map_team_to_archetype(opr)
        print(f"   OPR {opr:.1f} → {archetype}")
    
    print("\n4. Testing get_team_summary()...")
    summary = get_team_summary(client, 254, "2024casj")
    if summary:
        print(f"   ✓ {summary['name']} (Team {summary['number']})")
        print(f"      OPR: {summary['opr']:.2f}")
        print(f"      Rank: {summary['rank']}")
        print(f"      Archetype: {summary['archetype']}")
    else:
        print("   ✗ Failed to get team summary")


if __name__ == "__main__":
    test_basic_client()
