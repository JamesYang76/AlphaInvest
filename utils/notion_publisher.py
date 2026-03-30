"""Notion API를 통한 리포트 발행 유틸리티 모듈"""

import argparse
import datetime
import json
import os
import sys
import re
from typing import Any, Dict, List, Tuple, Union

from notion_client import Client

from utils.logger import get_logger

logger = get_logger("utils.notion_publisher")

_RICH_TEXT_LIMIT = 2000
_BLOCKS_PER_REQUEST = 100

_INLINE_PATTERN = re.compile(r"(\*\*(.+?)\*\*|\*(.+?)\*|([^*]+))")
_HEADING_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("heading_3", re.compile(r"^###\s+(.+)")),
    ("heading_2", re.compile(r"^##\s+(.+)")),
    ("heading_1", re.compile(r"^#\s+(.+)")),
]
_BULLET_PATTERN = re.compile(r"^[-*]\s+(.*)")
_NUMBERED_PATTERN = re.compile(r"^\d+\.\s+(.*)")
_DIVIDER_PATTERN = re.compile(r"^-{3,}$|^\*{3,}$")


# ============================================================
# 1. Notion Rich-Text 변환
# ============================================================
def _rich_text_obj(content: str, bold: bool = False, italic: bool = False) -> Dict[str, Any]:
    """단일 Notion rich_text 오브젝트를 생성합니다."""
    rt: Dict[str, Any] = {
        "type": "text",
        "text": {"content": content},
    }
    if bold or italic:
        rt["annotations"] = {"bold": bold, "italic": italic}
    return rt


def _chunk_text(content: str, chunk_size: int = _RICH_TEXT_LIMIT) -> List[str]:
    """Notion rich_text 길이 제한(2000자)에 맞춰 안전하게 분할합니다."""
    if not content:
        return [""]
    return [content[i : i + chunk_size] for i in range(0, len(content), chunk_size)]


def _rich_text_objects(content: str, bold: bool = False, italic: bool = False) -> List[Dict[str, Any]]:
    """문자열을 Notion rich_text 배열(길이 제한 분할 포함)로 변환합니다."""
    return [_rich_text_obj(chunk, bold=bold, italic=italic) for chunk in _chunk_text(content)]


def _parse_inline_markdown(text: str) -> List[Dict[str, Any]]:
    """인라인 마크다운(**bold**, *italic*)을 Notion rich_text 배열로 변환합니다."""
    segments: List[Dict[str, Any]] = []
    for match in _INLINE_PATTERN.finditer(text):
        if match.group(2):
            segments.extend(_rich_text_objects(match.group(2), bold=True))
        elif match.group(3):
            segments.extend(_rich_text_objects(match.group(3), italic=True))
        elif match.group(4):
            segments.extend(_rich_text_objects(match.group(4)))
    return segments or _rich_text_objects(text)


