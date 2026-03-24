from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, TypeVar

from utils.logger import get_logger

logger = get_logger("utils.helpers")


def export_graph_visualization(app) -> None:
    """마크다운(.md) 및 이미지(.png) 포맷 두 가지로 다이어그램을 산출합니다."""

    # 1. Markdown(.md) 추출
    mermaid_text = app.get_graph().draw_mermaid()
    mermaid_text = mermaid_text.replace("<p>", "").replace("</p>", "")

    import re

    mermaid_text = re.sub(r"^---\nconfig:.*?\n---\n", "", mermaid_text, flags=re.DOTALL)

    md_content = f"## 📊 AlphaInvest Architecture Flow\n\n```mermaid\n{mermaid_text}\n```\n"
    with open("graph_flow.md", "w", encoding="utf-8") as f:
        f.write(md_content)

    # 2. PNG 이미지 렌더링 (그림 자체를 저장하여 에디터 한계를 원천 회피)
    try:
        png_data = app.get_graph().draw_mermaid_png()
        with open("graph_flow.png", "wb") as f:
            f.write(png_data)
        logger.info("아키텍처 다이어그램이 'graph_flow.md' 및 'graph_flow.png'에 모두 산출되었습니다.")
    except Exception as e:
        logger.warning(f"PNG 이미지 산출 중 에러 발생 (인터넷 API 연결 필요): {e}")


# ─── 병렬 처리 유틸리티 (ThreadPool 기반) ───

T = TypeVar("T")


def parallel_map_dict(
    items: Dict[str, T],
    worker: Callable[[T], Any],
    max_workers: int,
) -> Dict[str, Any]:
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        fmap = {pool.submit(worker, v): k for k, v in items.items()}
        return {fmap[f]: f.result() for f in as_completed(fmap)}


def parallel_map_list(
    items: List[T],
    worker: Callable[[T], Any],
    max_workers: int,
) -> List[Any]:
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        idx_map = {pool.submit(worker, it): i for i, it in enumerate(items)}
        results: List[Any] = [None] * len(items)
        for f in as_completed(idx_map):
            results[idx_map[f]] = f.result()
    return results


def parse_llm_json(text: str) -> List[Dict[str, Any]]:
    """LLM 응답 마크다운 블록에서 JSON을 추출하고 파싱합니다."""
    import json
    import re

    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`")
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        match = re.search(r"\[.*]", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return []
