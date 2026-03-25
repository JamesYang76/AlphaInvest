"""Notion API를 통한 리포트 발행 유틸리티 모듈"""

import os
import re
from typing import Any, Dict, List, Tuple

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
        "text": {"content": content[:_RICH_TEXT_LIMIT]},
    }
    if bold or italic:
        rt["annotations"] = {"bold": bold, "italic": italic}
    return rt


def _parse_inline_markdown(text: str) -> List[Dict[str, Any]]:
    """인라인 마크다운(**bold**, *italic*)을 Notion rich_text 배열로 변환합니다."""
    segments = [
        _rich_text_obj(m.group(2), bold=True)
        if m.group(2)
        else _rich_text_obj(m.group(3), italic=True)
        if m.group(3)
        else _rich_text_obj(m.group(4))
        for m in _INLINE_PATTERN.finditer(text)
        if m.group(2) or m.group(3) or m.group(4)
    ]
    return segments or [_rich_text_obj(text)]


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
    return ("paragraph", stripped)


def markdown_to_notion_blocks(markdown_text: str) -> List[Dict[str, Any]]:
    """마크다운 전문을 Notion Block 오브젝트 리스트로 변환합니다."""
    blocks: List[Dict[str, Any]] = []
    for line in markdown_text.split("\n"):
        block_type, content = _classify_line(line)
        if block_type == "empty":
            continue
        if block_type == "divider":
            blocks.append({"object": "block", "type": "divider", "divider": {}})
            continue
        blocks.append(_make_block(block_type, _parse_inline_markdown(content)))
    return blocks


# ============================================================
# 3. Notion 페이지 생성 API
# ============================================================
def _detect_title_property(client: Client, database_id: str) -> str:
    """데이터베이스 스키마에서 title 타입 프로퍼티 이름을 자동 탐지합니다."""
    db = client.databases.retrieve(database_id=database_id)
    title_props = [name for name, prop in db["properties"].items() if prop["type"] == "title"]
    return title_props[0] if title_props else "Name"


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
    title_prop = _detect_title_property(client, database_id)
    blocks = markdown_to_notion_blocks(markdown_text)

    page = client.pages.create(
        parent={"database_id": database_id},
        properties={title_prop: {"title": [{"text": {"content": title}}]}},
        children=blocks[:_BLOCKS_PER_REQUEST],
    )

    page_url = page.get("url", "")
    _append_remaining_blocks(client, page["id"], blocks[_BLOCKS_PER_REQUEST:])

    logger.info(f"[Notion] 페이지 발행 완료: {page_url}")
    return page_url
