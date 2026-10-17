# This file is part of the Stark split-up package. It continues on from
# vision.py, and this one line below pulls in every name defined in every
# file before it in the chain - so this file has access to everything above
# it, exactly like it would if this were all still one big file.
from vision import *
from identity import _DIFFUSERS_AVAILABLE
from vision import _image_file_to_data_url, _local_pipe_lock

import runtime

# ---------- Image generation/editing: Stark draws it himself, no web search ----------
OPENROUTER_IMAGE_MODEL = os.environ.get("OPENROUTER_IMAGE_MODEL", "google/gemini-2.5-flash-image")
GENERATED_IMAGE_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "AI_Downloads", "generated")


def _save_generated_image(image_url_or_b64, prefix="stark_image"):
    os.makedirs(GENERATED_IMAGE_DIR, exist_ok=True)
    try:
        if image_url_or_b64.startswith("data:"):
            raw = base64.b64decode(image_url_or_b64.split(",", 1)[1])
        elif image_url_or_b64.startswith("http"):
            resp = requests.get(image_url_or_b64, timeout=30)
            resp.raise_for_status()
            raw = resp.content
        else:
            raw = base64.b64decode(image_url_or_b64)
        filename = f"{prefix}_{int(time.time())}.png"
        path = os.path.join(GENERATED_IMAGE_DIR, filename)
        with open(path, "wb") as f:
            f.write(raw)
        return path
    except Exception as e:
        print("Save generated image error:", e)
        return None


def _generate_image_openrouter(prompt, input_image_path=None):
    try:
        content = [{"type": "text", "text": prompt}]
        if input_image_path:
            content.append({"type": "image_url", "image_url": {"url": _image_file_to_data_url(input_image_path)}})

        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": OPENROUTER_IMAGE_MODEL,
                "messages": [{"role": "user", "content": content}],
                "modalities": ["image", "text"],
            },
            timeout=90,
        )
        r.raise_for_status()
        data = r.json()
        message = data["choices"][0]["message"]
        images = message.get("images") or []
        if not images:
            fallback_text = (message.get("content") or "").strip()
            return None, (fallback_text or f"{OPENROUTER_IMAGE_MODEL} didn't return an image for that prompt - "
                                            f"try rephrasing it, or set OPENROUTER_IMAGE_MODEL to a different "
                                            f"image-capable model on OpenRouter.")
        image_url = (images[0].get("image_url") or {}).get("url") or images[0].get("url")
        if not image_url:
            return None, "The model returned an image in a format Stark couldn't read."
        saved_path = _save_generated_image(image_url, prefix="stark_edit" if input_image_path else "stark_gen")
        if not saved_path:
            return None, "Got the image back but couldn't save it to disk."
        return saved_path, None
    except Exception as e:
        print("OpenRouter image generation error:", e)
        return None, f"Image generation failed: {e}"


def _generate_image_pollinations(prompt):
    """Free, no-key text-to-image via Pollinations.ai. Pure generation only -
    it can't edit a specific uploaded image without a publicly reachable URL
    for it, which Stark (running on localhost) doesn't have."""
    try:
        url = POLLINATIONS_IMAGE_URL + requests.utils.quote(prompt)
        r = requests.get(url, params={"nologo": "true", "width": 1024, "height": 1024}, timeout=60)
        r.raise_for_status()
        os.makedirs(GENERATED_IMAGE_DIR, exist_ok=True)
        filename = f"stark_gen_{int(time.time())}.png"
        path = os.path.join(GENERATED_IMAGE_DIR, filename)
        with open(path, "wb") as f:
            f.write(r.content)
        return path, None
    except Exception as e:
        print("Pollinations image generation error:", e)
        return None, f"Free image generation failed: {e}"


# ---------- Fully local, offline image generation/editing via diffusers ----------
# Most private option: once the model is downloaded and cached on first use,
# every later generation runs entirely on this machine - no network call, no
# API key, nothing sent anywhere. Slower on CPU than the cloud paths, and the
# first request pays a one-time download (a few GB), but it's the "build your
# own, from scratch, no third party at all" option.
LOCAL_IMAGE_MODEL = os.environ.get("LOCAL_IMAGE_MODEL", "stabilityai/sd-turbo")
_local_t2i_pipe = None
_local_i2i_pipe = None


