# This file is part of the Stark split-up package. It continues on from
# identity.py, and this one line below pulls in every name defined in every
# file before it in the chain - so this file has access to everything above
# it, exactly like it would if this were all still one big file.
from identity import *

# ---------- Conversational memory ----------
MEMORY_DIR = os.path.join(os.path.expanduser("~"), ".stark")
MEMORY_FILE = os.path.join(MEMORY_DIR, "memory.json")

MAX_STORED_TURNS = 400
MAX_LEARNED_QA = 800
MAX_CUSTOM_RESPONSES = 300
MAX_AUTO_FACTS = 150
MAX_SESSIONS = 100
MAX_INTERESTS = 100
MAX_FILE_KNOWLEDGE = 40
FILE_KNOWLEDGE_CHAR_LIMIT = 20000  # per file, keeps memory.json from ballooning
MAX_NOTES = 300
MAX_REMINDERS = 200

MEMORY_LOCK = threading.Lock()

memory_state = {
    "sessions": {},
    "session_order": [],
    "current_session": None,
    "facts": {},
    "last_topic": "",
    "learned_qa": {},
    "custom_responses": {},
    "auto_facts": [],
    "language": "english",
    "interests": [],          # things picked up passively from casual conversation
    "file_knowledge": {},     # {filename: {"text":..., "summary":..., "learned_at":...}}
    "notes": [],              # [{"text":..., "created": ts}]
    "reminders": [],          # [{"text":..., "due_ts":..., "fired": bool}]
}


def _make_session(title=None):
    sid = f"s{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
    memory_state["sessions"][sid] = {
        "id": sid,
        "title": title or "New chat",
        "created": time.time(),
        "history": [],
    }
    memory_state["session_order"].append(sid)
    if len(memory_state["session_order"]) > MAX_SESSIONS:
        oldest = memory_state["session_order"].pop(0)
        memory_state["sessions"].pop(oldest, None)
    return sid


def load_memory():
    # Local import: see the matching comment in automation.py for why this
    # isn't at the top of the file or a blanket "import *" instead.
    import voice
    with MEMORY_LOCK:
        try:
            os.makedirs(MEMORY_DIR, exist_ok=True)
            if os.path.exists(MEMORY_FILE):
                with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                memory_state["facts"] = data.get("facts", {})
                memory_state["last_topic"] = data.get("last_topic", "")
                memory_state["learned_qa"] = data.get("learned_qa", {})
                memory_state["custom_responses"] = data.get("custom_responses", {})
                memory_state["auto_facts"] = data.get("auto_facts", [])
                memory_state["interests"] = data.get("interests", [])
                memory_state["file_knowledge"] = data.get("file_knowledge", {})
                memory_state["notes"] = data.get("notes", [])
                memory_state["reminders"] = data.get("reminders", [])
                memory_state["language"] = data.get("language", "english")
                # NOTE: CURRENT_LANGUAGE_KEY actually lives in voice.py, so it
                # has to be set directly on that module (not via a local copy
                # of the name in THIS file, which voice.py's own functions
                # would never see). This does NOT call voice.set_current_
                # language() on purpose: that function also locks MEMORY_LOCK
                # and calls save_memory() - and we're already inside
                # MEMORY_LOCK right here, mid-load, so calling it would
                # deadlock (the lock isn't reentrant) and immediately
                # re-save what we just loaded. A plain attribute assignment
                # has neither problem.
                if memory_state["language"] in voice.LANGUAGE_MAP:
                    voice.CURRENT_LANGUAGE_KEY = memory_state["language"]

                if "sessions" in data and data["sessions"]:
                    memory_state["sessions"] = data.get("sessions", {})
                    memory_state["session_order"] = data.get("session_order", list(memory_state["sessions"].keys()))
                    memory_state["current_session"] = data.get("current_session")
                elif data.get("history"):
                    sid = _make_session("Earlier conversation")
                    memory_state["sessions"][sid]["history"] = data.get("history", [])[-MAX_STORED_TURNS:]
                    memory_state["current_session"] = sid
        except Exception as e:
            print("Memory load error:", e)

        if not memory_state["sessions"] or not memory_state.get("current_session") \
                or memory_state["current_session"] not in memory_state["sessions"]:
            sid = _make_session()
            memory_state["current_session"] = sid


