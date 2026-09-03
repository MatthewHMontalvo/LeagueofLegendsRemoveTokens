"""
╔══════════════════════════════════════════╗
║   LoL Token Remover  —  v3.0.0          ║
║   Removes all Challenge Tokens from     ║
║   your League of Legends profile.       ║
╚══════════════════════════════════════════╝

Zero extra installs needed — just Python 3.8+.
tkinter (the UI) is bundled with the standard Python installer.

Run:
    python remove_lol_tokens.py          → opens the GUI
    python remove_lol_tokens.py --cli    → headless / terminal mode
"""

import argparse
import base64
import re
import sys

# ── optional GUI ──────────────────────────────────────────────────────────────
try:
    import tkinter as tk
    from tkinter import font as tkfont
    HAS_TK = True
except ImportError:
    HAS_TK = False

# ── required deps ─────────────────────────────────────────────────────────────
try:
    import psutil
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    print("Missing dependencies. Run:  pip install psutil requests urllib3")
    sys.exit(1)


# ═════════════════════════════════════════════════════════════════════════════
#  LCU CORE  (shared by GUI and CLI)
# ═════════════════════════════════════════════════════════════════════════════

def find_lcu_credentials():
    """Scan running processes for LeagueClientUx and extract auth credentials."""
    for proc in psutil.process_iter(["name", "cmdline"]):
        try:
            name = proc.info["name"] or ""
            if "LeagueClientUx" not in name:
                continue
            cmdline = " ".join(proc.info["cmdline"] or [])
            port_m  = re.search(r"--app-port=(\d+)", cmdline)
            token_m = re.search(r"--remoting-auth-token=([\w-]+)", cmdline)
            if port_m and token_m:
                return {"port": port_m.group(1), "token": token_m.group(1)}
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def lcu_request(creds, method, endpoint, body=None):
    """Send an authenticated HTTPS request to the local LCU API."""
    auth    = base64.b64encode(f"riot:{creds['token']}".encode()).decode()
    url     = f"https://127.0.0.1:{creds['port']}{endpoint}"
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }
    return requests.request(
        method, url, headers=headers, json=body, verify=False, timeout=10
    )


def get_summoner_name(creds):
    """Return the display name of the logged-in summoner, or None."""
    try:
        r = lcu_request(creds, "GET", "/lol-summoner/v1/current-summoner")
        if r.status_code == 200:
            data = r.json()
            return data.get("displayName") or data.get("gameName")
    except Exception:
        pass
    return None


def clear_tokens(creds):
    """
    Attempt to clear all challenge tokens.
    Returns (success: bool, message: str).
    """
    # ── Primary: Challenges API (stable since 2022) ───────────────────────────
    try:
        r = lcu_request(
            creds, "POST",
            "/lol-challenges/v1/update-player-preferences/",
            body={"challengeIds": []},
        )
        if r.status_code in (200, 201, 204):
            return True, "All tokens removed via Challenges API."
    except Exception as e:
        pass

    # ── Fallback: Regalia API ─────────────────────────────────────────────────
    try:
        get_r = lcu_request(creds, "GET", "/lol-regalia/v2/current-summoner/regalia")
        if get_r.status_code == 200:
            current = get_r.json()
            payload = {
                "crestType":             "none",
                "bannerType":            current.get("bannerType", "lastSeasonHighestRank"),
                "selectedPrestigeCrest": 0,
            }
            put_r = lcu_request(
                creds, "PUT",
                "/lol-regalia/v2/current-summoner/regalia",
                body=payload,
            )
            if put_r.status_code in (200, 201, 204):
                return True, "Tokens cleared via Regalia API (fallback)."
    except Exception:
        pass

    return False, (
        "Both API methods failed.\n\n"
        "Make sure the League client is fully loaded (you can see the home screen), "
        "then try again.\n\n"
        "On Windows you may need to run this as Administrator.\n"
        "On macOS run with: sudo python3 remove_lol_tokens.py"
    )


# ═════════════════════════════════════════════════════════════════════════════
#  GUI
# ═════════════════════════════════════════════════════════════════════════════

