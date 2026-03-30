import os
from typing import List

from fredapi import Fred
from tavily import TavilyClient


def get_macro_context() -> str:
    """
    Tavily Search와 FRED 지표를 결합하여 현재의 거시 경제(Macro) 컨텍스트를 생성합니다.
    """
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    fred_api_key = os.getenv("FRED_API_KEY")

    macro_context = ""

    # 1. Tavily를 이용한 최신 경제 뉴스/시황 검색
    if tavily_api_key:
        try:
            tavily = TavilyClient(api_key=tavily_api_key)
            # 'current global macro market state 2026' 등의 쿼리로 검색
            search_result = tavily.search(
                query="current global macro market outlook, interest rates, geopolitics, war, natural disasters",
                search_depth="advanced",
                max_results=3,
            )

            # 검색 결과를 순수 텍스트 리스트로 변환
            news_items = [f"- {r.get('title')}: {r.get('content')[:200]}..." for r in search_result.get("results", [])]
            macro_context += "\n".join(news_items) + "\n\n"
        except Exception as e:
            macro_context += f"- 시황 검색 실패: {str(e)}\n\n"

    # 2. FRED를 이용한 주요 경제 지표 (금리 등) 확보
    if fred_api_key:
        try:
            fred = Fred(api_key=fred_api_key)
            fed_funds = fred.get_series("FEDFUNDS").iloc[-1]
            macro_context += f"- 미국 연방기금금리(Fed Funds Rate): {fed_funds}%\n"
        except Exception as e:
            macro_context += f"- FRED 데이터 수집 불가: {str(e)}\n"

    return macro_context.strip() if macro_context else "현재 수집된 시황 정보가 없습니다."


def get_sector_context(tickers: List[str] = None) -> str:
    """
    Tavily Search를 이용하여 현재 주도 섹터(Alpha) 및 내 종목 관련 섹터 정보를 수집합니다.
    """
    tavily_api_key = os.getenv("TAVILY_API_KEY")

    if not tavily_api_key:
        return "TAVILY_API_KEY가 설정되지 않았습니다."

    # 1. 동적 쿼리 생성
    # 기본: 현재 가장 뜨거운 주도주 섹터 Top 2 및 트렌드 검색
    query = "current top 2 hottest investment leading sectors, sector rotation alpha"

    # 추가: 내 종목 섹터 전망 포함
    if tickers:
        joined_tickers = ", ".join(tickers[:3])  # 너무 길면 검색 품질이 떨어지므로 3개까지만
        query += f", investment outlook for industries related to {joined_tickers}"

    try:
        tavily = TavilyClient(api_key=tavily_api_key)
        search_result = tavily.search(
            query=query,
            search_depth="advanced",
            max_results=3,
        )

        sector_items = [f"- {r.get('title')}: {r.get('content')[:200]}..." for r in search_result.get("results", [])]
        return "\n".join(sector_items)
    except Exception as e:
        return f"- 섹터 정보 수집 실패: {str(e)}"