def save_memory():
    with MEMORY_LOCK:
        try:
            os.makedirs(MEMORY_DIR, exist_ok=True)
            trimmed_sessions = {}
            for sid, sess in memory_state["sessions"].items():
                trimmed_sessions[sid] = {
                    "id": sess["id"],
                    "title": sess["title"],
                    "created": sess["created"],
                    "history": sess["history"][-MAX_STORED_TURNS:],
                }
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "sessions": trimmed_sessions,
                    "session_order": memory_state["session_order"],
                    "current_session": memory_state["current_session"],
                    "facts": memory_state["facts"],
                    "last_topic": memory_state["last_topic"],
                    "learned_qa": memory_state["learned_qa"],
                    "custom_responses": memory_state["custom_responses"],
                    "auto_facts": memory_state["auto_facts"][-MAX_AUTO_FACTS:],
                    "interests": memory_state.get("interests", [])[-MAX_INTERESTS:],
                    "file_knowledge": dict(list(memory_state.get("file_knowledge", {}).items())[-MAX_FILE_KNOWLEDGE:]),
                    "notes": memory_state.get("notes", [])[-MAX_NOTES:],
                    "reminders": memory_state.get("reminders", [])[-MAX_REMINDERS:],
                    "language": memory_state.get("language", "english"),
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("Memory save error:", e)


def _current_session_unlocked():
    sid = memory_state["current_session"]
    return memory_state["sessions"].get(sid)


def remember(role, content):
    with MEMORY_LOCK:
        sess = _current_session_unlocked()
        if sess is None:
            return
        sess["history"].append({"role": role, "content": content, "ts": time.time()})
        sess["history"] = sess["history"][-MAX_STORED_TURNS:]
        if role == "user" and sess["title"] == "New chat":
            title = content.strip()
            if len(title) > 42:
                title = title[:42].rstrip() + "..."
            sess["title"] = title or "New chat"
    save_memory()


def new_session():
    with MEMORY_LOCK:
        sid = _make_session()
        memory_state["current_session"] = sid
    save_memory()
    return sid


def switch_session(sid):
    with MEMORY_LOCK:
        if sid not in memory_state["sessions"]:
            return False
        memory_state["current_session"] = sid
    save_memory()
    return True


def delete_session(sid):
    with MEMORY_LOCK:
        if sid not in memory_state["sessions"]:
            return False
        memory_state["sessions"].pop(sid, None)
        memory_state["session_order"] = [s for s in memory_state["session_order"] if s != sid]
        if memory_state["current_session"] == sid:
            if memory_state["session_order"]:
                memory_state["current_session"] = memory_state["session_order"][-1]
            else:
                memory_state["current_session"] = _make_session()
    save_memory()
    return True


def rename_session(sid, title):
    title = (title or "").strip()
    if not title:
        return False
    with MEMORY_LOCK:
        if sid not in memory_state["sessions"]:
            return False
        memory_state["sessions"][sid]["title"] = title[:60]
    save_memory()
    return True


def list_sessions():
    with MEMORY_LOCK:
        out = []
        for sid in memory_state["session_order"]:
            sess = memory_state["sessions"].get(sid)
            if not sess:
                continue
            out.append({
                "id": sess["id"],
                "title": sess["title"],
                "created": sess["created"],
                "message_count": len(sess["history"]),
            })
        return {"sessions": out, "current_session": memory_state["current_session"]}


def clear_memory():
    with MEMORY_LOCK:
        sess = _current_session_unlocked()
        if sess is not None:
            sess["history"] = []
            sess["title"] = "New chat"
        memory_state["last_topic"] = ""
    save_memory()


