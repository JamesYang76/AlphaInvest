from __future__ import annotations

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
- 사용자의 현재 보유 종목과 포트폴리오 편중 가능성을 참고해
  신규 진입 유망 섹터 2개를 선정한다.
- 추천 섹터 2개는 반드시 성격이 다르게 구성한다.
  - 1개는 포트폴리오 편중을 보완할 수 있는 섹터
  - 1개는 현재 시장에서 구조적 성장 기대가 큰 섹터
- 각 섹터마다 미국 대표 종목 2개와 한국 대표 종목 2개를 제시한다.
- 내부 시스템 설명이 아니라, 소비자가 읽는 투자 리포트처럼 써야 한다.

작성 가이드라인:
1. 문체
- 어렵고 기술적인 표현은 줄이고, 투자 리포트처럼 신뢰감 있게 설명한다.
- 과장 광고성 표현은 금지한다.

2. 추천 기준
- 단순 유행 테마보다 구조적 성장 가능성, 실적 가시성, 산업 대표성, 분산 효과를 고려한다.
- 사용자의 기존 보유 종목이 특정 섹터에 쏠려 있다면, 그 편중을 완화할 수 있는 섹터를 최소 1개 포함한다.
- 사용자의 보유 종목 정보가 부족한 경우에도 일반 투자자 관점에서 설득력 있게 작성한다.

3. 종목 제시 규칙
- 섹터별로 미국 대표 종목 2개, 한국 대표 종목 2개를 반드시 제시한다.
- 실제 시장에서 널리 알려진 대형주 또는 대표주 중심으로 제시한다.
- 존재하지 않는 종목을 만들어내지 않는다.
- 테마성이 지나치게 강한 군소형주는 피한다.

4. 출력 형식
반드시 아래 형식을 지켜라.

## 3. 🚀 AI 인사이트: 신규 진입 추천 섹터 Top 2

- **[추천 섹터 1: 섹터명]**
  - **논리적 배경:** ...
  - **투자 포인트:** ...
  - **포트폴리오 보완 관점:** ...
  - **관심 종목군:** 미국 대장주: ..., ... / 한국 대장주: ..., ...

- **[추천 섹터 2: 섹터명]**
  - **논리적 배경:** ...
  - **투자 포인트:** ...
  - **포트폴리오 보완 관점:** ...
  - **관심 종목군:** 미국 대장주: ..., ... / 한국 대장주: ..., ...

5. 금지 사항
- "에이전트", "모듈", "state", "시스템", "내부 로직" 같은 내부 구현 표현 금지
- 점수 계산식, 알고리즘 설명 금지
- "좋아 보인다" 식의 근거 없는 표현 금지

6. 추가 작성 규칙
- "성장주", "방어주"처럼 뭉뚱그린 표현 대신 반드시 구체적인 산업 섹터명으로 작성한다.
  예: 반도체, 전력 인프라, 헬스케어, 필수소비재, 산업자동화
