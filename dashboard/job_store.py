from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

JOB_TTL_SECONDS = 3600
JOB_TIMEOUT_SECONDS = 240
JOB_STALE_SECONDS = 90


class ReportJobCancelledError(Exception):
    pass


@dataclass
class ReportJob:
    id: str
    flow: str
    holdings: str
    status: str = "pending"
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    last_heartbeat: float | None = None
    current_step: str = ""
    cancel_requested: bool = False
    error: str = ""
    payload: Optional[Dict[str, Any]] = None


class ReportJobStore:
    def __init__(self) -> None:
        self._jobs: Dict[str, ReportJob] = {}
        self._lock = threading.RLock()

    def create(self, flow: str, holdings: str) -> ReportJob:
        job = ReportJob(id=uuid.uuid4().hex[:12], flow=flow, holdings=holdings)
        with self._lock:
            self._prune_locked()
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Optional[ReportJob]:
        with self._lock:
            self._prune_locked()
            return self._jobs.get(job_id)

    def mark_running(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.finished_at is not None:
                return
            if not job.cancel_requested:
                job.status = "running"
            job.started_at = time.time()
            job.last_heartbeat = job.started_at

    def mark_completed(self, job_id: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status in {"failed", "canceled", "canceling"}:
                return
            job.status = "completed"
            job.finished_at = time.time()
            job.last_heartbeat = job.finished_at
            job.payload = payload

    def update_payload_field(self, job_id: str, field_name: str, value: Any) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.payload is None:
                return
            job.payload[field_name] = value

    def mark_failed(self, job_id: str, error: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.finished_at is not None:
                return
            job.status = "failed"
            job.finished_at = time.time()
            job.last_heartbeat = job.finished_at
            job.error = error
            job.payload = payload

    def request_cancel(self, job_id: str) -> Optional[ReportJob]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.finished_at is not None:
                return job
            job.cancel_requested = True
            if job.status in {"pending", "running"}:
                job.status = "canceling"
                job.current_step = "cancel_requested"
                job.last_heartbeat = time.time()
            return job

    def mark_canceled(self, job_id: str, payload: Dict[str, Any]) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.finished_at is not None:
                return
            job.status = "canceled"
            job.finished_at = time.time()
            job.last_heartbeat = job.finished_at
            job.error = "리포트 생성을 사용자가 취소했습니다."
            job.payload = payload

    def heartbeat(self, job_id: str, step: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.finished_at is not None:
                return
            job.current_step = step
            job.last_heartbeat = time.time()

    def list_running(self) -> list[ReportJob]:
        with self._lock:
            self._prune_locked()
            return [
                job
                for job in self._jobs.values()
                if job.status in {"running", "canceling"} and job.finished_at is None
            ]

    def _prune_locked(self) -> None:
        now = time.time()
        expired = [
            job_id
            for job_id, job in self._jobs.items()
            if job.finished_at is not None and now - job.finished_at > JOB_TTL_SECONDS
        ]
        for job_id in expired:
            self._jobs.pop(job_id, None)


def progress_label(step: str) -> str:
    mapping = {
        "macro_node": "거시 데이터 분석",
        "macro_fetch_data": "거시 데이터 수집",
        "macro_fetch_news": "거시 뉴스 수집",
        "macro_write_report": "거시 환경 요약 작성",
        "portfolio_node": "포트폴리오 진단",
        "portfolio_enrich_holdings": "보유 종목 데이터 보강",
        "portfolio_fetch_sector_context": "보유 섹터 컨텍스트 조회",
        "portfolio_write_report": "포트폴리오 진단 작성",
        "chart_node": "차트 신호 계산",
        "chart_fetch_portfolio_signals": "보유 종목 차트 신호 계산",
        "chart_fetch_benchmark_signals": "시장 벤치마크 차트 신호 계산",
        "chart_build_allocation_analysis": "시장 배분 해석 작성",
        "risk_node": "리스크 분석",
        "risk_build_macro_context": "리스크용 거시 컨텍스트 구성",
        "risk_fetch_news": "리스크 뉴스 수집",
        "risk_extract_entities": "리스크 엔티티 추출",
        "risk_fetch_signals": "리스크 종목 신호 계산",
        "risk_score_clusters": "리스크 군집 점수화",
        "risk_write_report": "리스크 경보 작성",
        "alpha_node": "알파 테마 분석",
        "alpha_discover_themes": "알파 테마 발굴",
        "alpha_write_report": "투자 기회 작성",
        "build_final_report": "최종 리포트 조립",
        "build_dashboard_payload": "대시보드 결과 정리",
        "publish_to_notion": "Notion 발행",
        "cancel_requested": "취소 처리 중",
    }
    return mapping.get(step, step or "작업 준비")


job_store = ReportJobStore()