# Hextech-inspired palette  ──────────────────────────────────────────────────
C_BG        = "#010A13"   # near-black blue-black — Hextech background
C_SURFACE   = "#0A1628"   # panel surface
C_BORDER    = "#785A28"   # gold border
C_ACCENT    = "#C89B3C"   # Hextech gold
C_ACCENT_HI = "#F0E6D3"   # light gold / cream — headings
C_MUTED     = "#A09B8C"   # muted text
C_SUCCESS   = "#0BC4E3"   # Hextech blue — success
C_ERROR     = "#C0392B"   # error red
C_BTN_BG    = "#1E2D3E"   # button resting face
C_BTN_HOV   = "#243447"   # button hover
C_BTN_GOLD  = "#C89B3C"   # gold button background for primary action


def run_gui():
    root = tk.Tk()
    root.title("LoL Token Remover")
    root.resizable(False, False)
    root.configure(bg=C_BG)

    # ── Geometry: center on screen ────────────────────────────────────────────
    WIN_W, WIN_H = 420, 340
    root.update_idletasks()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    root.geometry(f"{WIN_W}x{WIN_H}+{(sw-WIN_W)//2}+{(sh-WIN_H)//2}")

    # ── Fonts ─────────────────────────────────────────────────────────────────
    # Beaufort for LoL is a paid font; fall back gracefully to Georgia / system
    def best_font(preferred, fallback, size, weight="normal"):
        families = tkfont.families()
        fam = preferred if preferred in families else fallback
        return tkfont.Font(family=fam, size=size, weight=weight)

    f_title  = best_font("Georgia", "TkDefaultFont", 15, "bold")
    f_body   = best_font("Segoe UI", "TkDefaultFont", 10)
    f_small  = best_font("Segoe UI", "TkDefaultFont",  9)
    f_mono   = best_font("Consolas", "TkFixedFont",    9)
    f_btn    = best_font("Segoe UI", "TkDefaultFont", 11, "bold")

    # ── Gold separator ────────────────────────────────────────────────────────
    def gold_sep(parent, pady=(0, 0)):
        tk.Frame(parent, bg=C_BORDER, height=1).pack(fill="x", pady=pady)

    # ── Outer border frame ────────────────────────────────────────────────────
    outer = tk.Frame(root, bg=C_BORDER, padx=2, pady=2)
    outer.pack(fill="both", expand=True, padx=10, pady=10)
    inner = tk.Frame(outer, bg=C_BG)
    inner.pack(fill="both", expand=True)

    # ── Header ────────────────────────────────────────────────────────────────
    header = tk.Frame(inner, bg=C_SURFACE, padx=16, pady=12)
    header.pack(fill="x")

    tk.Label(
        header, text="⚔  LoL Token Remover",
        bg=C_SURFACE, fg=C_ACCENT_HI, font=f_title, anchor="w"
    ).pack(fill="x")
    tk.Label(
        header,
        text="Clears all Challenge Token slots from your profile banner.",
        bg=C_SURFACE, fg=C_MUTED, font=f_small, anchor="w", wraplength=380, justify="left"
    ).pack(fill="x", pady=(4, 0))

    gold_sep(inner)

    # ── Status area ───────────────────────────────────────────────────────────
    status_frame = tk.Frame(inner, bg=C_BG, padx=16, pady=10)
    status_frame.pack(fill="x")

    summoner_var = tk.StringVar(value="Searching for League client…")
    status_var   = tk.StringVar(value="")

    tk.Label(
        status_frame, textvariable=summoner_var,
        bg=C_BG, fg=C_ACCENT, font=f_body, anchor="w", wraplength=380, justify="left"
    ).pack(fill="x")

    status_lbl = tk.Label(
        status_frame, textvariable=status_var,
        bg=C_BG, fg=C_MUTED, font=f_small, anchor="w", wraplength=380, justify="left"
    )
    status_lbl.pack(fill="x", pady=(4, 0))

    gold_sep(inner, pady=(4, 0))

    # ── Button area ───────────────────────────────────────────────────────────
    btn_frame = tk.Frame(inner, bg=C_BG, padx=16, pady=14)
    btn_frame.pack(fill="x")

    # State shared in closure
    state = {"creds": None, "ready": False}

    def set_status(text, color=C_MUTED):
        status_var.set(text)
        status_lbl.configure(fg=color)
        root.update_idletasks()

    def set_summoner(text):
        summoner_var.set(text)
        root.update_idletasks()

    def on_remove():
        if not state["ready"] or not state["creds"]:
            set_status("Client not ready — check it is open and fully loaded.", C_ERROR)
            return
        remove_btn.configure(state="disabled", text="Removing…")
        set_status("Sending request to League client…", C_MUTED)
        root.update_idletasks()

        ok, msg = clear_tokens(state["creds"])

        if ok:
            remove_btn.configure(text="✓  Done!", bg=C_SUCCESS, fg=C_BG)
            set_status(
                "Tokens removed! Re-open your profile in the client to see the change.",
                C_SUCCESS
            )
        else:
            remove_btn.configure(state="normal", text="Remove All Tokens",
                                 bg=C_BTN_GOLD, fg=C_BG)
            set_status(msg, C_ERROR)

    remove_btn = tk.Button(
        btn_frame,
        text="Remove All Tokens",
        command=on_remove,
        bg=C_BTN_GOLD, fg=C_BG,
        activebackground=C_ACCENT_HI, activeforeground=C_BG,
        font=f_btn,
        relief="flat", cursor="hand2",
        padx=20, pady=8,
        state="disabled",
    )
    remove_btn.pack(fill="x")

    gold_sep(inner, pady=(4, 0))

    # ── Footer ────────────────────────────────────────────────────────────────
    footer = tk.Frame(inner, bg=C_BG, padx=16, pady=8)
    footer.pack(fill="x")
    tk.Label(
        footer,
        text="Not affiliated with Riot Games  •  All requests go to 127.0.0.1 only",
        bg=C_BG, fg=C_MUTED, font=f_small
    ).pack()

    # ── Initial client probe (after mainloop starts) ──────────────────────────
    def probe_client():
        creds = find_lcu_credentials()
        if creds:
            state["creds"] = creds
            name = get_summoner_name(creds)
            if name:
                set_summoner(f"Logged in as:  {name}")
            else:
                set_summoner("League client found.")
            set_status("Ready — click the button to clear your tokens.", C_ACCENT)
            state["ready"] = True
            remove_btn.configure(state="normal")
        else:
            set_summoner("League client not found.")
            set_status(
                "Open the League of Legends client and log in, then relaunch this tool.",
                C_ERROR
            )
            # Retry every 3 s
            root.after(3000, probe_client)

    root.after(300, probe_client)
    root.mainloop()