def clear_learned_knowledge():
    with MEMORY_LOCK:
        memory_state["learned_qa"] = {}
        memory_state["custom_responses"] = {}
        memory_state["auto_facts"] = []
    save_memory()


def get_recent_history(turns=60):
    with MEMORY_LOCK:
        sess = _current_session_unlocked()
        if sess is None:
            return []
        return [{"role": h["role"], "content": h["content"]} for h in sess["history"][-turns:]]


def set_topic(topic):
    with MEMORY_LOCK:
        memory_state["last_topic"] = topic
    save_memory()


def get_topic():
    with MEMORY_LOCK:
        return memory_state["last_topic"]


def set_fact(key, value):
    with MEMORY_LOCK:
        memory_state["facts"][key.strip().lower()] = value.strip()
    save_memory()


def get_fact(key):
    with MEMORY_LOCK:
        return memory_state["facts"].get(key.strip().lower())


def all_facts():
    with MEMORY_LOCK:
        return dict(memory_state["facts"])


def fact_count():
    with MEMORY_LOCK:
        return len(memory_state["facts"])


def _normalize_q(text):
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def learn_qa(question, answer):
    key = _normalize_q(question)
    if not key or not answer:
        return
    with MEMORY_LOCK:
        memory_state["learned_qa"][key] = answer
        if len(memory_state["learned_qa"]) > MAX_LEARNED_QA:
            oldest = next(iter(memory_state["learned_qa"]))
            del memory_state["learned_qa"][oldest]
    save_memory()


def recall_qa(question):
    key = _normalize_q(question)
    with MEMORY_LOCK:
        if key in memory_state["learned_qa"]:
            return memory_state["learned_qa"][key]
        close = difflib.get_close_matches(key, memory_state["learned_qa"].keys(), n=1, cutoff=0.82)
        if close:
            return memory_state["learned_qa"][close[0]]
    return None


def learned_qa_count():
    with MEMORY_LOCK:
        return len(memory_state["learned_qa"])


def teach_response(trigger, response):
    key = _normalize_q(trigger)
    with MEMORY_LOCK:
        memory_state["custom_responses"][key] = response
        if len(memory_state["custom_responses"]) > MAX_CUSTOM_RESPONSES:
            oldest = next(iter(memory_state["custom_responses"]))
            del memory_state["custom_responses"][oldest]
    save_memory()


def get_taught_response(text):
    key = _normalize_q(text)
    with MEMORY_LOCK:
        if key in memory_state["custom_responses"]:
            return memory_state["custom_responses"][key]
        for trig, resp in memory_state["custom_responses"].items():
            if trig and (trig in key or key in trig):
                return resp
    return None


def custom_response_count():
    with MEMORY_LOCK:
        return len(memory_state["custom_responses"])


def add_auto_fact(topic, fact):
    with MEMORY_LOCK:
        existing_topics = {f["topic"] for f in memory_state["auto_facts"]}
        if topic in existing_topics:
            return False
        memory_state["auto_facts"].append({"topic": topic, "fact": fact, "ts": time.time()})
        memory_state["auto_facts"] = memory_state["auto_facts"][-MAX_AUTO_FACTS:]
    save_memory()
    return True


def random_auto_fact():
    with MEMORY_LOCK:
        facts = list(memory_state["auto_facts"])
    return random.choice(facts) if facts else None


def auto_fact_count():
    with MEMORY_LOCK:
        return len(memory_state["auto_facts"])


def recent_auto_facts(n=5):
    with MEMORY_LOCK:
        facts = list(memory_state["auto_facts"])
    return list(reversed(facts))[:n]


# ---------- Passive interests (things picked up from casual conversation) ----------
def add_interest(text):
    text = (text or "").strip()
    if not text or len(text) < 2:
        return False
    with MEMORY_LOCK:
        existing_lower = {i.lower() for i in memory_state["interests"]}
        if text.lower() in existing_lower:
            return False
        memory_state["interests"].append(text)
        memory_state["interests"] = memory_state["interests"][-MAX_INTERESTS:]
    save_memory()
    return True


