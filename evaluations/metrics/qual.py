from typing import Any, Dict

from langchain_core.prompts import ChatPromptTemplate

from data.fetchers import get_llm


def evaluate_with_llm_judge(report: str, style_guide_path: str = "STYLE_GUIDE.md") -> Dict[str, Any]:
    """
    LLM-as-a-Judge: 실제 생성된 리포트가 스타일 가이드와 거시경제 애널리스트 페르소나를
    얼마나 잘 지켰는지 '정성 평가'를 수행합니다.
    """
    llm = get_llm(temperature=0.1)  # 평가용 LLM은 일관성을 위해 낮은 온도로 설정

    # 실제 스타일 가이드 로드 (단순화된 형태)
    with open(style_guide_path, "r", encoding="utf-8") as f:
        style_content = f.read()

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "당신은 투자 리포트 품질 평가 위원입니다. "
                "생성된 리포트가 아래 스타일 가이드를 준수했는지 비판적으로 평가하고 1~10점 사이의 점수를 부여하세요. "
                "반드시 JSON 형식으로 응답하세요: {{'score': float, 'reasoning': str}}",
            ),
            (
                "user",
                "[스타일 가이드]\n{style_content}\n\n[평가할 리포트]\n{report}",
            ),
        ]
    )

    evaluate_chain = prompt | llm
    response = evaluate_chain.invoke(
        {
            "style_content": style_content[:1000],  # 용량 최적화
            "report": report,
        }
    )

    # JSON 파싱 로직 개선 (마크다운 백틱 제거 및 유연한 파싱)
    try:
        import json
        import re

        content = response.content
        # ```json ... ``` 형태의 백틱 제거
        json_str = re.sub(r"```json\s?|\s?```", "", content).strip()
        return json.loads(json_str)
    except Exception as e:
        return {"score": 0, "reasoning": f"JSON 파싱 실패: {str(e)}", "raw": response.content}


def check_hallucination(report: str, context_data: Dict[str, Any]) -> float:
    """
    Hallucination(환각) 발생 여부를 확인합니다.
    (Macro data 리스트 등 원본 데이터와 리포트 내용이 충돌하는지 체크)
    """
    # ... GP 노드의 로직을 활용하거나 추가적인 별도 LLM 검증 가능 ...
    return 1.0  # (임시)
