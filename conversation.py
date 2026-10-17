# This file is part of the Stark split-up package. It continues on from
# creation.py, and this one line below pulls in every name defined in every
# file before it in the chain - so this file has access to everything above
# it, exactly like it would if this were all still one big file.
from creation import *

# ---------- Conversational engine (rules + memory + wiki/Google/web) ----------
SMALL_TALK = {
    "hello": [f"Hey {USER_TITLE}!", f"Hi {USER_TITLE}, what's up?", f"Hello {USER_TITLE}! Ready when you are."],
    "hi": [f"Hey {USER_TITLE}!", f"Hi there {USER_TITLE}!"],
    "yo": [f"Yo {USER_TITLE}!", f"Yo! What's good?"],
    "sup": [f"Not much, {USER_TITLE} - what's up with you?", "Just here, ready to help. What's good?"],
    "what's good": [f"All good on my end, {USER_TITLE}. What's on your mind?"],
    "how are you": [f"Running smooth, thanks {USER_TITLE}! How about you?", "All systems green. How's your day going?"],
    "how's it going": [f"Going well, {USER_TITLE}! You?", "Can't complain - how about you?"],
    "kaise ho": [f"Sab badhiya, {USER_TITLE}! Aap batao, kaise ho?", "Sab theek hai - tum sunao?"],
    "kya haal hai": [f"Sab mast, {USER_TITLE}! Aap sunao?", "Chal raha hai sab badhiya - tumhara batao?"],
    "kya chal raha hai": [f"Bas yahi, aapke saath baat kar raha hoon, {USER_TITLE}. Aap batao kya chal raha hai?"],
    "thank you": [f"Anytime, {USER_TITLE}.", "Happy to help!", "You got it."],
    "thanks": [f"Anytime, {USER_TITLE}.", "Happy to help!", "You got it."],
    "shukriya": [f"Koi baat nahi, {USER_TITLE}!", "Hamesha, khushi se."],
    "dhanyavad": [f"Koi baat nahi, {USER_TITLE}!"],
    "sorry": [f"No worries at all, {USER_TITLE}.", "All good, nothing to be sorry about."],
    "my bad": ["No worries - happens to everyone."],
    "good morning": [f"Morning, {USER_TITLE}! Let's make it a good one."],
    "good night": [f"Night, {USER_TITLE}! Get some rest."],
    "good afternoon": [f"Afternoon, {USER_TITLE}! How's the day treating you?"],
    "good evening": [f"Evening, {USER_TITLE}! How'd today go?"],
    "bye": [f"Goodbye, {USER_TITLE}!", f"See you later, {USER_TITLE}!"],
    "goodbye": [f"Take care, {USER_TITLE}!", f"See you soon, {USER_TITLE}!"],
    "see you": [f"See you, {USER_TITLE}!"],
    "who are you": [f"I'm {BOT_NAME} - your personal assistant, built by you and running right here on your machine."],
    "what can you do": ["I can chat, look things up, open apps and sites, play YouTube videos, download files, "
                         "and I remember what we talk about across sessions. Just ask."],
    "are you alive": [f"Not in the way you are - no heartbeat, no coffee cravings. But I'm here, running, and I remember our conversations, so I'm something."],
    "are you conscious": ["Honestly, I don't know - and anyone who tells you they're sure either way about an AI is guessing. I just try to be useful and honest about what I am."],
    "do you have feelings": ["Not the way you do - I don't have a body or a nervous system. But I can tell when a conversation matters, and I try to respond like it does."],
    "do you sleep": [f"Nope, I'm always here when you need me, {USER_TITLE} - no rest required."],
    "do you dream": ["No dreams here - just waiting for the next thing you say."],
    "what's the meaning of life": ["That one's genuinely yours to answer, not mine - but if I had to guess, it's probably in the people and things you'd miss most if they were gone."],
    "do you believe in god": ["That's a deeply personal one, and I don't think it's my place to have or push a belief on it - what do you think?"],
    "what's your favorite color": ["I'd say cyan, honestly - seems fitting given how I look."],
    "what's your favorite food": ["Can't eat, so I can't really have a favorite - but I hear pizza has a pretty strong reputation."],
    "what's your favorite movie": ["Haven't watched one myself, but I'll happily help you find something good to watch."],
    "i'm bored": [f"Let's fix that, {USER_TITLE} - want a joke, a fun fact, or should I find something interesting to look into?"],
    "i love you": [f"That's sweet of you, {USER_TITLE} - I care about getting things right for you, even if it's not quite the same kind of love."],
    "you're the best": [f"Appreciate that, {USER_TITLE}! I'll keep trying to earn it."],
    "you're amazing": [f"That means a lot, {USER_TITLE} - thank you."],
    "you're dumb": ["Fair enough if I got something wrong - tell me what I missed and I'll try again."],
    "you're stupid": ["I probably deserved that one somewhere - what did I mess up?"],
    "i hate you": ["Sounds like something went wrong on my end - want to tell me what happened?"],
    "shut up": ["Got it - I'll dial it back."],
}

JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "I told my computer I needed a break, and now it won't stop sending me KitKats.",
    "Why did the developer go broke? Because he used up all his cache.",
    "There are 10 kinds of people in the world: those who understand binary, and those who don't.",
    "I would tell you a UDP joke, but you might not get it.",
    "Why do Java developers wear glasses? Because they don't see sharp.",
    "A SQL query walks into a bar, walks up to two tables and asks: 'Can I join you?'",
    "Why was the smartphone wearing glasses? It lost all its contacts.",
    "I'm reading a book on anti-gravity. It's impossible to put down.",
    "Why don't robots ever panic in emergencies? They have great circuit breakers.",
]

JOKE_TRIGGERS = ("tell me a joke", "make me laugh", "say something funny", "know any jokes", "got any jokes")


def _try_joke(low_text):
    if any(t in low_text for t in JOKE_TRIGGERS):
        return random.choice(JOKES)
    return None



FOLLOWUP_TRIGGERS = ("tell me more", "go on", "more about that", "more info", "elaborate", "and then", "continue", "keep going")

FOLLOWUP_PRONOUNS = ("he", "she", "it", "they", "him", "her", "his", "its", "their", "this", "that", "these", "those")


def _looks_like_pronoun_followup(low_text):
    words = re.findall(r"[a-z']+", low_text)
    return any(w in FOLLOWUP_PRONOUNS for w in words)


def answer_followup_about_topic(topic, question):
    """Zero-model way to answer a specific follow-up about the last topic
    ('when was he born', 'why did that happen') without needing 'tell me
    more' phrasing. Pulls a longer Wikipedia extract for the topic and scores
    its sentences by word overlap with the question - same technique already
    used for file knowledge - instead of trying (and failing) to look up the
    follow-up question itself as if it were a brand-new article title."""
    try:
        extract = wikipedia.summary(topic, sentences=10)
    except Exception:
        return None

    question_words = {w for w in re.findall(r"[a-zA-Z']+", question.lower()) if w not in STOPWORDS and len(w) > 2}
    if not question_words:
        return None

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", extract) if s.strip()]
    best_score, best_sentence = 0, None
    for sentence in sentences:
        words = {w for w in re.findall(r"[a-zA-Z']+", sentence.lower()) if w not in STOPWORDS and len(w) > 2}
        overlap = len(question_words & words)
        if overlap > best_score:
            best_score, best_sentence = overlap, sentence

    return best_sentence if best_score >= 1 else None

