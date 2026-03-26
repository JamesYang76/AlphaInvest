from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from dashboard.data import build_dashboard_payload
from dashboard.render import render_dashboard


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        holdings = parse_qs(parsed.query).get("holdings", [""])[0]
        if parsed.path == "/api/dashboard":
            self._send_json(build_dashboard_payload(holdings=holdings))
            return
        if parsed.path in {"/", "/index.html"}:
            self._send_html(render_dashboard(build_dashboard_payload(holdings=holdings)))
            return
        self.send_error(404, "Not Found")

    def log_message(self, format: str, *args) -> None:
        return

    def _send_html(self, body: str) -> None:
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8000), DashboardHandler)
    print("AlphaInvest dashboard available at http://127.0.0.1:8000")
    server.serve_forever()


if __name__ == "__main__":
    main()
