import json
import re
from typing import Any, Dict, List

from langchain_core.prompts import ChatPromptTemplate

from data.fetchers import get_llm


def _extract_json_from_response(content: str) -> Dict[str, Any]:
    """
    LLM 응답에서 JSON 부분만 최대한 안정적으로 추출합니다.
    """
    if not content:
        return {
            "signal": "neutral",
            "confidence": "low",
            "verdict": "fail",
            "framework_review": {},
            "strengths": [],
            "weaknesses": [],
            "improvement_suggestions": [],
            "reasoning": "Empty response from judge",
            "raw": content,
        }

    text = content.strip()

    # ```json ... ``` 제거
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    # 가장 바깥 JSON 객체 추출 시도
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        text = match.group(0)

    try:
        return json.loads(text)
    except Exception:
        return {
            "signal": "neutral",
            "confidence": "low",
            "verdict": "fail",
            "framework_review": {},
            "strengths": [],
            "weaknesses": [],
            "improvement_suggestions": [],
            "reasoning": "JSON parsing failed",
            "raw": content,
        }


def evaluate_with_llm_judge(report: str, style_guide_path: str = "STYLE_GUIDE.md") -> Dict[str, Any]:
    """
    CIO 최종 리포트에 대해 LLM-as-a-Judge 방식의 정성 평가를 수행합니다.
    점수형이 아닌 프레임워크 기반 정성 평가를 반환합니다.
    """
    if not report or not report.strip():
        return {
            "signal": "neutral",
            "confidence": "low",
            "verdict": "fail",
            "framework_review": {
                "thesis_quality": "",
                "risk_balance": "",
                "consistency": "",
                "actionability": "",
                "expert_tone": "",
                "readability": "",
            },
            "strengths": [],
            "weaknesses": [],
            "improvement_suggestions": [],
            "reasoning": "평가할 리포트가 비어 있습니다.",
        }

    llm = get_llm(model="gpt-5.4", temperature=0.1)

    try:
        with open(style_guide_path, "r", encoding="utf-8") as f:
            style_content = f.read()
    except FileNotFoundError:
        style_content = "격식 있는 투자 리포트 문체, 문단형 서술, 섹션 구조 유지, 전문가 톤 유지"

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
당신은 투자 리포트의 품질을 평가하는 AI 심사관입니다.
As an AI 시스템 설계자,
I want LLM을 심사관(LLM-as-a-Judge)으로 활용하여
생성된 투자 리포트를 아래 기준대로 판단하고,
So that 사람이 일일이 검토하지 않아도
리포트가 안정적이고 신뢰 가능한 수준으로 생성되었는지에 대해
정성적인 평가를 얻고 싶다.

1. thesis_quality
- 핵심 투자 아이디어가 대체로 보이는가
- 단순 나열을 넘어서 왜 이런 판단이 나왔는지 어느 정도 설명되는가

2. risk_balance
- 긍정적인 내용만 있지 않고 리스크도 함께 다루는가
- 전체적으로 한쪽으로 과도하게 치우치지 않는가

3. consistency
- 리포트 안의 주요 섹션들이 크게 모순되지 않는가
- 전체 흐름이 대체로 자연스러운가

4. actionability
- 투자자가 읽고 어느 정도 참고할 만한 방향성이 있는가
- 완벽하지 않아도 실질적인 시사점이 있는가

추가로 아래도 함께 고려하세요:
- expert_tone: 투자 리포트다운 차분한 문체인지
- readability: 너무 복잡하지 않고 읽기 편안한지

평가 원칙:
- 프로젝트 결과물이라는 점을 감안하세요
- 치명적인 모순이나 매우 부정확한 구조가 아니면 너무 엄격하게 fail 주지 마세요
- JSON 외의 텍스트는 출력하지 마세요
- 코드블록 없이 JSON만 출력하세요
- strengths, weaknesses, improvement_suggestions는 각각 1개 이상 작성하세요
- reasoning은 3~5문장 정도로 간단히 작성하세요

signal 기준:
- "positive": 구조와 내용이 전반적으로 무난하고 참고할 가치가 있음
- "neutral": 기본 형태는 갖췄지만 설명력이나 구체성이 다소 부족함
- "negative": 핵심 흐름이 어색하거나 참고자료로 쓰기 어려운 문제가 큼

confidence 기준:
- "high": 판단이 비교적 분명함
- "medium": 대체로 판단 가능함
- "low": 내용이 너무 부족하거나 모호함

verdict 기준:
- "pass": 프로젝트 결과물 기준에서 참고 가능한 수준
- "fail": 기본 구조나 내용 보완이 더 필요한 수준

아래 형식으로만 응답하세요:

{{
  "signal": "positive / neutral / negative",
  "confidence": "high / medium / low",
  "verdict": "pass / fail",
  "framework_review": {{
    "thesis_quality": "...",
    "risk_balance": "...",
    "consistency": "...",
    "actionability": "...",
    "expert_tone": "...",
    "readability": "..."
  }},
  "strengths": [
    "..."
  ],
  "weaknesses": [
    "..."
  ],
  "improvement_suggestions": [
    "..."
  ],
  "reasoning": "..."
}}

판정 기준:
- overall_score ≥ 4.0 → pass
- overall_score < 4.0 → fail