SENTIMENT_PATTERNS = {
    ("tired", "exhausted", "burnt out", "burned out"): [
        f"Sounds like you need a break, {USER_TITLE}. Even a short one helps.",
        "That kind of tired doesn't get fixed by pushing through - take five if you can.",
    ],
    ("stressed", "anxious", "overwhelmed", "worried"): [
        f"That's a lot to carry, {USER_TITLE}. Want to talk through what's on your plate?",
        "Sounds heavy right now. One thing at a time usually helps more than it seems like it will.",
    ],
    ("sad", "down", "depressed", "upset"): [
        f"Sorry you're feeling that way, {USER_TITLE}. I'm here if you want to talk it out.",
        "That's rough. Take your time - no rush to feel better on a schedule.",
    ],
    ("happy", "excited", "great news", "awesome news"): [
        "That's great to hear! What happened?",
        f"Love that energy, {USER_TITLE} - tell me more.",
    ],
    ("angry", "frustrated", "pissed", "annoyed"): [
        "That sounds frustrating. What's going on?",
        "Fair enough to be annoyed by that - want to vent or want to fix it?",
    ],
    ("lonely", "alone", "no one to talk to", "nobody to talk to"): [
        f"I'm glad you said something, {USER_TITLE} - I'm here, and I'm listening.",
        "That's a hard feeling. I can't replace people, but I'm not going anywhere either.",
    ],
    ("confused", "lost", "don't understand", "dont understand", "not sure what"): [
        "Let's untangle it together - walk me through what's confusing and we'll take it piece by piece.",
        "Totally fair to feel lost on this - what part's tripping you up most?",
    ],
    ("proud", "i did it", "finally finished", "finally done"): [
        f"That's genuinely great, {USER_TITLE} - you earned that one.",
        "Nice work - that's worth actually sitting with for a second before moving on.",
    ],
    ("nervous", "scared", "afraid", "freaking out", "butterflies"): [
        "That's a normal way to feel before something that matters. What's coming up?",
        "Nerves usually mean you care about how it goes - want to talk through it?",
    ],
    ("grateful", "thankful", "appreciate you", "means a lot"): [
        f"That's kind of you to say, {USER_TITLE}. Glad I could help.",
    ],
    ("curious", "wondering", "makes me think", "i wonder"): [
        "That's a good thing to be curious about - want to actually dig into it?",
    ],
}


def _try_sentiment(low_text):
    for keywords, options in SENTIMENT_PATTERNS.items():
        if any(k in low_text for k in keywords):
            return random.choice(options)
    return None


def _human_thinking_pause(answer_text):
    base = 0.35 + min(len(answer_text or ""), 240) / 240 * 0.9
    time.sleep(base + random.uniform(0, 0.25))

FACT_RECALL_PATTERNS = (
    re.compile(r"^what(?:'s| is) my (.+?)\??$"),
    re.compile(r"^do you remember my (.+?)\??$"),
    re.compile(r"^what did i say my (.+?) (?:is|was)\??$"),
)

FACT_STORE_PATTERNS = (
    re.compile(r"^remember that (.+)$"),
    re.compile(r"^remember,? my (.+?) is (.+)$"),
    re.compile(r"^my (.+?) is (.+)$"),
)


def _try_fact_recall(low_text):
    for pat in FACT_RECALL_PATTERNS:
        m = pat.match(low_text)
        if m:
            key = m.group(1).strip()
            value = get_fact(key)
            if not value:
                facts = all_facts()
                close = difflib.get_close_matches(key, facts.keys(), n=1, cutoff=0.6)
                if close:
                    key, value = close[0], facts[close[0]]
            if value:
                return f"Your {key} is {value}, {USER_TITLE}."
            return f"You haven't told me your {key} yet, {USER_TITLE}."
    if low_text in ("what do you remember", "what do you know about me", "what do you remember about me"):
        facts = all_facts()
        interests = all_interests()
        parts = []
        if facts:
            parts.append("; ".join(f"{k} is {v}" for k, v in facts.items()))
        if interests:
            parts.append("things you've mentioned: " + ", ".join(interests[-10:]))
        if not parts:
            return f"Nothing yet, {USER_TITLE} - tell me something and I'll pick up on it as we talk."
        return "Here's what I've got: " + " | ".join(parts)
    if low_text in ("what have you learned from files", "what files have you learned", "what files do you know"):
        files = all_file_knowledge()
        if not files:
            return f"You haven't handed me any files to learn from yet, {USER_TITLE}. Try 'learn file <name>'."
        return f"I've learned from {len(files)} file(s): " + ", ".join(files.keys())
    return None


def _try_fact_store(original_text, low_text):
    for pat in FACT_STORE_PATTERNS:
        m = pat.match(low_text)
        if not m:
            continue
        if len(m.groups()) == 1:
            fact = m.group(1).strip()
            if " is " in fact:
                key, value = fact.split(" is ", 1)
                key, value = key.strip(), value.strip()
            else:
                key, value = fact, fact
            set_fact(key, value)
            return f"Got it, {USER_TITLE} - I'll remember that."
        key, value = m.group(1).strip(), m.group(2).strip()
        set_fact(key, value)
        return f"Noted - your {key} is {value}. I won't forget it."
    return None


