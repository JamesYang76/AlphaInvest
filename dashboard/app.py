from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from dashboard.data import build_dashboard_payload
from dashboard.jobs import build_pending_payload, cancel_report_job, enqueue_report_job, job_store, serialize_job
from dashboard.render import render_dashboard
from utils.logger import get_logger
from utils.timing import format_elapsed_ms, start_timer

logger = get_logger("dashboard.app")


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        request_started_at = start_timer()
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        holdings = qs.get("holdings", [""])[0]
        job_id = qs.get("job_id", [""])[0].strip()
        if parsed.path == "/api/dashboard":
            self._send_json(build_dashboard_payload(holdings=holdings))
            logger.info("[Timing] dashboard GET path=%s duration=%s", parsed.path, format_elapsed_ms(request_started_at))
            return
        if parsed.path.startswith("/api/report-jobs/"):
            job_id = parsed.path.rsplit("/", 1)[-1].strip()
            job = job_store.get(job_id)
            if job is None:
                self.send_error(404, "Job Not Found")
                return
            self._send_json(serialize_job(job))
            logger.info("[Timing] dashboard GET path=%s duration=%s", parsed.path, format_elapsed_ms(request_started_at))
            return
        if parsed.path in {"/", "/index.html"}:
            if job_id:
                job = job_store.get(job_id)
                if job is not None:
                    if job.status in {"completed", "failed", "canceled"} and job.payload is not None:
                        self._send_html(render_dashboard(job.payload))
                    else:
                        self._send_html(render_dashboard(build_pending_payload(job)))
                    logger.info(
                        "[Timing] dashboard GET path=%s job_id=%s duration=%s",
                        parsed.path,
                        job_id,
                        format_elapsed_ms(request_started_at),
                    )
                    return
            self._send_html(render_dashboard(build_dashboard_payload(holdings=holdings)))
            logger.info("[Timing] dashboard GET path=%s duration=%s", parsed.path, format_elapsed_ms(request_started_at))
            return
        self.send_error(404, "Not Found")

    def do_POST(self) -> None:
        request_started_at = start_timer()
        parsed = urlparse(self.path)
        if parsed.path not in {"/", "/index.html"}:
            if parsed.path.startswith("/api/report-jobs/") and parsed.path.endswith("/cancel"):
                job_id = parsed.path.split("/")[-2].strip()
                job = cancel_report_job(job_id)
                if job is None:
                    self.send_error(404, "Job Not Found")
                    return
                self._send_json(serialize_job(job))
                logger.info(
                    "[Timing] dashboard POST path=%s job_id=%s duration=%s",
                    parsed.path,
                    job_id,
                    format_elapsed_ms(request_started_at),
                )
                return
            self.send_error(404, "Not Found")
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length).decode("utf-8") if length else ""
        qs = parse_qs(body)
        holdings = qs.get("holdings", [""])[0]
        flow = qs.get("flow", ["portfolio"])[0]
        if flow == "portfolio" and not holdings.strip():
            payload = build_dashboard_payload(
                holdings=holdings,
                portfolio_report_override={"portfolio_label": "", "report": "", "error": "보유 종목을 입력해주세요."},
                fallback_to_saved_portfolio=False,
                defer_reports=True,
            )
            self._send_html(render_dashboard(payload))
            logger.info("[Timing] dashboard POST flow=%s total duration=%s", flow, format_elapsed_ms(request_started_at))
            return

        job = enqueue_report_job(flow=flow, holdings=holdings)
        self._redirect(f"/?job_id={job.id}")
        logger.info("[Timing] dashboard POST flow=%s enqueued_job=%s duration=%s", flow, job.id, format_elapsed_ms(request_started_at))

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

    def _redirect(self, location: str) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8000), DashboardHandler)
    print("AlphaInvest dashboard available at http://127.0.0.1:8000")
    server.serve_forever()


if __name__ == "__main__":
    main()