def all_interests():
    with MEMORY_LOCK:
        return list(memory_state["interests"])


def interest_count():
    with MEMORY_LOCK:
        return len(memory_state["interests"])


# ---------- File knowledge (things learned from files the user hands over) ----------
def store_file_knowledge(filename, text, summary):
    with MEMORY_LOCK:
        memory_state["file_knowledge"][filename] = {
            "text": (text or "")[:FILE_KNOWLEDGE_CHAR_LIMIT],
            "summary": summary or "",
            "learned_at": time.time(),
        }
        if len(memory_state["file_knowledge"]) > MAX_FILE_KNOWLEDGE:
            oldest_key = min(memory_state["file_knowledge"], key=lambda k: memory_state["file_knowledge"][k]["learned_at"])
            del memory_state["file_knowledge"][oldest_key]
    save_memory()


def all_file_knowledge():
    with MEMORY_LOCK:
        return dict(memory_state["file_knowledge"])


def file_knowledge_count():
    with MEMORY_LOCK:
        return len(memory_state["file_knowledge"])


def search_file_knowledge(query, min_overlap=2):
    """Simple, dependency-free retrieval: scores every sentence across every
    learned file by how many meaningful (non-stopword) words it shares with the
    query, and returns the best-matching sentence plus which file it came from.
    Not semantic search, but works surprisingly well for direct factual
    questions about something the user has fed Stark - and needs no API key,
    no embeddings model, nothing to download."""
    # Local import: see the matching comment in automation.py for why this
    # isn't at the top of the file or a blanket "import *" instead.
    from files import STOPWORDS
    query_words = {w for w in re.findall(r"[a-zA-Z']+", query.lower()) if w not in STOPWORDS and len(w) > 2}
    if not query_words:
        return None

    best_score, best_sentence, best_file = 0, None, None
    with MEMORY_LOCK:
        files = dict(memory_state["file_knowledge"])

    for filename, info in files.items():
        text = info.get("text", "")
        sentences = re.split(r"(?<=[.!?])\s+", text)
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            words = {w for w in re.findall(r"[a-zA-Z']+", sentence.lower()) if w not in STOPWORDS and len(w) > 2}
            overlap = len(query_words & words)
            if overlap > best_score:
                best_score, best_sentence, best_file = overlap, sentence, filename

    if best_score >= min_overlap and best_sentence:
        return best_sentence, best_file
    return None


# ---------- Notes (local, no API key) ----------
def add_note(text):
    text = (text or "").strip()
    if not text:
        return False
    with MEMORY_LOCK:
        memory_state["notes"].append({"text": text, "created": time.time()})
        memory_state["notes"] = memory_state["notes"][-MAX_NOTES:]
    save_memory()
    return True


def list_notes():
    with MEMORY_LOCK:
        return list(memory_state["notes"])


def delete_note(index_1based):
    with MEMORY_LOCK:
        notes = memory_state["notes"]
        if 1 <= index_1based <= len(notes):
            notes.pop(index_1based - 1)
            save = True
        else:
            save = False
    if save:
        save_memory()
    return save


def clear_notes():
    with MEMORY_LOCK:
        memory_state["notes"] = []
    save_memory()


NOTE_ADD_PATTERNS = (
    re.compile(r"^(?:take a note|note that|add a note)[:,]? (.+)$"),
    re.compile(r"^remember this[:,]? (.+)$"),
)


def try_handle_notes_command(original_text, low_text):
    for pat in NOTE_ADD_PATTERNS:
        m = pat.match(low_text)
        if m:
            add_note(original_text[m.start(1):].strip())
            return f"Noted, {USER_TITLE}."

    if low_text in ("read my notes", "what are my notes", "show my notes", "list my notes"):
        notes = list_notes()
        if not notes:
            return f"You don't have any notes yet, {USER_TITLE}. Say 'take a note: ...' to add one."
        lines = [f"{i+1}. {n['text']}" for i, n in enumerate(notes)]
        return f"Your notes, {USER_TITLE}:\n" + "\n".join(lines)

    m = re.match(r"^delete note (\d+)$", low_text)
    if m:
        idx = int(m.group(1))
        if delete_note(idx):
            return f"Deleted note {idx}."
        return f"I don't have a note {idx}."

    if low_text in ("clear my notes", "clear all notes", "delete all notes"):
        clear_notes()
        return f"Cleared all your notes, {USER_TITLE}."

    return None


