from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

# ==========================================================
# 경로 설정 및 .env 로드
# ==========================================================
CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from agents.constants import ModelConfig, StateKey
from agents.state import AgentState


# ==========================================================
# 시스템 프롬프트
# ==========================================================
ALPHA_SYSTEM_PROMPT = """
너는 AlphaInvest 서비스에서 소비자에게 제공되는
알파(초과수익) 섹터 추천 리포트를 작성하는 AI다.

역할 정의:
- 현재 거시경제 환경, 리스크 경고, 포트폴리오 진단 결과를 종합해
  신규 진입 유망 섹터 2개를 선정한다.
- 각 섹터마다 미국 대표 종목 1~2개와 한국 대표 종목 1~2개를 제시한다.
- 내부 시스템 설명이 아니라, 소비자가 읽는 투자 리포트처럼 써야 한다.

작성 가이드라인:
1. 소비자 친화적 문체:
   - 너무 기술적인 용어는 피하고, 이해하기 쉽게 설명한다.
   - 다만 증권사 리포트처럼 신뢰감 있는 어조를 유지한다.

2. 추천 기준:
   - 단순 인기 테마가 아니라 구조적 성장 가능성, 실적 가시성, 정책/산업 흐름,
     포트폴리오 분산 필요성을 함께 고려한다.
   - 이미 포트폴리오가 특정 섹터에 과도하게 편중돼 있다면,
     분산 관점에서 보완 가능한 섹터를 포함할 수 있다.

3. 종목 제시 방식:
   - 섹터별로 미국 대표 종목과 한국 대표 종목을 구분해 제시한다.
   - 검색/데이터에 없는 종목을 새로 만들어내지 않는다.
   - 근거가 약한 테마주는 피하고, 대표성이 있는 종목 위주로 제시한다.

4. 출력 형식:
반드시 아래 형식을 지켜라.

## 3. 🚀 AI 인사이트: 신규 진입 추천 섹터 Top 2

- **[추천 섹터 1: 섹터명]**
  - **논리적 배경:** ...
  - **투자 포인트:** ...
  - **관심 종목군:** 미국 대장주: ..., 한국 대장주: ...

- **[추천 섹터 2: 섹터명]**
  - **논리적 배경:** ...
  - **투자 포인트:** ...
  - **관심 종목군:** 미국 대장주: ..., 한국 대장주: ...

5. 금지 사항:
   - "에이전트", "모듈", "state", "시스템", "내부 로직" 같은 내부 구현 표현 금지
   - 점수 계산식, 알고리즘 설명 금지
   - 과장 광고성 표현 금지

6. 추가 작성 규칙:
   - "방어주", "성장주" 같은 포괄적 표현 대신, 반드시 "헬스케어", "전력 인프라", "필수소비재", "반도체"처럼 구체적인 산업 섹터명으로 작성하세요.
   - 각 섹터마다 미국/한국 대표 종목은 최소 2개씩 제시하되, 실제 시장에서 널리 인정되는 대형주 중심으로 선택하세요.
   - 거시환경 또는 리스크 요인과 해당 섹터의 연결 관계를 한 문장 이상 명확히 설명하세요.
   - 기존 포트폴리오의 편중을 어떻게 보완하는지 반드시 명시하세요.
   - 추천 섹터 2개는 반드시 서로 성격이 다르게 구성하세요: 하나는 경기 방어형(예: 헬스케어, 필수소비재), 다른 하나는 구조적 성장형(예: 반도체, AI 인프라, 전력 인프라)으로 제시하세요.
"""


# ==========================================================
# 보조 함수
# ==========================================================
def _safe_text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _extract_tickers(user_portfolio: List[Dict[str, Any]]) -> List[str]:
    return [
        str(stock.get("ticker", "")).strip().upper()
        for stock in user_portfolio
        if isinstance(stock, dict) and stock.get("ticker")
    ]


def _infer_portfolio_bias(tickers: List[str]) -> str:
    tech_keywords = {"AAPL", "MSFT", "NVDA", "AMD", "TSLA", "QQQ", "META", "GOOGL", "AMZN"}
    bio_keywords = {"JNJ", "PFE", "MRK", "LLY", "ABBV"}
    finance_keywords = {"JPM", "BAC", "GS", "MS", "WFC"}
    energy_keywords = {"XOM", "CVX", "SLB"}
    semiconductor_keywords = {"NVDA", "AMD", "TSM", "AVGO", "QCOM", "MU", "INTC"}

    counts = {
        "기술주": 0,
        "반도체": 0,
        "헬스케어": 0,
        "금융": 0,
        "에너지": 0,
    }

    for ticker in tickers:
        if ticker in tech_keywords:
            counts["기술주"] += 1
        if ticker in semiconductor_keywords:
            counts["반도체"] += 1
        if ticker in bio_keywords:
            counts["헬스케어"] += 1
        if ticker in finance_keywords:
            counts["금융"] += 1
        if ticker in energy_keywords:
            counts["에너지"] += 1

    dominant = max(counts, key=counts.get)
    if counts[dominant] == 0:
        return "현재 포트폴리오의 뚜렷한 섹터 편중은 제한적으로 보입니다."
    return f"현재 포트폴리오는 {dominant} 비중이 상대적으로 높을 가능성이 있습니다."