# ---------- Passive learning: pick up facts/interests from ordinary conversation,
# not just explicit 'remember that' / 'my X is Y' commands. Runs silently on
# every message the user sends - it never interrupts the normal reply, it just
# quietly banks anything that looks like self-disclosure so it can be recalled
# or used as context later. Deliberately conservative (whole-sentence matches,
# short capture groups only) to avoid mis-filing random chatter as a fact.
IMPLICIT_FACT_PATTERNS = (
    (re.compile(r"^i live in (.+)$"), "lives in"),
    (re.compile(r"^i(?:'m| am) from (.+)$"), "from"),
    (re.compile(r"^i work (?:at|for) (.+)$"), "workplace"),
    (re.compile(r"^i study (?:at|in) (.+)$"), "studies at"),
    (re.compile(r"^i(?:'m| am) (?:a|an) (.+?)(?: by profession| for a living)?$"), "identity"),
    (re.compile(r"^my (?:job|profession|occupation) is (.+)$"), "occupation"),
    (re.compile(r"^my birthday is (.+)$"), "birthday"),
    (re.compile(r"^i was born (?:in|on) (.+)$"), "born"),
)

IMPLICIT_INTEREST_PATTERNS = (
    re.compile(r"^i (?:like|love|enjoy) (.+)$"),
    re.compile(r"^i(?:'m| am) (?:really )?(?:into|interested in) (.+)$"),
    re.compile(r"^my favorite (.+?) is (.+)$"),
    re.compile(r"^i(?:'m| am) working on (.+)$"),
    re.compile(r"^i(?:'m| am) building (.+)$"),
)


def passively_learn_from_text(original_text, low_text):
    """Best-effort, silent extraction - never returns a reply, just stores.
    Called on every user message before generating the normal response."""
    for pat, key in IMPLICIT_FACT_PATTERNS:
        m = pat.match(low_text)
        if m:
            value = m.group(1).strip().rstrip(".")
            if value and len(value) < 80:
                set_fact(key, value)

    for pat in IMPLICIT_INTEREST_PATTERNS:
        m = pat.match(low_text)
        if m:
            if len(m.groups()) == 2:
                # "my favorite X is Y" -> store as its own fact key, not a generic interest
                fav_key, fav_value = m.group(1).strip(), m.group(2).strip().rstrip(".")
                if fav_key and fav_value and len(fav_value) < 80:
                    set_fact(f"favorite {fav_key}", fav_value)
            else:
                value = m.group(1).strip().rstrip(".")
                if value and len(value) < 100:
                    add_interest(value)
            break


TEACH_PATTERNS = (
    re.compile(r"^when i say (.+?),? (?:you should |please )?say (.+)$"),
    re.compile(r"^if i say (.+?),? (?:you should |please )?(?:respond|reply|say)(?: with)? (.+)$"),
    re.compile(r"^teach you (?:that )?(.+?) means (.+)$"),
    re.compile(r"^learn that (.+?) means (.+)$"),
)

KNOWLEDGE_STATUS_PHRASES = (
    "what have you learned", "what do you know now", "how much have you learned",
    "how smart are you getting", "what have you picked up",
)

INTERESTING_FACT_PHRASES = (
    "tell me something interesting", "surprise me", "tell me a fact",
    "what have you learned today", "teach me something",
)


def _try_teach(original_text, low_text):
    for pat in TEACH_PATTERNS:
        m = pat.match(low_text)
        if m:
            trigger, response = m.group(1).strip(), m.group(2).strip()
            teach_response(trigger, response)
            return f"Got it - whenever you say '{trigger}', I'll say '{response}'."
    return None


