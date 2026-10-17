# This file is part of the Stark split-up package. It continues on from
# automation.py, and this one line below pulls in every name defined in every
# file before it in the chain - so this file has access to everything above
# it, exactly like it would if this were all still one big file.
from automation import *
from identity import _detect_lang

# ---------- Text-to-speech ----------
_tts_lock = threading.Lock()
_current_engine = None
_current_engine_lock = threading.Lock()
_speech_generation = 0
_speech_generation_lock = threading.Lock()


def _speak_now(text, my_gen):
    global _current_engine
    with _tts_lock:
        with _speech_generation_lock:
            if my_gen != _speech_generation:
                return
        update_state(speaking=True)
        try:
            engine = pyttsx3.init()
            with _current_engine_lock:
                _current_engine = engine
            engine.setProperty("rate", 175)
            _pick_voice_for_language(engine, detect_language_key(text))
            engine.say(text)
            engine.runAndWait()
            engine.stop()
            del engine
        except Exception as e:
            print("TTS error:", e)
        finally:
            with _current_engine_lock:
                _current_engine = None
            update_state(speaking=False)


def interrupt_speech():
    global _speech_generation
    with _speech_generation_lock:
        _speech_generation += 1
    with _current_engine_lock:
        eng = _current_engine
    if eng is not None:
        try:
            eng.stop()
        except Exception:
            pass


def speak(text):
    with _speech_generation_lock:
        global _speech_generation
        _speech_generation += 1
        my_gen = _speech_generation
    threading.Thread(target=_speak_now, args=(text, my_gen), daemon=True).start()


# ---------- Voice input ----------
recognizer = sr.Recognizer()
SAMPLE_RATE = 16000
MAX_RECORD_SECONDS = 8
SILENCE_LIMIT = 1.0
SILENCE_THRESHOLD = 500

# ---------- Multi-language support (no API key/Ollama needed) ----------
# Maps a spoken-friendly language name to: (Google STT locale code, a keyword
# used to pick a matching installed TTS voice, langdetect's 2-letter code).
# recognize_google's free endpoint (used above, no key required) accepts a
# 'language' locale and already understands dozens of languages - we just have
# to tell it which one to listen for. TTS voice-matching is best-effort: it
# depends on which voices are actually installed on the OS (Windows SAPI5,
# macOS NSSpeech, or Linux espeak all ship a different voice set).
LANGUAGE_MAP = {
    "english":    {"stt": "en-US", "voice_hint": "english", "code": "en"},
    "hindi":      {"stt": "hi-IN", "voice_hint": "hindi",   "code": "hi"},
    "hinglish":   {"stt": "hi-IN", "voice_hint": "hindi",   "code": "hi"},
    "spanish":    {"stt": "es-ES", "voice_hint": "spanish", "code": "es"},
    "french":     {"stt": "fr-FR", "voice_hint": "french",  "code": "fr"},
    "german":     {"stt": "de-DE", "voice_hint": "german",  "code": "de"},
    "italian":    {"stt": "it-IT", "voice_hint": "italian", "code": "it"},
    "portuguese": {"stt": "pt-PT", "voice_hint": "portuguese", "code": "pt"},
    "russian":    {"stt": "ru-RU", "voice_hint": "russian", "code": "ru"},
    "japanese":   {"stt": "ja-JP", "voice_hint": "japanese", "code": "ja"},
    "korean":     {"stt": "ko-KR", "voice_hint": "korean",  "code": "ko"},
    "chinese":    {"stt": "zh-CN", "voice_hint": "chinese", "code": "zh-cn"},
    "arabic":     {"stt": "ar-SA", "voice_hint": "arabic",  "code": "ar"},
    "bengali":    {"stt": "bn-IN", "voice_hint": "bengali", "code": "bn"},
    "urdu":       {"stt": "ur-PK", "voice_hint": "urdu",    "code": "ur"},
    "punjabi":    {"stt": "pa-IN", "voice_hint": "punjabi", "code": "pa"},
    "tamil":      {"stt": "ta-IN", "voice_hint": "tamil",   "code": "ta"},
    "telugu":     {"stt": "te-IN", "voice_hint": "telugu",  "code": "te"},
    "marathi":    {"stt": "mr-IN", "voice_hint": "marathi", "code": "mr"},
    "gujarati":   {"stt": "gu-IN", "voice_hint": "gujarati", "code": "gu"},
    "turkish":    {"stt": "tr-TR", "voice_hint": "turkish", "code": "tr"},
    "dutch":      {"stt": "nl-NL", "voice_hint": "dutch",   "code": "nl"},
    "vietnamese": {"stt": "vi-VN", "voice_hint": "vietnamese", "code": "vi"},
    "indonesian": {"stt": "id-ID", "voice_hint": "indonesian", "code": "id"},
    "thai":       {"stt": "th-TH", "voice_hint": "thai",    "code": "th"},
}

