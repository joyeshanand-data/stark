# This file is part of the Stark split-up package. It continues on from
# brain.py, and this one line below pulls in every name defined in every
# file before it in the chain - so this file has access to everything above
# it, exactly like it would if this were all still one big file.
from brain import *
from identity import _TRANSFORMERS_AVAILABLE

import runtime

# ---------- Vision: actually understand an uploaded image, not just OCR it ----------
def _image_file_to_data_url(path):
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    mime = {"jpg": "jpeg"}.get(ext, ext) or "jpeg"
    return f"data:image/{mime};base64,{b64}"


# Free, no-signup, no-API-key fallback for text+vision when OPENROUTER_API_KEY
# isn't set. Pollinations.ai (pollinations.ai) is an open, anonymous-access
# platform - no account, no key, no billing - though it's rate-limited and
# lower-quality than a paid model, and (being free/public) shouldn't be used
# for sensitive images.
POLLINATIONS_TEXT_URL = "https://text.pollinations.ai/openai"
POLLINATIONS_TEXT_MODEL = os.environ.get("POLLINATIONS_TEXT_MODEL", "openai")
POLLINATIONS_IMAGE_URL = "https://image.pollinations.ai/prompt/"


def _openrouter_vision_chat(path, prompt, max_tokens=300):
    if not OPENROUTER_ENABLED:
        return None
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": OPENROUTER_MODEL,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": _image_file_to_data_url(path)}},
                    ],
                }],
                "max_tokens": max_tokens,
            },
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        return (data["choices"][0]["message"]["content"] or "").strip() or None
    except Exception as e:
        print("OpenRouter vision error:", e)
        return None


def _pollinations_vision_chat(path, prompt):
    """Free, no-key fallback vision call. Best-effort - Pollinations' free
    tier can be slow/rate-limited/inconsistent, so this is a graceful
    downgrade, not a guaranteed replacement for a paid vision model."""
    try:
        r = requests.post(
            POLLINATIONS_TEXT_URL,
            json={
                "model": POLLINATIONS_TEXT_MODEL,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": _image_file_to_data_url(path)}},
                    ],
                }],
            },
            timeout=45,
        )
        r.raise_for_status()
        data = r.json()
        return (data["choices"][0]["message"]["content"] or "").strip() or None
    except Exception as e:
        print("Pollinations vision error:", e)
        return None


_local_pipe_lock = threading.Lock()
_local_caption_pipe = None  # (processor, model) tuple, or False if load failed, or None if not yet tried
_local_vqa_pipe = None

LOCAL_CAPTION_MODEL = os.environ.get("LOCAL_CAPTION_MODEL", "Salesforce/blip-image-captioning-base")
LOCAL_VQA_MODEL = os.environ.get("LOCAL_VQA_MODEL", "Salesforce/blip-vqa-base")


def _get_local_caption_pipe():
    global _local_caption_pipe
    if not _TRANSFORMERS_AVAILABLE:
        return None
    with _local_pipe_lock:
        if _local_caption_pipe is None:
            try:
                print(f"(Loading local vision model {LOCAL_CAPTION_MODEL} for image captioning - fully "
                      f"offline, no key needed. First run downloads and caches it, may take a minute.)")
                processor = BlipProcessor.from_pretrained(LOCAL_CAPTION_MODEL)
                model = BlipForConditionalGeneration.from_pretrained(LOCAL_CAPTION_MODEL)
                _local_caption_pipe = (processor, model)
            except Exception as e:
                print("Local caption model load error:", e)
                _local_caption_pipe = False
    return _local_caption_pipe or None


def _get_local_vqa_pipe():
    global _local_vqa_pipe
    if not _TRANSFORMERS_AVAILABLE:
        return None
    with _local_pipe_lock:
        if _local_vqa_pipe is None:
            try:
                print(f"(Loading local vision model {LOCAL_VQA_MODEL} for image Q&A - fully offline, no key "
                      f"needed. First run downloads and caches it, may take a minute.)")
                processor = BlipProcessor.from_pretrained(LOCAL_VQA_MODEL)
                model = BlipForQuestionAnswering.from_pretrained(LOCAL_VQA_MODEL)
                _local_vqa_pipe = (processor, model)
            except Exception as e:
                print("Local VQA model load error:", e)
                _local_vqa_pipe = False
    return _local_vqa_pipe or None