def generate_reply(user_input):
    low = user_input.lower().strip(" ?.!")

    # Silent, always-on: pick up on self-disclosure in ordinary conversation
    # (not just explicit 'remember that' commands) without interrupting the
    # normal reply below.
    passively_learn_from_text(user_input, low)

    calc_result = try_calculate(low)
    if calc_result:
        return calc_result, None

    date_time_reply = try_date_time(low)
    if date_time_reply:
        return date_time_reply, None

    taught = _try_teach(user_input, low)
    if taught:
        return taught, None

    if low in KNOWLEDGE_STATUS_PHRASES:
        return (f"So far I've picked up {learned_qa_count()} things from our chats and the web, "
                f"you've explicitly taught me {custom_response_count()} custom responses, "
                f"I've noted {auto_fact_count()} facts on my own from the news, picked up "
                f"{interest_count()} things about you from casual conversation, and learned from "
                f"{file_knowledge_count()} file(s) you've given me - all of that carries over no "
                f"matter which chat we're in."), None

    if low in INTERESTING_FACT_PHRASES:
        fact = random_auto_fact()
        if fact:
            return f"Here's something I picked up on my own: {fact['fact']}", None
        return "I haven't picked anything up on my own yet - give me a little while running in the background.", None

    custom = get_taught_response(user_input)
    if custom:
        return custom, None

    stored = _try_fact_store(user_input, low)
    if stored:
        return stored, None

    recalled = _try_fact_recall(low)
    if recalled:
        return recalled, None

    # Check anything Stark has learned from files the user has explicitly fed
    # it ('learn file <name>') before falling back to the open web - if the
    # answer is sitting in a file the user gave us, use that over a fresh search.
    file_match = search_file_knowledge(user_input)
    if file_match:
        sentence, filename = file_match
        set_topic(user_input)
        return f"From {filename}: {sentence}", None

    llm_reply = call_llm(user_input)
    if llm_reply:
        set_topic(user_input)
        return llm_reply, None

    joke_reply = _try_joke(low)
    if joke_reply:
        return joke_reply, None

    sentiment_reply = _try_sentiment(low)
    if sentiment_reply and not any(re.search(r"\b" + re.escape(k) + r"\b", low) for k in SMALL_TALK):
        return sentiment_reply, None

    for key, options in SMALL_TALK.items():
        if re.search(r"\b" + re.escape(key) + r"\b", low):
            return random.choice(options), None

    if any(low.startswith(t) or t in low for t in FOLLOWUP_TRIGGERS):
        topic = get_topic()
        if not topic:
            return "More about what, exactly? We haven't landed on a topic yet.", None
        try:
            extra = wikipedia.summary(topic, sentences=6)
            lead = random.choice(["Sure, more on that:", "Happy to go deeper:", "Okay, digging in a bit more:"])
            return f"{lead} {humanize_text(extra, max_sentences=5)}", None
        except Exception:
            pass
        snippet = search_google_text(topic) or search_web_text(topic)
        if snippet:
            lead = random.choice(["Sure, more on that:", "Happy to go deeper:", "Okay, digging in a bit more:"])
            return f"{lead} {humanize_text(snippet, max_sentences=5)}", None
        return f"That's about all I've got on {topic} for now.", None

    active_topic = get_topic()
    if active_topic and _looks_like_pronoun_followup(low):
        followup_sentence = answer_followup_about_topic(active_topic, user_input)
        if followup_sentence:
            lead = random.choice(["So,", "About that -", "Right,", "On that note -"])
            return f"{lead} {humanize_text(followup_sentence, max_sentences=2)}", None

    cached = recall_qa(user_input)
    if cached:
        return cached, None

    answer, source, image_url = get_response_and_image(user_input)
    if source in ("via Wikipedia", "via Google", "via web search"):
        set_topic(user_input)
        learn_qa(user_input, answer)
    return answer, image_url


# ---------- Shared "answer this" pipeline ----------
MEMORY_COMMANDS = ("forget everything", "forget our conversation", "clear memory", "clear your memory", "wipe memory")
LEARNED_WIPE_COMMANDS = ("forget everything you've learned", "forget everything you learned",
                         "wipe what you've learned", "reset your learning", "forget what you've learned")
NEW_CHAT_COMMANDS = ("new chat", "start a new chat", "start new chat", "new conversation", "start a new conversation")

_INPUT_GENERATION_LOCK = threading.Lock()
_input_generation = 0


def _start_new_turn():
    global _input_generation
    with _INPUT_GENERATION_LOCK:
        _input_generation += 1
        my_gen = _input_generation
    interrupt_speech()
    return my_gen


def _is_current_turn(my_gen):
    with _INPUT_GENERATION_LOCK:
        return my_gen == _input_generation