# langdetect's 2-letter codes back to a LANGUAGE_MAP key, so an auto-detected
# reply (e.g. user typed in Spanish) can drive TTS voice selection too.
_LANGDETECT_TO_KEY = {v["code"]: k for k, v in LANGUAGE_MAP.items()}

CURRENT_LANGUAGE_KEY = "english"  # mirrors memory_state["language"] once memory loads


def set_current_language(lang_key):
    global CURRENT_LANGUAGE_KEY
    lang_key = (lang_key or "english").lower().strip()
    if lang_key not in LANGUAGE_MAP:
        return False
    CURRENT_LANGUAGE_KEY = lang_key
    with MEMORY_LOCK:
        memory_state["language"] = lang_key
    save_memory()
    return True


def get_current_language():
    return CURRENT_LANGUAGE_KEY


LANGUAGE_COMMAND_PATTERNS = (
    re.compile(r"^(?:speak|talk|reply|respond)(?: to me)? in (\w+)$"),
    re.compile(r"^switch (?:to )?(\w+)$"),
)


def try_handle_language_command(low_text):
    """Recognizes 'speak in spanish' / 'talk to me in hindi' / 'switch to french'
    style commands and switches both STT locale and TTS voice accordingly."""
    for pat in LANGUAGE_COMMAND_PATTERNS:
        m = pat.match(low_text)
        if m:
            candidate = m.group(1).lower().strip()
            if candidate in LANGUAGE_MAP:
                set_current_language(candidate)
                if candidate == "hindi":
                    return f"Theek hai {USER_TITLE}, ab main Hindi mein baat karunga."
                return f"Switched to {candidate.capitalize()}, {USER_TITLE}."
    if low_text in ("what language are you speaking", "what language is this", "which language are you using"):
        return f"Right now I'm set to {get_current_language().capitalize()}, {USER_TITLE}. Say 'speak in <language>' to switch."
    return None


_PREFERRED_VOICE_LOCK = threading.Lock()
_PREFERRED_VOICE_ID = None  # explicit user choice from the Customize panel; overrides language auto-matching
_VOICE_LIST_CACHE = None    # [{"id":..., "name":...}, ...], populated on first /voices request


def set_preferred_voice(voice_id):
    global _PREFERRED_VOICE_ID
    with _PREFERRED_VOICE_LOCK:
        _PREFERRED_VOICE_ID = voice_id or None


def get_preferred_voice():
    with _PREFERRED_VOICE_LOCK:
        return _PREFERRED_VOICE_ID


def list_installed_voices():
    """Queries the OS for installed TTS voices once and caches the result -
    spinning up a pyttsx3 engine is slow enough that doing it on every request
    would make the Customize panel feel sluggish."""
    global _VOICE_LIST_CACHE
    if _VOICE_LIST_CACHE is not None:
        return _VOICE_LIST_CACHE
    try:
        probe_engine = pyttsx3.init()
        voices = probe_engine.getProperty("voices") or []
        _VOICE_LIST_CACHE = [{"id": v.id, "name": getattr(v, "name", v.id)} for v in voices]
        probe_engine.stop()
    except Exception as e:
        print("Voice list error:", e)
        _VOICE_LIST_CACHE = []
    return _VOICE_LIST_CACHE


def _pick_voice_for_language(engine, lang_key):
    """Explicit user choice (set via the Customize panel) always wins. Failing
    that: best-effort scan of the OS's installed TTS voices for one whose name
    or metadata mentions the target language. Silently falls back to the
    default voice if nothing matches - never raises, since not every OS ships
    more than one voice (Windows SAPI5 often ships just one or two)."""
    preferred = get_preferred_voice()
    if preferred:
        try:
            engine.setProperty("voice", preferred)
            return True
        except Exception as e:
            print("Preferred voice selection error:", e)

    try:
        hint = LANGUAGE_MAP.get(lang_key, {}).get("voice_hint", "english")
        voices = engine.getProperty("voices") or []
        for v in voices:
            name = (getattr(v, "name", "") or "").lower()
            langs = getattr(v, "languages", None) or []
            lang_strs = " ".join(str(l).lower() for l in langs)
            if hint in name or hint in lang_strs:
                engine.setProperty("voice", v.id)
                return True
    except Exception as e:
        print("Voice selection error:", e)
    return False


