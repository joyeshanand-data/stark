# This file is part of the Stark split-up package. It continues on from
# app_launcher.py, and this one line below pulls in every name defined in every
# file before it in the chain - so this file has access to everything above
# it, exactly like it would if this were all still one big file.
from app_launcher import *
from app_launcher import _play_or_search_youtube

import runtime

# ---------- In-app automation (typing, clicking, hotkeys) ----------
# Optional - only used if pyautogui is installed, never required. Lets Stark
# actually operate other apps once they're open/focused: type text, hit keys,
# click, scroll. No API key needed, just local OS-level input simulation.
try:
    import pyautogui
    pyautogui.FAILSAFE = True  # snap mouse to a screen corner to abort, same as pyautogui's own safety net
    _AUTOMATION_AVAILABLE = True
except ImportError:
    pyautogui = None
    _AUTOMATION_AVAILABLE = False

_MODIFIER_KEY = "command" if sys.platform == "darwin" else "ctrl"

KEY_ALIASES = {
    "enter": "enter", "return": "enter", "tab": "tab", "escape": "esc", "esc": "esc",
    "space": "space", "spacebar": "space", "backspace": "backspace", "delete": "delete",
    "up": "up", "down": "down", "left": "left", "right": "right",
    "home": "home", "end": "end", "page up": "pageup", "page down": "pagedown",
}

AUTOMATION_PHRASES = {
    "select all": lambda: pyautogui.hotkey(_MODIFIER_KEY, "a"),
    "copy": lambda: pyautogui.hotkey(_MODIFIER_KEY, "c"),
    "paste": lambda: pyautogui.hotkey(_MODIFIER_KEY, "v"),
    "cut": lambda: pyautogui.hotkey(_MODIFIER_KEY, "x"),
    "undo": lambda: pyautogui.hotkey(_MODIFIER_KEY, "z"),
    "redo": lambda: pyautogui.hotkey(_MODIFIER_KEY, "y"),
    "save": lambda: pyautogui.hotkey(_MODIFIER_KEY, "s"),
    "switch window": lambda: pyautogui.hotkey("alt", "tab") if sys.platform != "darwin" else pyautogui.hotkey("command", "tab"),
    "alt tab": lambda: pyautogui.hotkey("alt", "tab"),
    "click": lambda: pyautogui.click(),
    "double click": lambda: pyautogui.doubleClick(),
    "right click": lambda: pyautogui.rightClick(),
}

# "Write it here" style commands: types Stark's most recent reply directly into
# whichever app currently has keyboard focus (e.g. say something to Stark,
# click into Notepad/an email/anything else, then say one of these) - the
# core of the floating-orb "do what I say in whatever app I'm in" workflow.
WRITE_HERE_PHRASES = (
    "write it here", "write this here", "put it here", "put this here",
    "type it here", "type this here", "paste it here", "paste this here",
)


def _get_last_answer_text():
    with STATE_LOCK:
        return (state.get("answer") or "").strip()


