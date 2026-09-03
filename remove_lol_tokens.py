"""
╔══════════════════════════════════════════╗
║   LoL Token Remover  —  v3.0.0          ║
║   Removes all Challenge Tokens from     ║
║   your League of Legends profile.       ║
╚══════════════════════════════════════════╝

HOW THIS SCRIPT WORKS:
  The League of Legends client secretly runs a mini web server on your own
  computer while it's open. This is called the "LCU API". It's how the
  client's own different windows talk to each other internally.

  This script:
    1. Finds the League client running on your PC.
    2. Reads its secret password and port number from its process info.
    3. Sends it a request to clear your challenge tokens — the exact same
       request the client sends itself when you swap tokens normally.

Zero extra installs needed beyond Python 3.8+.
tkinter (the GUI library) comes bundled with the standard Python installer.

Run:
    python remove_lol_tokens.py          → opens the GUI window
    python remove_lol_tokens.py --cli    → runs in the terminal instead
"""

# ── Standard library imports ──────────────────────────────────────────────────
# These come built into Python — no installation needed.
import argparse   # lets us read command-line flags like --cli
import base64     # used to encode the password in the format the API expects
import re         # "regular expressions" — used to search text for patterns
import sys        # lets us exit the script with an error code if something goes wrong

# ── Optional GUI import ───────────────────────────────────────────────────────
# tkinter is Python's built-in GUI toolkit. We wrap this in try/except because
# some non-standard Python builds (e.g. certain Linux installs) omit it.
# HAS_TK tracks whether we successfully imported it so we can decide later
# whether to show the window or fall back to terminal mode.
try:
    import tkinter as tk
    from tkinter import font as tkfont  # lets us define custom text styles
    HAS_TK = True
except ImportError:
    HAS_TK = False

# ── Third-party imports (require: pip install psutil requests urllib3) ─────────
# We wrap this in try/except too so we can show a helpful message instead of
# a confusing Python traceback if someone forgot to install them.
try:
    import psutil    # reads information about running processes on your PC
    import requests  # sends HTTP/HTTPS requests (like a browser, but in code)
    import urllib3   # the underlying HTTP library — we use it only to silence
                     # a harmless warning about the client's self-signed certificate
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    print("Missing dependencies. Run:  pip install psutil requests urllib3")
    sys.exit(1)


# ═════════════════════════════════════════════════════════════════════════════
#  LCU CORE
#  These three functions do the actual work. They're shared by both the GUI
#  and the CLI so we only have to write the logic once.
# ═════════════════════════════════════════════════════════════════════════════

def find_lcu_credentials():
    """
    Scans running programs on your PC to find LeagueClientUx.exe.
    When found, it reads two values from the process's command-line arguments:
      - port:  the random port number the client's API is listening on
      - token: a randomly-generated password the client creates at startup

    These change every time you launch the game, which is why we read them
    live rather than hardcoding them.

    Returns a dict like {"port": "58392", "token": "abc123..."}, or None
    if the League client isn't running.
    """
    # psutil.process_iter() loops over every process currently running.
    # We ask for "name" (the exe name) and "cmdline" (the full launch command).
    for proc in psutil.process_iter(["name", "cmdline"]):
        try:
            name = proc.info["name"] or ""

            # Skip any process that isn't the League client — there are hundreds
            # of other processes running at any given time, so this filters fast.
            if "LeagueClientUx" not in name:
                continue

            # Join the list of command-line arguments into one big string so we
            # can search it with regex. It looks something like:
            #   "LeagueClientUx.exe --app-port=58392 --remoting-auth-token=abc123 ..."
            cmdline = " ".join(proc.info["cmdline"] or [])

            # re.search() scans the string for a pattern.
            # (\d+) means "capture one or more digits" — that's our port number.
            port_m  = re.search(r"--app-port=(\d+)", cmdline)

            # ([\w-]+) means "capture word characters and hyphens" — that's the token.
            token_m = re.search(r"--remoting-auth-token=([\w-]+)", cmdline)

            # If we found both values, we're done — return them as a dictionary.
            if port_m and token_m:
                return {"port": port_m.group(1), "token": token_m.group(1)}

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # NoSuchProcess: the process ended between our scan and our read — safe to skip.
            # AccessDenied:  we don't have permission to read this process — also skip.
            continue

    # If we finished the loop without finding the client, return None.
    return None