중요:
- 과도하게 공격적인 투자 의견이 없어도 감점하지 마세요
- 안정적이고 보수적인 리포트는 오히려 긍정적으로 평가하세요
- 일반적인 수준의 투자 조언도 논리와 일관성이 있으면 높은 점수를 줄 수 있습니다
                """.strip(),
            ),
            (
                "user",
                """
[스타일 가이드]
{style_content}

[평가 대상 리포트]
{report}
                """.strip(),
            ),
        ]
    )

    chain = prompt | llm
    response = chain.invoke(
        {
            "style_content": style_content[:2000],
            "report": report,
        }
    )

    parsed = _extract_json_from_response(response.content)

    # 기본값 보정
    parsed.setdefault("signal", "neutral")
    parsed.setdefault("confidence", "medium")
    parsed.setdefault("verdict", "fail")

    parsed.setdefault("framework_review", {})
    if not isinstance(parsed["framework_review"], dict):
        parsed["framework_review"] = {}

    parsed["framework_review"].setdefault("thesis_quality", "")
    parsed["framework_review"].setdefault("risk_balance", "")
    parsed["framework_review"].setdefault("consistency", "")
    parsed["framework_review"].setdefault("actionability", "")
    parsed["framework_review"].setdefault("expert_tone", "")
    parsed["framework_review"].setdefault("readability", "")

    parsed.setdefault("strengths", [])
    parsed.setdefault("weaknesses", [])
    parsed.setdefault("improvement_suggestions", [])
    parsed.setdefault("reasoning", "No reasoning provided")

    if not isinstance(parsed["strengths"], list):
        parsed["strengths"] = [str(parsed["strengths"])]
    if not isinstance(parsed["weaknesses"], list):
        parsed["weaknesses"] = [str(parsed["weaknesses"])]
    if not isinstance(parsed["improvement_suggestions"], list):
        parsed["improvement_suggestions"] = [str(parsed["improvement_suggestions"])]

    return parsed


def evaluate_with_llm_judge_average(
    report: str,
    style_guide_path: str = "STYLE_GUIDE.md",
    num_runs: int = 3,
) -> Dict[str, Any]:
    """
    동일 리포트에 대해 LLM Judge를 여러 번 실행하고 결과를 집계합니다.
    """
    runs: List[Dict[str, Any]] = []

    for _ in range(num_runs):
        result = evaluate_with_llm_judge(report, style_guide_path=style_guide_path)
        runs.append(result)

    valid_scores = [float(r.get("overall_score", 0.0)) for r in runs if isinstance(r.get("overall_score", 0.0), (int, float))]
    pass_count = sum(1 for r in runs if r.get("verdict") == "pass")
    signal_counts = {
        "positive": sum(1 for r in runs if r.get("signal") == "positive"),
        "neutral": sum(1 for r in runs if r.get("signal") == "neutral"),
        "negative": sum(1 for r in runs if r.get("signal") == "negative"),
    }
    confidence_counts = {
        "high": sum(1 for r in runs if r.get("confidence") == "high"),
        "medium": sum(1 for r in runs if r.get("confidence") == "medium"),
        "low": sum(1 for r in runs if r.get("confidence") == "low"),
    }

    framework_fields = [
        "thesis_quality",
        "risk_balance",
        "consistency",
        "actionability",
        "expert_tone",
        "readability",
    ]

    framework_summary: Dict[str, List[str]] = {}
    for field in framework_fields:
        values = []
        for r in runs:
            framework = r.get("framework_review", {})
            if isinstance(framework, dict):
                value = framework.get(field)
                if isinstance(value, str) and value.strip():
                    values.append(value.strip())
        framework_summary[field] = values

    final_signal = max(signal_counts, key=signal_counts.get) if runs else "neutral"
    final_confidence = max(confidence_counts, key=confidence_counts.get) if runs else "low"
    final_verdict = "pass" if pass_count >= ((num_runs + 1) // 2) else "fail"

    return {
        "num_runs": num_runs,
        "pass_rate": round(pass_count / num_runs, 2) if num_runs else 0.0,
        "signal_distribution": signal_counts,
        "confidence_distribution": confidence_counts,
        "final_signal": final_signal,
        "final_confidence": final_confidence,
        "final_verdict": final_verdict,
        "framework_summary": framework_summary,
        "runs": runs,
    }


def check_hallucination(report: str, context_data: Dict[str, Any]) -> float:
    """
    추후 확장용 함수.
    현재는 placeholder입니다.
    """
    return 1.0


if __name__ == "__main__":
    sample_report = """
# [2026-03-25] 일일 투자 전략 리포트

## I. 거시경제 시황
금리는 높은 수준에서 유지되고 있으며 인플레이션 둔화 흐름이 이어지고 있다.

## II. 포트폴리오 진단
Apple은 높은 수익률을 기록했지만 밸류에이션 부담이 존재한다.

## III. 리스크 경고
에너지 시장 변동성과 고용 시장 불확실성이 존재한다.

## IV. 투자 기회
금융 및 기술 섹터 중심으로 안정적인 성장 가능성이 있다.
"""

    result = evaluate_with_llm_judge(sample_report)

    print("\n=== LLM Judge Result ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))