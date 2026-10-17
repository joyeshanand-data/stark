# This file is part of the Stark split-up package. It continues on from
# files.py, and this one line below pulls in every name defined in every
# file before it in the chain - so this file has access to everything above
# it, exactly like it would if this were all still one big file.
from files import *

# ---------- Uploaded files: track the "active" file for conversation + editing ----------
_ACTIVE_UPLOAD_LOCK = threading.Lock()
_active_upload = {"filename": None, "path": None, "is_image": False, "mime": None}

# Optional OCR support - only used if pytesseract + PIL are both installed and a
# Tesseract binary is on PATH. Never required; images still upload and preview
# fine without it, they just can't be read as text.
try:
    import pytesseract
    from PIL import Image as _PILImage
    _OCR_AVAILABLE = True
except ImportError:
    pytesseract = None
    _PILImage = None
    _OCR_AVAILABLE = False


def set_active_upload(filename, path, is_image, mime):
    with _ACTIVE_UPLOAD_LOCK:
        _active_upload["filename"] = filename
        _active_upload["path"] = path
        _active_upload["is_image"] = is_image
        _active_upload["mime"] = mime


def get_active_upload():
    with _ACTIVE_UPLOAD_LOCK:
        return dict(_active_upload)


def _safe_upload_path(filename):
    """Resolves a filename to a path strictly inside UPLOAD_DIR, refusing any
    path traversal - edits are only ever allowed on files Stark itself saved
    there, never on arbitrary paths elsewhere on disk."""
    candidate = os.path.normpath(os.path.join(UPLOAD_DIR, os.path.basename(filename)))
    if not candidate.startswith(os.path.normpath(UPLOAD_DIR)):
        return None
    return candidate


def ocr_image(path):
    if not _OCR_AVAILABLE:
        return None
    try:
        img = _PILImage.open(path)
        text = pytesseract.image_to_string(img)
        return text.strip() or None
    except Exception as e:
        print("OCR error:", e)
        return None


def handle_file_upload(filename, raw_bytes, mime):
    """Saves an uploaded file into the sandbox, extracts+learns its content if
    it's text (or OCRs it if it's an image and pytesseract is available), marks
    it as the 'active' file so bare references like 'this file' resolve to it,
    and returns a confirmation string ready to show/speak."""
    # Local imports: see the matching comment in automation.py for why
    # these aren't at the top of the file or a blanket "import *" instead.
    from vision import describe_image_via_llm
    from brain import OPENROUTER_MODEL
    filename = os.path.basename(filename).strip() or f"upload_{int(time.time())}"
    path = _safe_upload_path(filename)
    if not path:
        return "That filename isn't valid - try a simpler name without path separators."

    # Avoid silently clobbering a same-named file already learned from.
    base, ext = os.path.splitext(filename)
    counter = 1
    while os.path.exists(path):
        filename = f"{base}_{counter}{ext}"
        path = _safe_upload_path(filename)
        counter += 1

    try:
        with open(path, "wb") as f:
            f.write(raw_bytes)
    except Exception as e:
        return f"Couldn't save the upload: {e}"

    is_image = ext.lower() in IMAGE_FILE_EXTS
    set_active_upload(filename, path, is_image, mime)

    if is_image:
        ocr_text = ocr_image(path)
        vision_desc = describe_image_via_llm(path, ocr_text=ocr_text)

        if vision_desc:
            knowledge_text = vision_desc + (f"\n\nText found in the image: {ocr_text}" if ocr_text else "")
            store_file_knowledge(filename, knowledge_text, vision_desc)
            ocr_note = " I also read the text printed in it." if ocr_text else ""
            return (f"Got the image {filename}, {USER_TITLE} - here's what I see: {vision_desc}{ocr_note}\n\n"
                    f"Ask me anything about it, or tell me to change something in it.")

        if ocr_text:
            summary = summarize_text(ocr_text, max_sentences=3)
            store_file_knowledge(filename, ocr_text, summary)
            return (f"Got the image {filename}, {USER_TITLE} - I read the text in it via OCR, but couldn't "
                    f"get a visual description this time (the free vision fallback may be rate-limited right "
                    f"now, or set OPENROUTER_API_KEY for a more reliable one). Quick summary of the text: "
                    f"{summary}\n\nAsk me anything about it, or tell me to edit the text.")

        return (f"Got the image {filename}, {USER_TITLE}. I can see it's uploaded and I'll keep it as the "
                f"active file, but I couldn't get a look at it just now - the free vision fallback may be "
                f"rate-limited or briefly down. Try again in a bit, set OPENROUTER_API_KEY for a more reliable "
                f"vision-capable model like {OPENROUTER_MODEL}, or install pytesseract + Pillow + the "
                f"Tesseract binary for OCR on top of that.")

    result = extract_text_from_file(path)
    if isinstance(result, tuple):
        return f"Got {filename}, but that .{result[1]} format needs an extra library installed to read it."
    if not result:
        return f"Got {filename}, {USER_TITLE}, but I couldn't extract readable text from it."

    summary = summarize_text(result, max_sentences=5)
    store_file_knowledge(filename, result, summary)
    editable = ext.lower() in EDITABLE_EXTS
    edit_hint = " I can also edit it directly if you tell me to - e.g. 'add ... to the file' or 'replace X with Y in the file'." if editable else ""
    return f"Learned from {filename}, {USER_TITLE}. Quick summary: {summary}\n\nAsk me anything about it.{edit_hint}"