def lcu_request(creds, method, endpoint, body=None):
    """
    Sends one HTTPS request to the League client's local API.

    Arguments:
      creds    — the dict from find_lcu_credentials() with "port" and "token"
      method   — the HTTP verb: "GET", "POST", or "PUT"
      endpoint — the API path, e.g. "/lol-summoner/v1/current-summoner"
      body     — optional Python dict that gets sent as JSON in the request body

    The League client uses "Basic Auth", which is a standard way of sending
    a username:password. Here the username is always "riot" and the password
    is the random token. Basic Auth requires the credentials to be Base64
    encoded — that's what the base64 line does.

    verify=False tells the requests library not to validate the SSL certificate.
    The client uses a self-signed cert (not issued by a real certificate authority),
    which would normally trigger a security error. Since we're talking to our own
    machine on 127.0.0.1 this is completely safe to ignore.
    """
    # Build the Authorization header value.
    # base64 encodes "riot:TOKEN" → "cmludDpUT0tFTg==" (or similar)
    auth = base64.b64encode(f"riot:{creds['token']}".encode()).decode()

    # The full URL, e.g. "https://127.0.0.1:58392/lol-summoner/v1/current-summoner"
    # 127.0.0.1 always means "this computer" — the request never leaves your machine.
    url = f"https://127.0.0.1:{creds['port']}{endpoint}"

    headers = {
        "Authorization": f"Basic {auth}",  # our encoded credentials
        "Content-Type":  "application/json",  # we're sending JSON
        "Accept":        "application/json",  # we want JSON back
    }

    return requests.request(
        method, url,
        headers=headers,
        json=body,      # requests automatically converts the dict to a JSON string
        verify=False,   # skip SSL cert validation (safe for localhost)
        timeout=10,     # give up after 10 seconds if the client doesn't respond
    )


def get_summoner_name(creds):
    """
    Asks the League client for the currently logged-in player's name.
    This is only used to show a friendly "Logged in as: YourName" message —
    it has no effect on the token removal itself.

    Returns the name as a string, or None if the request fails for any reason.
    """
    try:
        r = lcu_request(creds, "GET", "/lol-summoner/v1/current-summoner")
        if r.status_code == 200:  # 200 means "OK" in HTTP
            data = r.json()  # parse the JSON response into a Python dict
            # Try "displayName" first (older accounts), then "gameName" (Riot ID accounts)
            return data.get("displayName") or data.get("gameName")
    except Exception:
        # If anything goes wrong (network error, JSON parse error, etc.),
        # just return None — the name display is cosmetic and not worth crashing over.
        pass
    return None


def clear_tokens(creds):
    """
    The main action: tells the League client to remove all challenge tokens.

    We try two different API endpoints in order. If the first works, great.
    If not, we try the second. If both fail, we return a helpful error message.

    Returns a tuple: (success: bool, message: str)
    The caller checks the bool to know whether it worked.
    """

    # ── Method 1: Challenges API ──────────────────────────────────────────────
    # This is the correct, purpose-built endpoint. Sending an empty list for
    # "challengeIds" tells the client: "I have no challenge tokens equipped."
    # The client then clears all three slots. This mirrors exactly what the
    # client does internally when you manually change your tokens.
    try:
        r = lcu_request(
            creds, "POST",
            "/lol-challenges/v1/update-player-preferences/",
            body={"challengeIds": []},  # empty list = no tokens equipped
        )
        # HTTP 200/201/204 all mean success (the exact code varies by endpoint)
        if r.status_code in (200, 201, 204):
            return True, "All tokens removed via Challenges API."
    except Exception:
        # If the request itself fails (e.g. connection refused), fall through
        # to the next method rather than crashing.
        pass

    # ── Method 2: Regalia API (fallback) ─────────────────────────────────────
    # "Regalia" is the system that controls the decorative elements on your
    # profile banner (rank border, crest, etc.). Setting crestType to "none"
    # hides the token display. We first GET the current settings so we can
    # preserve everything else (like your rank banner style) and only change
    # the crest/token part.
    try:
        # Step 1: fetch what's currently set
        get_r = lcu_request(creds, "GET", "/lol-regalia/v2/current-summoner/regalia")
        if get_r.status_code == 200:
            current = get_r.json()

            # Step 2: build the update, keeping bannerType intact
            payload = {
                "crestType":             "none",  # "none" hides all token slots
                "bannerType":            current.get("bannerType", "lastSeasonHighestRank"),
                "selectedPrestigeCrest": 0,       # 0 = no prestige crest selected
            }

            # Step 3: send the update back
            put_r = lcu_request(
                creds, "PUT",
                "/lol-regalia/v2/current-summoner/regalia",
                body=payload,
            )
            if put_r.status_code in (200, 201, 204):
                return True, "Tokens cleared via Regalia API (fallback)."
    except Exception:
        pass

    # ── Both methods failed ───────────────────────────────────────────────────
    # Return False and a multi-line message explaining what to try next.
    return False, (
        "Both API methods failed.\n\n"
        "Make sure the League client is fully loaded (you can see the home screen), "
        "then try again.\n\n"
        "On Windows you may need to run this as Administrator.\n"
        "On macOS run with: sudo python3 remove_lol_tokens.py"
    )


