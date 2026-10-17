# This file is part of the Stark split-up package. It continues on from
# webserver.py, and this one line below pulls in every name defined in every
# file before it in the chain - so this file has access to everything above
# it, exactly like it would if this were all still one big file.
from webserver import *
from identity import _detect_lang, _TRANSFORMERS_AVAILABLE, _DIFFUSERS_AVAILABLE, _TKINTER_AVAILABLE
from automation import _AUTOMATION_AVAILABLE

import runtime

# ---------- Main loop ----------
# ---------- Floating "magical sphere" orb - always-on-top companion that follows you across apps ----------
_orb_root = None
_orb_expanded = False
_orb_auto_opened = False


def _orb_submit_text(entry_widget):
    text = entry_widget.get().strip()
    if not text:
        return
    entry_widget.delete(0, tk.END)
    threading.Thread(target=process_user_input, args=(text,), daemon=True).start()


def create_floating_orb():
    """Builds a small always-on-top, borderless, draggable orb (pure tkinter -
    ships with Python, no extra install) that mirrors Stark's state (idle,
    listening, thinking, speaking) as a rotating "data sphere" made of glowing
    points, and can be clicked to reveal a tiny type/listen panel. Meant to
    float on top of whatever other app is in use. Saying "hello Stark" from
    anywhere (voice, typed, dashboard) triggers a few seconds of "awake" mode:
    the sphere brightens/speeds up and the panel pops open automatically."""
    global _orb_root, _orb_expanded, _orb_auto_opened
    if not _TKINTER_AVAILABLE:
        print("(tkinter not available - the floating orb widget is disabled. It ships with most Python installs; "
              "on some Linux distros install it separately, e.g. 'sudo apt install python3-tk'.)")
        return

    root = tk.Tk()
    _orb_root = root
    root.title("Stark Orb")
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    is_windows = sys.platform.startswith("win")
    TRANSPARENT_KEY = "magenta"
    if is_windows:
        try:
            root.attributes("-transparentcolor", TRANSPARENT_KEY)
        except Exception:
            is_windows = False
    if not is_windows:
        try:
            root.attributes("-alpha", 0.95)
        except Exception:
            pass

    ORB_SIZE = 110
    bg_color = TRANSPARENT_KEY if is_windows else "#05090f"
    root.configure(bg=bg_color)
    screen_w = root.winfo_screenwidth()
    root.geometry(f"{ORB_SIZE}x{ORB_SIZE}+{screen_w-160}+140")

    canvas = tk.Canvas(root, width=ORB_SIZE, height=ORB_SIZE, bg=bg_color, highlightthickness=0)
    canvas.pack()

    # Points spread evenly over a unit sphere (Fibonacci sphere) - these are the
    # "data particles" that get rotated every frame to form the globe.
    _golden_angle = math.pi * (3 - math.sqrt(5))
    _N_PTS = 46
    _sphere_points = []
    for i in range(_N_PTS):
        y = 1 - (i / (_N_PTS - 1)) * 2
        r_at_y = math.sqrt(max(0, 1 - y * y))
        theta = _golden_angle * i
        _sphere_points.append((math.cos(theta) * r_at_y, y, math.sin(theta) * r_at_y))

    _bg_stars = [(random.uniform(4, ORB_SIZE - 4), random.uniform(4, ORB_SIZE - 4)) for _ in range(16)]
    _orb_angle = {"a": 0.0, "b": 0.0}

    def _lerp_color(c1, c2, t):
        def hx(c):
            c = c.lstrip('#')
            return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
        r1, g1, b1 = hx(c1); r2, g2, b2 = hx(c2)
        r = int(r1 + (r2 - r1) * t); g = int(g1 + (g2 - g1) * t); b = int(b1 + (b2 - b1) * t)
        return f"#{r:02x}{g:02x}{b:02x}"

    def draw_orb(base_color="#00d9ff", intensity=1.0, speed=1.0):
        canvas.delete("all")
        cx = cy = ORB_SIZE / 2
        R = ORB_SIZE * 0.34

        for (sx, sy) in _bg_stars:
            canvas.create_oval(sx - 1, sy - 1, sx + 1, sy + 1, fill="#4fb8d6", outline="")

        _orb_angle["a"] += 0.045 * speed
        _orb_angle["b"] += 0.021 * speed
        a, b = _orb_angle["a"], _orb_angle["b"]
        cos_a, sin_a, cos_b, sin_b = math.cos(a), math.sin(a), math.cos(b), math.sin(b)

        projected = []
        for (px, py, pz) in _sphere_points:
            x1 = px * cos_a - pz * sin_a
            z1 = px * sin_a + pz * cos_a
            y2 = py * cos_b - z1 * sin_b
            z2 = py * sin_b + z1 * cos_b
            depth = (z2 + 1) / 2
            projected.append((cx + x1 * R, cy + y2 * R, depth))

        projected.sort(key=lambda p: p[2])
        for (sx, sy, depth) in projected:
            dot_r = 1.1 + depth * 2.2 * intensity
            color = _lerp_color("#1a3a4d", base_color, 0.35 + depth * 0.65)
            canvas.create_oval(sx - dot_r, sy - dot_r, sx + dot_r, sy + dot_r, fill=color, outline="")

        core_r = ORB_SIZE * 0.10 * intensity
        canvas.create_oval(cx - core_r, cy - core_r, cx + core_r, cy + core_r, fill="#f2feff", outline="")

    draw_orb()

    # ---- expand panel: small type/listen box that appears next to the orb ----
    panel = tk.Toplevel(root, bg="#0b1420")
    panel.overrideredirect(True)
    panel.attributes("-topmost", True)
    panel.withdraw()

    tk.Label(panel, text="STARK", fg="#00d9ff", bg="#0b1420", font=("Consolas", 10, "bold")).pack(anchor="w", padx=8, pady=(8, 2))
    answer_lbl = tk.Label(panel, text="", fg="#d6f2fb", bg="#0b1420", font=("Consolas", 9), wraplength=260, justify="left")
    answer_lbl.pack(anchor="w", padx=8, pady=(0, 6))

    entry_row = tk.Frame(panel, bg="#0b1420")
    entry_row.pack(fill="x", padx=8, pady=(0, 4))
    entry = tk.Entry(entry_row, width=26, bg="#10202e", fg="#d6f2fb", insertbackground="#d6f2fb",
                      relief="flat", font=("Consolas", 10))
    entry.pack(side="left", fill="x", expand=True, ipady=4)
    entry.bind("<Return>", lambda e: _orb_submit_text(entry))

    tk.Button(entry_row, text="\U0001F3A4", command=lambda: threading.Thread(target=handle_listen_request, daemon=True).start(),
              bg="#10202e", fg="#00d9ff", relief="flat", font=("Consolas", 10)).pack(side="left", padx=(4, 0))

    tk.Label(panel, text="Say \"hello Stark\" from anywhere to wake the orb, or \"write it here\" after "
                         "clicking into another app to type the last reply there.",
             fg="#7c8b96", bg="#0b1420", font=("Consolas", 7), wraplength=260, justify="left").pack(anchor="w", padx=8, pady=(0, 4))
    tk.Label(panel, text="Drag the orb to move it. Click to expand/collapse.",
             fg="#5b6a74", bg="#0b1420", font=("Consolas", 7), wraplength=260, justify="left").pack(anchor="w", padx=8, pady=(0, 8))

    def position_panel():
        panel.geometry(f"300x170+{root.winfo_x() - 230}+{root.winfo_y()}")

    def toggle_panel():
        global _orb_expanded, _orb_auto_opened
        _orb_auto_opened = False
        _orb_expanded = not _orb_expanded
        if _orb_expanded:
            position_panel()
            panel.deiconify()
            entry.focus_set()
        else:
            panel.withdraw()

    drag_data = {"x": 0, "y": 0, "moved": False}

    def on_press(event):
        drag_data["x"], drag_data["y"], drag_data["moved"] = event.x, event.y, False

    def on_motion(event):
        dx, dy = event.x - drag_data["x"], event.y - drag_data["y"]
        if abs(dx) > 2 or abs(dy) > 2:
            drag_data["moved"] = True
        root.geometry(f"+{root.winfo_x() + dx}+{root.winfo_y() + dy}")
        if _orb_expanded:
            position_panel()

    def on_release(event):
        if not drag_data["moved"]:
            toggle_panel()

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_motion)
    canvas.bind("<ButtonRelease-1>", on_release)

    def poll():
        with STATE_LOCK:
            speaking, listening, thinking = state.get("speaking"), state.get("listening"), state.get("thinking")
            answer = state.get("answer") or ""
        awake = orb_is_awake()

        if speaking:
            color, intensity, speed = "#00d9ff", 1.35, 2.2
        elif listening:
            color, intensity, speed = "#ff9628", 1.25, 1.8
        elif thinking:
            color, intensity, speed = "#b388ff", 1.2, 2.6
        elif awake:
            color, intensity, speed = "#7cf5ff", 1.15, 1.6
        else:
            color, intensity, speed = "#0091c7", 0.85, 0.7

        draw_orb(color, intensity, speed)

        global _orb_expanded, _orb_auto_opened
        if awake and not _orb_expanded:
            _orb_auto_opened = True
            _orb_expanded = True
            position_panel()
            panel.deiconify()
        elif not awake and _orb_auto_opened and _orb_expanded:
            _orb_auto_opened = False
            _orb_expanded = False
            panel.withdraw()

        if _orb_expanded:
            answer_lbl.config(text=answer[:220])
        root.after(40, poll)

    poll()
    root.mainloop()


