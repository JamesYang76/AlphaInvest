from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage
from openai import OpenAI

# =========================================================
# Path / Env
# =========================================================
CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

# =========================================================
# Project imports
# =========================================================
from agents.constants import StateKey
from agents.state import AgentState

# =========================================================
# OpenAI
# =========================================================
OPENAI_MODEL = os.getenv("OPENAI_ALPHA_MODEL", "gpt-4.1-mini")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# =========================================================
# fetch.py adapter
# 최신 데이터 수집은 fetch.py 담당
# 함수명이 다르면 여기만 맞추면 됨
# =========================================================
try:
    from agents.nodes.fetch import fetch_alpha_facts
except ImportError:
    fetch_alpha_facts = None


# =========================================================
# Domain rules
# =========================================================
@dataclass(frozen=True)
class SectorRule:
    name: str
    thesis: str
    us_leaders: Sequence[str]
    kr_leaders: Sequence[str]
    keywords: Sequence[str]


SECTOR_RULES: Sequence[SectorRule] = (
    SectorRule(
        name="전력 인프라 / 전력기기",
        thesis=(
            "AI 데이터센터·산업 전력 수요 증가와 노후 전력망 교체 수요가 동시에 작동하는 구간으로 해석한다."
        ),
        us_leaders=("Eaton", "Vertiv"),
        kr_leaders=("효성중공업", "LS ELECTRIC"),
        keywords=(
            "power",
            "electric",
            "grid",
            "utility",
            "transformer",
            "transmission",
            "distribution",
            "data center power",
            "전력",
            "전력망",
            "변압기",
            "송전",
            "배전",
        ),
    ),
    SectorRule(
        name="AI 반도체 / AI 인프라",
        thesis=(
            "기업 투자 우선순위가 생성형 AI 인프라와 고성능 컴퓨팅으로 이동하는 국면으로 해석한다."
        ),
        us_leaders=("NVIDIA", "Broadcom"),
        kr_leaders=("SK하이닉스", "한미반도체"),
        keywords=(
            "ai",
            "gpu",
            "semiconductor",
            "chip",
            "hbm",
            "server",
            "inference",
            "compute",
            "반도체",
            "고대역폭 메모리",
            "HBM",
            "서버",
            "AI 인프라",
        ),
    ),
    SectorRule(
        name="K-뷰티 수출",
        thesis=(
            "브랜드·유통·플랫폼이 결합된 수출 확장 구간에서는 이익 레버리지와 재평가 가능성이 커진다고 본다."
        ),
        us_leaders=("e.l.f. Beauty", "Ulta Beauty"),
        kr_leaders=("실리콘투", "한국콜마"),
        keywords=(
            "beauty",
            "cosmetic",
            "k-beauty",
            "export",
            "consumer",
            "brand",
            "유통",
            "화장품",
            "미용",
            "뷰티",
            "수출",
        ),
    ),
    SectorRule(
        name="방산 / 우주항공",
        thesis=(
            "지정학적 긴장과 재고 확충 수요가 이어질수록 수주 가시성과 실적 지속성이 높아진다고 본다."
        ),
        us_leaders=("Lockheed Martin", "RTX"),
        kr_leaders=("한화에어로스페이스", "LIG넥스원"),
        keywords=(
            "defense",
            "military",
            "missile",
            "aerospace",
            "security",
            "rearm",
            "방산",
            "군수",
            "미사일",
            "우주항공",
        ),
    ),
    SectorRule(
        name="사이버보안",
        thesis=(
            "기업 IT 예산이 선택적 축소를 겪어도 보안 지출은 방어적으로 유지되는 경향이 있다고 본다."
        ),
        us_leaders=("Palo Alto Networks", "CrowdStrike"),
        kr_leaders=("안랩", "파수"),
        keywords=(
            "cyber",
            "security",
            "breach",
            "threat",
            "endpoint",
            "zero trust",
            "보안",
            "사이버",
            "해킹",
            "위협",
        ),
    ),
)

NEGATIVE_HINTS: Sequence[str] = (
    "commercial real estate",
    "office",
    "distressed",
    "bankruptcy",
    "rollover risk",
    "inventory glut",
    "price war",
    "dilution",
    "오피스",
    "부도",
    "재고 부담",
    "증자",
    "가격 경쟁",
)


# =========================================================
# Helpers
# =========================================================
def _get_state_value(state: AgentState, key: str, default: Any) -> Any:
    return state.get(key, default)


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except Exception:
        return str(value)