def _get_local_t2i_pipe():
    global _local_t2i_pipe
    if not _DIFFUSERS_AVAILABLE:
        return None
    with _local_pipe_lock:
        if _local_t2i_pipe is None:
            try:
                print(f"(Loading local image model {LOCAL_IMAGE_MODEL} - fully offline, no key needed. "
                      f"First run downloads and caches it (a few GB), may take a while.)")
                pipe = AutoPipelineForText2Image.from_pretrained(LOCAL_IMAGE_MODEL, torch_dtype=torch.float32)
                pipe.to("cpu")
                _local_t2i_pipe = pipe
            except Exception as e:
                print("Local image model load error:", e)
                _local_t2i_pipe = False
    return _local_t2i_pipe or None


def _get_local_i2i_pipe():
    global _local_i2i_pipe
    if not _DIFFUSERS_AVAILABLE:
        return None
    with _local_pipe_lock:
        if _local_i2i_pipe is None:
            t2i = _get_local_t2i_pipe()
            if not t2i:
                _local_i2i_pipe = False
            else:
                try:
                    # from_pipe reuses the already-loaded weights instead of downloading/loading a second copy
                    _local_i2i_pipe = AutoPipelineForImage2Image.from_pipe(t2i)
                except Exception as e:
                    print("Local image2image pipe error:", e)
                    _local_i2i_pipe = False
    return _local_i2i_pipe or None


def _generate_image_local(prompt, input_image_path=None):
    """Returns (saved_path, status). status is None on success, an error
    string on a real failure, or the special value "unavailable" when
    torch/diffusers just aren't installed - callers use that distinction to
    decide whether to silently fall through to a cloud tier or surface the
    error."""
    if not _DIFFUSERS_AVAILABLE:
        return None, "unavailable"
    try:
        os.makedirs(GENERATED_IMAGE_DIR, exist_ok=True)
        from PIL import Image as _PILImg

        if input_image_path:
            pipe = _get_local_i2i_pipe()
            if not pipe:
                return None, "unavailable"
            init_image = _PILImg.open(input_image_path).convert("RGB").resize((512, 512))
            result = pipe(prompt=prompt, image=init_image, strength=0.65,
                          guidance_scale=1.0, num_inference_steps=4).images[0]
            filename = f"stark_edit_local_{int(time.time())}.png"
        else:
            pipe = _get_local_t2i_pipe()
            if not pipe:
                return None, "unavailable"
            result = pipe(prompt=prompt, num_inference_steps=1, guidance_scale=0.0).images[0]
            filename = f"stark_gen_local_{int(time.time())}.png"

        path = os.path.join(GENERATED_IMAGE_DIR, filename)
        result.save(path)
        return path, None
    except Exception as e:
        print("Local image generation error:", e)
        return None, f"Local image generation failed: {e}"


def generate_image_via_llm(prompt, input_image_path=None):
    """Generates a brand-new image from scratch, or edits an existing one if
    input_image_path is given. Stark actually produces the pixels itself here
    - this never touches Google/DuckDuckGo image search. Returns
    (saved_path, error_message). Tries, in priority order:

    1. Fully local via diffusers (if torch+diffusers installed) - most
       private, no key, no data leaves the machine, but needs a one-time
       model download and is slower without a GPU.
    2. OpenRouter, if OPENROUTER_API_KEY is set - paid, cloud, handles both
       generation and editing well.
    3. Pollinations.ai, no key needed - free, anonymous, generation only
       (can't edit a specific upload without a publicly reachable URL)."""
    if _DIFFUSERS_AVAILABLE:
        local_path, local_status = _generate_image_local(prompt, input_image_path=input_image_path)
        if local_path:
            return local_path, None
        if local_status not in (None, "unavailable"):
            print("Local image generation failed, falling back to a cloud tier:", local_status)

    if OPENROUTER_ENABLED:
        return _generate_image_openrouter(prompt, input_image_path=input_image_path)

    if input_image_path:
        return None, (f"Editing a specific image needs either the local model (install torch + diffusers "
                       f"for fully offline editing) or OPENROUTER_API_KEY set to an image-editing-capable "
                       f"model, {USER_TITLE} - the free no-key cloud path can only generate brand-new images.")

    return _generate_image_pollinations(prompt)