# ═════════════════════════════════════════════════════════════════════════════
#  GUI
#  Everything below here is about drawing the window and reacting to clicks.
#  It uses tkinter, Python's built-in GUI toolkit.
# ═════════════════════════════════════════════════════════════════════════════

# Color palette — Hextech-inspired (League of Legends' visual theme).
# Colors are defined as hex strings, e.g. "#010A13" = very dark blue-black.
# Naming them as constants here means we only have to change a color in one
# place if we ever want to update the theme.
C_BG        = "#010A13"   # main window background — near-black blue-black
C_SURFACE   = "#0A1628"   # slightly lighter surface for the header panel
C_BORDER    = "#785A28"   # dark gold — used for the window border and dividers
C_ACCENT    = "#C89B3C"   # bright Hextech gold — used for highlights
C_ACCENT_HI = "#F0E6D3"   # lightest gold/cream — used for the title text
C_MUTED     = "#A09B8C"   # grey-beige — used for secondary/hint text
C_SUCCESS   = "#0BC4E3"   # Hextech blue — shown when the operation succeeds
C_ERROR     = "#C0392B"   # red — shown when something goes wrong
C_BTN_BG    = "#1E2D3E"   # button background (unused directly, kept for reference)
C_BTN_HOV   = "#243447"   # button hover color (unused directly, kept for reference)
C_BTN_GOLD  = "#C89B3C"   # gold — the primary button color


