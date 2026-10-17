# This file is part of the Stark split-up package. It continues on from
# search.py, and this one line below pulls in every name defined in every
# file before it in the chain - so this file has access to everything above
# it, exactly like it would if this were all still one big file.
from search import *
from identity import _PdfReader, _docx

# ---------- Smarter reasoning: calculator + date awareness ----------
_ALLOWED_MATH_NODES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.USub, ast.UAdd,
)


def safe_eval_math(expr):
    try:
        tree = ast.parse(expr, mode="eval")
        for node in ast.walk(tree):
            if not isinstance(node, _ALLOWED_MATH_NODES):
                return None
            if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
                return None
        return eval(compile(tree, "<stark-calc>", "eval"))
    except Exception:
        return None


MATH_TRIGGER = re.compile(
    r"^(?:what(?:'s| is)|calculate|compute|solve)?\s*([0-9()+\-*/.%^\s]+(?:[+\-*/%^][0-9()+\-*/.%^\s]+)+)\??$"
)


def try_calculate(low_text):
    m = MATH_TRIGGER.match(low_text.replace("x", "*").replace("^", "**"))
    if not m:
        return None
    expr = m.group(1).strip()
    if not re.search(r"\d", expr):
        return None
    result = safe_eval_math(expr)
    if result is None:
        return None
    if isinstance(result, float) and result.is_integer():
        result = int(result)
    return f"That's {result}."


DATE_PHRASES = ("what's today's date", "what is today's date", "what's the date today",
                "what day is it", "what's the day today", "what day is today")
TIME_PHRASES = ("what time is it", "what's the time", "current time")


def try_date_time(low_text):
    now = datetime.datetime.now()
    if low_text in DATE_PHRASES or low_text.startswith("what's today") or low_text.startswith("what is today"):
        return now.strftime("Today is %A, %B %d, %Y.")
    if low_text in TIME_PHRASES:
        return now.strftime("It's %I:%M %p right now.")
    return None


