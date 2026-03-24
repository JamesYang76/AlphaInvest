"""
Phase 5 — Report & Publish (최종 리포트 작성 및 발행)
담당 팀원이 이 파일을 작업합니다.

노드 구성:
  compile_report_node  : 1~4단계 결과 → 최종 리포트 작성
  notion_publish_node  : Notion 발행 또는 로컬 파일 저장
"""
import os
from datetime import datetime
from langchain_core.messages import HumanMessage
from agent.state import InvestmentState
from data.fetchers import get_llm

NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DB_ID = os.getenv("NOTION_DATABASE_ID", "")


def compile_report_node(state: InvestmentState) -> dict:
    """Phase 5-1: 4개 Phase 결과를 읽기 좋은 일일 투자 리포트로 종합"""
    print("\n📝 [Phase 5] 최종 리포트 작성 중...")
    today = datetime.now().strftime("%Y-%m-%d")
    llm = get_llm(temperature=0.6)

    prompt = f"""
당신은 수석 투자 전략가(CIO)입니다.
4가지 분석 결과를 종합하여 개인 투자자가 아침에 읽기 좋은
간결하고 실용적인 투자 리포트를 작성해주세요.

[오늘 날짜]: {today}
[Phase 1 - 거시경제]: {state.get('macro_analysis', '')}
[Phase 2 - 위험 섹터]: {state.get('risk_report', '')}
[Phase 3 - 계좌 진단]: {state.get('portfolio_diagnosis', '')}
[Phase 4 - 알파 섹터]: {state.get('alpha_sectors', '')}

---
# [{today}] 📊 일일 투자 리포트

## 오늘의 시장 한 줄 요약

## 🔴 절대 피해야 할 섹터/종목 Top 3

## 👤 내 계좌 맞춤 진단 & 액션 플랜

## 🚀 지금 주목할 섹터 Top 2

## ✅ 오늘의 Action Plan (3가지)
"""

    response = llm.invoke([HumanMessage(content=prompt)])
    print("  ✅ 리포트 작성 완료!")
    return {
        "final_report":  response.content,
        "current_phase": "report_compiled",
    }


def notion_publish_node(state: InvestmentState) -> dict:
    """Phase 5-2: Notion 발행 / 로컬 파일 저장 (fallback)"""
    print("\n📤 [Phase 5] 리포트 발행 중...")
    final_report = state.get("final_report", "리포트 생성 실패")

    if NOTION_TOKEN and NOTION_DB_ID:
        try:
            from notion_client import Client
            today = datetime.now().strftime("%Y-%m-%d")
            Client(auth=NOTION_TOKEN).pages.create(
                parent={"database_id": NOTION_DB_ID},
                properties={
                    "Name": {"title": [{"text": {"content": f"[{today}] 일일 투자 리포트"}}]}
                },
                children=[{
                    "object": "block", "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": final_report[:2000]}}]
                    }
                }],
            )
            print("  ✅ Notion 발행 완료!")
        except Exception as e:
            print(f"  Notion 오류: {e} → 파일로 저장")
            _save_to_file(final_report)
    else:
        _save_to_file(final_report)

    return {"current_phase": "published"}


def _save_to_file(report: str):
    """리포트를 로컬 .md 파일로 저장"""
    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"daily_report_{today}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"  💾 저장 완료: {filename}")
    print("\n" + "─" * 60)
    print(report[:800] + ("..." if len(report) > 800 else ""))
    print("─" * 60)