def _describe_image_local(path):
    """Fully offline image captioning via a local BLIP model - no network
    call, nothing leaves the machine. Captions are shorter/plainer than a
    cloud vision model's, but genuinely private."""
    pipe = _get_local_caption_pipe()
    if not pipe:
        return None
    try:
        from PIL import Image as _PILImg
        processor, model = pipe
        image = _PILImg.open(path).convert("RGB")
        inputs = processor(image, return_tensors="pt")
        out = model.generate(**inputs, max_new_tokens=40)
        caption = processor.decode(out[0], skip_special_tokens=True).strip()
        return caption or None
    except Exception as e:
        print("Local caption error:", e)
        return None


def _answer_about_image_local(path, question):
    """Fully offline visual question-answering via a local BLIP-VQA model."""
    pipe = _get_local_vqa_pipe()
    if not pipe:
        return None
    try:
        from PIL import Image as _PILImg
        processor, model = pipe
        image = _PILImg.open(path).convert("RGB")
        inputs = processor(image, question, return_tensors="pt")
        out = model.generate(**inputs, max_new_tokens=40)
        answer = processor.decode(out[0], skip_special_tokens=True).strip()
        return answer or None
    except Exception as e:
        print("Local VQA error:", e)
        return None


def _vision_chat(path, prompt, max_tokens=300):
    """Tries a paid OpenRouter vision model first (better, if a key is set),
    then falls back to the free no-key Pollinations endpoint."""
    result = _openrouter_vision_chat(path, prompt, max_tokens=max_tokens)
    if result:
        return result
    return _pollinations_vision_chat(path, prompt)


def describe_image_via_llm(path, ocr_text=None):
    """Actually looks at the image (not just OCR text) so Stark can describe
    objects, scene, colors, composition - real visual understanding. Tries,
    in order: a fully offline local model (if torch+transformers installed -
    most private, no data leaves the machine), then a paid OpenRouter vision
    model (if a key is set), then the free no-key Pollinations fallback. OCR
    text (if any) is folded in as extra context for the cloud paths."""
    local = _describe_image_local(path)
    if local:
        if ocr_text:
            local += f" It also has this text printed on it: {ocr_text[:200]}"
        return local

    prompt = ("Look at this image and describe what's actually in it - objects, people, setting, colors, "
              "mood - in 2-4 concise sentences, like you're describing it to someone who can't see it.")
    if ocr_text:
        prompt += f" It also contains this readable text, which you can mention if relevant: {ocr_text[:400]}"
    return _vision_chat(path, prompt)


def answer_about_image_via_llm(path, question):
    """Same idea as describe_image_via_llm but for a specific follow-up
    question about the active image ('what color is the car', 'how many
    people are in this', etc) instead of a generic description."""
    local = _answer_about_image_local(path, question)
    if local:
        return local
    return _vision_chat(path, question)


# ---------- Voice-triggered camera scans: "scan my face" / "scan the room" ----------
# Grabs a frame straight from the local webcam via OpenCV - no browser
# round-trip needed, works even if the dashboard's camera panel is off -
# then runs it through the same vision pipeline as uploaded images.
def capture_camera_frame():
    """Returns a single frame from the local webcam as a PIL Image, or None
    if OpenCV/the camera isn't available. This is independent of the
    browser's live preview in the Camera panel - it opens the device
    directly, takes one frame, and releases it immediately."""
    if cv2 is None:
        return None
    cap = None
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return None
        for _ in range(4):  # a few throwaway reads let auto-exposure/white-balance settle
            cap.read()
        ok, frame = cap.read()
        if not ok or frame is None:
            return None
        from PIL import Image as _PILImg
        return _PILImg.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    except Exception as e:
        print("Camera capture error:", e)
        return None
    finally:
        if cap is not None:
            cap.release()


def analyze_face_via_llm(path):
    """Looks at a face-scan snapshot and gives a casual, practical style
    read - general face shape plus what hairstyles/glasses/colors tend to
    suit it. Explicitly kept to friendly styling territory, not a medical or
    biometric assessment."""
    prompt = (
        "This is a close-up photo of a person's face, taken for a quick, friendly style check. "
        "First name their general face shape (round, oval, square, heart, long, diamond, etc). Then in "
        "2-4 practical sentences suggest what tends to suit that face shape - hairstyle lengths or "
        "partings, glasses frame shapes, and beard or makeup notes if relevant. Keep the tone warm and "
        "casual, like a friend giving style tips, not a clinical or biometric report. Don't guess at or "
        "mention age, race, or health."
    )
    result = _vision_chat(path, prompt)
    if result:
        return result
    local = _describe_image_local(path)
    if local:
        return (f"I can see {local.lower()} but I can't do a full style read right now - no cloud vision "
                f"model is reachable, only the offline captioner.")
    return None


