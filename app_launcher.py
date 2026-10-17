# This file is part of the Stark split-up package. It continues on from
# desktop.py, and this one line below pulls in every name defined in every
# file before it in the chain - so this file has access to everything above
# it, exactly like it would if this were all still one big file.
from desktop import *

# ---------- Minimize the dashboard window whenever something else opens ----------
DASHBOARD_WINDOW_TITLES = ("STARK", "Stark Mini")


def _minimize_windows():
    try:
        import ctypes
        user32 = ctypes.windll.user32
        titles = []

        def _enum_handler(hwnd, _lparam):
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if any(t.lower() in buf.value.lower() for t in DASHBOARD_WINDOW_TITLES):
                titles.append(hwnd)
            return True

        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        user32.EnumWindows(EnumWindowsProc(_enum_handler), 0)
        for hwnd in titles:
            user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
    except Exception as e:
        print("Minimize (Windows) error:", e)


def _minimize_macos():
    try:
        script = (
            'tell application "Google Chrome"\n'
            '  repeat with w in windows\n'
            '    if title of w contains "STARK" then set minimized of w to true\n'
            '  end repeat\n'
            'end tell'
        )
        subprocess.run(["osascript", "-e", script], timeout=5,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print("Minimize (macOS) error:", e)


def _minimize_linux():
    try:
        for title in DASHBOARD_WINDOW_TITLES:
            subprocess.run(["wmctrl", "-r", title, "-b", "add,hidden"], timeout=5,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print("Minimize (Linux) error:", e)


def minimize_dashboard():
    def _run():
        # Local import (not at module top) on purpose: system_tools.py
        # itself transitively depends on this file loading first, so
        # importing it up at the top would create a circular import.
        # A local import here only runs the first time minimize_dashboard()
        # is actually CALLED, by which point every file has already
        # finished loading, so there's no cycle.
        from system_tools import _current_platform_key
        plat = _current_platform_key()
        if plat == "win":
            _minimize_windows()
        elif plat == "darwin":
            _minimize_macos()
        else:
            _minimize_linux()
    threading.Thread(target=_run, daemon=True).start()


# ---------- Generic desktop app launcher ----------
CUSTOM_APP_PATHS = {
    # "photoshop": r"C:\Program Files\Adobe\Adobe Photoshop 2025\Photoshop.exe",
}


# ---------- Universal app launcher ----------
# Instead of guessing a shell command from the spoken name (which only works if
# the app happens to be registered on PATH), this builds a real index of every
# app actually installed on the machine - Start Menu shortcuts on Windows,
# .app bundles on macOS, .desktop launchers on Linux - and fuzzy-matches
# against that. Massively more reliable for "open <anything>" than the old
# single shell-guess approach, and needs no extra libraries.
_APP_INDEX_LOCK = threading.Lock()
_app_index = {}  # {lowercase display name: launch target}
_app_index_built_at = 0


def _index_windows_apps():
    import glob
    index = {}
    search_roots = [
        os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), r"Microsoft\Windows\Start Menu\Programs"),
        os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs") if os.environ.get("APPDATA") else None,
    ]
    for root in filter(None, search_roots):
        if not os.path.isdir(root):
            continue
        for path in glob.glob(os.path.join(root, "**", "*.lnk"), recursive=True):
            name = os.path.splitext(os.path.basename(path))[0].strip().lower()
            if name and name not in index:
                index[name] = path  # os.startfile() opens .lnk shortcuts directly, no resolving needed
    return index


def _index_macos_apps():
    index = {}
    for root in ("/Applications", os.path.expanduser("~/Applications")):
        if not os.path.isdir(root):
            continue
        for entry in os.listdir(root):
            if entry.endswith(".app"):
                name = entry[:-4].strip().lower()
                if name and name not in index:
                    index[name] = entry[:-4]  # macOS 'open -a' wants the app name, not a path
    return index


