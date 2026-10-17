"""
runtime.py

Tiny module with no dependencies of its own. It holds the couple of values
that change once while the app is running (which port the local server
actually started on, and whether it's serving http or https) and get read
from several other files.

Why this gets its own tiny file instead of just living in webserver.py: if
every file grabbed these with `from webserver import SERVER_PORT`, each
file would get its own frozen snapshot from whenever it was first loaded -
and since webserver.py sets the real values later (after start_server()
actually runs), every other file would be stuck seeing the old default
forever. Keeping it here means every file does `import runtime` and reads
`runtime.SERVER_PORT` at the moment it actually needs it, so it always sees
the current value.
"""

SERVER_PORT = 8765
SERVER_SCHEME = "http"  # flips to "https" once a self-signed cert is successfully loaded