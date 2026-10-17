# This file is part of the Stark split-up package. It continues on from
# voice.py, and this one line below pulls in every name defined in every
# file before it in the chain - so this file has access to everything above
# it, exactly like it would if this were all still one big file.
from voice import *

# ---------- Web + Wikipedia + Google lookup ----------
def search_google_text(query):
    if GOOGLE_SEARCH_ENABLED:
        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {"key": GOOGLE_API_KEY, "cx": GOOGLE_CSE_ID, "q": query, "num": 3}
            r = requests.get(url, params=params, timeout=8)
            data = r.json()
            for item in data.get("items", []):
                snippet = item.get("snippet", "").strip()
                if snippet:
                    return snippet
        except Exception as e:
            print("Google API search error:", e)

    snippets, _ = google_scrape_search(query)
    return snippets[0] if snippets else None

def search_google_image(query):
    if GOOGLE_SEARCH_ENABLED:
        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {"key": GOOGLE_API_KEY, "cx": GOOGLE_CSE_ID, "q": query,
                      "searchType": "image", "num": 3}
            r = requests.get(url, params=params, timeout=8)
            data = r.json()
            for item in data.get("items", []):
                link = item.get("link")
                if link:
                    return link
        except Exception as e:
            print("Google API image search error:", e)

    try:
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}&tbm=isch"
        r = requests.get(url, headers=SCRAPE_HEADERS, timeout=8)
        matches = re.findall(r'\["(https:[^"]+?)",\d+,\d+\]', r.text)
        for m in matches:
            if "gstatic.com" not in m.lower():
                return m
        return matches[0] if matches else None
    except Exception as e:
        print("Google image scrape error:", e)
    return None


def search_web_text(query):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
        for r in results:
            snippet = r.get("body", "").strip()
            if snippet:
                return snippet
    except Exception:
        pass
    return None


def search_web_image(query):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.images(query, max_results=3))
        for r in results:
            url = r.get("image")
            if url:
                return url
    except Exception:
        pass
    return None


def search_web_images_multi(query, max_results=6):
    """Returns a list of {image, thumbnail, title, source} dicts for a gallery
    strip - used by the world-map country panel so a click surfaces more than
    just one hero photo."""
    out = []
    try:
        with DDGS() as ddgs:
            results = list(ddgs.images(query, max_results=max_results))
        for r in results:
            url = r.get("image")
            if not url:
                continue
            out.append({
                "image": url,
                "thumbnail": r.get("thumbnail") or url,
                "title": r.get("title") or "",
                "source": r.get("source") or "",
            })
    except Exception as e:
        print("Multi image search error:", query, e)
    return out


def search_web_videos(query, max_results=4):
    """Returns a list of {title, url, thumbnail, duration, publisher} dicts
    used to populate a small video strip in the country/location panels."""
    out = []
    try:
        with DDGS() as ddgs:
            results = list(ddgs.videos(query, max_results=max_results))
        for r in results:
            url = r.get("content") or r.get("url") or r.get("embed_url")
            if not url:
                continue
            images = r.get("images") or {}
            out.append({
                "title": r.get("title") or "",
                "url": url,
                "thumbnail": images.get("medium") or images.get("large") or images.get("small") or "",
                "duration": r.get("duration") or "",
                "publisher": r.get("publisher") or "",
            })
    except Exception as e:
        print("Video search error:", query, e)
    return out


def _image_if_wanted(text, wants_image, existing=None):
    if not wants_image:
        return None
    return existing or search_google_image(text) or search_web_image(text)


# ---------- Humanizer: make retrieved text sound like a person, not an encyclopedia ----------
# Pure string/regex rules - no model, no API call, nothing "AI" about it. Just
# post-processing on whatever Wikipedia/Google/web search already handed back.
_CONTRACTIONS = (
    (r"\bit is\b", "it's"), (r"\bIt is\b", "It's"),
    (r"\bthat is\b", "that's"), (r"\bThat is\b", "That's"),
    (r"\bthere is\b", "there's"), (r"\bThere is\b", "There's"),
    (r"\bthey are\b", "they're"), (r"\bThey are\b", "They're"),
    (r"\bwe are\b", "we're"), (r"\bWe are\b", "We're"),
    (r"\byou are\b", "you're"), (r"\bYou are\b", "You're"),
    (r"\bdo not\b", "don't"), (r"\bDo not\b", "Don't"),
    (r"\bdoes not\b", "doesn't"), (r"\bDoes not\b", "Doesn't"),
    (r"\bdid not\b", "didn't"), (r"\bDid not\b", "Didn't"),
    (r"\bcannot\b", "can't"), (r"\bCannot\b", "Can't"),
    (r"\bwill not\b", "won't"), (r"\bWill not\b", "Won't"),
    (r"\bwas not\b", "wasn't"), (r"\bwere not\b", "weren't"),
    (r"\bhas not\b", "hasn't"), (r"\bhave not\b", "haven't"),
)
_STIFF_PHRASES = (
    (r"\bit should be noted that\b", ""),
    (r"\bIt should be noted that\b", ""),
    (r"\bit is (?:important|worth noting) to (?:note|mention) that\b", ""),
    (r"\bIt is (?:important|worth noting) to (?:note|mention) that\b", ""),
    (r"\bis (?:commonly |often )?(?:defined|referred to) as\b", "is basically"),
    (r"\bis used (?:in order )?to\b", "helps to"),
    (r"\ba type of\b", "a kind of"),
    (r"\s*\[\d+\]", ""),  # strip Wikipedia-style [12] citation markers
)