# ---------- Editing the active uploaded file ----------
FILE_EDIT_PATTERNS = (
    ("append", re.compile(r"^(?:add|append) (.+?) to (?:the |this )?file$")),
    ("replace", re.compile(r"^replace (.+?) with (.+?) in (?:the |this )?file$")),
    ("remove", re.compile(r"^(?:remove|delete) (.+?) from (?:the |this )?file$")),
    ("rewrite", re.compile(r"^rewrite (?:the |this )?file(?: to say| as)? (.+)$")),
)


def _reload_file_knowledge(filename, path):
    """Re-extracts and re-stores content after an edit, so both the retrieval
    (search_file_knowledge) and future summaries reflect the new content."""
    result = extract_text_from_file(path)
    if isinstance(result, tuple) or not result:
        return None
    summary = summarize_text(result, max_sentences=5)
    store_file_knowledge(filename, result, summary)
    return summary


def try_handle_file_edit_command(text):
    """Returns a reply string if this looked like an in-place file edit
    command, else None. Only ever touches files inside UPLOAD_DIR - never an
    arbitrary path elsewhere on disk - and only plain-text formats."""
    low = text.strip().lower()

    active = get_active_upload()
    if not active.get("filename"):
        # Still let the patterns match so we can give a helpful "no active
        # file" message instead of silently falling through to a web search.
        for _, pat in FILE_EDIT_PATTERNS:
            if pat.match(low):
                return f"I don't have an active file to edit yet, {USER_TITLE} - upload one first, or say 'learn file <name>'."
        return None

    filename, path = active["filename"], active["path"]
    ext = os.path.splitext(filename)[1].lower()
    if ext not in EDITABLE_EXTS:
        for _, pat in FILE_EDIT_PATTERNS:
            if pat.match(low):
                return f"{filename} is a .{ext.lstrip('.')} file - I can only edit plain-text formats directly (txt, md, csv, json, py, js, html, css)."
        return None

    for kind, pat in FILE_EDIT_PATTERNS:
        m = pat.match(low)
        if not m:
            continue
        try:
            if kind == "append":
                addition = text[m.start(1):m.end(1)] if m.start(1) else m.group(1)
                with open(path, "a", encoding="utf-8") as f:
                    f.write(("\n" if os.path.getsize(path) > 0 else "") + m.group(1).strip())
                summary = _reload_file_knowledge(filename, path)
                return f"Added that to {filename}, {USER_TITLE}." + (f" Updated summary: {summary}" if summary else "")

            if kind == "replace":
                old, new = m.group(1).strip(), m.group(2).strip()
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if old not in content:
                    return f"I couldn't find '{old}' in {filename} to replace."
                content = content.replace(old, new)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                summary = _reload_file_knowledge(filename, path)
                return f"Replaced '{old}' with '{new}' in {filename}." + (f" Updated summary: {summary}" if summary else "")

            if kind == "remove":
                target = m.group(1).strip()
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                if target not in content:
                    return f"I couldn't find '{target}' in {filename} to remove."
                content = content.replace(target, "")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                summary = _reload_file_knowledge(filename, path)
                return f"Removed '{target}' from {filename}." + (f" Updated summary: {summary}" if summary else "")

            if kind == "rewrite":
                new_content = m.group(1).strip()
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                summary = _reload_file_knowledge(filename, path)
                return f"Rewrote {filename}, {USER_TITLE}." + (f" Updated summary: {summary}" if summary else "")
        except Exception as e:
            return f"Something went wrong editing {filename}: {e}"

    return None