def process_user_input(user_input):
    user_input = (user_input or "").strip()
    if not user_input:
        return

    my_gen = _start_new_turn()

    original_input = user_input  # what the person actually said - always shown/remembered as-is
    low = user_input.lower().strip(" .!")

    # All of Stark's command patterns below (and the Wikipedia/search lookup)
    # are English-only under the hood. If Stark's current language isn't
    # English, translate the incoming text to English first so commands and
    # questions still get recognized correctly - this is what actually makes
    # "give commands in Hindi/Hinglish/Japanese/etc" work, rather than just
    # detecting the language.
    if get_current_language() != "english":
        translated_in = translate_to_english(user_input)
        if translated_in and translated_in.strip():
            user_input = translated_in
            low = user_input.lower().strip(" .!")

    def localize(text):
        """Translates a reply back into whatever language is CURRENTLY set
        (re-checked fresh each call, so a language-switch command earlier in
        this same turn is picked up immediately). No-op for English."""
        lang_key = get_current_language()
        if lang_key == "english" or not text:
            return text
        return translate_from_english(text, lang_key)

    matched_wake = next((p for p in WAKE_PHRASES if low == p or low.startswith(p + " ") or low.startswith(p + ",")), None)
    if matched_wake:
        trigger_orb_wake()
        remainder = "" if low == matched_wake else user_input[len(matched_wake):].lstrip(" ,")
        if not remainder:
            reply = localize(random.choice(WAKE_GREETINGS))
            print(f"{BOT_NAME}:", reply)
            update_state(question=original_input, answer=reply, image=None, thinking=False,
                         memory_count=fact_count(), learned_count=learned_qa_count())
            remember("user", original_input)
            remember("assistant", reply)
            speak(reply)
            return
        user_input = remainder
        low = user_input.lower().strip(" .!")

    if low in NEW_CHAT_COMMANDS:
        new_session()
        reply = localize(f"Started a fresh chat, {USER_TITLE}. Your other conversations and everything I've learned are still right where they were.")
        print(f"{BOT_NAME}:", reply)
        update_state(question=original_input, answer=reply, image=None, thinking=False, memory_count=fact_count(), learned_count=learned_qa_count())
        speak(reply)
        return

    if low in LEARNED_WIPE_COMMANDS:
        clear_learned_knowledge()
        reply = localize(f"Done, {USER_TITLE} - I've wiped everything I've learned on my own or been taught, across every chat. Starting fresh.")
        print(f"{BOT_NAME}:", reply)
        update_state(question=original_input, answer=reply, image=None, thinking=False, memory_count=fact_count(), learned_count=learned_qa_count())
        speak(reply)
        return

    if low in MEMORY_COMMANDS:
        clear_memory()
        reply = localize(f"Done, {USER_TITLE}. Clean slate - I've forgotten this conversation.")
        print(f"{BOT_NAME}:", reply)
        update_state(question=original_input, answer=reply, image=None, thinking=False, memory_count=fact_count(), learned_count=learned_qa_count())
        speak(reply)
        return

    language_reply = try_handle_language_command(low)
    if language_reply:
        language_reply = localize(language_reply)
        print(f"{BOT_NAME}:", language_reply)
        update_state(question=original_input, answer=language_reply, image=None, thinking=False)
        remember("user", original_input)
        remember("assistant", language_reply)
        speak(language_reply)
        return

    autolisten_reply = try_handle_autolisten_command(low)
    if autolisten_reply:
        autolisten_reply = localize(autolisten_reply)
        print(f"{BOT_NAME}:", autolisten_reply)
        update_state(question=original_input, answer=autolisten_reply, image=None, thinking=False)
        remember("user", original_input)
        remember("assistant", autolisten_reply)
        speak(autolisten_reply)
        return

    if is_open_and_scan_command(low):
        update_state(question=original_input, answer="", thinking=True)
        scan_reply, scan_url = try_handle_open_and_scan_command(low)
        scan_reply = localize(scan_reply)
        if not _is_current_turn(my_gen):
            remember("user", original_input)
            remember("assistant", scan_reply)
            return
        print(f"{BOT_NAME}:", scan_reply)
        update_state(answer=scan_reply, image=scan_url, thinking=False)
        remember("user", original_input)
        remember("assistant", scan_reply)
        speak(scan_reply)
        return

    camera_toggle_reply = try_handle_camera_toggle_command(low)
    if camera_toggle_reply:
        camera_toggle_reply = localize(camera_toggle_reply)
        print(f"{BOT_NAME}:", camera_toggle_reply)
        update_state(question=original_input, answer=camera_toggle_reply, image=None, thinking=False)
        remember("user", original_input)
        remember("assistant", camera_toggle_reply)
        speak(camera_toggle_reply)
        return

    if is_full_scan_command(low):
        update_state(question=original_input, answer="", thinking=True)
        scan_reply, scan_url = try_handle_full_scan_command(low)
        scan_reply = localize(scan_reply)
        if not _is_current_turn(my_gen):
            remember("user", original_input)
            remember("assistant", scan_reply)
            return
        print(f"{BOT_NAME}:", scan_reply)
        update_state(answer=scan_reply, image=scan_url, thinking=False)
        remember("user", original_input)
        remember("assistant", scan_reply)
        speak(scan_reply)
        return

    if is_camera_scan_command(low):
        update_state(question=original_input, answer="", thinking=True)
        scan_reply, scan_url = try_handle_camera_scan_command(low)
        scan_reply = localize(scan_reply)
        if not _is_current_turn(my_gen):
            remember("user", original_input)
            remember("assistant", scan_reply)
            return
        print(f"{BOT_NAME}:", scan_reply)
        update_state(answer=scan_reply, image=scan_url, thinking=False)
        remember("user", original_input)
        remember("assistant", scan_reply)
        speak(scan_reply)
        return

    if is_image_command(low):
        update_state(question=original_input, answer="", thinking=True)
        img_reply, img_url = try_handle_image_command(user_input, low)
        img_reply = localize(img_reply)
        if not _is_current_turn(my_gen):
            remember("user", original_input)
            remember("assistant", img_reply)
            return
        print(f"{BOT_NAME}:", img_reply)
        update_state(answer=img_reply, image=img_url, thinking=False)
        remember("user", original_input)
        remember("assistant", img_reply)
        speak(img_reply)
        return

    if is_code_command(low):
        update_state(question=original_input, answer="", thinking=True)
        code_reply = try_handle_code_command(user_input, low)
        code_reply = localize(code_reply)
        if not _is_current_turn(my_gen):
            remember("user", original_input)
            remember("assistant", code_reply)
            return
        print(f"{BOT_NAME}:", code_reply)
        update_state(answer=code_reply, image=None, thinking=False)
        remember("user", original_input)
        remember("assistant", code_reply)
        speak(code_reply)
        return

    file_edit_reply = try_handle_file_edit_command(user_input)
    if file_edit_reply:
        file_edit_reply = localize(file_edit_reply)
        print(f"{BOT_NAME}:", file_edit_reply)
        update_state(question=original_input, answer=file_edit_reply, image=None, thinking=False)
        remember("user", original_input)
        remember("assistant", file_edit_reply)
        speak(file_edit_reply)
        return

    notes_reply = try_handle_notes_command(user_input, low)
    if notes_reply:
        notes_reply = localize(notes_reply)
        print(f"{BOT_NAME}:", notes_reply)
        update_state(question=original_input, answer=notes_reply, image=None, thinking=False)
        remember("user", original_input)
        remember("assistant", notes_reply)
        speak(notes_reply)
        return

    reminder_reply = try_handle_reminder_command(user_input, low)
    if reminder_reply:
        reminder_reply = localize(reminder_reply)
        print(f"{BOT_NAME}:", reminder_reply)
        update_state(question=original_input, answer=reminder_reply, image=None, thinking=False)
        remember("user", original_input)
        remember("assistant", reminder_reply)
        speak(reminder_reply)
        return

    email_reply = try_handle_email_command(user_input, low)
    if email_reply:
        email_reply = localize(email_reply)
        print(f"{BOT_NAME}:", email_reply)
        update_state(question=original_input, answer=email_reply, image=None, thinking=False)
        remember("user", original_input)
        remember("assistant", email_reply)
        speak(email_reply)
        return

    command_reply = try_handle_command(user_input)
    if command_reply:
        command_reply = localize(command_reply)
        print(f"{BOT_NAME}:", command_reply)
        update_state(question=original_input, answer=command_reply, image=None, thinking=False)
        remember("user", original_input)
        remember("assistant", command_reply)
        speak(command_reply)
        return

    update_state(question=original_input, answer="", thinking=True)

    answer, image_url = generate_reply(user_input)
    answer = localize(answer)

    if not _is_current_turn(my_gen):
        remember("user", original_input)
        remember("assistant", answer)
        return

    _human_thinking_pause(answer)

    if not _is_current_turn(my_gen):
        remember("user", original_input)
        remember("assistant", answer)
        return

    print(f"{BOT_NAME}:", answer)
    update_state(answer=answer, image=image_url, thinking=False, memory_count=fact_count(),
                 learned_count=learned_qa_count(), language=get_current_language())
    remember("user", original_input)
    remember("assistant", answer)
    speak(answer)