def humanize_text(text, max_sentences=3):
    """Trims a retrieved passage to a few sentences and reworks its phrasing
    to sound more like a person talking - contractions, no citation markers,
    no stiff textbook phrasing. Still the same underlying facts, just less
    like it was copy-pasted from a reference page."""
    if not text:
        return text
    for pattern, replacement in _STIFF_PHRASES:
        text = re.sub(pattern, replacement, text)
    for pattern, replacement in _CONTRACTIONS:
        text = re.sub(pattern, replacement, text)
    text = re.sub(r"\s+", " ", text).strip()

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if len(sentences) > max_sentences:
        sentences = sentences[:max_sentences]
    return " ".join(sentences)


QUESTION_LEADINS = {
    "why":     ["Here's the reason:", "So basically:", "Good question - here's why:", "Mainly because of this:"],
    "how":     ["Here's how it works:", "So basically:", "Here's the gist of it:", "Here's how that goes:"],
    "when":    ["Here's the timing on that:", "So:", "From what I found:"],
    "who":     ["Here's who:", "So:", "From what I found:"],
    "where":   ["Here's where:", "So:", "From what I turned up:"],
    "what":    ["So:", "Here's the deal:", "Basically:", "Here's what that is:"],
    "which":   ["So:", "From what I found:"],
    "general": ["So:", "Here's what I found:", "From what I turned up:", "Here's the short version:"],
}

_QUESTION_TYPE_PATTERN = re.compile(
    r"^(?:so\s+|well\s+|um+\s+)?(why|how|when|who|where|what|which)\b"
)


def detect_question_type(low_text):
    m = _QUESTION_TYPE_PATTERN.match(low_text.strip())
    return m.group(1) if m else "general"


_last_leadin_by_type = {}


def pick_leadin(question_type):
    """Rotates lead-ins per question type so Stark doesn't say 'So:' every
    single time - purely a randomness trick, no model involved."""
    options = QUESTION_LEADINS.get(question_type, QUESTION_LEADINS["general"])
    last = _last_leadin_by_type.get(question_type)
    choices = [o for o in options if o != last] or options
    chosen = random.choice(choices)
    _last_leadin_by_type[question_type] = chosen
    return chosen


def humanize_answer(user_input, raw_answer):
    """Combines humanize_text() with a question-type-aware lead-in so a
    Wikipedia/Google/web-search result reads like Stark talking, not a pasted
    reference snippet. Still zero model/API involvement - string rules only."""
    body = humanize_text(raw_answer)
    q_type = detect_question_type(user_input.lower())
    return f"{pick_leadin(q_type)} {body}"


def get_response_and_image(text):
    text_lower = text.lower()
    for key, options in responses.items():
        if key in text_lower:
            return random.choice(options), "local reply", None

    wants_image = True  # any real factual lookup below benefits from a picture, not just explicit "show me X"

    try:
        summary = wikipedia.summary(text, sentences=3)
        image_url = None
        try:
            page = wikipedia.page(text, auto_suggest=False)
            image_url = next((i for i in page.images if not any(b in i.lower() for b in BAD_IMAGE_HINTS)), None)
        except Exception:
            pass
        return humanize_answer(text, summary), "via Wikipedia", _image_if_wanted(text, wants_image, image_url)
    except Exception:
        pass

    for source_name, text_fn in (("via Google", search_google_text), ("via web search", search_web_text)):
        answer = text_fn(text)
        if answer:
            return humanize_answer(text, answer), source_name, _image_if_wanted(text, wants_image)

    return "I couldn't find anything on that, sorry - want me to try rephrasing the search?", "no source found", None