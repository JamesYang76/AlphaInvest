import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

from agents.constants import StateKey
from agents.state import get_initial_state
from agents.workflow import build_skeleton
from evaluations.metrics.qual import evaluate_with_llm_judge
from evaluations.metrics.quant import calculate_extraction_score, evaluate_cio_report_structure


def load_samples(path: str) -> List[Dict[str, Any]]:
    """평가용 골든 데이터셋을 로드합니다."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


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


def evaluate_results(run_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    CIO가 최종 생성한 'FINAL_REPORT'를 기반으로 정량/정성 평가를 수행합니다.
    """
    return [
        {
            "id": data["id"],
            "final_report": data["result"].get(StateKey.FINAL_REPORT, ""),
            "structure_check": evaluate_cio_report_structure(data["result"].get(StateKey.FINAL_REPORT, "")),
            "quant_score": calculate_extraction_score(data["result"].get(StateKey.FINAL_REPORT, ""), data["expected_entities"]),
            "qual_eval": evaluate_with_llm_judge(data["result"].get(StateKey.FINAL_REPORT, "")),
            "timestamp": datetime.now().isoformat(),
        }
        for data in run_data
    ]


def save_report(eval_results: List[Dict[str, Any]], output_dir: str = "evaluations/results"):
    """평가 결과를 파일로 저장합니다."""
    output_path = Path(output_dir) / f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(eval_results, indent=2, ensure_ascii=False))
    logging.info(f"✅ [CIO 최종 리포트 평가완료] 결과 저장: {output_path}")


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