def analyze_surroundings_via_llm(path):
    """Looks at a surroundings/object snapshot and identifies what's in
    frame in plain language - used for 'scan the room' / 'what is this'
    voice commands."""
    prompt = (
        "Look at this photo of the person's surroundings, or an object they're holding up to the camera. "
        "Identify what's in frame in plain, specific language - name the objects, the setting, and "
        "anything notable (brand, color, condition, what it's likely used for) in 2-4 concise sentences, "
        "like you're describing it to someone who can't see it."
    )
    result = _vision_chat(path, prompt)
    if result:
        return result
    return _describe_image_local(path)


FACE_SCAN_PHRASES = (
    "scan my face", "scan the face", "face scan", "look at my face", "check my face",
    "analyze my face", "analyse my face", "what suits my face", "what would suit my face",
    "what should suit my face", "how do i look", "rate my face", "what suits me",
)
SURROUNDINGS_SCAN_PHRASES = (
    "scan the room", "scan my surroundings", "scan surroundings", "scan the area",
    "scan this object", "scan the object", "what's around me", "what is around me",
    "look around", "what do you see around me", "what is in front of me", "what's in front of me",
    "identify this object", "identify this", "what am i holding", "scan my room",
)


def is_face_scan_command(low_text):
    return any(p in low_text for p in FACE_SCAN_PHRASES)


def is_surroundings_scan_command(low_text):
    return any(p in low_text for p in SURROUNDINGS_SCAN_PHRASES)


def is_camera_scan_command(low_text):
    return is_face_scan_command(low_text) or is_surroundings_scan_command(low_text)


def try_handle_camera_scan_command(low_text):
    """Returns (reply_text, image_url_or_None) for a voice-triggered camera
    scan, or None if this wasn't one. The captured frame becomes the active
    image afterward (same mechanism uploads use), so a follow-up like 'edit
    this image' or 'what color is the wall' keeps working on the very same
    snapshot without needing to say anything camera-specific again."""
    is_face = is_face_scan_command(low_text)
    if not is_face and not is_surroundings_scan_command(low_text):
        return None

    if cv2 is None:
        return (f"I can't reach a camera from here, {USER_TITLE} - OpenCV isn't installed on this machine "
                f"(pip install opencv-python), so I have no way to grab a frame."), None

    frame = capture_camera_frame()
    if frame is None:
        return (f"I couldn't get a frame from the webcam just now, {USER_TITLE} - make sure it's plugged "
                f"in, not already in use by another app, and that this is the machine the camera is "
                f"actually attached to."), None

    filename = f"{'face' if is_face else 'surroundings'}_scan_{int(time.time())}.jpg"
    path = os.path.join(UPLOAD_DIR, filename)
    try:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        frame.save(path, "JPEG", quality=90)
    except Exception as e:
        print("Camera scan save error:", e)
        return f"Grabbed the frame but couldn't save it, {USER_TITLE} - {e}", None

    if is_face:
        result = analyze_face_via_llm(path)
        opener = "Here's my read"
    else:
        result = analyze_surroundings_via_llm(path)
        opener = "Here's what I can make out"

    if not result:
        return (f"I captured the frame, {USER_TITLE}, but couldn't get a read on it - no vision model is "
                f"reachable right now (no OPENROUTER_API_KEY set, and no local caption model installed "
                f"either)."), None

    set_active_upload(filename, path, True, "image/jpeg")
    store_file_knowledge(filename, "", f"Camera scan ({'face' if is_face else 'surroundings'}): {result}")

    image_url = f"{runtime.SERVER_SCHEME}://127.0.0.1:{runtime.SERVER_PORT}/uploads/{filename}"
    reply = (f"{opener}, {USER_TITLE}: {result} It's saved as the active image too, so just say the word "
             f"if you want me to edit it or dig into any detail.")
    return reply, image_url


