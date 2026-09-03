
# LoL Token Remover

A single Python script that removes all three Challenge Token slots from your
League of Legends profile banner — something the official client won't let you
do (it always leaves at least one filled).

Opens as a **one-click GUI app** when you run it normally. Falls back to a
terminal prompt if you prefer (`--cli` flag).

> **Not affiliated with Riot Games.** All requests go to `127.0.0.1` only —
> nothing leaves your machine.

---

## Why this instead of other tools?

| Tool | What you need |
|---|---|
| **ChallengesAreEvil** (most popular) | Download an `.exe`, bypass antivirus warnings, trust a binary |
| **PowerShell / Bash scripts** | Know how to open a terminal, set execution policy, etc. |
| **This tool** | Just Python — open it like any other program |

Because the GUI is built with `tkinter` (bundled with every standard Python
installer), you need **zero extra installs** beyond Python itself.

---

## Requirements

| | |
|---|---|
| **Python** | 3.8 or newer — [python.org](https://www.python.org/downloads/) |
| **OS** | Windows 10/11 or macOS |
| **League client** | Must be open and logged in when you run the tool |

---

## Setup (one time)

### 1 — Install Python

Download from [python.org](https://www.python.org/downloads/).

> **Windows:** tick **"Add Python to PATH"** during installation.

### 2 — Install the two small dependencies

Open a terminal and run:

```
pip install psutil requests urllib3
```

`psutil` reads the League client process to find its port and auth token.
`requests` sends the API call. `urllib3` suppresses the SSL warning from the
client's self-signed certificate. The GUI itself (`tkinter`) is already
included with Python — no install needed.

### 3 — Download the script

Save `remove_lol_tokens.py` anywhere on your computer.

---

## How to run

**Double-click** `remove_lol_tokens.py` in File Explorer (Windows) or Finder
(macOS) — if Python is associated with `.py` files, the GUI opens immediately.

Or from a terminal:

```bash
python remove_lol_tokens.py          # GUI
python remove_lol_tokens.py --cli    # terminal mode
```

The tool will detect the League client automatically, show your summoner name,
and wait for you to click the button. That's it.

---

## What it looks like

```
┌──────────────────────────────────────────┐  ← gold border
│  ⚔  LoL Token Remover                   │
│  Clears all Challenge Token slots…       │
├──────────────────────────────────────────┤
│  Logged in as:  YourName                 │
│  Ready — click the button to clear.      │
├──────────────────────────────────────────┤
│  [ Remove All Tokens ]                   │
├──────────────────────────────────────────┤
│  Not affiliated with Riot Games  •  …   │
└──────────────────────────────────────────┘
```

The button is disabled until the client is detected. After clicking, it shows
a confirmation inline — no popups.

---

## How it works

The League client runs a local HTTPS REST API on `127.0.0.1` (the LCU API).
The script reads the `LeagueClientUx` process arguments to find the random
port and session token, then calls:

```
POST /lol-challenges/v1/update-player-preferences/
{ "challengeIds": [] }
```

An empty array tells the client to unequip all token slots — the same internal
call the client makes when you swap tokens manually. If that endpoint fails
(e.g. after a Riot patch), the script automatically tries a second method via
`/lol-regalia/v2/current-summoner/regalia`.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "League client not found" | Make sure the client is fully loaded (home screen visible), then try again. The tool retries every 3 seconds automatically. |
| Button stays disabled | Wait a few more seconds after the client loads, then check again. |
| "Permission denied" on Windows | Right-click your terminal → Run as Administrator |
| "Permission denied" on macOS | `sudo python3 remove_lol_tokens.py` |
| Tokens reappear after a game | The client sometimes re-equips tokens after matches — just run the tool again |
| Script fails after a patch | Riot may have changed the endpoint. Open an issue or check [lcu.vivide.re](https://lcu.vivide.re/) |
| Double-click opens Notepad instead | Right-click → Open with → Python |

---

## FAQ

**Will I get banned?**
Almost certainly not. This uses the same local API the client itself uses
internally, doesn't touch game files, and only modifies a cosmetic profile
setting. No bans have been reported from similar tools. Use at your own
discretion — Riot's policies can change.

**Does it change anything else on my profile?**
No. Only the three Challenge Token slots. Rank banner, profile icon,
background, title — all untouched.

**Do I have to run it every game?**
Sometimes the client re-equips tokens after a match. If that happens, just
run the tool again.

**Can I use the --cli flag on Windows?**
Yes: open Command Prompt or PowerShell, navigate to the script's folder, and
run `python remove_lol_tokens.py --cli`.

**Why not just ship a .exe?**
A compiled `.exe` with no verified publisher triggers antivirus false positives
(ChallengesAreEvil's biggest user complaint). A plain `.py` file is fully
readable — you can see exactly what it does before running it.

---

## License

Public domain — do whatever you want with it.