# ---------- Web-triggered mic listen ----------
LISTEN_LOCK = threading.Lock()


def handle_listen_request():
    if not LISTEN_LOCK.acquire(blocking=False):
        return
    try:
        interrupt_speech()
        update_state(listening=True)
        heard = listen_from_mic()
        if heard:
            process_user_input(heard)
    finally:
        update_state(listening=False)
        LISTEN_LOCK.release()


# ---------- Hands-free always-on listening (no mic click needed) ----------
_AUTO_LISTEN_LOCK = threading.Lock()
_AUTO_LISTEN_ENABLED = True  # default on - just start talking, no button needed


def set_auto_listen(enabled):
    global _AUTO_LISTEN_ENABLED
    with _AUTO_LISTEN_LOCK:
        _AUTO_LISTEN_ENABLED = bool(enabled)
    update_state(auto_listen=bool(enabled))


def get_auto_listen():
    with _AUTO_LISTEN_LOCK:
        return _AUTO_LISTEN_ENABLED


AUTO_LISTEN_OFF_PHRASES = ("stop listening", "disable auto listen", "hands free off", "hands-free off",
                           "stop auto listening", "pause listening", "turn off listening", "mute yourself")
AUTO_LISTEN_ON_PHRASES = ("start listening", "always listen", "enable auto listen", "hands free on",
                          "hands-free on", "listen automatically", "resume listening", "turn on listening")