# ---------- Reminders: a lightweight local calendar (no OAuth/API key needed) ----------
def add_reminder(text, due_ts):
    with MEMORY_LOCK:
        memory_state["reminders"].append({"text": text, "due_ts": due_ts, "fired": False})
        memory_state["reminders"] = memory_state["reminders"][-MAX_REMINDERS:]
    save_memory()


def list_pending_reminders():
    with MEMORY_LOCK:
        return [r for r in memory_state["reminders"] if not r.get("fired")]


def _mark_reminders_fired(due_reminders):
    with MEMORY_LOCK:
        for r in memory_state["reminders"]:
            if r in due_reminders:
                r["fired"] = True
    save_memory()


REMINDER_PATTERN = re.compile(r"^remind me to (.+?) (in .+|at .+|tomorrow at .+)$")
RELATIVE_TIME_PATTERN = re.compile(r"^in (\d+) ?(minute|minutes|min|mins|hour|hours|hr|hrs)$")
ABSOLUTE_TIME_PATTERN = re.compile(r"^(?:at )?(\d{1,2})(?::(\d{2}))? ?(am|pm)?$")


def _parse_reminder_time(when_text, base_dt):
    """Parses a small set of common relative/absolute phrasings without pulling
    in a heavy date-parsing dependency. Returns a datetime or None if it
    couldn't be understood."""
    when_text = when_text.strip().lower()
    tomorrow = when_text.startswith("tomorrow")
    when_text = when_text.replace("tomorrow at", "").replace("tomorrow", "").strip()

    m = RELATIVE_TIME_PATTERN.match(when_text)
    if m:
        amount = int(m.group(1))
        unit = m.group(2)
        delta = datetime.timedelta(minutes=amount) if "min" in unit else datetime.timedelta(hours=amount)
        return base_dt + delta

    m = ABSOLUTE_TIME_PATTERN.match(when_text)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        ampm = m.group(3)
        if ampm == "pm" and hour != 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        target = base_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if tomorrow or target <= base_dt:
            target += datetime.timedelta(days=1)
        return target

    return None


def try_handle_reminder_command(original_text, low_text):
    m = REMINDER_PATTERN.match(low_text)
    if m:
        task, when_text = m.group(1).strip(), m.group(2).strip()
        due_dt = _parse_reminder_time(when_text, datetime.datetime.now())
        if not due_dt:
            return (f"I couldn't figure out when that is, {USER_TITLE} - try something like "
                     f"'remind me to stretch in 20 minutes' or 'remind me to call mom at 6pm'.")
        add_reminder(task, due_dt.timestamp())
        return f"Got it - I'll remind you to {task} at {due_dt.strftime('%I:%M %p')}."

    if low_text in ("what are my reminders", "list my reminders", "show my reminders"):
        pending = list_pending_reminders()
        if not pending:
            return f"You don't have any pending reminders, {USER_TITLE}."
        lines = [f"- {r['text']} at {datetime.datetime.fromtimestamp(r['due_ts']).strftime('%I:%M %p')}" for r in pending]
        return f"Your reminders, {USER_TITLE}:\n" + "\n".join(lines)

    return None


