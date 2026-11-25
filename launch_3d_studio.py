"""Launch Simi's local 3D Character Studio directly on your PC."""

from __future__ import annotations

import functools
import http.server
import socketserver
import threading
import webbrowser
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent / "docs"
PORT = 8799


def main() -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DOCS_DIR))
    socketserver.TCPServer.allow_reuse_address = True
    try:
        httpd = socketserver.TCPServer(("127.0.0.1", PORT), handler)
    except OSError:
        # Already running
        webbrowser.open(f"http://127.0.0.1:{PORT}/3d-studio.html")
        return

    threading.Timer(0.6, lambda: webbrowser.open(f"http://127.0.0.1:{PORT}/3d-studio.html")).start()
    print(f"Simi 3D Studio running at http://127.0.0.1:{PORT}/3d-studio.html (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
