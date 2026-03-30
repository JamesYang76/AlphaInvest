from __future__ import annotations

from typing import Any, Dict

from dashboard.data import build_dashboard_payload
from dashboard.job_store import ReportJob, progress_label


def build_failure_payload(flow: str, holdings: str, error: str) -> Dict[str, Any]:
    market_override = None
    portfolio_override = None

    if flow == "market":
        market_override = {
            "portfolio_label": "시장 전체 (보유 종목 없음)",
            "report": "",
            "error": error,
            "mode": "fast",
            "pipeline_snapshot": {},
        }
    else:
        portfolio_override = {
            "portfolio_label": "",
            "report": "",
            "error": error,
            "mode": "fast",
            "pipeline_snapshot": {},
        }

    return build_dashboard_payload(
        holdings=holdings,
        market_report_override=market_override,
        portfolio_report_override=portfolio_override,
        fallback_to_saved_portfolio=flow != "portfolio",
        defer_reports=True,
        pending_job={},
    )


def build_canceled_payload(flow: str, holdings: str) -> Dict[str, Any]:
    return build_failure_payload(flow, holdings, "리포트 생성을 취소했습니다.")


def build_pending_payload(job: ReportJob) -> Dict[str, Any]:
    return build_dashboard_payload(
        holdings=job.holdings,
        fallback_to_saved_portfolio=job.flow != "portfolio",
        defer_reports=True,
        pending_job={
            "id": job.id,
            "flow": job.flow,
            "status": job.status,
            "current_step": progress_label(job.current_step),
            "status_url": f"/api/report-jobs/{job.id}",
            "cancel_url": f"/api/report-jobs/{job.id}/cancel",
            "result_url": f"/?job_id={job.id}",
        },
    )


def serialize_job(job: ReportJob) -> Dict[str, Any]:
    return {
        "id": job.id,
        "flow": job.flow,
        "status": job.status,
        "current_step": progress_label(job.current_step),
        "error": job.error,
        "cancel_url": f"/api/report-jobs/{job.id}/cancel",
        "result_url": f"/?job_id={job.id}",
    }
