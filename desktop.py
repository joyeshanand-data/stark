# This file is part of the Stark split-up package. It continues on from
# state.py, and this one line below pulls in every name defined in every
# file before it in the chain - so this file has access to everything above
# it, exactly like it would if this were all still one big file.
from state import *

import runtime

# ---------- Google Search ----------
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GOOGLE_CSE_ID = os.environ.get("GOOGLE_CSE_ID", "")
GOOGLE_SEARCH_ENABLED = bool(GOOGLE_API_KEY and GOOGLE_CSE_ID)

SCRAPE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/115.0 Mobile Safari/537.36"
}


def google_scrape_search(query, num=8):
    try:
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}&num={num}"
        r = requests.get(url, headers=SCRAPE_HEADERS, timeout=8)
        html = r.text

        snippets = re.findall(r'<div class="BNeawe s3v9rd AP7Wnd">(.*?)</div>', html)
        snippets = [re.sub("<.*?>", "", s).strip() for s in snippets]
        snippets = [s for s in snippets if s]

        links = []
        for raw in re.findall(r'href="(/url\?q=[^"]+)"', html):
            m = re.search(r"/url\?q=([^&]+)", raw)
            if m:
                real = unquote(m.group(1))
                if real.startswith("http") and "google.com" not in real:
                    links.append(real)

        return snippets, links
    except Exception as e:
        print("Google scrape error:", e)
        return [], []

# ---------- Basic canned replies ----------
responses = {
    "hello": [f"Hi {USER_TITLE}!", f"Hey {USER_TITLE}! How can I help?"],
    "how are you": [f"Doing well, thanks for asking, {USER_TITLE}!", "I'm just code, but I'm running fine."],
    "bye": [f"Goodbye, {USER_TITLE}!", f"See you later, {USER_TITLE}!"],
}

GREETINGS = [
    f"Hey {USER_TITLE}! Good to see you, ask me anything, i will give you the answer.",
    f"Hi {USER_TITLE}! I'm up and ready when you are.",
    f"Hello {USER_TITLE}! Let's find something interesting today.",
]

WAKE_PHRASES = ("hello stark", "hey stark", "hi stark", "ok stark", "okay stark")
WAKE_GREETINGS = [
    f"Yes, {USER_TITLE}?", f"I'm here, {USER_TITLE}.",
    f"Right here, {USER_TITLE} - what do you need?", f"Online and listening, {USER_TITLE}.",
]

_ORB_WAKE_LOCK = threading.Lock()
_orb_wake_until = 0.0


def trigger_orb_wake(duration=5.0):
    global _orb_wake_until
    with _ORB_WAKE_LOCK:
        _orb_wake_until = time.time() + duration


def orb_is_awake():
    with _ORB_WAKE_LOCK:
        return time.time() < _orb_wake_until

BAD_IMAGE_HINTS = ("commons-logo", "wiktionary", "wikisource",
                    "question_book", "edit-icon", "ambox", "folder", ".svg")

IMAGE_KEYWORDS = ("image", "picture", "photo", "show me", "pic of")


# ---------- Find Chrome for a real fullscreen "app" window ----------
def find_chrome_path():
    if sys.platform.startswith("win"):
        paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
    elif sys.platform == "darwin":
        paths = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    else:
        paths = ["/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium-browser"]
    return next((p for p in paths if os.path.exists(p)), None)


CHROME_PATH = find_chrome_path()
CHROME_AVAILABLE = CHROME_PATH is not None
if CHROME_AVAILABLE:
    webbrowser.register("chrome", None, webbrowser.BackgroundBrowser(CHROME_PATH))


def open_in_chrome(url):
    # Local import: see the matching comment in automation.py for why this
    # isn't a top-of-file or blanket "import *" instead.
    from app_launcher import minimize_dashboard
    minimize_dashboard()
    if CHROME_AVAILABLE:
        webbrowser.get("chrome").open_new_tab(url)
    else:
        webbrowser.open_new_tab(url)


def launch_dashboard(url):
    if CHROME_PATH:
        # --ignore-certificate-errors + --allow-insecure-localhost: Stark's
        # HTTPS cert is self-signed (made by Stark itself, not a public
        # authority), so without these flags Chrome shows a full security
        # warning page instead of the dashboard - and in --kiosk mode
        # there's no visible browser UI to click "Proceed anyway" on, so it
        # just looks like a blank/frozen window with no way forward. These
        # flags tell Chrome to trust it up front instead, only for this
        # dedicated app window - not your regular browsing.
        subprocess.Popen([CHROME_PATH, "--kiosk", "--ignore-certificate-errors",
                           "--allow-insecure-localhost", f"--app={url}"])
    else:
        webbrowser.open(url)
        print("(Tip: Chrome wasn't found for true kiosk mode - press F11 in your browser for fullscreen. "
              "Since Stark's HTTPS certificate is self-signed, your browser will show a security warning "
              "the first time - click 'Advanced' then 'Proceed anyway' (or 'visit this website'); this is "
              "expected and safe on your own machine.)")


def launch_mini_widget(port):
    url = f"{runtime.SERVER_SCHEME}://127.0.0.1:{port}/mini"
    if CHROME_PATH:
        subprocess.Popen([CHROME_PATH, f"--app={url}", "--window-size=380,640",
                           "--ignore-certificate-errors", "--allow-insecure-localhost"])
    else:
        webbrowser.open(url)
        print("(Tip: Chrome wasn't found, so the mini widget opened in a normal browser tab/window instead. "
              "Resize that window small and it'll behave the same way.)")