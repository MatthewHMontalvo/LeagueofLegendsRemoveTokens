"""
League of Legends - Remove All Profile Tokens
Uses the LCU (League Client Update) API to clear all token slots from your profile banner.

Requirements:
  pip install psutil requests urllib3

Usage:
  1. Open the League of Legends client and log in.
  2. Run this script: python remove_lol_tokens.py
"""

import json
import os
import re
import sys
import base64

try:
    import psutil
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    print("Missing dependencies. Please run:")
    print("  pip install psutil requests urllib3")
    sys.exit(1)


def find_lcu_credentials():
    """Find the League Client process and extract connection credentials."""
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            name = proc.info['name'] or ''
            if 'LeagueClientUx' not in name:
                continue
            cmdline = ' '.join(proc.info['cmdline'] or [])

            port_match = re.search(r'--app-port=(\d+)', cmdline)
            token_match = re.search(r'--remoting-auth-token=([\w-]+)', cmdline)

            if port_match and token_match:
                return {
                    'port': port_match.group(1),
                    'token': token_match.group(1),
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def make_lcu_request(creds, method, endpoint, body=None):
    """Make an authenticated request to the LCU API."""
    auth = base64.b64encode(f"riot:{creds['token']}".encode()).decode()
    url = f"https://127.0.0.1:{creds['port']}{endpoint}"
    headers = {
        'Authorization': f'Basic {auth}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    resp = requests.request(
        method, url,
        headers=headers,
        json=body,
        verify=False,
        timeout=10
    )
    return resp


def get_current_profile(creds):
    """Fetch the current summoner profile."""
    resp = make_lcu_request(creds, 'GET', '/lol-summoner/v1/current-summoner')
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to get summoner info: {resp.status_code} {resp.text}")
    return resp.json()


def get_profile_background(creds):
    """Get current profile background/token configuration."""
    resp = make_lcu_request(creds, 'GET', '/lol-summoner/v1/current-summoner/summoner-profile')
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to get profile: {resp.status_code} {resp.text}")
    return resp.json()


def remove_all_tokens(creds):
    """Remove all tokens from the profile by setting empty token arrays."""
    # The payload to clear all token slots
    payload = {
        "inventory": json.dumps({
            "backgroundSkinId": None,
            "profileIconId": None,
            "regalia": {
                "crestType": "none",
                "bannerType": "lastSeasonHighestRank",
                "selectedPrestigeCrest": 0
            }
        })
    }

    # First, try the regalia endpoint which controls tokens/crests
    resp = make_lcu_request(creds, 'GET', '/lol-regalia/v2/current-summoner/regalia')
    if resp.status_code == 200:
        current_regalia = resp.json()
        print(f"Current regalia: {json.dumps(current_regalia, indent=2)}")

        # Build cleared regalia - set crestType to 'none' to remove all tokens
        cleared = {
            "crestType": "none",
            "bannerType": current_regalia.get("bannerType", "lastSeasonHighestRank"),
            "selectedPrestigeCrest": 0
        }

        put_resp = make_lcu_request(
            creds, 'PUT',
            '/lol-regalia/v2/current-summoner/regalia',
            body=cleared
        )
        if put_resp.status_code in (200, 201, 204):
            print("\n✅ Successfully removed all tokens from your profile!")
            print("Your profile banner now has no token slots filled.")
            return True
        else:
            print(f"Regalia PUT failed ({put_resp.status_code}): {put_resp.text}")

    # Fallback: try the summoner profile endpoint
    print("\nTrying alternative method via summoner profile...")
    profile_resp = make_lcu_request(creds, 'GET', '/lol-summoner/v1/current-summoner/summoner-profile')
    if profile_resp.status_code == 200:
        profile = profile_resp.json()
        print(f"Current profile config: {json.dumps(profile, indent=2)}")

        try:
            inventory = json.loads(profile.get('inventory', '{}'))
        except (json.JSONDecodeError, TypeError):
            inventory = {}

        # Clear token slots
        if 'regalia' in inventory:
            inventory['regalia']['crestType'] = 'none'
            inventory['regalia']['selectedPrestigeCrest'] = 0
        else:
            inventory['regalia'] = {
                'crestType': 'none',
                'bannerType': 'lastSeasonHighestRank',
                'selectedPrestigeCrest': 0
            }

        update_payload = {'inventory': json.dumps(inventory)}
        update_resp = make_lcu_request(
            creds, 'PUT',
            '/lol-summoner/v1/current-summoner/summoner-profile',
            body=update_payload
        )
        if update_resp.status_code in (200, 201, 204):
            print("\n✅ Successfully removed all tokens from your profile!")
            return True
        else:
            print(f"Profile PUT failed ({update_resp.status_code}): {update_resp.text}")

    return False


def main():
    print("=" * 50)
    print("  League of Legends - Remove All Profile Tokens")
    print("=" * 50)
    print()

    print("🔍 Searching for League Client process...")
    creds = find_lcu_credentials()

    if not creds:
        print("\n❌ Could not find the League Client process.")
        print("   Please make sure:")
        print("   1. The League of Legends client is open and you are logged in.")
        print("   2. You are running this script with sufficient permissions.")
        print("      (On Windows, try running as Administrator.)")
        sys.exit(1)

    print(f"✅ Found League Client on port {creds['port']}")
    print()

    try:
        summoner = get_current_profile(creds)
        print(f"👤 Logged in as: {summoner.get('displayName', 'Unknown')}")
        print()
    except Exception as e:
        print(f"⚠️  Could not fetch summoner info: {e}")
        print()

    confirm = input("Remove ALL tokens from your profile banner? (yes/no): ").strip().lower()
    if confirm not in ('yes', 'y'):
        print("Aborted.")
        sys.exit(0)

    print()
    success = remove_all_tokens(creds)

    if not success:
        print("\n❌ Could not remove tokens automatically.")
        print("   The LCU API endpoints may have changed in a recent patch.")
        print("   You can check the current API at: https://lcu.vivide.re/")
    else:
        print("\nRestart or refresh your client profile to see the changes.")


if __name__ == '__main__':
    main()