# ---------- Voice-triggered "open/close the camera" ----------
# The actual camera stream can only be opened from the BROWSER
# (getUserMedia needs a real permission prompt tied to a page, the server
# can't fake that) - so this just raises a one-shot flag in the shared HUD
# state. The dashboard page's poll() loop checks that flag every tick and
# calls its own toggleCamera() function when it sees it.
OPEN_CAMERA_PHRASES = (
    "open camera", "open the camera", "turn on the camera", "turn on camera",
    "start the camera", "start camera", "activate the camera", "activate camera",
    "show me the camera", "enable the camera", "enable camera",
)
CLOSE_CAMERA_PHRASES = (
    "close camera", "close the camera", "turn off the camera", "turn off camera",
    "stop the camera", "stop camera", "deactivate the camera", "deactivate camera",
    "disable the camera", "disable camera",
)


def is_open_camera_command(low_text):
    return any(p in low_text for p in OPEN_CAMERA_PHRASES)


def is_close_camera_command(low_text):
    return any(p in low_text for p in CLOSE_CAMERA_PHRASES)


def try_handle_camera_toggle_command(low_text):
    if is_open_camera_command(low_text):
        update_state(open_camera=True)
        return f"Camera coming on now, {USER_TITLE}."
    if is_close_camera_command(low_text):
        update_state(close_camera=True)
        return f"Camera off, {USER_TITLE}."
    return None


# ---------- Combined "scan it" - face + surroundings in one go, narrated live ----------
FULL_SCAN_PHRASES = (
    "scan it", "scan everything", "full scan", "do a full scan", "scan me",
    "scan me and my surroundings", "read my face", "read my face and surroundings",
    "read my face and my surroundings", "read faces", "do a face reading",
    "face reading",
)


def is_full_scan_command(low_text):
    return any(p in low_text for p in FULL_SCAN_PHRASES)


def read_face_via_llm(path):
    """A richer face pass used by the combined scan: names the apparent
    emotion/expression, then gives a couple of playful, physiognomy/
    astrology-flavored observations - face-shape-to-personality style
    fortune-telling, purely for entertainment.

    Deliberately does NOT rate or score attractiveness/beauty/handsomeness.
    That's on purpose, not a missing feature - an AI assigning a "beauty
    score" to someone's face is the kind of thing that's more likely to
    hurt than help (it's not a meaningful measurement, and it can be a
    genuinely bad thing to fixate on), so this stays in warm/playful
    territory instead: emotion + just-for-fun face reading.
    """
    prompt = (
        "Look at the face in this photo and give a fun, upbeat mini 'face reading'. "
        "First, name the person's apparent emotion or expression in the photo (happy, calm, "
        "focused, tired, surprised, etc) based on visible cues like their mouth and eyes. "
        "Then name their general face shape in one word (round, oval, square, heart, long, "
        "diamond, or oblong). Then give 2-3 short, playful observations in the style of "
        "traditional face-reading / physiognomy folklore (for example, associating a strong "
        "jawline with determination, a high forehead with creativity, or expressive eyebrows "
        "with confidence) - keep this entertaining and clearly framed as just-for-fun folklore, "
        "not a real personality assessment or a rating of their looks. Be warm and "
        "complimentary. Do NOT rate, score, or comment on attractiveness/beauty/handsomeness in "
        "any way, and don't mention age, race, gender, or health."
    )
    return _vision_chat(path, prompt)


# Used to pull a face-shape word back out of read_face_via_llm's reply, so a
# real web search can be layered on top for actual style tips (haircuts,
# glasses, etc) rather than Stark inventing that advice itself.
FACE_SHAPE_WORDS = ("round", "oval", "square", "heart", "long", "diamond", "oblong")


def _extract_face_shape(text):
    if not text:
        return None
    low = text.lower()
    for shape in FACE_SHAPE_WORDS:
        if shape in low:
            return shape
    return None