# ---------- Shortcuts: side app-dock + quick-access lists ----------
def open_folder(path):
    minimize_dashboard()
    path = os.path.expanduser(path)
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return True
    except Exception as e:
        print("Folder open error:", e)
        return False


SPECIAL_COMMANDS = {
    "control_panel":    {"win": ["control"], "darwin": ["open", "/System/Library/PreferencePanes"], "linux": ["xdg-open", "/"]},
    "network_settings": {"win": ["control", "ncpa.cpl"], "darwin": ["open", "/System/Library/PreferencePanes/Network.prefPane"], "linux": ["nm-connection-editor"]},
    "recycle_bin":      {"win": ["explorer", "shell:RecycleBinFolder"], "darwin": ["open", os.path.expanduser("~/.Trash")], "linux": ["xdg-open", os.path.expanduser("~/.local/share/Trash")]},
    "uninstall_panel":  {"win": ["control", "appwiz.cpl"], "darwin": ["open", "/System/Applications"], "linux": ["xdg-open", "/usr/share/applications"]},
    "remote_desktop":   {"win": ["mstsc"], "darwin": ["open", "-a", "Screen Sharing"], "linux": ["remmina"]},
    "screen_record":    {"win": ["explorer", "ms-screenclip:"], "darwin": ["open", "-a", "QuickTime Player"], "linux": ["gnome-screenshot", "-i"]},
    "sound_record":     {"win": ["soundrecorder"], "darwin": ["open", "-a", "QuickTime Player"], "linux": ["gnome-sound-recorder"]},
}


def _current_platform_key():
    return "win" if sys.platform.startswith("win") else "darwin" if sys.platform == "darwin" else "linux"


def run_special(key):
    minimize_dashboard()
    plat = _current_platform_key()

    if key == "lock_screen":
        try:
            if plat == "win":
                subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
            elif plat == "darwin":
                subprocess.Popen(["osascript", "-e",
                                   'tell application "System Events" to keystroke "q" using {control down, command down}'])
            else:
                subprocess.Popen(["loginctl", "lock-session"])
            return True
        except Exception as e:
            print("Lock screen error:", e)
            return False

    if key == "shutdown":
        try:
            cmd = {"win": ["shutdown", "/s", "/t", "5"],
                   "darwin": ["osascript", "-e", 'tell app "System Events" to shut down'],
                   "linux": ["shutdown", "-h", "now"]}[plat]
            subprocess.Popen(cmd)
            return True
        except Exception as e:
            print("Shutdown error:", e)
            return False

    cmd = SPECIAL_COMMANDS.get(key, {}).get(plat)
    if not cmd:
        return False
    try:
        subprocess.Popen(cmd, shell=(plat == "win"))
        return True
    except Exception as e:
        print(f"Special command error ({key}):", e)
        return False