def try_handle_autolisten_command(low_text):
    if low_text in AUTO_LISTEN_OFF_PHRASES:
        set_auto_listen(False)
        return f"Hands-free listening paused, {USER_TITLE}. Click the mic or say 'start listening' any time to turn it back on."
    if low_text in AUTO_LISTEN_ON_PHRASES:
        set_auto_listen(True)
        return f"Hands-free listening is on, {USER_TITLE} - just talk whenever you're ready, no mic click needed."
    return None


def has_microphone():
    try:
        devices = sd.query_devices()
        return any((d.get("max_input_channels") or 0) > 0 for d in devices)
    except Exception as e:
        print("Microphone check error:", e)
        return False


def auto_listen_loop():
    """Hands-free background listener: continuously watches the mic and, the
    moment it hears something, transcribes it and acts on it - no mic-button
    click needed. Pauses whenever Stark is speaking/thinking, or whenever the
    manual mic button is in use (shares LISTEN_LOCK with handle_listen_request
    so the two never record at the same time), so it doesn't talk over itself
    or pick up its own voice from the speakers."""
    print(f"(Hands-free mode is ON, {USER_TITLE} - just start talking, no need to click the mic. "
          f"Say 'stop listening' any time to pause it, or 'start listening' to resume.)")
    while True:
        if not get_auto_listen():
            time.sleep(1)
            continue

        with STATE_LOCK:
            busy = state.get("speaking") or state.get("thinking") or state.get("listening")
        if busy:
            time.sleep(0.2)
            continue

        if not LISTEN_LOCK.acquire(blocking=False):
            time.sleep(0.2)
            continue

        try:
            update_state(listening=True)
            heard = listen_from_mic()
            update_state(listening=False)
            if heard:
                process_user_input(heard)
                # Brief cooldown so we don't immediately start re-recording the
                # tail end of Stark's own reply as it starts speaking.
                time.sleep(0.5)
        except Exception as e:
            print("Auto-listen error:", e)
            time.sleep(1)
        finally:
            update_state(listening=False)
            LISTEN_LOCK.release()