# This file is part of the Stark split-up package. It continues on from
# conversation.py, and this one line below pulls in every name defined in every
# file before it in the chain - so this file has access to everything above
# it, exactly like it would if this were all still one big file.
from conversation import *
from identity import _face_cascade
from system_tools import _safe_upload_path
from identity import _CRYPTOGRAPHY_AVAILABLE

HTML_PAGE = open(os.path.join(STATIC_DIR, "index.html"), "r", encoding="utf-8").read()


# ---------- Compact "little screen" widget - open in its own small window ----------
MINI_HTML = open(os.path.join(STATIC_DIR, "mini.html"), "r", encoding="utf-8").read()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._reply_html(HTML_PAGE)
        elif self.path == "/mini":
            self._reply_html(MINI_HTML)
        elif self.path == "/state":
            with STATE_LOCK:
                payload_obj = dict(state)
                # one-shot flags: the browser acts on them once, so clear them
                # here rather than leaving them true and re-triggering forever
                if state.get("open_camera"):
                    state["open_camera"] = False
                if state.get("close_camera"):
                    state["close_camera"] = False
            payload_obj["has_topic"] = bool(get_topic())
            payload = json.dumps(payload_obj).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        elif self.path == "/history":
            payload = json.dumps({"history": get_recent_history(turns=60)}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        elif self.path == "/sessions":
            payload = json.dumps(list_sessions()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        elif self.path == "/extra":
            with EXTRA_LOCK:
                payload_obj = dict(extra_state)
            payload_obj["recent_facts"] = recent_auto_facts(6)
            payload = json.dumps(payload_obj).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        elif self.path.startswith("/country_info"):
            query = parse_qs(urlparse(self.path).query)
            name = (query.get("name") or [""])[0]
            info = fetch_country_info(name) if name else {"country": "", "weather": None, "news": [], "stock": None}
            payload = json.dumps(info).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        elif self.path == "/voices":
            payload = json.dumps({
                "voices": list_installed_voices(),
                "current_voice_id": get_preferred_voice(),
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        elif self.path.startswith("/generated/"):
            fname = os.path.basename(unquote(self.path[len("/generated/"):]))
            self._serve_file(os.path.join(GENERATED_IMAGE_DIR, fname))
        elif self.path.startswith("/uploads/"):
            fname = os.path.basename(unquote(self.path[len("/uploads/"):]))
            upload_path = _safe_upload_path(fname)
            if upload_path and os.path.isfile(upload_path):
                self._serve_file(upload_path)
            else:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_file(self, path):
        try:
            with open(path, "rb") as f:
                data = f.read()
        except Exception:
            self.send_response(404)
            self.end_headers()
            return
        content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else b""

        if self.path == "/command":
            try:
                payload = json.loads(body.decode("utf-8")) if body else {}
            except Exception:
                payload = {}
            text = (payload.get("text") or "").strip()
            if text:
                threading.Thread(target=process_user_input, args=(text,), daemon=True).start()
            self._reply_ok()

        elif self.path == "/listen":
            threading.Thread(target=handle_listen_request, daemon=True).start()
            self._reply_ok()

        elif self.path == "/camera_analyze":
            try:
                payload = json.loads(body.decode("utf-8")) if body else {}
            except Exception:
                payload = {}
            faces = None
            if cv2 is not None and _face_cascade is not None and payload.get("image"):
                try:
                    img_b64 = payload["image"].split(",")[1] if "," in payload["image"] else payload["image"]
                    img_data = base64.b64decode(img_b64)
                    arr = np.frombuffer(img_data, dtype=np.uint8)
                    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    if frame is not None:
                        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                        detected = _face_cascade.detectMultiScale(gray, 1.1, 5)
                        faces = len(detected)
                except Exception as e:
                    print("Camera analyze error:", e)
            out = json.dumps({"faces": faces}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        elif self.path == "/set_voice":
            try:
                payload = json.loads(body.decode("utf-8")) if body else {}
            except Exception:
                payload = {}
            set_preferred_voice(payload.get("voice_id"))
            self._reply_ok()

        elif self.path == "/upload":
            try:
                payload = json.loads(body.decode("utf-8")) if body else {}
            except Exception:
                payload = {}
            filename = payload.get("filename") or "upload.txt"
            data_url = payload.get("data") or ""
            mime = payload.get("mime")
            try:
                b64_part = data_url.split(",")[1] if "," in data_url else data_url
                raw_bytes = base64.b64decode(b64_part)
            except Exception as e:
                reply = f"Couldn't decode the upload: {e}"
                raw_bytes = None

            if raw_bytes is not None:
                reply = handle_file_upload(filename, raw_bytes, mime)

            active = get_active_upload()
            preview_url = None
            if active.get("is_image") and active.get("filename"):
                preview_url = f"{runtime.SERVER_SCHEME}://127.0.0.1:{runtime.SERVER_PORT}/uploads/{active['filename']}"

            print(f"{BOT_NAME}:", reply)
            update_state(question=f"[Uploaded: {filename}]", answer=reply, image=preview_url, thinking=False)
            remember("user", f"[Uploaded file: {filename}]")
            remember("assistant", reply)
            speak(reply)

            out = json.dumps({"ok": True, "reply": reply, "filename": active.get("filename")}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        elif self.path == "/sessions/new":
            new_session()
            update_state(question="", answer="", image=None, thinking=False)
            self._reply_ok()

        elif self.path == "/sessions/switch":
            try:
                payload = json.loads(body.decode("utf-8")) if body else {}
            except Exception:
                payload = {}
            sid = payload.get("id")
            if sid:
                switch_session(sid)
                update_state(question="", answer="", image=None, thinking=False)
            self._reply_ok()

        elif self.path == "/sessions/delete":
            try:
                payload = json.loads(body.decode("utf-8")) if body else {}
            except Exception:
                payload = {}
            sid = payload.get("id")
            if sid:
                delete_session(sid)
                update_state(question="", answer="", image=None, thinking=False)
            self._reply_ok()

        elif self.path == "/sessions/rename":
            try:
                payload = json.loads(body.decode("utf-8")) if body else {}
            except Exception:
                payload = {}
            sid, title = payload.get("id"), payload.get("title")
            if sid and title:
                rename_session(sid, title)
            self._reply_ok()

        elif self.path == "/system":
            try:
                payload = json.loads(body.decode("utf-8")) if body else {}
            except Exception:
                payload = {}
            action = payload.get("action")
            if action == "lock":
                threading.Thread(target=run_special, args=("lock_screen",), daemon=True).start()
            elif action == "shutdown":
                threading.Thread(target=run_special, args=("shutdown",), daemon=True).start()
            self._reply_ok()

        else:
            self.send_response(404)
            self.end_headers()

    def _reply_html(self, page):
        content = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def _reply_ok(self):
        resp = b'{"ok": true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)


import runtime

CERT_DIR = os.path.join(os.path.expanduser("~"), ".stark", "cert")
CERT_FILE = os.path.join(CERT_DIR, "stark_cert.pem")
KEY_FILE = os.path.join(CERT_DIR, "stark_key.pem")


def _ensure_self_signed_cert():
    """Generates a self-signed HTTPS certificate once and caches it under
    ~/.stark/cert, so restarts reuse the same certificate instead of
    generating a fresh one each time (which would make every device that
    already accepted the browser security warning have to accept it again).
    Returns True if a usable cert+key pair is available (either just
    generated or already cached), False if cryptography isn't installed or
    generation failed for some other reason."""
    if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
        return True
    if not _CRYPTOGRAPHY_AVAILABLE:
        return False
    try:
        os.makedirs(CERT_DIR, exist_ok=True)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "stark.local")])
        san_names = [x509.DNSName("localhost"), x509.DNSName("stark.local")]
        try:
            import ipaddress
            san_names.append(x509.IPAddress(ipaddress.ip_address("127.0.0.1")))
            lan_ip = get_lan_ip()
            if lan_ip and lan_ip != "127.0.0.1":
                san_names.append(x509.IPAddress(ipaddress.ip_address(lan_ip)))
        except Exception:
            pass
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow())
            .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=3650))
            .add_extension(x509.SubjectAlternativeName(san_names), critical=False)
            .sign(key, hashes.SHA256())
        )
        with open(CERT_FILE, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        with open(KEY_FILE, "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ))
        return True
    except Exception as e:
        print("Self-signed certificate generation error:", e)
        return False


def get_lan_ip():
    """Best-effort detection of this machine's LAN IP (the address other
    devices on the same WiFi/network would use to reach it) - not the same as
    'localhost', which only works from this machine itself. Opens a UDP
    'connection' to a public IP (sends nothing, just asks the OS to pick a
    route) purely to see which local interface/IP the OS would use - this is
    the standard no-dependency trick for this, and works even with no
    internet access since UDP is connectionless."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


def start_server(port=8765):
    runtime.SERVER_PORT = port
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)

    if _ensure_self_signed_cert():
        try:
            import ssl
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
            server.socket = ctx.wrap_socket(server.socket, server_side=True)
            runtime.SERVER_SCHEME = "https"
        except Exception as e:
            print("HTTPS setup error, falling back to plain HTTP:", e)
            runtime.SERVER_SCHEME = "http"
    else:
        runtime.SERVER_SCHEME = "http"

    threading.Thread(target=server.serve_forever, daemon=True).start()
    return port