def try_handle_automation_command(low_text):
    """Returns a reply string if this looked like an in-app automation command,
    else None. Requires pyautogui - gives a clear install hint if it's not
    available instead of silently doing nothing."""
    is_automation_attempt = (
        low_text in AUTOMATION_PHRASES
        or low_text in WRITE_HERE_PHRASES
        or low_text.startswith("type ")
        or re.match(r"^press \w[\w ]*$", low_text)
        or re.match(r"^click at \d+ \d+$", low_text)
        or re.match(r"^move mouse to \d+ \d+$", low_text)
        or re.match(r"^scroll (up|down)(?: \d+)?$", low_text)
    )
    if not is_automation_attempt:
        return None

    if not _AUTOMATION_AVAILABLE:
        return (f"I'd need pyautogui installed for that, {USER_TITLE} - run "
                f"'pip install pyautogui --break-system-packages' and restart me.")

    try:
        if low_text in WRITE_HERE_PHRASES:
            last_answer = _get_last_answer_text()
            if not last_answer:
                return f"I don't have anything to write yet, {USER_TITLE} - ask me something first."
            time.sleep(0.4)  # brief pause so focus has settled on the target app before typing
            pyautogui.write(last_answer, interval=0.01)
            return f"Wrote it in, {USER_TITLE}."

        if low_text in AUTOMATION_PHRASES:
            AUTOMATION_PHRASES[low_text]()
            return f"Done, {USER_TITLE}."

        if low_text.startswith("type "):
            text_to_type = low_text[5:]
            pyautogui.write(text_to_type, interval=0.02)
            return f"Typed it, {USER_TITLE}."

        m = re.match(r"^press (\w[\w ]*)$", low_text)
        if m:
            key_name = m.group(1).strip()
            key = KEY_ALIASES.get(key_name, key_name)
            pyautogui.press(key)
            return f"Pressed {key_name}, {USER_TITLE}."

        m = re.match(r"^click at (\d+) (\d+)$", low_text)
        if m:
            pyautogui.click(int(m.group(1)), int(m.group(2)))
            return f"Clicked at ({m.group(1)}, {m.group(2)})."

        m = re.match(r"^move mouse to (\d+) (\d+)$", low_text)
        if m:
            pyautogui.moveTo(int(m.group(1)), int(m.group(2)))
            return f"Moved the mouse to ({m.group(1)}, {m.group(2)})."

        m = re.match(r"^scroll (up|down)(?: (\d+))?$", low_text)
        if m:
            direction, amount = m.group(1), int(m.group(2) or 5)
            pyautogui.scroll(amount * 100 if direction == "up" else -amount * 100)
            return f"Scrolled {direction}, {USER_TITLE}."
    except Exception as e:
        return f"Automation error: {e}"

    return None


def try_handle_command(text):
    t = text.lower().strip()

    if t in UPDATE_PHRASES:
        return build_full_update()

    automation_reply = try_handle_automation_command(t)
    if automation_reply:
        return automation_reply

    if t in ("refresh apps", "rescan apps", "reindex apps", "refresh app list"):
        threading.Thread(target=lambda: build_app_index(force=True), daemon=True).start()
        return f"Rescanning installed apps in the background, {USER_TITLE}."

    if t in ("open mini", "mini mode", "open mini widget", "open mini window", "little screen", "pop out mini"):
        launch_mini_widget(runtime.SERVER_PORT)
        return "Opening the mini widget in its own little window."

    # Local import (not at module top): files.py transitively depends on
    # this file loading first, so importing it up at the top - or via a
    # blanket "from files import *" down here - can silently pull in an
    # incomplete copy of files.py depending on which module happens to
    # trigger the load first. A local import only runs the first time this
    # line actually executes, by which point every file has already
    # finished loading for real, so there's no ambiguity.
    from files import try_handle_file_command
    file_reply = try_handle_file_command(text)
    if file_reply:
        return file_reply

    if t.startswith("download "):
        query = t[len("download "):].strip()
        if not query:
            return "Tell me what to download, e.g. 'download python logo image'."
        link = find_download_url(query)
        if not link:
            return f"I couldn't find anything to download for '{query}'."
        saved_path = download_file(link)
        if saved_path:
            return f"Downloaded '{os.path.basename(saved_path)}' to {DOWNLOAD_DIR}"
        return f"Found a link but couldn't download it: {link}"

    if "youtube" in t and any(w in t for w in ("play", "search", "find", "open", "watch")):
        query = t
        for phrase in ("search youtube for", "search for", "on youtube", "youtube",
                       "open", "play", "search", "find", "watch", "for"):
            query = re.sub(rf"\b{re.escape(phrase)}\b", "", query)
        query = re.sub(r"\s+", " ", query).strip()
        if query:
            return _play_or_search_youtube(query)
        open_in_chrome(APP_LINKS["youtube"])
        return "Opening YouTube."

    if t.startswith("play "):
        query = t[len("play "):].strip()
        if query:
            return _play_or_search_youtube(query)

    if "search google for" in t or t.startswith("google "):
        query = re.sub(r"\bsearch google for\b|\bgoogle\b", "", t)
        query = re.sub(r"\s+", " ", query).strip()
        if query:
            url = "https://www.google.com/search?q=" + query.replace(" ", "+")
            open_in_chrome(url)
            return f"Searching Google for '{query}'."

    if t.startswith("open "):
        target = t[5:].strip()
        for key, url in APP_LINKS.items():
            if key in target:
                open_in_chrome(url)
                return f"Opening {key.capitalize()}."
        if open_app(target):
            return f"Trying to open {target}."
        return f"I couldn't open {target}."

    return None