def run_gui():
    """
    Builds and displays the GUI window.

    tkinter works by creating a "root" window, adding widgets (labels, buttons,
    frames) to it, and then entering a "mainloop" — an infinite loop that waits
    for user actions (clicks, key presses) and redraws the window as needed.
    """

    # ── Create the root window ────────────────────────────────────────────────
    root = tk.Tk()
    root.title("LoL Token Remover")
    root.resizable(False, False)        # prevent the user from resizing the window
    root.configure(bg=C_BG)            # set the window's background color

    # ── Center the window on the screen ──────────────────────────────────────
    WIN_W, WIN_H = 420, 340             # window dimensions in pixels
    root.update_idletasks()             # force tkinter to compute its internal layout
    sw = root.winfo_screenwidth()       # get the screen's total width
    sh = root.winfo_screenheight()      # get the screen's total height
    # geometry() positions the window: "WIDTHxHEIGHT+LEFT+TOP"
    # We calculate LEFT and TOP so the window lands in the middle of the screen.
    root.geometry(f"{WIN_W}x{WIN_H}+{(sw-WIN_W)//2}+{(sh-WIN_H)//2}")

    # ── Font setup ────────────────────────────────────────────────────────────
    # We define a helper that tries to use a preferred font and falls back to a
    # safe default if the preferred one isn't installed on this computer.
    def best_font(preferred, fallback, size, weight="normal"):
        families = tkfont.families()  # list of all fonts installed on the system
        fam = preferred if preferred in families else fallback
        return tkfont.Font(family=fam, size=size, weight=weight)

    f_title = best_font("Georgia",  "TkDefaultFont", 15, "bold")  # window title
    f_body  = best_font("Segoe UI", "TkDefaultFont", 10)           # summoner name
    f_small = best_font("Segoe UI", "TkDefaultFont",  9)           # hint/status text
    f_btn   = best_font("Segoe UI", "TkDefaultFont", 11, "bold")   # button label

    # ── Helper: draw a thin gold horizontal line ──────────────────────────────
    # We use this as a visual divider between sections of the window.
    # A 1-pixel-tall Frame filled with the border color looks like a ruled line.
    def gold_sep(parent, pady=(0, 0)):
        tk.Frame(parent, bg=C_BORDER, height=1).pack(fill="x", pady=pady)

    # ── Outer gold border ─────────────────────────────────────────────────────
    # To create a colored border around the whole window we nest two Frames.
    # The outer Frame is the gold color with 2px padding all around.
    # The inner Frame sits inside it with the dark background color.
    # This creates the illusion of a gold border.
    outer = tk.Frame(root, bg=C_BORDER, padx=2, pady=2)
    outer.pack(fill="both", expand=True, padx=10, pady=10)
    inner = tk.Frame(outer, bg=C_BG)
    inner.pack(fill="both", expand=True)

    # ── Header section ────────────────────────────────────────────────────────
    # A slightly lighter background panel containing the title and subtitle.
    header = tk.Frame(inner, bg=C_SURFACE, padx=16, pady=12)
    header.pack(fill="x")   # fill="x" means stretch to the full width

    tk.Label(
        header, text="⚔  LoL Token Remover",
        bg=C_SURFACE, fg=C_ACCENT_HI, font=f_title, anchor="w"  # anchor="w" = left-align
    ).pack(fill="x")

    tk.Label(
        header,
        text="Clears all Challenge Token slots from your profile banner.",
        bg=C_SURFACE, fg=C_MUTED, font=f_small,
        anchor="w", wraplength=380, justify="left"   # wraplength stops text going off screen
    ).pack(fill="x", pady=(4, 0))   # pady=(top, bottom) adds vertical space

    gold_sep(inner)   # dividing line between header and status area

    # ── Status area ───────────────────────────────────────────────────────────
    # This section shows two live-updating lines of text:
    #   - summoner_var: the logged-in player's name (or "Searching…")
    #   - status_var:   a short hint or result message
    #
    # tk.StringVar is a special tkinter variable — when its value changes,
    # any Label bound to it automatically redraws with the new text.
    status_frame = tk.Frame(inner, bg=C_BG, padx=16, pady=10)
    status_frame.pack(fill="x")

    summoner_var = tk.StringVar(value="Searching for League client…")
    status_var   = tk.StringVar(value="")

    # Bind the summoner label to summoner_var — it updates automatically.
    tk.Label(
        status_frame, textvariable=summoner_var,
        bg=C_BG, fg=C_ACCENT, font=f_body, anchor="w", wraplength=380, justify="left"
    ).pack(fill="x")

    # We keep a reference to status_lbl because we need to change its color
    # later (green for success, red for error, grey for neutral).
    status_lbl = tk.Label(
        status_frame, textvariable=status_var,
        bg=C_BG, fg=C_MUTED, font=f_small, anchor="w", wraplength=380, justify="left"
    )
    status_lbl.pack(fill="x", pady=(4, 0))

    gold_sep(inner, pady=(4, 0))

    # ── Button area ───────────────────────────────────────────────────────────
    btn_frame = tk.Frame(inner, bg=C_BG, padx=16, pady=14)
    btn_frame.pack(fill="x")

    # "state" is a dictionary used as a simple shared memory between the
    # inner functions below. Python closures can read outer variables but
    # can't reassign them directly; using a dict lets us get around that.
    state = {"creds": None, "ready": False}

    # ── Inner helper functions ─────────────────────────────────────────────────
    # These are defined inside run_gui() so they can access the widgets above.

    def set_status(text, color=C_MUTED):
        """Update the status label text and color, then refresh the window."""
        status_var.set(text)
        status_lbl.configure(fg=color)
        root.update_idletasks()   # force an immediate repaint so the user sees the change

    def set_summoner(text):
        """Update the summoner name label, then refresh the window."""
        summoner_var.set(text)
        root.update_idletasks()

    def on_remove():
        """
        Called when the user clicks the "Remove All Tokens" button.
        Validates state, shows progress feedback, calls clear_tokens(),
        then shows the result.
        """
        # Guard: don't do anything if we haven't found the client yet.
        if not state["ready"] or not state["creds"]:
            set_status("Client not ready — check it is open and fully loaded.", C_ERROR)
            return

        # Disable the button while the request is in flight so the user
        # can't click it multiple times.
        remove_btn.configure(state="disabled", text="Removing…")
        set_status("Sending request to League client…", C_MUTED)
        root.update_idletasks()  # repaint before we block on the network call

        # Do the actual work — this call may take a moment.
        ok, msg = clear_tokens(state["creds"])

        if ok:
            # Turn the button into a permanent success indicator.
            remove_btn.configure(text="✓  Done!", bg=C_SUCCESS, fg=C_BG)
            set_status(
                "Tokens removed! Re-open your profile in the client to see the change.",
                C_SUCCESS
            )
        else:
            # Re-enable the button so the user can try again.
            remove_btn.configure(state="normal", text="Remove All Tokens",
                                 bg=C_BTN_GOLD, fg=C_BG)
            set_status(msg, C_ERROR)

    # ── The button itself ─────────────────────────────────────────────────────
    # state="disabled" means it's greyed out and unclickable at first.
    # probe_client() (below) enables it once the League client is found.
    remove_btn = tk.Button(
        btn_frame,
        text="Remove All Tokens",
        command=on_remove,               # the function to call when clicked
        bg=C_BTN_GOLD, fg=C_BG,         # gold background, dark text
        activebackground=C_ACCENT_HI,   # slightly lighter when held down
        activeforeground=C_BG,
        font=f_btn,
        relief="flat",                   # no 3D border effect — flatter look
        cursor="hand2",                  # show a pointer cursor on hover
        padx=20, pady=8,                 # internal padding inside the button
        state="disabled",                # start disabled until client is found
    )
    remove_btn.pack(fill="x")   # stretch the button to the full width

    gold_sep(inner, pady=(4, 0))

    # ── Footer ────────────────────────────────────────────────────────────────
    footer = tk.Frame(inner, bg=C_BG, padx=16, pady=8)
    footer.pack(fill="x")
    tk.Label(
        footer,
        text="Not affiliated with Riot Games  •  All requests go to 127.0.0.1 only",
        bg=C_BG, fg=C_MUTED, font=f_small
    ).pack()

    # ── Client detection loop ─────────────────────────────────────────────────
    def probe_client():
        """
        Checks whether the League client is running and updates the UI.
        If the client isn't found yet, this function schedules itself to
        run again in 3 seconds using root.after() — so it keeps checking
        in the background without freezing the window.
        """
        creds = find_lcu_credentials()

        if creds:
            # Client found — save credentials and enable the button.
            state["creds"] = creds
            name = get_summoner_name(creds)
            if name:
                set_summoner(f"Logged in as:  {name}")
            else:
                set_summoner("League client found.")
            set_status("Ready — click the button to clear your tokens.", C_ACCENT)
            state["ready"] = True
            remove_btn.configure(state="normal")   # unlock the button
        else:
            # Client not found yet — update the message and try again shortly.
            set_summoner("League client not found.")
            set_status(
                "Open the League of Legends client and log in, then relaunch this tool.",
                C_ERROR
            )
            # root.after(ms, func) schedules func() to run after ms milliseconds.
            # This is non-blocking — the window stays responsive while waiting.
            root.after(3000, probe_client)

    # Schedule the first probe 300ms after the window opens.
    # We delay it slightly so the window has time to draw before we start work.
    root.after(300, probe_client)

    # ── Start the event loop ──────────────────────────────────────────────────
    # mainloop() hands control to tkinter. It sits here processing window events
    # (repaints, clicks, timers) until the user closes the window.
    root.mainloop()


