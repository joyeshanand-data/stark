# This file is part of the Stark split-up package. It continues on from
# live_data.py, and this one line below pulls in every name defined in every
# file before it in the chain - so this file has access to everything above
# it, exactly like it would if this were all still one big file.
from live_data import *

# ---------- Optional email integration (opt-in via environment variables) ----------
# Disabled by default - set these to enable. Uses your own mail provider's
# IMAP/SMTP directly (e.g. a Gmail "app password"), no third-party API or key.
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS", "")
EMAIL_APP_PASSWORD = os.environ.get("EMAIL_APP_PASSWORD", "")
EMAIL_IMAP_HOST = os.environ.get("EMAIL_IMAP_HOST", "imap.gmail.com")
EMAIL_SMTP_HOST = os.environ.get("EMAIL_SMTP_HOST", "smtp.gmail.com")
EMAIL_SMTP_PORT = int(os.environ.get("EMAIL_SMTP_PORT", "587"))
EMAIL_ENABLED = bool(EMAIL_ADDRESS and EMAIL_APP_PASSWORD)


def check_email(max_results=5):
    import imaplib
    import email as email_lib
    try:
        conn = imaplib.IMAP4_SSL(EMAIL_IMAP_HOST)
        conn.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        conn.select("INBOX")
        status, data = conn.search(None, "UNSEEN")
        ids = (data[0].split() if status == "OK" else [])[-max_results:]
        results = []
        for msg_id in reversed(ids):
            status, msg_data = conn.fetch(msg_id, "(RFC822)")
            if status != "OK":
                continue
            msg = email_lib.message_from_bytes(msg_data[0][1])
            results.append({"from": msg.get("From", "Unknown"), "subject": msg.get("Subject", "(no subject)")})
        conn.logout()
        return results
    except Exception as e:
        print("Email check error:", e)
        return None


def send_email(to_addr, subject, body):
    import smtplib
    from email.mime.text import MIMEText
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = to_addr
        with smtplib.SMTP(EMAIL_SMTP_HOST, EMAIL_SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, [to_addr], msg.as_string())
        return True
    except Exception as e:
        print("Send email error:", e)
        return False


EMAIL_SEND_PATTERN = re.compile(r"^send an email to (\S+) saying (.+)$")


def try_handle_email_command(original_text, low_text):
    is_email_attempt = (
        low_text in ("check my email", "do i have new emails", "check inbox", "check my inbox")
        or EMAIL_SEND_PATTERN.match(low_text)
    )
    if not is_email_attempt:
        return None

    if not EMAIL_ENABLED:
        return (f"Email isn't set up yet, {USER_TITLE} - set the EMAIL_ADDRESS and EMAIL_APP_PASSWORD "
                f"environment variables (a Gmail 'app password' works well) and restart me.")

    if low_text in ("check my email", "do i have new emails", "check inbox", "check my inbox"):
        results = check_email()
        if results is None:
            return "I couldn't connect to check your email - double check the email settings."
        if not results:
            return f"No new emails, {USER_TITLE}."
        lines = [f"- {r['subject']} (from {r['from']})" for r in results]
        return f"You've got {len(results)} new email(s), {USER_TITLE}:\n" + "\n".join(lines)

    m = EMAIL_SEND_PATTERN.match(low_text)
    if m:
        to_addr, body = m.group(1), original_text[m.start(2):].strip()
        if send_email(to_addr, f"Message from {USER_TITLE} via {BOT_NAME}", body):
            return f"Sent, {USER_TITLE}."
        return "I couldn't send that email - double check the email settings."

    return None


# ---------- Real conversational brain: OpenRouter LLM, memory-aware ----------
# OPENROUTER_API_KEY / OPENROUTER_MODEL / OPENROUTER_ENABLED now live in
# identity.py - moved there because state.py (which loads before this
# file) needs OPENROUTER_ENABLED immediately when it builds the initial
# HUD state dict, not just later inside a function.
LLM_HISTORY_TURNS = 16


def _build_system_prompt():
    facts = all_facts()
    facts_line = "; ".join(f"{k}: {v}" for k, v in facts.items()) if facts else "none yet"
    topic = get_topic() or "none"
    recents = recent_auto_facts(3)
    recents_line = "; ".join(f"{r['topic']} - {r['fact'][:120]}" for r in recents) if recents else "none yet"
    interests = all_interests()
    interests_line = ", ".join(interests[-10:]) if interests else "none yet"
    files = all_file_knowledge()
    files_line = "; ".join(f"{name} - {info.get('summary', '')[:150]}" for name, info in files.items()) if files else "none yet"
    return (
        f"You are {BOT_NAME}, a personal JARVIS-style AI assistant running locally on {USER_TITLE}'s own "
        f"machine as part of a portfolio project. Address the user as '{USER_TITLE}'. Keep replies short, "
        f"warm, and direct - a couple of sentences unless asked for detail. Match the user's language: if "
        f"they write in Hinglish (Hindi-English mix), reply in Hinglish too. Right now your active "
        f"spoken language is set to {get_current_language().capitalize()} - reply in that language unless "
        f"the user is clearly typing in a different one, in which case match them instead. Stay in "
        f"character as Stark; never mention that you're an OpenRouter/LLM API call under the hood.\n\n"
        f"Known facts about {USER_TITLE}: {facts_line}\n"
        f"Things {USER_TITLE} has mentioned in casual conversation: {interests_line}\n"
        f"Last topic discussed: {topic}\n"
        f"Things picked up recently from the news on your own: {recents_line}\n"
        f"Files {USER_TITLE} has taught you: {files_line}"
    )


CLOUD_LLM_URL = os.environ.get("STARK_CLOUD_LLM_URL", "")  # e.g. your HF Space's /chat endpoint


def call_llm(user_input):
    messages = [{"role": "system", "content": _build_system_prompt()}]
    for turn in get_recent_history(turns=LLM_HISTORY_TURNS):
        messages.append({"role": "assistant" if turn["role"] == "assistant" else "user", "content": turn["content"]})
    messages.append({"role": "user", "content": user_input})

    if CLOUD_LLM_URL:
        try:
            r = requests.post(CLOUD_LLM_URL, json={"messages": messages}, timeout=30)
            r.raise_for_status()
            reply = (r.json().get("reply") or "").strip()
            if reply:
                return reply
        except Exception as e:
            print("Cloud LLM error:", e)

    if not OPENROUTER_ENABLED:
        return None
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            json={"model": OPENROUTER_MODEL, "messages": messages, "max_tokens": 400, "temperature": 0.7},
            timeout=20,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip() or None
    except Exception as e:
        print("OpenRouter LLM error:", e)
        return None