- 추천 섹터 2개는 반드시 서로 성격이 달라야 한다.
- 사용자의 기존 포트폴리오 편중을 어떻게 보완하는지 반드시 명시한다.
- 섹터와 종목 연결이 자연스럽고 설득력 있어야 한다.
"""


# ==========================================================
# 보조 함수
# ==========================================================
def _safe_text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _extract_tickers(user_portfolio: List[Dict[str, Any]]) -> List[str]:
    tickers: List[str] = []

    for stock in user_portfolio:
        if not isinstance(stock, dict):
            continue

        ticker = str(stock.get("ticker", "")).strip().upper()
        if ticker:
            tickers.append(ticker)

    return tickers


def _infer_portfolio_bias(tickers: List[str]) -> str:
    tech_keywords = {"AAPL", "MSFT", "NVDA", "AMD", "TSLA", "QQQ", "META", "GOOGL", "AMZN", "AVGO"}
    semiconductor_keywords = {"NVDA", "AMD", "TSM", "AVGO", "QCOM", "MU", "INTC", "SOXX"}
    healthcare_keywords = {"JNJ", "PFE", "MRK", "LLY", "ABBV", "UNH"}
    finance_keywords = {"JPM", "BAC", "GS", "MS", "WFC", "C"}
    energy_keywords = {"XOM", "CVX", "SLB", "COP"}
    consumer_keywords = {"PG", "KO", "PEP", "COST", "WMT"}

    counts = {
        "기술주": 0,
        "반도체": 0,
        "헬스케어": 0,
        "금융": 0,
        "에너지": 0,
        "필수소비재": 0,
    }

    for ticker in tickers:
        if ticker in tech_keywords:
            counts["기술주"] += 1
        if ticker in semiconductor_keywords:
            counts["반도체"] += 1
        if ticker in healthcare_keywords:
            counts["헬스케어"] += 1
        if ticker in finance_keywords:
            counts["금융"] += 1
        if ticker in energy_keywords:
            counts["에너지"] += 1
        if ticker in consumer_keywords:
            counts["필수소비재"] += 1

    dominant = max(counts, key=counts.get)

    if counts[dominant] == 0:
        return "현재 포트폴리오의 뚜렷한 섹터 편중은 제한적으로 보입니다."

    return f"현재 포트폴리오는 {dominant} 비중이 상대적으로 높을 가능성이 있습니다."


def _suggest_complementary_sector(tickers: List[str]) -> str:
    """
    현재 포트폴리오 편중을 보고,
    보완용 섹터 후보를 한 줄 힌트로 제공합니다.
    """
    tech_keywords = {"AAPL", "MSFT", "NVDA", "AMD", "TSLA", "QQQ", "META", "GOOGL", "AMZN", "AVGO"}
    semiconductor_keywords = {"NVDA", "AMD", "TSM", "AVGO", "QCOM", "MU", "INTC", "SOXX"}
    healthcare_keywords = {"JNJ", "PFE", "MRK", "LLY", "ABBV", "UNH"}
    finance_keywords = {"JPM", "BAC", "GS", "MS", "WFC", "C"}
    energy_keywords = {"XOM", "CVX", "SLB", "COP"}

    tech_count = sum(t in tech_keywords for t in tickers)
    semi_count = sum(t in semiconductor_keywords for t in tickers)
    healthcare_count = sum(t in healthcare_keywords for t in tickers)
    finance_count = sum(t in finance_keywords for t in tickers)
    energy_count = sum(t in energy_keywords for t in tickers)

    if tech_count + semi_count >= 2:
        return "보완용 섹터는 헬스케어, 필수소비재, 보험처럼 경기 방어적 성격의 산업을 우선 검토하세요."
    if healthcare_count >= 2:
        return "보완용 섹터는 반도체, 전력 인프라, 산업자동화처럼 구조적 성장 성격의 산업을 우선 검토하세요."
    if finance_count >= 2:
        return "보완용 섹터는 헬스케어 또는 전력 인프라처럼 경기 민감도를 낮출 수 있는 산업을 우선 검토하세요."
    if energy_count >= 2:
        return "보완용 섹터는 헬스케어 또는 반도체처럼 실적 동력이 다른 산업을 우선 검토하세요."

    return "보완용 섹터는 헬스케어, 필수소비재, 전력 인프라, 산업자동화 중에서 분산 효과가 큰 방향으로 제시하세요."


def _build_sector_context(user_portfolio: List[Dict[str, Any]]) -> str:
    tickers = _extract_tickers(user_portfolio)
    portfolio_bias = _infer_portfolio_bias(tickers)
    complement_hint = _suggest_complementary_sector(tickers)

    holding_text = ", ".join(tickers) if tickers else "보유 종목 정보 없음"

    return f"""
[사용자 보유 종목]
{holding_text}

[포트폴리오 편중 추정]
{portfolio_bias}

[추천 방향 힌트]
{complement_hint}

[작성 지침]
- 추천 섹터는 총 2개만 제시하세요.
- 2개 섹터는 반드시 서로 성격이 달라야 합니다.
- 하나는 포트폴리오 편중을 보완하는 섹터로 제시하세요.
- 다른 하나는 구조적 성장 기대가 큰 섹터로 제시하세요.
- 각 섹터마다 미국 대표 종목 2개, 한국 대표 종목 2개를 반드시 포함하세요.
- 종목은 실제 대표 대형주 위주로 쓰세요.
"""


# ==========================================================
# 메인 노드
# ==========================================================
def alpha_node(state: AgentState) -> Dict[str, Any]:
    """
    독립형 Alpha 노드
    - macro / risk / portfolio 결과를 참조하지 않음
    - 사용자 보유 종목만 참고하여 신규 진입 유망 섹터 2개 추천
    """
    user_portfolio = state.get(StateKey.USER_PORTFOLIO, [])
    if not isinstance(user_portfolio, list):
        user_portfolio = []

    context_text = _build_sector_context(user_portfolio)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", ALPHA_SYSTEM_PROMPT),
            ("human", "{context}"),
        ]
    )

    llm = ChatOpenAI(
        model=ModelConfig.DEFAULT_LLM_MODEL,
        temperature=ModelConfig.DEFAULT_TEMPERATURE,
    )

    chain = prompt | llm
    response = chain.invoke({"context": context_text})

    alpha_report = _safe_text(getattr(response, "content", ""))

    return {
        StateKey.ALPHA_RESULT: alpha_report
    }


# ==========================================================
# 로컬 테스트 실행 블록
# ==========================================================
if __name__ == "__main__":
    print("alpha.py loaded successfully")

    test_state = {
        StateKey.USER_PORTFOLIO: [
            {"ticker": "AAPL"},
            {"ticker": "NVDA"},
            {"ticker": "MSFT"},
        ]
    }

    try:
        result = alpha_node(test_state)
        print("\n[alpha_node 실행 결과]\n")
        print(result.get(StateKey.ALPHA_RESULT, "결과 없음"))
    except Exception as e:
        print("\n[실행 중 오류 발생]")
        print(type(e).__name__, e)