import os

from langchain_openai import ChatOpenAI


def get_llm(model: str = "gpt-5.4-mini", temperature: float = 0.7) -> ChatOpenAI:
    """공통 LLM 인스턴스 반환."""
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=os.getenv("OPENAI_API_KEY", ""),
        timeout=25,
        max_retries=1,
    )