def _index_linux_apps():
    index = {}
    dirs = ["/usr/share/applications", os.path.expanduser("~/.local/share/applications")]
    for root in dirs:
        if not os.path.isdir(root):
            continue
        for entry in os.listdir(root):
            if not entry.endswith(".desktop"):
                continue
            try:
                with open(os.path.join(root, entry), "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                name_match = re.search(r"^Name=(.+)$", content, re.MULTILINE)
                exec_match = re.search(r"^Exec=(.+)$", content, re.MULTILINE)
                if name_match and exec_match:
                    name = name_match.group(1).strip().lower()
                    cmd = re.sub(r"%[a-zA-Z]", "", exec_match.group(1)).strip()
                    if name and name not in index:
                        index[name] = cmd
            except Exception:
                continue
    return index


def build_app_index(force=False):
    global _app_index, _app_index_built_at
    with _APP_INDEX_LOCK:
        if _app_index and not force:
            return _app_index
        try:
            if sys.platform.startswith("win"):
                _app_index = _index_windows_apps()
            elif sys.platform == "darwin":
                _app_index = _index_macos_apps()
            else:
                _app_index = _index_linux_apps()
            _app_index_built_at = time.time()
        except Exception as e:
            print("App index build error:", e)
            _app_index = {}
        return _app_index


def find_installed_app(name):
    """Fuzzy-matches a spoken app name against the installed-app index. Tries
    an exact/substring match first (fast, precise for common cases like
    'chrome' -> 'Google Chrome'), then falls back to closest-match scoring."""
    index = build_app_index()
    if not index:
        return None
    key = name.lower().strip()
    if key in index:
        return index[key]
    substring_hits = [v for k, v in index.items() if key in k or k in key]
    if substring_hits:
        return substring_hits[0]
    close = difflib.get_close_matches(key, index.keys(), n=1, cutoff=0.6)
    if close:
        return index[close[0]]
    return None


def _launch_resolved_app(target):
    try:
        if sys.platform.startswith("win"):
            os.startfile(target)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-a", target])
        else:
            subprocess.Popen(target, shell=True)
        return True
    except Exception as e:
        print("App launch error:", target, e)
        return False


def open_app(name):
    """Universal app opener: checks the small manual override dict first,
    then the real installed-app index, then falls back to a best-effort shell
    guess (works for anything already on PATH even if not indexed)."""
    minimize_dashboard()
    key = name.lower().strip()
    try:
        if key in CUSTOM_APP_PATHS:
            subprocess.Popen([CUSTOM_APP_PATHS[key]])
            return True

        resolved = find_installed_app(name)
        if resolved and _launch_resolved_app(resolved):
            return True

        if sys.platform.startswith("win"):
            subprocess.Popen(f'start "" "{name}"', shell=True)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-a", name])
        else:
            subprocess.Popen([name])
        return True
    except Exception:
        return False


# ---------- App-launch commands (typed/spoken, e.g. "open gmail") ----------
APP_LINKS = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "maps": "https://maps.google.com",
    "amazon": "https://www.amazon.com",
    "chrome": "https://www.google.com",
}

# ---------- Downloads ----------
DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "AI_Downloads")
DOWNLOADABLE_EXTS = (".pdf", ".mp3", ".mp4", ".zip", ".docx", ".doc", ".png",
                     ".jpg", ".jpeg", ".gif", ".apk", ".exe", ".txt", ".csv")


def find_download_url(query):
    candidates = []

    if GOOGLE_SEARCH_ENABLED:
        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {"key": GOOGLE_API_KEY, "cx": GOOGLE_CSE_ID, "q": query, "num": 6}
            r = requests.get(url, params=params, timeout=8)
            for item in r.json().get("items", []):
                link = item.get("link")
                if link:
                    candidates.append(link)
        except Exception as e:
            print("Google download search error:", e)

    if not candidates:
        _, links = google_scrape_search(query, num=10)
        candidates.extend(links)

    if not candidates:
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=8))
            for r in results:
                link = r.get("href")
                if link:
                    candidates.append(link)
        except Exception as e:
            print("DuckDuckGo download search error:", e)

    for link in candidates:
        if link.lower().split("?")[0].endswith(DOWNLOADABLE_EXTS):
            return link
    return candidates[0] if candidates else None


def download_file(url):
    try:
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        r = requests.get(url, stream=True, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        filename = os.path.basename(url.split("?")[0]) or f"download_{int(time.time())}"
        path = os.path.join(DOWNLOAD_DIR, filename)
        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return path
    except Exception as e:
        print("Download error:", e)
        return None


def youtube_search_first_video(query):
    try:
        url = "https://www.youtube.com/results?search_query=" + query.replace(" ", "+")
        r = requests.get(url, headers=SCRAPE_HEADERS, timeout=5)
        match = re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', r.text)
        if match:
            return match.group(1)
    except Exception as e:
        print("YouTube search error:", e)
    return None


def _play_or_search_youtube(query):
    video_id = youtube_search_first_video(query)
    if video_id:
        open_in_chrome(f"https://www.youtube.com/watch?v={video_id}&autoplay=1")
        return f"Playing '{query}' on YouTube."
    url = "https://www.youtube.com/results?search_query=" + query.replace(" ", "+")
    open_in_chrome(url)
    return f"Searching YouTube for '{query}'."