def _normalize_item(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()

    if isinstance(item, Mapping):
        fields = (
            item.get("title"),
            item.get("summary"),
            item.get("snippet"),
            item.get("description"),
            item.get("source"),
            item.get("date"),
            item.get("url"),
        )
        return " | ".join(filter(None, map(_safe_text, fields))).strip()

    return _safe_text(item)


def _normalize_facts(raw_facts: Any) -> List[str]:
    if raw_facts is None:
        return []

    if isinstance(raw_facts, Mapping):
        candidate_lists = (
            raw_facts.get("facts"),
            raw_facts.get("results"),
            raw_facts.get("items"),
            raw_facts.get("articles"),
            raw_facts.get("documents"),
            raw_facts.get("data"),
        )
        flattened = next((value for value in candidate_lists if value), [])
        if isinstance(flattened, list):
            return [text for text in map(_normalize_item, flattened) if text]
        return [_normalize_item(flattened)] if flattened else []

    if isinstance(raw_facts, list):
        return [text for text in map(_normalize_item, raw_facts) if text]

    normalized = _normalize_item(raw_facts)
    return [normalized] if normalized else []


def _fetch_alpha_facts_from_adapter(state: AgentState) -> List[str]:
    if fetch_alpha_facts is None:
        return []

    call_candidates = (
        lambda: fetch_alpha_facts(state),
        lambda: fetch_alpha_facts(
            user_portfolio=_get_state_value(state, StateKey.USER_PORTFOLIO, []),
            macro_result=_get_state_value(state, StateKey.MACRO_RESULT, ""),
            risk_result=_get_state_value(state, StateKey.RISK_RESULT, ""),
        ),
        lambda: fetch_alpha_facts(
            _get_state_value(state, StateKey.USER_PORTFOLIO, []),
            _get_state_value(state, StateKey.MACRO_RESULT, ""),
            _get_state_value(state, StateKey.RISK_RESULT, ""),
        ),
    )

    for candidate in call_candidates:
        try:
            return _normalize_facts(candidate())
        except TypeError:
            continue
        except Exception:
            return []

    return []


def _build_context_texts(state: AgentState, facts: Sequence[str]) -> Dict[str, str]:
    return {
        "portfolio_text": _safe_text(_get_state_value(state, StateKey.USER_PORTFOLIO, [])),
        "macro_text": _safe_text(_get_state_value(state, StateKey.MACRO_RESULT, "")),
        "risk_text": _safe_text(_get_state_value(state, StateKey.RISK_RESULT, "")),
        "facts_text": "\n".join(f"- {fact}" for fact in facts),
    }


def _score_rule(rule: SectorRule, texts: Iterable[str]) -> int:
    combined = " ".join(texts).lower()
    return sum(1 for keyword in rule.keywords if keyword.lower() in combined)


def _count_negative_hints(texts: Iterable[str]) -> int:
    combined = " ".join(texts).lower()
    return sum(1 for hint in NEGATIVE_HINTS if hint.lower() in combined)


def _build_sector_analysis(state: AgentState, facts: Sequence[str]) -> List[Dict[str, Any]]:
    context = _build_context_texts(state, facts)
    texts = (
        context["facts_text"],
        context["macro_text"],
        context["risk_text"],
        context["portfolio_text"],
    )

    scored = [
        {
            "sector": rule.name,
            "score": _score_rule(rule, texts),
            "thesis": rule.thesis,
            "us_leaders": list(rule.us_leaders),
            "kr_leaders": list(rule.kr_leaders),
        }
        for rule in SECTOR_RULES
    ]

    ranked = sorted(scored, key=lambda item: item["score"], reverse=True)
    positive = [item for item in ranked if item["score"] > 0]
    selected = positive[:2] if len(positive) >= 2 else ranked[:2]

    negative_count = _count_negative_hints(texts)
    risk_bias = "주의 강화" if negative_count >= 2 else "중립"

    return [
        {
            **item,
            "risk_bias": risk_bias,
            "negative_hint_count": negative_count,
            "investment_point": _make_investment_point(item["sector"], item["score"]),
        }
        for item in selected
    ]


def _make_investment_point(sector_name: str, score: int) -> str:
    if score >= 4:
        return f"{sector_name} 관련 팩트가 반복적으로 관측되어 상대 강도 신호가 가장 뚜렷하다."
    if score >= 2:
        return f"{sector_name} 관련 팩트가 여러 번 확인되어 주도 섹터 후보로 볼 수 있다."
    return f"{sector_name} 관련 직접 팩트는 제한적이지만 현재 맥락에서 대안이 아닌 주도 후보로 검토할 만하다."


def _serialize_analysis(analysis: Sequence[Dict[str, Any]]) -> str:
    return json.dumps(list(analysis), ensure_ascii=False, indent=2)


def _build_user_prompt(state: AgentState, facts: Sequence[str], analysis: Sequence[Dict[str, Any]]) -> str:
    context = _build_context_texts(state, facts)

    return f"""
[사용자 포트폴리오]
{context["portfolio_text"]}

[매크로 요약]
{context["macro_text"]}

[리스크 요약]
{context["risk_text"]}

[수집된 facts]
{context["facts_text"] if context["facts_text"] else "- 없음"}

[구조화 분석 결과]
{_serialize_analysis(analysis)}

위 자료만 사용해서 알파 섹터 추천 파트를 작성하라.
facts와 구조화 분석 결과에 없는 새로운 사실은 추가하지 마라.
추천 섹터는 정확히 2개만 제시하라.
각 섹터마다 미국 대표 종목 1~2개, 한국 대표 종목 1~2개를 반드시 포함하라.
"""


def _call_responses_api(prompt: str) -> str:
    response = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {
                "role": "developer",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "너는 AlphaInvest의 알파 섹터 담당 애널리스트다. "
                            "facts와 analysis만 사용해 투자 리포트 문장을 다듬어라. "
                            "새로운 사실, 수치, 기사, 종목은 임의로 만들지 마라."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            },
        ],
    )
    return response.output_text.strip()