IMAGE_GEN_TRIGGER = re.compile(
    r"^(?:generate|create|make|draw|paint|design)\s+(?:me\s+)?(?:an?\s+)?"
    r"(?:image|picture|photo|artwork|illustration)\s*(?:of|showing|depicting)?\s*(.*)$"
)
IMAGE_EDIT_KEYWORDS = ("edit", "change", "modify", "replace", "swap", "remove", "add", "turn", "recolor", "colour", "color")
IMAGE_REF_KEYWORDS = ("this image", "this photo", "this picture", "the image", "the photo", "the picture",
                      "this file", "active image", "in it", "to it")
IMAGE_QUESTION_KEYWORDS = ("what's in", "what is in", "describe this image", "describe the image", "what does this image",
                           "what do you see", "how many", "what color", "what colour", "what's happening in")


def is_image_generation_command(low_text):
    return bool(IMAGE_GEN_TRIGGER.match(low_text))


def is_image_edit_command(low_text):
    return any(k in low_text for k in IMAGE_EDIT_KEYWORDS) and any(k in low_text for k in IMAGE_REF_KEYWORDS)


def is_image_question(low_text):
    return any(k in low_text for k in IMAGE_QUESTION_KEYWORDS)


def _run_image_generation(prompt, input_image_path):
    saved_path, error = generate_image_via_llm(prompt, input_image_path=input_image_path)
    if not saved_path:
        return (error or "Something went wrong generating that image."), None

    filename = os.path.basename(saved_path)
    image_url = f"{runtime.SERVER_SCHEME}://127.0.0.1:{runtime.SERVER_PORT}/generated/{filename}"

    if input_image_path:
        set_active_upload(filename, saved_path, True, "image/png")
        store_file_knowledge(filename, "", f"Edited image - instruction: {prompt}")
        reply = (f"Edited it, {USER_TITLE} - saved as {filename}. It's now the active image, so you can "
                 f"keep editing it further if you want.")
    else:
        store_file_knowledge(filename, "", f"Generated image - prompt: {prompt}")
        reply = f"Here you go, {USER_TITLE} - I generated that myself. Saved as {filename}."
    return reply, image_url


def is_image_command(low_text):
    return is_image_generation_command(low_text) or is_image_edit_command(low_text) or is_image_question(low_text)


def try_handle_image_command(original_text, low_text):
    """Returns (reply_text, image_url_or_None) if this looked like an image
    generation, editing, or vision-question request; else None. Only ever
    called after a cheap is_image_*() check has already confirmed a match, so
    the (potentially slow) network call only happens when it's warranted."""
    if is_image_generation_command(low_text):
        m = IMAGE_GEN_TRIGGER.match(low_text)
        prompt = original_text[m.start(1):].strip() if m and m.group(1) else ""
        if not prompt:
            return f"Sure, {USER_TITLE} - what should I generate an image of?", None
        return _run_image_generation(prompt, None)

    active = get_active_upload()

    if is_image_question(low_text):
        if not active.get("filename") or not active.get("is_image"):
            return f"I don't have an active image to look at yet, {USER_TITLE} - upload one first.", None
        answer = answer_about_image_via_llm(active["path"], original_text)
        if not answer:
            return (f"I couldn't get a read on that image just now, {USER_TITLE} - the free vision fallback "
                     f"may be rate-limited or briefly down. Try again in a bit, or set OPENROUTER_API_KEY "
                     f"for a more reliable vision-capable model."), None
        return answer, None

    if is_image_edit_command(low_text):
        if not active.get("filename") or not active.get("is_image"):
            return f"I don't have an active image to edit yet, {USER_TITLE} - upload one first.", None
        return _run_image_generation(original_text, active["path"])

    return None


# ---------- Code generation: write code, save it, run it only after a confirm step ----------
# Safety note: generated code runs with exactly Stark's own account permissions -
# there is no sandbox. The one deliberate safeguard here is that nothing ever
# executes in the same turn it was generated; the person always sees the code
# first and has to explicitly say "run it" before anything touches the disk.
GENERATED_CODE_DIR = os.path.join(os.path.expanduser("~"), ".stark", "generated_code")

CODE_GEN_TRIGGER = re.compile(
    r"^(?:write|create|build|make|generate|code)\s+(?:me\s+)?(?:a\s+|an\s+)?"
    r"(?:python\s+)?(?:script|program|app|application|tool)\s*(?:that|to|for|which)?\s*(.*)$"
)
RUN_CODE_TRIGGERS = ("run it", "run the script", "run that", "execute it", "yes run it",
                     "go ahead and run it", "run the code")

