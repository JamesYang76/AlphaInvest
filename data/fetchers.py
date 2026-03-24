"""
공통 데이터 수집 함수 — 모든 Phase에서 공유 사용
"""
import os
from langchain_openai import ChatOpenAI

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
FRED_API_KEY = os.getenv("FRED_API_KEY", "")


def get_llm(temperature: float = 0.7) -> ChatOpenAI:
    """LLM 인스턴스 반환"""
    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=temperature,
        api_key=os.getenv("OPENAI_API_KEY", ""),
    )


def fetch_macro_data() -> dict:
    """거시경제 데이터 수집 (FRED & yfinance API 연동)"""
    fred_api_key = os.getenv("FRED_API_KEY", "")
    if not fred_api_key:
        return {
            "fed_rate": "N/A (FRED 키 누락)",
            "cpi": "N/A (FRED 키 누락)",
            "unemployment": "N/A (FRED 키 누락)",
            "vix": "N/A",
            "dxy": "N/A",
            "sp500_trend": "N/A",
            "market_trend": "API Key Missing",
            "source": "None"
        }

    try:
        from fredapi import Fred
        import yfinance as yf

        fred = Fred(api_key=fred_api_key)

        # 1. 미국 기준 금리 (FEDFUNDS)
        fed_rate_series = fred.get_series('FEDFUNDS')
        current_fed_rate = f"{fed_rate_series.iloc[-1]}%"

        # 2. 소비자 물가 지수 (CPIAUCSL) - 전년 대비 상승률(YoY) 계산
        cpi_series = fred.get_series('CPIAUCSL')
        cpi_yoy = ((cpi_series.iloc[-1] / cpi_series.iloc[-13]) - 1) * 100
        current_cpi = f"{cpi_yoy:.2f}%"

        # 3. 실업률 (UNRATE)
        unrate_series = fred.get_series('UNRATE')
        current_unrate = f"{unrate_series.iloc[-1]}%"

        # 4. 실시간 시장 지표 (yfinance 활용)
        # VIX: 공포지수, DXY: 달러인덱스, ^GSPC: S&P500
        vix = yf.Ticker("^VIX").history(period="1d")['Close'].iloc[-1]
        dxy = yf.Ticker("DX-Y.NYB").history(period="1d")['Close'].iloc[-1]
        sp500 = yf.Ticker("^GSPC").history(period="5d")
        sp500_trend = "상승세" if sp500['Close'].iloc[-1] > sp500['Close'].iloc[0] else "조정/하락세"

        return {
            "fed_rate": current_fed_rate,
            "cpi": current_cpi,
            "unemployment": current_unrate,
            "vix": f"{vix:.2f}",
            "dxy": f"{dxy:.2f}",
            "sp500_trend": sp500_trend,
            "market_trend": "Real-time Macro Environment",
            "source": "FRED & yfinance"
        }
    except Exception as e:
        return {
            "fed_rate": f"Error: {str(e)}",
            "cpi": "Error",
            "unemployment": "Error",
            "vix": "Error",
            "dxy": "Error",
            "sp500_trend": "Error",
            "market_trend": "Data Collection Failed",
            "source": "None"
        }


def fetch_stock_data(tickers: list) -> dict:
    """주식 시세 및 재무 데이터 수집 (yfinance)"""
    import yfinance as yf

    result = {}
    for ticker in tickers:
        try:
            info = yf.Ticker(ticker).info
            result[ticker] = {
                "price":          info.get("currentPrice",    "N/A"),
                "pe_ratio":       info.get("trailingPE",      "N/A"),
                "market_cap":     info.get("marketCap",       "N/A"),
                "dividend_yield": info.get("dividendYield",   "N/A"),
                "52w_high":       info.get("fiftyTwoWeekHigh","N/A"),
            }
        except Exception as e:
            result[ticker] = {"error": str(e)}
    return result


def fetch_news(query: str) -> str:
    """실시간 뉴스 검색 (Tavily API 연동)"""
    tavily_api_key = os.getenv("TAVILY_API_KEY", "")
    if not tavily_api_key:
        return f"Tavily API 키가 설정되지 않았습니다. '{query}'에 대한 실시간 뉴스를 가져올 수 없습니다."

    try:
        from tavily import TavilyClient
        results = TavilyClient(api_key=tavily_api_key).search(
            query=query, max_results=5
        )
        return "\n".join(
            f"- {r['title']}: {r['content'][:200]}"
            for r in results["results"]
        )
    except Exception as e:
        return f"Tavily 뉴스 검색 중 오류 발생: {str(e)}"