def detect_language_key(text):
    """Best-effort auto language detection for text Stark is about to speak, so
    replies come out in a matching voice even if the person didn't explicitly
    say 'speak in X'. Falls back to the current sticky language if langdetect
    isn't installed or the text is too short/ambiguous to classify."""
    if not _detect_lang or not text or len(text.strip()) < 4:
        return get_current_language()
    try:
        code = _detect_lang(text)
        return _LANGDETECT_TO_KEY.get(code, get_current_language())
    except Exception:
        return get_current_language()


# ---------- Translation: lets commands/questions work in any language ----------
# Free, no-key translation via Google Translate's public web endpoint (the
# same "no official API, best-effort scraping" pattern already used elsewhere
# in this file for search/stocks). All of Stark's command patterns (open X,
# remind me to X, take a note, etc.) and the Wikipedia/search lookup are
# English-only under the hood - this is what actually lets you speak or type
# in Hindi, Hinglish, Japanese, Chinese, Korean, Russian, etc. and have
# commands recognized and questions answered, with the reply translated back.
def translate_to_english(text):
    if not text or not text.strip():
        return text
    try:
        r = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "auto", "tl": "en", "dt": "t", "q": text},
            timeout=6,
        )
        r.raise_for_status()
        data = r.json()
        return "".join(seg[0] for seg in data[0] if seg[0]) if data and data[0] else text
    except Exception as e:
        print("Translation (to English) error:", e)
        return text


def translate_from_english(text, target_lang_key):
    if not text or not text.strip():
        return text
    target_code = LANGUAGE_MAP.get(target_lang_key, {}).get("code", "en")
    if target_code == "en":
        return text
    try:
        r = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "en", "tl": target_code, "dt": "t", "q": text},
            timeout=6,
        )
        r.raise_for_status()
        data = r.json()
        return "".join(seg[0] for seg in data[0] if seg[0]) if data and data[0] else text
    except Exception as e:
        print("Translation (from English) error:", e)
        return text


def listen_from_mic(language=None):
    lang_key = language or get_current_language()
    stt_locale = LANGUAGE_MAP.get(lang_key, {}).get("stt", "en-US")
    print(f"Listening... (locale: {stt_locale})")
    block_seconds = 0.1
    block_size = int(SAMPLE_RATE * block_seconds)
    max_blocks = int(MAX_RECORD_SECONDS / block_seconds)
    frames = []
    started_talking = False
    silence_start = None
    peak_volume = 0

    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16") as stream:
            for _ in range(max_blocks):
                block, _ = stream.read(block_size)
                frames.append(block.copy())
                volume = np.abs(block).mean()
                peak_volume = max(peak_volume, volume)

                if volume > SILENCE_THRESHOLD:
                    started_talking = True
                    silence_start = None
                elif started_talking:
                    if silence_start is None:
                        silence_start = time.time()
                    elif time.time() - silence_start > SILENCE_LIMIT:
                        break

        if not started_talking:
            print(f"(Mic picked up peak volume {peak_volume:.0f}, but never crossed the {SILENCE_THRESHOLD} "
                  f"threshold needed to count as speech - check your microphone's input level/selected "
                  f"device in Windows sound settings, or try speaking louder/closer to the mic.)")

        recording = np.concatenate(frames, axis=0)
        audio = sr.AudioData(recording.tobytes(), SAMPLE_RATE, 2)
        text = recognizer.recognize_google(audio, language=stt_locale)
        print("You said:", text)
        return text
    except sr.UnknownValueError:
        # If the current language locale didn't catch it and we weren't already
        # trying English, fall back to English once before giving up - covers
        # the common case of accidentally being left on the wrong language.
        if stt_locale != "en-US":
            try:
                audio = sr.AudioData(np.concatenate(frames, axis=0).tobytes(), SAMPLE_RATE, 2)
                text = recognizer.recognize_google(audio, language="en-US")
                print("You said (fell back to English):", text)
                return text
            except Exception:
                pass
        print(f"(Couldn't understand that - peak mic volume this attempt was {peak_volume:.0f}, "
              f"threshold is {SILENCE_THRESHOLD}.)")
    except sr.RequestError:
        print("(Speech service unavailable - check your internet connection.)")
    except Exception as e:
        print("Mic error:", e)
    return None