# ═════════════════════════════════════════════════════════════════════════════
#  CLI  (--cli flag or tkinter unavailable)
# ═════════════════════════════════════════════════════════════════════════════

def run_cli():
    print("=" * 50)
    print("  LoL Token Remover  v3.0.0  [CLI mode]")
    print("=" * 50)
    print()
    print("Searching for League client…")

    creds = find_lcu_credentials()
    if not creds:
        print("\n❌  League client not found.")
        print("    Open the client and log in, then run this script again.")
        print("    On Windows, try running as Administrator.")
        print("    On macOS, use: sudo python3 remove_lol_tokens.py --cli")
        sys.exit(1)

    print(f"✅  Client found on port {creds['port']}.")
    name = get_summoner_name(creds)
    if name:
        print(f"👤  Logged in as: {name}")
    print()

    ans = input("Remove ALL challenge tokens from your profile? (yes/no): ").strip().lower()
    if ans not in ("yes", "y"):
        print("Aborted — no changes made.")
        sys.exit(0)

    print()
    ok, msg = clear_tokens(creds)
    if ok:
        print(f"✅  {msg}")
        print("    Re-open your profile in the client to see the change.")
    else:
        print(f"❌  {msg}")
        sys.exit(1)


# ═════════════════════════════════════════════════════════════════════════════
#  Entry point
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Remove LoL challenge tokens from your profile.")
    parser.add_argument("--cli", action="store_true", help="Run in terminal mode (no GUI)")
    args = parser.parse_args()

    if args.cli or not HAS_TK:
        if not HAS_TK and not args.cli:
            print("Note: tkinter not available — falling back to CLI mode.")
        run_cli()
    else:
        run_gui()
