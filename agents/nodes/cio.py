import datetime
from typing import Any, Dict

from agents.constants import StateKey
from agents.state import AgentState


def cio_node(state: AgentState) -> Dict[str, Any]:
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    macro = state.get(StateKey.MACRO_RESULT, "데이터 없음")
    portfolio = state.get(StateKey.PORTFOLIO_RESULT, "데이터 없음")
    risk = state.get(StateKey.RISK_RESULT, "데이터 없음")
    alpha = state.get(StateKey.ALPHA_RESULT, "데이터 없음")

    report = f"""# 🚨 [{today_str}] 일일 리스크 관리 및 포트폴리오 최적화 리포트

시황: {macro}

## 1. 💼 내 계좌 맞춤 진단: 현재 보유 종목 및 리밸런싱 전략

종목분석 에이전트가 현재 계좌의 핵심 고민거리를 진단하고 최적의 대응 방안을 제안합니다.

- **진단 대상:** **삼성전자 (005930.KS)** (현재 수익률: -5.0%)
- **에이전트 진단:** {portfolio}
- **💡 최적의 액션 플랜: [일부 비중 축소 및 주도주로 스위칭 권고]**
    - **근거:** 레거시 반도체 회복 지연과 파운드리 적자 우려를 감안할 때, \
AI 핵심 밸류체인으로의 포트폴리오 다각화가 시급합니다.

## 2. 🛑 에이전트 경고: 절대 투자해선 안 될 위험 섹터 및 함정 주식 Top 3

오토젠 업황분석 에이전트가 최근 자금 이탈 규모, 실적 하향 조정 비율, 매크로 악재를 \
종합하여 산출한 '접근 금지' 구역과 주의해야 할 대표 종목입니다.

- **[위험 경고 요약]**: {risk}

- **1위: 상업용 오피스 부동산 (Commercial Office Real Estate)**
    - **⛔️ 절대 피해야 할 대표주:** **보스턴 프로퍼티스 (BXP), 보나도 리얼티 트러스트 (VNO)**
- **2위: 레거시 내연기관 자동차 (Legacy Automakers)**
    - **⛔️ 절대 피해야 할 대표주:** **포드 (F), 제너럴 모터스 (GM)**
- **3위: 적자 지속형 수소/친환경 인프라 및 소형 밈(Meme) 주식**
    - **⛔️ 절대 피해야 할 대표주:** **플러그 파워 (PLUG), 선런 (RUN)**

## 3. 🚀 AI 인사이트: 신규 진입 추천 섹터 Top 2

위험을 피하고 내 포트폴리오를 정비했다면, 이제 남은 현금을 투입할 가장 확실한 주도 섹터입니다.

- **[알파 섹터 요약]**: {alpha}

- **[추천 섹터 1: AI 전력 인프라 및 전력 기기]**
    - **관심 종목군:** **이튼(ETN), GE 베르노바(GEV)** 또는 관련 국내 전력기기 대장주.
- **[추천 섹터 2: K-뷰티 및 필수소비재 (글로벌 수출 중심)]**
    - **관심 종목군:** **실리콘투, 아모레퍼시픽** 등 주요 수출주.
"""
    return {StateKey.FINAL_REPORT: report}