# ═════════════════════════════════════════════════════════════════════════════
#  CLI MODE
#  A simple terminal version of the same logic, for users who prefer it or
#  whose Python installation doesn't have tkinter.
# ═════════════════════════════════════════════════════════════════════════════

def run_cli():
    """
    Runs the token remover as an interactive terminal session.
    Prints status messages and asks for a yes/no confirmation before acting.
    """
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
        sys.exit(1)   # exit with code 1 to signal failure to the terminal

    print(f"✅  Client found on port {creds['port']}.")
    name = get_summoner_name(creds)
    if name:
        print(f"👤  Logged in as: {name}")
    print()

    # Ask before doing anything — good practice for any destructive-ish action.
    ans = input("Remove ALL challenge tokens from your profile? (yes/no): ").strip().lower()
    if ans not in ("yes", "y"):
        print("Aborted — no changes made.")
        sys.exit(0)   # exit with code 0 = clean exit, user chose to abort

    print()
    ok, msg = clear_tokens(creds)
    if ok:
        print(f"✅  {msg}")
        print("    Re-open your profile in the client to see the change.")
    else:
        print(f"❌  {msg}")
        sys.exit(1)


# ═════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
#  Python runs this block when you execute the script directly.
#  The "if __name__ == '__main__'" guard means this block is skipped if someone
#  imports this file as a module from another script.
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # argparse handles reading command-line flags.
    # After calling parse_args(), args.cli is True if the user passed --cli,
    # and False otherwise.
    parser = argparse.ArgumentParser(description="Remove LoL challenge tokens from your profile.")
    parser.add_argument("--cli", action="store_true", help="Run in terminal mode (no GUI)")
    args = parser.parse_args()

    # Decide which mode to run:
    #   - If --cli was passed, or if tkinter isn't available → terminal mode
    #   - Otherwise → GUI mode
    if args.cli or not HAS_TK:
        if not HAS_TK and not args.cli:
            # Inform the user why we're not showing a window
            print("Note: tkinter not available — falling back to CLI mode.")
        run_cli()
    else:
        run_gui()
