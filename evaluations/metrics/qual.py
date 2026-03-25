import json
import re
from statistics import mean
from typing import Any, Dict, List

from langchain_core.prompts import ChatPromptTemplate

from data.fetchers import get_llm


def _extract_json_from_response(content: str) -> Dict[str, Any]:
    """
    LLM 응답에서 JSON 부분만 최대한 안정적으로 추출합니다.
    """
    if not content:
        return {
            "overall_score": 0.0,
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
            "overall_score": 0.0,
            "reasoning": "JSON parsing failed",
            "raw": content,
        }


def evaluate_with_llm_judge(report: str, style_guide_path: str = "STYLE_GUIDE.md") -> Dict[str, Any]:
    """
    CIO 최종 리포트에 대해 LLM-as-a-Judge 방식의 정성 평가를 수행합니다.
    유저스토리 기준에 맞춰 '돈 내고 읽을 가치(PMF)'를 5점 만점으로 평가합니다.
    """
    if not report or not report.strip():
        return {
            "overall_score": 0.0,
            "criteria_scores": {},
            "reasoning": "평가할 리포트가 비어 있습니다.",
            "paid_willingness": "no",
        }

    llm = get_llm(temperature=0.1)

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

당신의 역할은 아래 리포트가
"신뢰 가능한 투자 판단 자료로 활용 가능한 수준인지"를 평가하는 것입니다.

다음 기준을 바탕으로 평가하세요:

1. 논리성 (logic)
- 주장과 근거가 자연스럽게 연결되는가

2. 설득력 (persuasiveness)
- 투자 판단이 납득 가능한가

3. 전문성 (expert_tone)
- 경제/투자 리포트로서 적절한 톤을 유지하는가

4. 가독성 (readability)
- 문장이 명확하고 읽기 쉬운가

5. 일관성 (consistency)
- 리포트 전체에 모순 없이 일관된 메시지를 전달하는가

다음 규칙을 반드시 지키세요:

- 모든 점수는 1.0 ~ 5.0 사이의 소수점 한 자리로 평가하세요
- overall_score는 전체적인 품질을 종합한 점수입니다
- JSON 형식 외의 텍스트는 절대 출력하지 마세요
- 코드블록(```), 설명문 없이 JSON만 출력하세요

아래 형식으로만 응답하세요:

{{
  "overall_score": 0.0,
  "criteria_scores": {{
    "logic": 0.0,
    "persuasiveness": 0.0,
    "expert_tone": 0.0,
    "readability": 0.0,
    "consistency": 0.0
  }},
  "verdict": "pass/fail",
  "strengths": ["...","..."],
  "weaknesses": ["...","..."],
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

    parsed = _extract_json_from_response(response.content)

    # 기본값 보정
    parsed.setdefault("overall_score", 0.0)
    parsed.setdefault("criteria_scores", {})
    parsed.setdefault("paid_willingness", "no")
    parsed.setdefault("verdict", "fail")
    parsed.setdefault("strengths", [])
    parsed.setdefault("weaknesses", [])
    parsed.setdefault("reasoning", "No reasoning provided")

    return parsed


def evaluate_with_llm_judge_average(
    report: str,
    style_guide_path: str = "STYLE_GUIDE.md",
    num_runs: int = 3,
) -> Dict[str, Any]:
    """
    동일 리포트에 대해 LLM Judge를 여러 번 실행하고 평균 점수를 계산합니다.
    Acceptance Criteria의 '3~5개 테스트 런 평균 평점' 용도입니다.
    """
    runs: List[Dict[str, Any]] = []

    for _ in range(num_runs):
        result = evaluate_with_llm_judge(report, style_guide_path=style_guide_path)
        runs.append(result)

    valid_scores = [
        float(r.get("overall_score", 0.0))
        for r in runs
        if isinstance(r.get("overall_score", 0.0), (int, float))
    ]

    criteria_names = ["logic", "persuasiveness", "expert_tone", "readability", "consistency"]
    criteria_avg = {}

    for name in criteria_names:
        scores = []
        for r in runs:
            criteria = r.get("criteria_scores", {})
            value = criteria.get(name)
            if isinstance(value, (int, float)):
                scores.append(float(value))
        criteria_avg[name] = round(mean(scores), 2) if scores else 0.0

    avg_score = round(mean(valid_scores), 2) if valid_scores else 0.0
    pass_count = sum(1 for r in runs if r.get("verdict") == "pass")
    yes_count = sum(1 for r in runs if r.get("paid_willingness") == "yes")

    return {
        "overall_score_avg": avg_score,
        "criteria_scores_avg": criteria_avg,
        "num_runs": num_runs,
        "pass_rate": round(pass_count / num_runs, 2) if num_runs else 0.0,
        "paid_willingness_rate": round(yes_count / num_runs, 2) if num_runs else 0.0,
        "final_verdict": "pass" if avg_score >= 4.0 else "fail",
        "runs": runs,
    }


def check_hallucination(report: str, context_data: Dict[str, Any]) -> float:
    """
    추후 확장용 함수.
    현재는 placeholder입니다.
    """
    return 1.0