def _run_full_scan():
    """Does the actual work for a combined scan: captures one frame, reads
    the face (emotion + playful face-reading + a real web search for style
    tips matching the detected face shape), and separately identifies the
    surroundings (also enriched with a real web search for more info about
    whatever it recognizes) - narrating progress out loud as it goes.
    Returns (reply_text, image_url) or (error_text, None)."""
    if cv2 is None:
        return (f"I can't reach a camera from here, {USER_TITLE} - OpenCV isn't installed on this machine "
                f"(pip install opencv-python), so I have no way to grab a frame."), None

    speak(f"Alright {USER_TITLE}, hold still a second - scanning now.")

    frame = capture_camera_frame()
    if frame is None:
        return (f"I couldn't get a frame from the webcam just now, {USER_TITLE} - make sure it's plugged "
                f"in, not already in use by another app, and that this is the machine the camera is "
                f"actually attached to."), None

    filename = f"full_scan_{int(time.time())}.jpg"
    path = os.path.join(UPLOAD_DIR, filename)
    try:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        frame.save(path, "JPEG", quality=90)
    except Exception as e:
        print("Full scan save error:", e)
        return f"Grabbed the frame but couldn't save it, {USER_TITLE} - {e}", None

    speak("Got it - reading your face now.")
    face_result = read_face_via_llm(path)
    style_tip = None
    face_shape = _extract_face_shape(face_result)
    if face_shape:
        style_tip = search_web_text(f"best hairstyles and glasses frames for a {face_shape} face shape")

    speak("And now checking what's around you.")
    surroundings_result = analyze_surroundings_via_llm(path)
    fun_fact = None
    if surroundings_result:
        fun_fact = search_web_text(surroundings_result[:150])
        # Skip it if the search just echoed back something near-identical to
        # what was already said - only worth including if it adds something.
        # Uses a fuzzy similarity ratio rather than exact substring matching,
        # since two descriptions of the same thing rarely match word-for-word
        # (different punctuation/phrasing shouldn't defeat this check).
        if fun_fact:
            similarity = difflib.SequenceMatcher(
                None, surroundings_result.lower(), fun_fact.lower()
            ).ratio()
            if similarity > 0.6:
                fun_fact = None

    if not face_result and not surroundings_result:
        return (f"I captured the frame, {USER_TITLE}, but couldn't get a read on it - no vision model is "
                f"reachable right now (no OPENROUTER_API_KEY set, and no local caption model installed "
                f"either)."), None

    set_active_upload(filename, path, True, "image/jpeg")
    store_file_knowledge(
        filename, "",
        f"Full scan - face: {face_result or 'n/a'} | style tip: {style_tip or 'n/a'} | "
        f"surroundings: {surroundings_result or 'n/a'} | fun fact: {fun_fact or 'n/a'}"
    )

    parts = [f"Alright {USER_TITLE}, here's the full read."]
    if face_result:
        parts.append(f"On your face: {face_result}")
    if style_tip:
        parts.append(f"Style tip for that face shape: {style_tip}")
    if surroundings_result:
        parts.append(f"Around you: {surroundings_result}")
    if fun_fact:
        parts.append(f"A bit more on that: {fun_fact}")
    parts.append("I've saved it as the active image, so say the word if you want me to edit it or dig into anything else.")
    reply = " ".join(parts)

    image_url = f"{runtime.SERVER_SCHEME}://127.0.0.1:{runtime.SERVER_PORT}/uploads/{filename}"
    return reply, image_url


def try_handle_full_scan_command(low_text):
    """The 'scan it' command: captures one frame and reads BOTH the face
    and the surroundings in a single pass. See _run_full_scan for the
    actual work."""
    if not is_full_scan_command(low_text):
        return None
    return _run_full_scan()


# ---------- Combined "open camera and scan" - opens the browser's camera
# panel (so you can see it) AND runs a full scan immediately, instead of
# needing two separate commands. ----------
OPEN_AND_SCAN_PHRASES = (
    "open camera and scan", "open the camera and scan", "open camera and scan it",
    "open the camera and scan it", "open camera and scan my face",
    "open the camera and scan my face", "open camera and scan the surroundings",
    "open the camera and scan the surroundings", "open camera and scan everything",
    "open the camera and scan everything", "open camera and read my face",
    "open the camera and read my face", "open camera and do a face reading",
    "open the camera and do a face reading", "open camera and full scan",
    "open the camera and full scan",
)


def is_open_and_scan_command(low_text):
    return any(p in low_text for p in OPEN_AND_SCAN_PHRASES)


def try_handle_open_and_scan_command(low_text):
    """Combined command: opens the browser's live camera panel (a one-shot
    flag, same mechanism as the plain 'open camera' command) AND runs the
    full face+surroundings scan right away, so you don't have to say two
    separate things."""
    if not is_open_and_scan_command(low_text):
        return None
    update_state(open_camera=True)
    return _run_full_scan()