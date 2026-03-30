from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from utils.timeout import call_with_timeout
from utils.ttl_cache import ttl_cache

NEWS_CACHE_TTL_SECONDS = 300
EXTERNAL_CALL_TIMEOUT_SECONDS = 12


@ttl_cache(ttl_seconds=NEWS_CACHE_TTL_SECONDS, maxsize=128)
def fetch_news_with_sources(
    query: str,
    max_results: int = 5,
    link_prefix: str = "[Tavily]",
) -> Tuple[str, List[Dict[str, str]]]:
    """Tavily 검색 결과를 LLM용 텍스트와 링크 목록으로 반환."""
    import os

    tavily_api_key = os.getenv("TAVILY_API_KEY", "")
    if not tavily_api_key:
        msg = f"Tavily API 키가 설정되지 않았습니다. '{query}'에 대한 실시간 뉴스를 가져올 수 없습니다."
        return msg, []

    try:
        from tavily import TavilyClient

        results = call_with_timeout(
            lambda: TavilyClient(api_key=tavily_api_key).search(query=query, max_results=max_results),
            timeout_seconds=EXTERNAL_CALL_TIMEOUT_SECONDS,
            timeout_message=f"Tavily timeout: {query[:60]}",
        )
        rows = results.get("results", [])
        text = "\n".join(f"- {row['title']}: {row['content'][:200]}" for row in rows)
        links: List[Dict[str, str]] = []
        for row in rows:
            url = (row.get("url") or "").strip()
            if not url:
                continue
            title = (row.get("title") or "기사").strip()
            label = f"{link_prefix} {title}"[:200]
            links.append({"label": label, "url": url})
        return text, links
    except Exception as exc:
        return f"Tavily 뉴스 검색 중 오류 발생: {str(exc)}", []


def fetch_news(query: str) -> str:
    text, _ = fetch_news_with_sources(query)
    return text


def merge_report_source_links(
    existing: Optional[List[Dict[str, str]]],
    new_items: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    seen: set[str] = set()
    out: List[Dict[str, str]] = []
    for item in (existing or []) + new_items:
        url = (item.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        label = (item.get("label") or url).strip()
        out.append({"label": label, "url": url})
    return out


def format_report_sources_markdown(links: List[Dict[str, Any]]) -> str:
    if not links:
        return ""
    lines = ["", "## 참고 및 출처", ""]
    for index, item in enumerate(links, 1):
        label = str(item.get("label") or "링크").strip()
        url = str(item.get("url") or "").strip()
        if url:
            lines.append(f"{index}. [{label}]({url})")
    return "\n".join(lines) + "\n"
