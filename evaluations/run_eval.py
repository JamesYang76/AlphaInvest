import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

# 프로젝트 루트를 기준으로 경로 고정 (IDE/터미널 어디서 실행해도 동일하게 동작)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.constants import StateKey
from agents.state import get_initial_state
from agents.workflow import build_skeleton
from evaluations.metrics.qual import evaluate_with_llm_judge
from evaluations.metrics.quant import (
    calculate_composite_score,
    calculate_coverage_completeness_score,
    calculate_extraction_score,
    calculate_factual_grounding_score,
    calculate_numeric_density_score,
    calculate_section_depth_score,
    calculate_ticker_mention_score,
    evaluate_cio_report_structure,
)


# 시나리오: `python evaluations/run_eval.py` 준비 단계 — 샘플 JSON(포트폴리오·기대 엔티티)을 메모리로 읽는다.
def load_samples(path: str) -> List[Dict[str, Any]]:
    """평가용 골든 데이터셋을 로드합니다."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


# 시나리오: 평가 벤치 — 각 샘플 포트폴리오로 전체 그래프를 invoke해 최종 state를 수집한다.
def run_benchmark(app: Any, samples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    모든 샘플에 대해 파이프라인을 실행(Invoke)합니다.
    (START -> MACRO -> ... -> CIO -> END 전체 과정)
    """
    return [
        {
            "id": sample["id"],
            "input": sample["portfolio"],
            "expected_entities": sample["expected_entities"],
            # app.invoke()는 빌드된 그래프의 처음부터 끝까지(CIO 포함) 실행합니다.
            "result": app.invoke(get_initial_state(user_portfolio=sample["portfolio"])),
        }
        for sample in samples
    ]


# 시나리오: 벤치 실행 후 — FINAL_REPORT에 대해 정량 지표+LLM Judge를 한 번에 계산해 결과 행을 만든다.
def evaluate_results(run_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    CIO가 최종 생성한 'FINAL_REPORT'를 기반으로 정량/정성 평가를 수행합니다.
    """
    # 실시간 거시 데이터를 한 번만 호출 (모든 샘플에서 공유)
    from data.fetchers import fetch_macro_data

    macro_data = fetch_macro_data()

    results = []
    for data in run_data:
        report = data["result"].get(StateKey.FINAL_REPORT, "")
        portfolio = data["input"]

        structure_check = evaluate_cio_report_structure(report)
        extraction_score = calculate_extraction_score(report, data["expected_entities"])
        section_depth = calculate_section_depth_score(report)
        ticker_score = calculate_ticker_mention_score(report, portfolio)
        numeric_density = calculate_numeric_density_score(report)
        coverage = calculate_coverage_completeness_score(report)
        factual_grounding = calculate_factual_grounding_score(report, macro_data)
        composite = calculate_composite_score(
            extraction_score,
            structure_check,
            section_depth,
            ticker_score,
            numeric_density,
            coverage,
            factual_grounding,
        )

        results.append(
            {
                "id": data["id"],
                "final_report": report,
                # 세부 지표
                "structure_check": structure_check,
                "extraction_score": extraction_score,
                "section_depth": section_depth,
                "ticker_mention_score": ticker_score,
                "numeric_density_score": numeric_density,
                "coverage_score": coverage,
                "factual_grounding": factual_grounding,
                # 4대 카테고리 + 종합 점수
                "scores": composite,
                "qual_eval": evaluate_with_llm_judge(report),
                "timestamp": datetime.now().isoformat(),
            }
        )
    return results


# 시나리오: 평가 종료 시 — 타임스탬프 JSON 파일로 결과를 남겨 회귀 비교에 쓴다.
def save_report(eval_results: List[Dict[str, Any]], output_dir: str = "evaluations/results"):
    """평가 결과를 파일로 저장합니다."""
    output_path = Path(output_dir) / f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(eval_results, indent=2, ensure_ascii=False))
    logging.info(f"✅ [CIO 최종 리포트 평가완료] 결과 저장: {output_path}")


# 시나리오: 오프라인 품질 벤치 전체 오케스트레이션 — 샘플 로드→invoke→스코어→저장.
def main():
    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    # 1. 환경 준비 (LangGraph Skeleton 빌드)
    app = build_skeleton()
    samples = load_samples("evaluations/data/samples.json")

    # 2. 벤치마크 실행 (Macro부터 CIO까지 전체 자동화)
    logging.info(f"🚀 {len(samples)}개의 샘플에 대해 전체 파이프라인(START -> ... -> CIO) 평가를 시작합니다...")
    run_data = run_benchmark(app, samples)

    # 3. CIO 결과물 기반 평가 적용
    eval_results = evaluate_results(run_data)

    # 4. 결과 저장
    save_report(eval_results)


if __name__ == "__main__":
    main()