def console_loop():
    """The original terminal-based interaction loop, moved to a background
    thread so tkinter (which must own the main thread) can run the floating
    orb instead. Still fully functional - type or press Enter to talk/listen,
    same as before."""
    while True:
        typed = input("You: ").strip()
        if typed == "":
            user_input = listen_from_mic()
            if not user_input:
                continue
        else:
            user_input = typed

        if user_input.lower() in ("exit", "quit"):
            print(f"{BOT_NAME}: Goodbye, {USER_TITLE}!")
            update_state(question=user_input, answer=f"Goodbye, {USER_TITLE}!", image=None)
            speak(f"Goodbye, {USER_TITLE}!")
            os._exit(0)

        process_user_input(user_input)


def main():
    load_memory()

    port = start_server()
    threading.Thread(target=stats_refresher, daemon=True).start()
    threading.Thread(target=news_refresher, daemon=True).start()
    diagnose_stock_sources()
    threading.Thread(target=stocks_refresher, daemon=True).start()
    threading.Thread(target=weather_refresher, daemon=True).start()
    threading.Thread(target=auto_learn_refresher, daemon=True).start()
    threading.Thread(target=build_app_index, daemon=True).start()
    threading.Thread(target=reminder_checker_loop, daemon=True).start()

    if has_microphone():
        threading.Thread(target=auto_listen_loop, daemon=True).start()
    else:
        set_auto_listen(False)
        print("(No microphone detected - hands-free voice mode disabled. The mic button and typing still work "
              "once a microphone is connected; restart Stark after plugging one in.)")

    launch_dashboard(f"{runtime.SERVER_SCHEME}://127.0.0.1:{port}/")

    lan_ip = get_lan_ip()
    if lan_ip and lan_ip != "127.0.0.1":
        if runtime.SERVER_SCHEME == "https":
            print(f"(Stark is reachable from any other device on your WiFi - phone, tablet, another computer - "
                  f"at https://{lan_ip}:{port}/ - open that address in a browser there. The FIRST time, that "
                  f"browser will show a security warning because the certificate is self-signed (made by Stark "
                  f"itself, not a public authority) - this is expected on your own network, not a real problem; "
                  f"tap 'Advanced' then 'Proceed anyway' to continue. Camera, mic, and file upload then genuinely "
                  f"work per-device, so a phone uses its own camera/mic, not this computer's.)")
        else:
            print(f"(Stark is reachable from any other device on your WiFi - phone, tablet, another computer - "
                  f"at http://{lan_ip}:{port}/ - open that address in a browser there. Dashboard info, chat, and "
                  f"typed commands all work fine from there, but camera and microphone will NOT work from that "
                  f"other device over plain HTTP - browsers only allow camera/mic access over HTTPS or on this "
                  f"machine itself, no exceptions. Install cryptography (pip install cryptography "
                  f"--break-system-packages) and restart Stark to enable HTTPS and unlock camera/mic on other "
                  f"devices too.)")
    else:
        print(f"(Couldn't detect a LAN IP to share for other devices - Stark is still reachable at "
              f"{runtime.SERVER_SCHEME}://127.0.0.1:{port}/ from this machine.)")

    if not CHROME_AVAILABLE:
        print("(Chrome not found on this system - app-open commands will use your default browser instead.)")

    if GOOGLE_SEARCH_ENABLED:
        print("(Google Search connected via official API.)")
    else:
        print("(Google Search connected via direct scraping - no API key set. "
              "This is best-effort; Google may throttle it if used heavily.)")

    if CLOUD_LLM_URL:
        print(f"(Conversational brain connected via your own cloud endpoint: {CLOUD_LLM_URL})")
    elif OPENROUTER_ENABLED:
        print(f"(Conversational brain connected via OpenRouter, model: {OPENROUTER_MODEL}.)")
    else:
        print("(No STARK_CLOUD_LLM_URL or OPENROUTER_API_KEY set - Stark will fall back to the "
              "rule-based/Wikipedia/Google pipeline.)")

    if _DIFFUSERS_AVAILABLE:
        print(f"(Fully local, offline image generation/editing available via diffusers, model: "
              f"{LOCAL_IMAGE_MODEL}. No API key, nothing leaves this machine - first request downloads and "
              f"caches the model.)")
    else:
        print("(Local image generation not installed - install with: pip install torch diffusers "
              "--break-system-packages for fully offline, no-key image generation/editing. Falling back to "
              "OpenRouter if a key is set, else the free anonymous Pollinations.ai for generation only.)")

    if _TRANSFORMERS_AVAILABLE:
        print(f"(Fully local, offline image understanding available via transformers, caption model: "
              f"{LOCAL_CAPTION_MODEL}. No API key, nothing leaves this machine.)")
    else:
        print("(Local image understanding not installed - install with: pip install torch transformers "
              "--break-system-packages for fully offline image captioning/Q&A. Falling back to OpenRouter if "
              "a key is set, else the free anonymous Pollinations.ai.)")

    if CLOUD_LLM_URL or OPENROUTER_ENABLED:
        print(f"(Code generation available - try 'write me a script that ...'. Generated code is saved to "
              f"{GENERATED_CODE_DIR} and only ever runs after you explicitly say 'run it' - it runs with your "
              f"own account's full permissions, no sandbox, so read it before confirming.)")
    else:
        print("(Code generation needs a connected brain - set STARK_CLOUD_LLM_URL or OPENROUTER_API_KEY to "
              "enable 'write me a script that ...'.)")

    if cv2 is not None:
        print("(Camera face-detection available via OpenCV - the dashboard's camera panel can analyze snapshots.)")
    else:
        print("(OpenCV not installed - the camera panel will still show a live feed and let you snapshot, "
              "but face-count analysis is unavailable. Install with: pip install opencv-python)")

    if _detect_lang is not None:
        print("(Language auto-detection available via langdetect - replies switch TTS voice automatically.)")
    else:
        print("(langdetect not installed - language switching still works via 'speak in <language>', "
              "but auto-detection from typed text is unavailable. Install with: pip install langdetect)")

    if _AUTOMATION_AVAILABLE:
        print("(In-app automation available via pyautogui - try 'type ...', 'press enter', 'click', 'copy'/'paste'.)")
    else:
        print("(pyautogui not installed - in-app automation (typing/clicking/hotkeys) is unavailable. "
              "Install with: pip install pyautogui)")

    if EMAIL_ENABLED:
        print(f"(Email connected as {EMAIL_ADDRESS} - try 'check my email' or 'send an email to ... saying ...'.)")
    else:
        print("(Email not configured - set EMAIL_ADDRESS and EMAIL_APP_PASSWORD environment variables to enable "
              "'check my email' and 'send an email to...' commands.)")

    print(f"(Remembering {fact_count()} saved facts from before, across all chats. Nothing to install - "
          f"everything lives in {MEMORY_FILE}.)")
    print(f"(Current spoken language: {get_current_language().capitalize()}. "
          f"Say 'speak in <language>' any time to switch - e.g. 'speak in spanish', 'talk to me in hindi'.)")

    greeting = random.choice(GREETINGS)
    print(f"{BOT_NAME}:", greeting)
    update_state(question="", answer=greeting, image=None, language=get_current_language())
    speak(greeting)
    print("(Type your question in the terminal or in the dashboard's command box, or click the mic icon in the dashboard to speak.)")
    print("(Say 'new chat' to start a fresh conversation, or 'forget everything' to wipe just this one.)")
    print("(Say 'hello Stark' (or 'hey Stark' / 'hi Stark') from anywhere to wake the floating orb.)")

    if _TKINTER_AVAILABLE:
        print("(A small floating orb - a rotating sphere of glowing data points - is active in the top-right "
              "of your screen, on top of whatever app you're using. Say 'hello Stark' to wake it up, drag it "
              "to move it, click it to type or speak, and say 'write it here' after clicking into another app "
              "to type my last reply straight into it.)")
    threading.Thread(target=console_loop, daemon=True).start()
    create_floating_orb()  # blocks here on the main thread (tkinter requirement); falls back to nothing if unavailable

    if not _TKINTER_AVAILABLE:
        # No floating orb possible - keep the process alive on the console
        # loop instead of exiting immediately.
        while True:
            time.sleep(3600)


if __name__ == "__main__":
    main()