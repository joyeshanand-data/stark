# Stark - split into files

Same assistant, same features, no behavior changes - just organized into
separate files instead of one ~7,500-line script, so it's easier to read,
edit, and put on GitHub.

## Running it

Exactly the same as before:

```
python app.py
```

That's it - `app.py` is the entry point. It finds `static/` automatically
because it looks next to itself, not next to wherever you run the command
from.

## Folder layout

```
stark/
├── app.py            <- entry point: run this. Floating orb + startup.
├── runtime.py         <- tiny shared file (see "About runtime.py" below)
├── identity.py         <- name, greetings, Google search, Chrome finder
├── state.py            <- memory, sessions, notes/reminders, shared HUD state
├── desktop.py           <- opening the dashboard/mini widget, minimizing it
├── app_launcher.py       <- finding and opening installed apps
├── automation.py          <- typing/clicking into other apps, downloads
├── voice.py                <- text-to-speech, mic input, languages
├── search.py                <- web/Wikipedia search, humanizing answers
├── files.py                  <- reading/editing uploaded files
├── system_tools.py            <- CPU/RAM stats, misc system actions
├── live_data.py                 <- news, stocks, weather, world map data
├── brain.py                      <- email, the optional cloud LLM brain
├── vision.py                      <- understanding images, camera scans
├── creation.py                     <- image generation/editing, code generation
├── conversation.py                  <- the dispatcher that ties it all together
├── webserver.py                      <- the HTTP server + page routes
└── static/
    ├── index.html                      <- the main dashboard page
    └── mini.html                        <- the floating mini widget
```

## How the files connect to each other

Each file (after the first) starts with one line like:

```python
from identity import *
```

That pulls in every name the file before it knows about - which already
includes everything THAT file pulled in from the one before IT, and so on.
So by the time you get to the last file, it has access to everything, in
the same order the original single file would have loaded it in. This is
why the files are numbered/ordered the way they are in the list above -
that order matters, it's not arbitrary.

A few functions genuinely need something from a file that comes LATER in
that list (a handful of real two-way relationships exist in the original
code too - it's just invisible in a single file). Where that happens,
you'll see either:
- an extra `from some_later_file import *` near the bottom of the file, or
- a `from some_later_file import specific_name` written *inside* the one
  function that actually needs it, with a comment explaining why.

Both are intentional and tested - not leftover mistakes.

## About `runtime.py`

This one's different from the others. It only holds two values:

```python
SERVER_PORT = 8765
SERVER_SCHEME = "http"
```

These change once, when the local server actually starts, and get read
from several other files (to build links like `http://localhost:8765/...`).
Every file that needs them does `import runtime` and reads
`runtime.SERVER_PORT` - never a plain `SERVER_PORT` - so they always see
the current value instead of a stale copy from when that file first
loaded. It's a tiny, deliberate exception to the "just import *" pattern
above, for the one place where that pattern would silently break.

## What was actually tested

Before this was packaged, every file was:
1. Individually syntax-checked (`python -m py_compile`).
2. Actually imported end-to-end through `app.py` (the real entry point) in
   a clean environment, with the dependencies from `requirements.txt`
   installed, to catch real `NameError`/`ImportError` issues - not just
   "does it parse", but "does it actually run past every import statement".
3. Spot-checked with real function calls (switching language, changing the
   server port/scheme from one file and reading it back from another) to
   confirm state that's supposed to be shared across files actually is.

This does NOT mean every feature was exercised (no mic, camera, or GUI
available in the environment this was split in) - the underlying logic in
each function is untouched from your working original, only *where it
lives* changed. If something behaves differently than before, it's almost
certainly an environment/hardware difference, not a logic change - but
please test thoroughly on your own machine before relying on it, and open
an issue (or just ask) if anything doesn't work the way it used to.

## Uploading to GitHub

From inside this folder:
```
git init
git add .
git commit -m "Split into separate files"
git remote add origin <your repo url>
git branch -M main
git push -u origin main
```

## Requirements

See `requirements.txt`. Same dependencies as before - nothing new was
added or removed, this was purely a reorganization.

## Update: camera fix + face/surroundings scanning

**Found and fixed a real bug** while adding this: 46 places in
`static/index.html`'s JavaScript had doubled backslash-escaping
(`\\'` instead of `\'`) in `onerror`/`onclick` handlers - added while
building the world-map country panel in an earlier round of edits. This
is a JavaScript *syntax* error, and since browsers parse a whole
`<script>` block before running any of it, this was silently breaking
**the entire page's JavaScript** - which is almost certainly why voice
commands like "open the camera" weren't doing anything: the code that
would have handled them never even loaded. This is fixed now (verified
with Node's own JS parser, not just eyeballing it).

**New voice commands:**
- *"open the camera" / "close the camera"* - actually opens/closes the
  browser's camera panel now. The server can't open your camera directly
  (that needs a real permission prompt in the browser), so it raises a
  flag the page checks and acts on itself, automatically.
- *"scan it" / "scan everything" / "full scan" / "read my face"* - one
  combined scan of both your face and your surroundings, with Stark
  narrating what it's doing as it goes ("scanning now" → "reading your
  face now" → "checking your surroundings") instead of going silent until
  the very end.
- The face read includes: apparent emotion/expression, plus a couple of
  playful, folklore-style "face reading" observations (jawline, forehead,
  etc - the fortune-teller kind, framed as just-for-fun, not a real
  assessment).

**On purpose, this does NOT rate/score attractiveness or "handsomeness".**
That part of the request was intentionally left out - an AI assigning a
beauty score to someone's face isn't a meaningful measurement, and it's
the kind of thing that's more likely to feed into an unhealthy fixation
on looks than to actually help anyone. Everything else from the request
(emotion reading, playful face-reading/astrology-style commentary,
combined face+surroundings scan, live narration) is implemented.