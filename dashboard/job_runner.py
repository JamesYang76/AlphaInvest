from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional

from dashboard.data import build_dashboard_payload, parse_holdings_input
from dashboard.job_payloads import build_canceled_payload, build_failure_payload
from dashboard.job_store import (
    JOB_STALE_SECONDS,
    JOB_TIMEOUT_SECONDS,
    ReportJob,
    ReportJobCancelledError,
    job_store,
    progress_label,
)
from dashboard.reporting import build_market_report, build_portfolio_report
from utils.logger import get_logger
from utils.notion_publisher import publish_to_notion
from utils.timing import format_elapsed_ms, start_timer

logger = get_logger("dashboard.job_runner")


def cancel_report_job(job_id: str) -> Optional[ReportJob]:
    return job_store.request_cancel(job_id)


def enqueue_report_job(flow: str, holdings: str) -> ReportJob:
    job = job_store.create(flow=flow, holdings=holdings)
    threading.Thread(target=_run_report_job, args=(job.id,), daemon=True).start()
    logger.info("[Timing] report_job enqueued id=%s flow=%s", job.id, flow)
    return job


def _ensure_not_cancelled(job_id: str) -> None:
    job = job_store.get(job_id)
    if job is not None and job.cancel_requested:
        raise ReportJobCancelledError()


def _run_report_job(job_id: str) -> None:
    job = job_store.get(job_id)
    if job is None:
        return

    job_started_at = start_timer()
    job_store.mark_running(job_id)
    _ensure_not_cancelled(job_id)
    job_store.heartbeat(job_id, "job_started")

    def progress_callback(step: str) -> None:
        _ensure_not_cancelled(job_id)
        job_store.heartbeat(job_id, step)

    try:
        if job.flow == "market":
            report_payload = build_market_report(
                progress_callback=progress_callback,
                cancel_check=lambda: _ensure_not_cancelled(job_id),
            )
            _ensure_not_cancelled(job_id)
            pipeline_snapshot = report_payload.get("pipeline_snapshot")
            job_store.heartbeat(job_id, "build_dashboard_payload")
            _ensure_not_cancelled(job_id)
            payload = build_dashboard_payload(
                holdings=job.holdings,
                market_report_override=report_payload,
                market_notion_url="",
                persist_resolved_holdings=False,
                pipeline_snapshot=pipeline_snapshot,
            )
        else:
            job_store.heartbeat(job_id, "parse_holdings_input")
            _ensure_not_cancelled(job_id)
            parsed_holdings = parse_holdings_input(job.holdings)
            report_payload = build_portfolio_report(
                parsed_holdings,
                progress_callback=progress_callback,
                cancel_check=lambda: _ensure_not_cancelled(job_id),
            )
            _ensure_not_cancelled(job_id)
            pipeline_snapshot = report_payload.get("pipeline_snapshot")
            job_store.heartbeat(job_id, "build_dashboard_payload")
            _ensure_not_cancelled(job_id)
            payload = build_dashboard_payload(
                holdings=job.holdings,
                portfolio_report_override=report_payload,
                portfolio_notion_url="",
                persist_resolved_holdings=True,
                fallback_to_saved_portfolio=False,
                pipeline_snapshot=pipeline_snapshot,
            )

        job_store.mark_completed(job_id, payload)
        threading.Thread(
            target=_publish_report_to_notion_after_completion,
            args=(job_id, job.flow, report_payload),
            daemon=True,
        ).start()
        logger.info(
            "[Timing] report_job completed id=%s flow=%s duration=%s",
            job_id,
            job.flow,
            format_elapsed_ms(job_started_at),
        )
    except ReportJobCancelledError:
        payload = build_canceled_payload(job.flow, job.holdings)
        job_store.mark_canceled(job_id, payload)
        logger.info(
            "[Timing] report_job canceled id=%s flow=%s duration=%s",
            job_id,
            job.flow,
            format_elapsed_ms(job_started_at),
        )
    except Exception as exc:
        error_text = f"리포트 생성 중 오류가 발생했습니다: {exc}"
        payload = build_failure_payload(job.flow, job.holdings, error_text)
        job_store.mark_failed(job_id, error_text, payload)
        logger.exception(
            "[Timing] report_job failed id=%s flow=%s duration=%s error=%s",
            job_id,
            job.flow,
            format_elapsed_ms(job_started_at),
            exc,
        )


def _publish_report_to_notion(flow: str, report_payload: Dict[str, Any]) -> str:
    report_text = str(report_payload.get("report", "") or "").strip()
    report_error = str(report_payload.get("error", "") or "").strip()
    portfolio_label = str(report_payload.get("portfolio_label", "") or "").strip()
    if not report_text or report_error:
        return ""

    if flow == "market":
        title = "AlphaInvest 시장 리포트"
    else:
        title = f"AlphaInvest 포트폴리오 리포트 - {portfolio_label or '사용자 포트폴리오'}"

    try:
        return publish_to_notion(title=title, markdown_text=report_text)
    except Exception as exc:
        logger.warning("[Notion] dashboard publish failed flow=%s error=%s", flow, exc)
        return ""


def _publish_report_to_notion_after_completion(job_id: str, flow: str, report_payload: Dict[str, Any]) -> None:
    job = job_store.get(job_id)
    if job is None or job.cancel_requested:
        return
    notion_started_at = start_timer()
    notion_url = _publish_report_to_notion(flow, report_payload)
    if not notion_url:
        return
    field_name = "market_notion_url" if flow == "market" else "portfolio_notion_url"
    job_store.update_payload_field(job_id, field_name, notion_url)
    logger.info(
        "[Timing] report_job notion_published id=%s flow=%s duration=%s",
        job_id,
        flow,
        format_elapsed_ms(notion_started_at),
    )


def _watchdog_loop() -> None:
    while True:
        time.sleep(5)
        now = time.time()
        for job in job_store.list_running():
            if job.started_at is None:
                continue
            if now - job.started_at > JOB_TIMEOUT_SECONDS:
                error_text = (
                    f"리포트 생성 제한 시간({JOB_TIMEOUT_SECONDS}초)을 초과했습니다. "
                    f"마지막 단계: {progress_label(job.current_step)}"
                )
                payload = build_failure_payload(job.flow, job.holdings, error_text)
                job_store.mark_failed(job.id, error_text, payload)
                logger.error("[Timing] report_job timeout id=%s step=%s", job.id, job.current_step)
                continue
            last_heartbeat = job.last_heartbeat or job.started_at
            if now - last_heartbeat > JOB_STALE_SECONDS:
                error_text = (
                    "리포트 생성이 장시간 멈춘 것으로 감지되었습니다. "
                    f"마지막 단계: {progress_label(job.current_step)}"
                )
                payload = build_failure_payload(job.flow, job.holdings, error_text)
                job_store.mark_failed(job.id, error_text, payload)
                logger.error("[Timing] report_job stale id=%s step=%s", job.id, job.current_step)


threading.Thread(target=_watchdog_loop, daemon=True).start()