def _build_fallback_report(analysis: Sequence[Dict[str, Any]]) -> str:
    lines = ["## 3. 🚀 AI 인사이트: 신규 진입 추천 섹터 Top 2", ""]

    for item in analysis:
        us_names = ", ".join(item["us_leaders"])
        kr_names = ", ".join(item["kr_leaders"])
        lines.extend(
            [
                f'- **[추천 섹터: {item["sector"]}]**',
                f'  - **논리적 배경:** {item["thesis"]}',
                f'  - **투자 포인트:** {item["investment_point"]}',
                f"  - **미국 대표 종목:** {us_names}",
                f"  - **한국 대표 종목:** {kr_names}",
                "",
            ]
        )

    return "\n".join(lines).strip()


def _build_alpha_messages(report_text: str) -> List[Any]:
    return [
        HumanMessage(content="알파 섹터 추천 파트를 생성한다."),
        AIMessage(content=report_text),
    ]


# =========================================================
# Public node
# =========================================================
def alpha_agent(state: AgentState) -> Dict[str, Any]:
    """
    Alpha 섹터 추천 노드.
    - fetch.py가 수집한 최신 facts를 입력으로 받는다.
    - facts / macro / risk / portfolio를 조합해 구조화 분석을 수행한다.
    - Responses API는 문장 정리만 담당한다.
    - 기존 State 스키마의 alpha_messages, alpha_result만 갱신한다.
    """
    facts = _fetch_alpha_facts_from_adapter(state)
    analysis = _build_sector_analysis(state, facts)
    prompt = _build_user_prompt(state, facts, analysis)

    try:
        report_text = _call_responses_api(prompt)
    except Exception:
        report_text = _build_fallback_report(analysis)

    return {
        StateKey.ALPHA_MESSAGES: _build_alpha_messages(report_text),
        StateKey.ALPHA_RESULT: report_text,
    }


# =========================================================
# Manual test
# =========================================================
if __name__ == "__main__":
    from agents.state import get_initial_state

    sample_state = get_initial_state(
        user_portfolio=[
            {"ticker": "TSLA", "weight": 0.35},
            {"ticker": "SOXL", "weight": 0.25},
        ]
    )
    sample_state[StateKey.MACRO_RESULT] = "금리 경로 불확실성은 남아 있지만 AI·전력 투자 관련 설비 지출은 상대적으로 견조하다."
    sample_state[StateKey.RISK_RESULT] = "가격 경쟁이 심한 전기차 단일 베팅은 주의가 필요하다."

    result = alpha_agent(sample_state)

    print("\n" + "=" * 80)
    print("[ALPHA RESULT]")
    print(result[StateKey.ALPHA_RESULT])
    print("=" * 80 + "\n")