# ---------- File handling ----------
UPLOAD_DIR = os.path.join(os.path.expanduser("~"), ".stark", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

FILE_SEARCH_DIRS = [
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~/Downloads"),
    os.path.expanduser("~/Desktop"),
    DOWNLOAD_DIR,
    UPLOAD_DIR,
]
TEXT_FILE_EXTS = (".txt", ".md", ".csv", ".log", ".json", ".py", ".js", ".html", ".css")
EDITABLE_EXTS = TEXT_FILE_EXTS  # only plain-text formats are safe to rewrite in place
IMAGE_FILE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")
MAX_FILE_READ_CHARS = 20000

STOPWORDS = set((
    "a an the and or but if of to in on for with at by from is are was were be been being "
    "this that these those it its as into over under again further then once here there "
    "when where why how all any both each few more most other some such no nor not only "
    "own same so than too very s t can will just don should now i you he she we they them "
    "his her their our your my me him us"
).split())


def resolve_file_path(name_or_path):
    expanded = os.path.expanduser(name_or_path.strip().strip('"').strip("'"))
    if os.path.isfile(expanded):
        return expanded
    for folder in FILE_SEARCH_DIRS:
        candidate = os.path.join(folder, name_or_path)
        if os.path.isfile(candidate):
            return candidate
    best_match, best_score = None, 0.0
    target = os.path.basename(name_or_path).lower()
    for folder in FILE_SEARCH_DIRS:
        if not os.path.isdir(folder):
            continue
        try:
            for fname in os.listdir(folder):
                score = difflib.SequenceMatcher(None, target, fname.lower()).ratio()
                if score > best_score:
                    best_score, best_match = score, os.path.join(folder, fname)
        except Exception:
            continue
    return best_match if best_score > 0.6 else None


def extract_text_from_file(path):
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in TEXT_FILE_EXTS:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read(MAX_FILE_READ_CHARS)
        if ext == ".docx" and _docx:
            document = _docx.Document(path)
            return "\n".join(p.text for p in document.paragraphs)[:MAX_FILE_READ_CHARS]
        if ext == ".pdf" and _PdfReader:
            reader = _PdfReader(path)
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
            return text[:MAX_FILE_READ_CHARS]
        if ext == ".docx" and not _docx:
            return None, "docx"
        if ext == ".pdf" and not _PdfReader:
            return None, "pdf"
    except Exception as e:
        print("File read error:", e)
        return None
    return None


def summarize_text(text, max_sentences=5):
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if len(sentences) <= max_sentences:
        return " ".join(sentences)

    word_freq = {}
    for sentence in sentences:
        for word in re.findall(r"[a-zA-Z']+", sentence.lower()):
            if word not in STOPWORDS and len(word) > 2:
                word_freq[word] = word_freq.get(word, 0) + 1

    scored = []
    for i, sentence in enumerate(sentences):
        words = re.findall(r"[a-zA-Z']+", sentence.lower())
        if not words:
            continue
        score = sum(word_freq.get(w, 0) for w in words) / len(words)
        scored.append((score, i, sentence))

    chosen = []
    for score, i, sentence in sorted(scored, key=lambda x: x[0], reverse=True):
        if any(difflib.SequenceMatcher(None, sentence.lower(), c[2].lower()).ratio() > 0.85 for c in chosen):
            continue
        chosen.append((score, i, sentence))
        if len(chosen) >= max_sentences:
            break

    top_in_order = [s for _, _, s in sorted(chosen, key=lambda x: x[1])]
    return " ".join(top_in_order)


def try_handle_file_command(text):
    t = text.strip()
    low = t.lower()

    m = re.match(r"^(?:learn (?:from )?file|learn from) (.+)$", low)
    if m:
        path = resolve_file_path(t[m.start(1):])
        if not path:
            return f"I couldn't find a file matching '{t[m.start(1):]}' in Documents, Downloads, or Desktop."
        result = extract_text_from_file(path)
        if isinstance(result, tuple):
            return f"That's a .{result[1]} file - install python-{'docx' if result[1]=='docx' else 'pypdf'} to let me learn from those."
        if not result:
            return f"I found {os.path.basename(path)} but couldn't read its contents to learn from."
        filename = os.path.basename(path)
        summary = summarize_text(result, max_sentences=5)
        store_file_knowledge(filename, result, summary)
        return (f"Learned from {filename}, {USER_TITLE}. Quick summary: {summary}\n\n"
                f"Ask me anything about it any time - I'll pull from it even in a different chat.")

    m = re.match(r"^(?:read|open) file (.+)$", low)
    if m:
        path = resolve_file_path(t[m.start(1):])
        if not path:
            return f"I couldn't find a file matching '{t[m.start(1):]}' in Documents, Downloads, or Desktop."
        result = extract_text_from_file(path)
        if isinstance(result, tuple):
            return f"That's a .{result[1]} file - install python-{'docx' if result[1]=='docx' else 'pypdf'} to let me read those."
        if not result:
            return f"I found {os.path.basename(path)} but couldn't read its contents."
        preview = result[:600] + ("..." if len(result) > 600 else "")
        return f"Here's what's in {os.path.basename(path)}:\n\n{preview}"

    m = re.match(r"^summarize (?:file )?(.+)$", low)
    if m:
        path = resolve_file_path(t[m.start(1):])
        if not path:
            return f"I couldn't find a file matching '{t[m.start(1):]}'."
        result = extract_text_from_file(path)
        if isinstance(result, tuple):
            return f"That's a .{result[1]} file - install python-{'docx' if result[1]=='docx' else 'pypdf'} to let me summarize those."
        if not result:
            return f"I found {os.path.basename(path)} but couldn't read its contents to summarize."
        summary = summarize_text(result, max_sentences=5)
        return f"Summary of {os.path.basename(path)}:\n\n{summary}"

    m = re.match(r"^(?:what'?s|list files?) in (?:my )?(.+?) folder$", low) or re.match(r"^list files? in (.+)$", low)
    if m:
        folder_name = t[m.start(1):].strip()
        folder = os.path.expanduser(folder_name)
        if not os.path.isdir(folder):
            for candidate in FILE_SEARCH_DIRS:
                if folder_name.lower() in os.path.basename(candidate).lower():
                    folder = candidate
                    break
        if not os.path.isdir(folder):
            return f"I couldn't find a folder called '{folder_name}'."
        try:
            files = sorted(os.listdir(folder))[:25]
        except Exception as e:
            return f"Couldn't read that folder: {e}"
        if not files:
            return f"{os.path.basename(folder)} is empty."
        return f"{os.path.basename(folder)} has: " + ", ".join(files)

    m = re.match(r"^search (?:my )?files?(?: in (.+?))? for (.+)$", low)
    if m:
        folder_hint = t[m.start(1):m.end(1)].strip() if m.group(1) else None
        query = t[m.start(2):].strip().lower()
        folders = FILE_SEARCH_DIRS
        if folder_hint:
            expanded = os.path.expanduser(folder_hint)
            folders = [expanded] if os.path.isdir(expanded) else FILE_SEARCH_DIRS
        hits = []
        for folder in folders:
            if not os.path.isdir(folder):
                continue
            for fname in os.listdir(folder):
                if query in fname.lower():
                    hits.append(fname)
                    continue
                if fname.lower().endswith(TEXT_FILE_EXTS):
                    try:
                        with open(os.path.join(folder, fname), "r", encoding="utf-8", errors="ignore") as f:
                            if query in f.read(MAX_FILE_READ_CHARS).lower():
                                hits.append(fname)
                    except Exception:
                        continue
        if not hits:
            return f"No files matching '{query}' turned up in the folders I checked."
        return f"Found it in: " + ", ".join(hits[:15])

    return None