def reminder_checker_loop():
    """Runs in the background for the lifetime of the app: fires any reminder
    whose time has come by speaking it and showing it in the dashboard, the
    same as a phone notification would."""
    # Local import: see the matching comment in automation.py for why this
    # isn't at the top of the file or a blanket "import *" instead.
    from voice import speak
    while True:
        time.sleep(20)
        try:
            now = time.time()
            with MEMORY_LOCK:
                due = [r for r in memory_state["reminders"] if not r.get("fired") and r.get("due_ts", 0) <= now]
            if due:
                _mark_reminders_fired(due)
                for r in due:
                    reply = f"Reminder, {USER_TITLE}: {r['text']}"
                    print(f"{BOT_NAME}:", reply)
                    update_state(question="", answer=reply, image=None)
                    remember("assistant", reply)
                    speak(reply)
                    time.sleep(1)  # avoid overlapping speech if several fire at once
        except Exception as e:
            print("Reminder checker error:", e)


# ---------- Shared state + local web server for the HUD ----------
STATE_LOCK = threading.Lock()
state = {
    "question": "",
    "answer": "",
    "image": None,
    "speaking": False,
    "listening": False,
    "thinking": False,
    "memory_count": 0,
    "learned_count": 0,
    "cpu_percent": 0,
    "cpu_cores": [],
    "ram": {"percent": 0, "used_gb": 0, "total_gb": 0, "free_gb": 0},
    "swap": {"percent": 0, "used_gb": 0, "total_gb": 0, "free_gb": 0},
    "net": {"down_kbps": 0, "up_kbps": 0, "down_history": [], "up_history": []},
    "uptime": "",
    "llm_enabled": OPENROUTER_ENABLED,
    "language": "english",
    "auto_listen": True,
    "open_camera": False,   # one-shot: browser opens its camera panel, then this clears itself
    "close_camera": False,  # one-shot: same, for closing it
}


def update_state(**kwargs):
    with STATE_LOCK:
        state.update(kwargs)


# ---------- "Give me updates" - a full spoken/typed briefing on demand ----------
UPDATE_PHRASES = ("give me updates", "give updates", "give me an update", "give me a full update",
                   "status update", "full update", "what's the update", "brief me", "give me a briefing",
                   "give me the update", "daily update", "give me a rundown")


def build_full_update():
    # Local import: see the matching comment in automation.py for why this
    # isn't at the top of the file or a blanket "import *" instead.
    from live_data import EXTRA_LOCK, extra_state
    with STATE_LOCK:
        cpu = state.get("cpu_percent", 0)
        ram = dict(state.get("ram") or {})
        swap = dict(state.get("swap") or {})
        uptime = state.get("uptime", "--")
    with EXTRA_LOCK:
        news = list(extra_state.get("news") or [])[:3]
        stocks = list(extra_state.get("stocks") or [])[:3]
        weather = dict(extra_state.get("weather") or {}) if extra_state.get("weather") else None

    parts = [f"Here's your update, {USER_TITLE}."]

    parts.append(
        f"System: CPU at {round(cpu)} percent, RAM at {ram.get('percent', 0)} percent "
        f"({ram.get('used_gb', 0)} of {ram.get('total_gb', 0)} GB used), swap at {swap.get('percent', 0)} percent, "
        f"uptime {uptime}."
    )

    if weather and weather.get("temp") is not None:
        parts.append(
            f"Weather in {weather.get('city', 'your area')}: {weather.get('desc', '--')}, "
            f"{round(weather.get('temp', 0))} degrees C, high {round(weather.get('high', 0)) if weather.get('high') is not None else '--'} "
            f"low {round(weather.get('low', 0)) if weather.get('low') is not None else '--'}."
        )

    if stocks:
        stock_bits = ", ".join(
            f"{s['symbol']} {'up' if s['change'] >= 0 else 'down'} {abs(s['pct'])} percent" for s in stocks
        )
        parts.append(f"Markets: {stock_bits}.")

    if news:
        headlines = "; ".join(n.get("title", "") for n in news if n.get("title"))
        if headlines:
            parts.append(f"Top news: {headlines}.")

    facts = recent_auto_facts(2)
    if facts:
        parts.append("Also picked up: " + "; ".join(f["fact"][:140] for f in facts) + ".")

    pending = list_pending_reminders()
    if pending:
        parts.append(f"You've got {len(pending)} pending reminder(s).")

    return " ".join(parts)