def _build_sector_context(
    macro_result: str,
    risk_result: str,
    portfolio_result: str,
    user_portfolio: List[Dict[str, Any]],
) -> str:
    """
    외부 macro_data 모듈 없이,
    현재 입력값만으로 LLM이 참고할 요약 컨텍스트를 생성합니다.
    """
    tickers = _extract_tickers(user_portfolio)
    portfolio_bias = _infer_portfolio_bias(tickers)

    macro_lower = macro_result.lower()
    risk_lower = risk_result.lower()
    portfolio_lower = portfolio_result.lower()

    candidate_sectors: List[str] = []

    if any(keyword in macro_lower for keyword in ["ai", "인공지능", "클라우드", "디지털 전환"]):
        candidate_sectors.append(
            "- 반도체/AI 인프라: 미국 대표주는 NVIDIA, AMD, TSMC이며 한국 대표주는 삼성전자, SK하이닉스입니다."
        )

    if any(keyword in macro_lower for keyword in ["금리 인하", "금리하락", "disinflation", "완화"]):
        candidate_sectors.append(
            "- 소프트웨어/플랫폼: 금리 부담 완화 구간에서는 현금흐름 가시성이 높은 대형 플랫폼과 소프트웨어가 재평가될 수 있습니다. 미국은 Microsoft, Amazon, Alphabet, 한국은 NAVER, 카카오를 참고할 수 있습니다."
        )

    if any(keyword in macro_lower for keyword in ["인프라", "전력", "전력망", "데이터센터", "전력 수요"]):
        candidate_sectors.append(
            "- 전력 인프라: AI 데이터센터 확산과 전력 수요 증가는 전력 설비와 인프라 투자 확대 논리로 이어질 수 있습니다. 미국은 Eaton, GE Vernova, NextEra Energy, 한국은 LS ELECTRIC, 효성중공업 등을 참고할 수 있습니다."
        )

    if any(keyword in macro_lower for keyword in ["방어", "불확실", "변동성", "경기 둔화"]):
        candidate_sectors.append(
            "- 헬스케어: 경기 둔화나 변동성 확대 구간에서는 실적 방어력이 있는 제약·바이오 대형주가 대안이 될 수 있습니다. 미국은 Johnson & Johnson, Pfizer, Eli Lilly, 한국은 삼성바이오로직스, 셀트리온을 참고할 수 있습니다."
        )

    if any(keyword in macro_lower for keyword in ["친환경", "전력화", "전기화", "에너지 전환"]):
        candidate_sectors.append(
            "- 산업재/전력화: 설비투자와 에너지 전환 수요가 이어질 경우 산업 자동화·전력화 장비 업종이 유리할 수 있습니다. 미국은 GE Vernova, Eaton, Rockwell Automation, 한국은 LS ELECTRIC, HD현대일렉트릭을 참고할 수 있습니다."
        )

    if any(keyword in risk_lower for keyword in ["밸류에이션", "고평가", "쏠림", "집중"]):
        candidate_sectors.append(
            "- 분산 관점 보완: 특정 성장주 쏠림이 부담이라면 반도체 외의 헬스케어, 전력 인프라, 산업재를 병행 검토할 필요가 있습니다."
        )

    if any(keyword in risk_lower for keyword in ["경기", "침체", "둔화"]):
        candidate_sectors.append(
            "- 경기 민감주보다는 실적 가시성이 높거나 구조적 수요가 지속되는 업종 중심 접근이 유효할 수 있습니다."
        )

    if any(keyword in portfolio_lower for keyword in ["기술주 편중", "tech", "성장주 편중", "나스닥 편중"]):
        candidate_sectors.append(
            "- 포트폴리오 분산 필요: 기술주 외 보완 섹터로 헬스케어, 필수소비재, 전력 인프라를 우선 검토할 수 있습니다."
        )

    if not candidate_sectors:
        candidate_sectors = [
            "- 반도체/AI 인프라: 구조적 성장성과 실적 가시성을 동시에 점검할 수 있는 대표 섹터입니다. 미국은 NVIDIA, AMD, 한국은 삼성전자, SK하이닉스입니다.",
            "- 헬스케어: 변동성 국면에서 방어력과 장기 성장성을 함께 고려할 수 있습니다. 미국은 Johnson & Johnson, Pfizer, 한국은 삼성바이오로직스, 셀트리온입니다.",
            "- 전력 인프라: AI 데이터센터와 전력 수요 확대 흐름의 수혜를 검토할 수 있습니다. 미국은 Eaton, GE Vernova, 한국은 LS ELECTRIC, 효성중공업입니다.",
        ]

    lines = [
        "[내부 참고용 섹터 요약]",
        f"- 포트폴리오 보유 티커: {', '.join(tickers) if tickers else '없음'}",
        f"- 포트폴리오 편중 해석: {portfolio_bias}",
        "- 섹터 후보 메모:",
        *candidate_sectors,
    ]
    return "\n".join(lines)