# ============================================================
# 2. Markdown → Notion Block 변환
# ============================================================
def _make_block(block_type: str, rich_text: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Notion block 오브젝트를 생성합니다."""
    return {"object": "block", "type": block_type, block_type: {"rich_text": rich_text}}


def _classify_line(line: str) -> Tuple[str, str]:
    """마크다운 한 줄을 (block_type, content) 튜플로 분류합니다."""
    stripped = line.strip()
    if not stripped:
        return ("empty", "")
    if _DIVIDER_PATTERN.match(stripped):
        return ("divider", "")
    for block_type, pattern in _HEADING_PATTERNS:
        if m := pattern.match(stripped):
            return (block_type, m.group(1))
    if m := _BULLET_PATTERN.match(stripped):
        return ("bulleted_list_item", m.group(1))
    if m := _NUMBERED_PATTERN.match(stripped):
        return ("numbered_list_item", m.group(1))
    # 들여쓴 리스트도 리스트로 취급해 디자인 손실을 줄입니다.
    indented = stripped.lstrip()
    if m := _BULLET_PATTERN.match(indented):
        return ("bulleted_list_item", m.group(1))
    if m := _NUMBERED_PATTERN.match(indented):
        return ("numbered_list_item", m.group(1))
    return ("paragraph", stripped)


def markdown_to_notion_blocks(markdown_text: str) -> List[Dict[str, Any]]:
    """마크다운 전문을 Notion Block 오브젝트 리스트로 변환합니다."""
    blocks: List[Dict[str, Any]] = []
    paragraph_buffer: List[str] = []

    def flush_paragraph() -> None:
        if not paragraph_buffer:
            return
        paragraph_text = "\n".join(paragraph_buffer).strip()
        if paragraph_text:
            blocks.append(_make_block("paragraph", _parse_inline_markdown(paragraph_text)))
        paragraph_buffer.clear()

    for line in markdown_text.split("\n"):
        block_type, content = _classify_line(line)
        if block_type == "empty":
            flush_paragraph()
            continue
        if block_type == "divider":
            flush_paragraph()
            blocks.append({"object": "block", "type": "divider", "divider": {}})
            continue
        if block_type == "paragraph":
            paragraph_buffer.append(content)
            continue
        flush_paragraph()
        blocks.append(_make_block(block_type, _parse_inline_markdown(content)))
    flush_paragraph()
    return blocks


# ============================================================
# 3. Notion 페이지 생성 API_check
# ============================================================
def _detect_title_property(client: Client, database_id: str) -> str:
    """데이터베이스/데이터소스 스키마에서 title 타입 프로퍼티 이름을 자동 탐지합니다."""
    db = client.databases.retrieve(database_id=database_id)
    if "properties" in db:
        title_props = [name for name, prop in db["properties"].items() if prop["type"] == "title"]
        return title_props[0] if title_props else "Name"

    # Notion 최신 API 응답에서는 database에 properties 대신 data_sources가 포함될 수 있습니다.
    data_sources = db.get("data_sources", [])
    if data_sources and hasattr(client, "data_sources"):
        ds_id = data_sources[0]["id"]
        ds = client.data_sources.retrieve(data_source_id=ds_id)
        title_props = [name for name, prop in ds.get("properties", {}).items() if prop.get("type") == "title"]
        return title_props[0] if title_props else "Name"

    return "Name"


def _detect_date_property(client: Client, database_id: str) -> str:
    """데이터베이스/데이터소스 스키마에서 date 타입 프로퍼티 이름을 자동 탐지합니다."""
    db = client.databases.retrieve(database_id=database_id)
    if "properties" in db:
        date_props = [name for name, prop in db["properties"].items() if prop["type"] == "date"]
        return date_props[0] if date_props else ""

    data_sources = db.get("data_sources", [])
    if data_sources and hasattr(client, "data_sources"):
        ds_id = data_sources[0]["id"]
        ds = client.data_sources.retrieve(data_source_id=ds_id)
        date_props = [name for name, prop in ds.get("properties", {}).items() if prop.get("type") == "date"]
        return date_props[0] if date_props else ""

    return ""


def _build_page_properties(client: Client, database_id: str, title: str) -> Dict[str, Any]:
    """페이지 생성 시 사용할 속성(title/date)을 구성합니다."""
    title_prop = _detect_title_property(client, database_id)
    properties: Dict[str, Any] = {
        title_prop: {"title": [{"text": {"content": title}}]},
    }

    date_prop = _detect_date_property(client, database_id)
    if date_prop:
        now = datetime.datetime.now().replace(microsecond=0)
        properties[date_prop] = {
            "date": {
                "start": now.isoformat(),
                "time_zone": "Asia/Seoul",
            }
        }

    return properties


def _append_remaining_blocks(client: Client, page_id: str, blocks: List[Dict[str, Any]]) -> None:
    """100개 초과 블록을 배치 단위로 추가 적재합니다."""
    for i in range(0, len(blocks), _BLOCKS_PER_REQUEST):
        client.blocks.children.append(block_id=page_id, children=blocks[i : i + _BLOCKS_PER_REQUEST])


def publish_to_notion(title: str, markdown_text: str) -> str:
    """Notion 데이터베이스에 새 페이지를 생성하고 URL을 반환합니다."""
    api_key = os.getenv("NOTION_API_KEY", "")
    database_id = os.getenv("NOTION_DATABASE_ID", "")

    if not api_key or not database_id:
        logger.warning("[Notion] NOTION_API_KEY 또는 NOTION_DATABASE_ID 환경변수가 미설정입니다.")
        return ""

    client = Client(auth=api_key)
    blocks = markdown_to_notion_blocks(markdown_text)
    properties = _build_page_properties(client, database_id, title)

    page = client.pages.create(
        parent={"database_id": database_id},
        properties=properties,
        children=blocks[:_BLOCKS_PER_REQUEST],
    )

    page_url = page.get("url", "")
    _append_remaining_blocks(client, page["id"], blocks[_BLOCKS_PER_REQUEST:])

    logger.info(f"[Notion] 페이지 발행 완료: {page_url}")
    return page_url


def _risk_test_json_to_markdown(payload: Dict[str, Any]) -> str:
    """tests/test_risk_node.py 출력(JSON)을 Notion용 Markdown으로 포장합니다."""
    lines: List[str] = []

    if "risk_result" in payload:
        lines.append("## Risk Result")
        lines.append(str(payload.get("risk_result", "")))

    if "current_report" in payload:
        lines.append("")
        lines.append("## Current Report")
        lines.append(str(payload.get("current_report", "")))

    # 부가 디버깅 필드(있을 때만)
    if payload.get("last_node"):
        lines.append("")
        lines.append(f"- last_node: {payload.get('last_node')}")

    return "\n".join(lines).strip()


def publish_json_to_notion(title: str, json_payload: Union[str, Dict[str, Any]]) -> str:
    """JSON(텍스트 또는 dict)을 받아 Notion에 페이지로 발행합니다."""
    try:
        if isinstance(json_payload, str):
            payload = json.loads(json_payload)
        else:
            payload = json_payload
    except Exception as e:
        logger.error(f"[Notion] JSON 파싱 실패: {e}")
        return ""

    if isinstance(payload, dict) and ("risk_result" in payload or "current_report" in payload):
        markdown_text = _risk_test_json_to_markdown(payload)
    else:
        # 일반 JSON은 코드블록 없이도 일단 보기 좋게 정렬해서 paragraph로 보냅니다.
        markdown_text = json.dumps(payload, ensure_ascii=False, indent=2)

    return publish_to_notion(title=title, markdown_text=markdown_text)


def _read_text_from_stdin() -> str:
    chunks = []
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        chunks.append(line)
    return "".join(chunks).strip()


def main() -> None:
    # CLI 실행 시에도 .env를 읽어서 NOTION_* 환경변수를 채웁니다.
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        # .env 로더가 없거나 실패해도, 사용자가 환경변수를 직접 세팅하면 계속 동작합니다.
        pass

    today_str = datetime.date.today().strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(description="Publish Markdown/JSON to Notion database.")
    parser.add_argument(
        "--title",
        default=f"[{today_str}] AlphaInvest Notion Publish Smoke Test",
        help="Notion page title (title property).",
    )
    parser.add_argument("--json-file", default="", help="Path to JSON file (e.g. test output).")
    parser.add_argument("--json-stdin", action="store_true", help="Read JSON payload from stdin.")
    parser.add_argument("--markdown", default="", help="Publish raw markdown text.")
    parser.add_argument(
        "--smoke-risk",
        action="store_true",
        help="(TEST ONLY) risk_node를 static macro로 실행한 뒤 결과를 Notion에 발행합니다.",
    )
    parser.add_argument(
        "--risk-macro-source",
        choices=["static"],
        default="static",
        help="(TEST ONLY) Risk smoke test macro input source.",
    )
    parser.add_argument(
        "--risk-macro-result",
        default="미국 금리 고점권 유지, 하이일드 스프레드 확대 조짐.",
        help="(TEST ONLY) macro_result used to run risk_node.",
    )
    args = parser.parse_args()

    if args.markdown:
        url = publish_to_notion(title=args.title, markdown_text=args.markdown)
        print(url)
        return

    if args.json_file:
        with open(args.json_file, "r", encoding="utf-8") as f:
            url = publish_json_to_notion(title=args.title, json_payload=f.read())
            print(url)
            return

    if args.json_stdin:
        payload_text = _read_text_from_stdin()
        url = publish_json_to_notion(title=args.title, json_payload=payload_text)
        print(url)
        return

    # 기본은 CIO/에이전트가 생성한 텍스트(또는 테스트 JSON)를 받아 publish합니다.
    # risk 스모크 테스트는 원하면 명시적으로 --smoke-risk로만 실행합니다.
    if args.smoke_risk:
        try:
            from agents.constants import StateKey
            from agents.nodes.risk import risk_node
            from agents.state import get_initial_state
            from data.mock_data import get_portfolio

            state = get_initial_state(user_portfolio=get_portfolio())
            state[StateKey.MACRO_RESULT] = args.risk_macro_result
            risk_payload = risk_node(state)
            markdown_text = _risk_test_json_to_markdown(risk_payload)
            url = publish_to_notion(title=args.title, markdown_text=markdown_text)
            print(url)
        except Exception as e:
            raise SystemExit(f"--smoke-risk 실행 실패: {e}")
        return

    raise SystemExit("Provide one of: --markdown, --json-file, --json-stdin (or --smoke-risk for TEST ONLY).")


if __name__ == "__main__":
    main()