_last_generated_code = {"path": None}


def is_code_command(low_text):
    return bool(CODE_GEN_TRIGGER.match(low_text)) or low_text in RUN_CODE_TRIGGERS


def _extract_code_block(text):
    """Pulls the first fenced code block out of an LLM response - falls back
    to the whole reply if the model didn't use a fence."""
    m = re.search(r"```(?:\w+)?\s*\n?(.*?)```", text, re.S)
    return m.group(1).strip() if m else text.strip()


def generate_code_via_llm(request_text):
    """Generates a Python script for the request using whichever brain is
    connected (your own cloud endpoint first, then OpenRouter - same priority
    as call_llm). Returns (code_text, error_message)."""
    system_prompt = (
        "You are a careful Python programmer. Respond with ONLY one complete, "
        "runnable Python script inside a single ```python code block - no "
        "explanation before or after. Prefer the standard library. If a third-party "
        "package is required, add a '# pip install X' comment at the very top."
    )
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": request_text}]

    if CLOUD_LLM_URL:
        try:
            r = requests.post(CLOUD_LLM_URL, json={"messages": messages}, timeout=45)
            r.raise_for_status()
            reply = (r.json().get("reply") or "").strip()
            if reply:
                return _extract_code_block(reply), None
        except Exception as e:
            print("Cloud LLM code-gen error:", e)

    if OPENROUTER_ENABLED:
        try:
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
                json={"model": OPENROUTER_MODEL, "messages": messages, "max_tokens": 1200, "temperature": 0.3},
                timeout=45,
            )
            r.raise_for_status()
            reply = r.json()["choices"][0]["message"]["content"].strip()
            if reply:
                return _extract_code_block(reply), None
        except Exception as e:
            print("OpenRouter code-gen error:", e)
            return None, f"Code generation failed: {e}"

    return None, (f"Writing code needs a connected brain, {USER_TITLE} - set STARK_CLOUD_LLM_URL "
                   f"or OPENROUTER_API_KEY so I actually have something to write it with. The free "
                   f"Wikipedia/search fallback can't generate original code.")


def save_generated_code(code_text, extension=".py"):
    os.makedirs(GENERATED_CODE_DIR, exist_ok=True)
    filename = f"stark_code_{int(time.time())}{extension}"
    path = os.path.join(GENERATED_CODE_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(code_text)
    return path


def run_generated_python(path, timeout=20):
    """Runs a generated script as its own subprocess with a hard timeout, so
    a runaway/looping script can't hang Stark forever. Captures stdout/stderr
    to report back rather than letting it print into Stark's own console."""
    try:
        result = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=timeout)
        return (result.stdout or "").strip(), (result.stderr or "").strip(), result.returncode
    except subprocess.TimeoutExpired:
        return None, f"Timed out after {timeout} seconds - it may be waiting on input or stuck in a loop.", None
    except Exception as e:
        return None, str(e), None


def try_handle_code_command(original_text, low_text):
    m = CODE_GEN_TRIGGER.match(low_text)
    if m:
        request_text = original_text[m.start(1):].strip() if m.group(1) else ""
        if not request_text:
            return f"Sure, {USER_TITLE} - what should the script actually do?"

        code_text, error = generate_code_via_llm(request_text)
        if not code_text:
            return error or "Something went wrong generating that code."

        path = save_generated_code(code_text)
        _last_generated_code["path"] = path
        preview = code_text[:700] + ("\n..." if len(code_text) > 700 else "")
        return (f"Written and saved to {path}, {USER_TITLE}:\n\n{preview}\n\n"
                f"Take a look before running it - say \"run it\" when you're ready.")

    if low_text in RUN_CODE_TRIGGERS:
        path = _last_generated_code.get("path")
        if not path or not os.path.isfile(path):
            return f"I don't have a script ready to run yet, {USER_TITLE} - ask me to write one first."

        output, errors, returncode = run_generated_python(path)
        if output is None and returncode is None:
            return f"Couldn't run it, {USER_TITLE}: {errors}"

        parts = [f"Ran it, {USER_TITLE} (exit code {returncode})."]
        if output:
            parts.append(f"Output:\n{output[:800]}")
        if errors:
            parts.append(f"Errors:\n{errors[:800]}")
        return "\n\n".join(parts)

    return None