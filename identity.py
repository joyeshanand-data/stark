import os
import sys
import json
import random
import re
import time
import threading
import subprocess
import webbrowser
import ast
import difflib
import datetime
import math
from urllib.parse import unquote, urlparse, parse_qs

import requests
import wikipedia
import pyttsx3
import speech_recognition as sr
import sounddevice as sd
import numpy as np
import psutil  # pip install psutil - powers the real CPU/RAM/network stats
from ddgs import DDGS
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# The static/ folder (index.html, mini.html) always lives right next to this
# file, no matter what directory you run "python app.py" from.
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

# ---------- Assistant identity ----------
# Lives here (rather than down in desktop.py, where the Google-search/Chrome
# stuff is) because state.py needs these immediately - it's used all over
# state.py's reply strings - and identity.py is the one file guaranteed to
# already be fully loaded by then.
BOT_NAME = "Stark"
USER_TITLE = "boss"

# Optional camera/vision support - only used if opencv is installed AND working,
# never required. Guards against ImportError (not installed) as well as
# AttributeError (a broken/partial install, or a local file/folder literally
# named "cv2" shadowing the real package) - either way Stark just runs without
# face-count analysis instead of crashing on startup.
try:
    import cv2
    _face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    if _face_cascade.empty():
        raise RuntimeError("Haar cascade file failed to load")
except Exception as e:
    if "cv2" in sys.modules and not isinstance(e, ImportError):
        print(f"(OpenCV found but not working ({e}) - camera face-detection disabled. "
              f"Try: pip uninstall opencv-python opencv-python-headless opencv-contrib-python -y "
              f"&& pip install opencv-python --break-system-packages. Also check there's no local "
              f"file/folder named 'cv2' in your project folder shadowing the real package.)")
    cv2 = None
    _face_cascade = None
import base64
import mimetypes
import socket

# Optional floating orb widget - tkinter ships with most Python installs, but
# guard anyway (some minimal Linux distros split it into a separate package).
try:
    import tkinter as tk
    _TKINTER_AVAILABLE = True
except ImportError:
    tk = None
    _TKINTER_AVAILABLE = False

# Optional language detection - only used if installed, never required. Powers
# auto language matching for speech input/output with no API key needed.
try:
    from langdetect import detect as _detect_lang
except ImportError:
    _detect_lang = None

# Optional file-format readers - only used if installed, never required.
try:
    import docx as _docx  # pip install python-docx
except ImportError:
    _docx = None

try:
    from pypdf import PdfReader as _PdfReader  # pip install pypdf
except ImportError:
    try:
        from PyPDF2 import PdfReader as _PdfReader  # pip install PyPDF2
    except ImportError:
        _PdfReader = None

# Optional local AI - only used if installed, never required. When present,
# these let Stark generate/edit images and understand images fully offline,
# on your own machine, with no API key and nothing sent anywhere. Heavier to
# set up (multi-GB model downloads on first use, slower without a GPU) than
# the cloud fallbacks, but the most private option since nothing leaves the
# machine. Guarded the same way as the other optional deps above - Stark runs
# fine without them and just falls back to the cloud paths.
try:
    import torch
    from diffusers import AutoPipelineForText2Image, AutoPipelineForImage2Image
    _DIFFUSERS_AVAILABLE = True
except ImportError:
    torch = None
    _DIFFUSERS_AVAILABLE = False

try:
    from transformers import BlipProcessor, BlipForConditionalGeneration, BlipForQuestionAnswering
    _TRANSFORMERS_AVAILABLE = True
except ImportError:
    _TRANSFORMERS_AVAILABLE = False

# Optional HTTPS support - only used if the `cryptography` package is
# installed, never required. Browsers only grant camera/microphone access on
# a "secure context" (HTTPS, or localhost specifically) - a plain HTTP
# address like http://192.168.1.5:8765/ (what a phone would use over WiFi)
# is blocked by the browser itself, regardless of anything server-side. This
# lets Stark generate a self-signed certificate and serve over HTTPS instead,
# so camera/mic genuinely work from other devices too, not just this machine.
try:
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    _CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    _CRYPTOGRAPHY_AVAILABLE = False

# ---------- OpenRouter LLM toggle ----------
# Lives here (rather than down in brain.py, where the actual call_llm()
# function is) because state.py needs OPENROUTER_ENABLED immediately when
# it builds the initial HUD state dict, and identity.py is the one file
# guaranteed to already be loaded by then.
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENROUTER_ENABLED = bool(OPENROUTER_API_KEY)