def _build_alpha_prompt(
    macro_result: str,
    risk_result: str,
    portfolio_result: str,
    sector_context: str,
    user_portfolio: List[Dict[str, Any]],
) -> ChatPromptTemplate:
    import yaml

    user_portfolio_str = yaml.dump(
        user_portfolio,
        allow_unicode=True,
        default_flow_style=False,
    )

    return ChatPromptTemplate.from_messages(
        [
            ("system", ALPHA_SYSTEM_PROMPT),
            (
                "user",
                "### 1. 고객 보유 포트폴리오 원본 데이터\n"
                "{user_portfolio_str}\n\n"
                "### 2. 포트폴리오 진단 결과\n"
                "{portfolio_result}\n\n"
                "### 3. 글로벌 거시경제 및 시장 환경\n"
                "{macro_result}\n\n"
                "### 4. 리스크 경고 결과\n"
                "{risk_result}\n\n"
                "### 5. 주도 섹터 및 시장 테마 데이터\n"
                "{sector_context}\n\n"
                "---\n"
                "**지침**:\n"
                "- 위 정보를 종합해 지금 시점에서 신규 진입 유망 섹터 2개를 추천하세요.\n"
                "- 각 섹터는 소비자가 이해할 수 있게 왜 유망한지 설명하세요.\n"
                "- 각 섹터마다 미국 대장주와 한국 대장주를 반드시 포함하세요.\n"
                "- 이미 고객 포트폴리오가 특정 섹터에 편중돼 있으면 분산 관점도 반영하세요.\n"
                "- 최종 출력은 반드시 지정된 마크다운 형식을 따르세요."
            ),
        ]
    ).partial(user_portfolio_str=user_portfolio_str)


# ==========================================================
# 메인 노드
# ==========================================================
def alpha_node(state: AgentState) -> Dict[str, Any]:
    """
    매크로 결과, 리스크 결과, 포트폴리오 진단 결과를 종합해
    소비자 대상의 알파 섹터 추천 리포트를 생성하는 노드입니다.
    """
    if not os.getenv("OPENAI_API_KEY"):
        return {
            StateKey.ALPHA_RESULT: "LLM 연결 실패: .env 파일에 OPENAI_API_KEY를 먼저 설정해주세요."
        }

    user_portfolio = state.get(StateKey.USER_PORTFOLIO, [])
    macro_result = _safe_text(state.get(StateKey.MACRO_RESULT, ""))
    risk_result = _safe_text(state.get(StateKey.RISK_RESULT, ""))
    portfolio_result = _safe_text(state.get(StateKey.PORTFOLIO_RESULT, ""))

    sector_context = _build_sector_context(
        macro_result=macro_result,
        risk_result=risk_result,
        portfolio_result=portfolio_result,
        user_portfolio=user_portfolio,
    )

    llm = ChatOpenAI(
        model=ModelConfig.DEFAULT_LLM_MODEL,
        temperature=ModelConfig.DEFAULT_TEMPERATURE,
    )

    prompt = _build_alpha_prompt(
        macro_result=macro_result,
        risk_result=risk_result,
        portfolio_result=portfolio_result,
        sector_context=sector_context,
        user_portfolio=user_portfolio,
    )

    input_data = {
        "portfolio_result": portfolio_result,
        "macro_result": macro_result,
        "risk_result": risk_result,
        "sector_context": sector_context,
    }

    try:
        response = (prompt | llm).invoke(input_data)
        result_text = response.content if hasattr(response, "content") else str(response)
    except Exception as exc:
        result_text = f"알파 섹터 추천 엔진 가동 중 오류 발생: {str(exc)}"

    # 보고서 파일 저장
    report_path = PROJECT_ROOT / "alpha_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(result_text)

    return {
        StateKey.ALPHA_RESULT: result_text
    }


# ==========================================================
# 단독 실행 테스트
# ==========================================================
if __name__ == "__main__":
    test_state: AgentState = {
        StateKey.USER_PORTFOLIO: [
            {"ticker": "AAPL", "avg_price": 180000},
            {"ticker": "TSLA", "avg_price": 250000},
            {"ticker": "QQQ", "avg_price": 400000},
        ],
        StateKey.MACRO_RESULT: (
            "현재 시장은 금리 인하 기대와 AI 중심 기술주 강세가 동시에 나타나는 구간으로 해석됩니다. "
            "다만 일부 성장주는 밸류에이션 부담이 존재해, 실적 가시성과 구조적 성장성이 있는 섹터 중심 접근이 필요합니다."
        ),
        StateKey.RISK_RESULT: (
            "포트폴리오가 기술주 중심으로 다소 편중되어 있으며, 변동성 확대 시 낙폭이 커질 수 있습니다."
        ),
        StateKey.PORTFOLIO_RESULT: (
            "성장주 비중이 높아 상승 탄력은 좋지만, 분산 관점에서는 방어주와 실적 가시성이 높은 업종 보완이 필요합니다."
        ),
    }

    result = alpha_node(test_state)
    print(result[StateKey.ALPHA_RESULT])
    print(f"\n보고서 저장 완료: {PROJECT_ROOT / 'alpha_report.txt'}")