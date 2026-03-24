"""
공통 데이터 수집 함수 — 모든 Phase에서 공유 사용
"""

import os

from langchain_openai import ChatOpenAI

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
FRED_API_KEY = os.getenv("FRED_API_KEY", "")


def get_llm(model: str = "gpt-4o", temperature: float = 0.7) -> ChatOpenAI:
    """LLM 인스턴스 반환"""
    return ChatOpenAI(
        model=model,
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
            "source": "None",
        }

    try:
        import yfinance as yf
        from fredapi import Fred

        fred = Fred(api_key=fred_api_key)

        # 1. FRED 정밀 데이터 (지수별 최근 관측값)
        indicators = {
            "fed_rate": "FEDFUNDS",  # 연준 금리 (월간)
            "d_fed_rate": "DFF",  # 연준 금리 (일간)
            "cpi": "CPIAUCSL",  # CPI (월간)
            "unrate": "UNRATE",  # 실업률 (월간)
            "ten_year": "DGS10",  # 10년물 금리 (일간)
            "hy_spread": "BAMLH0A0HYM2",  # 하이일드 스프레드 (일간)
        }

        raw_data = {}
        for key, series_id in indicators.items():
            try:
                s = fred.get_series(series_id)
                raw_data[key] = float(s.iloc[-1]) if not s.empty else None
            except Exception:
                raw_data[key] = None

        # CPI YoY 계산
        cpi_series = fred.get_series("CPIAUCSL")
        cpi_yoy = ((cpi_series.iloc[-1] / cpi_series.iloc[-13]) - 1) * 100 if len(cpi_series) >= 13 else None

        # 2. 시장 지표 (yfinance)
        vix = yf.Ticker("^VIX").history(period="1d")["Close"].iloc[-1]
        dxy = yf.Ticker("DX-Y.NYB").history(period="1d")["Close"].iloc[-1]
        sp500 = yf.Ticker("^GSPC").history(period="5d")
        sp500_trend = "상승세" if sp500["Close"].iloc[-1] > sp500["Close"].iloc[0] else "조정/하락세"

        return {
            "fed_rate": f"{raw_data['fed_rate']:.2f}%" if raw_data["fed_rate"] else "N/A",
            "d_fed_rate": raw_data["d_fed_rate"],
            "cpi": f"{cpi_yoy:.2f}%" if cpi_yoy else "N/A",
            "unemployment": f"{raw_data['unrate']:.2f}%" if raw_data["unrate"] else "N/A",
            "vix": f"{vix:.2f}",
            "dxy": f"{dxy:.2f}",
            "sp500_trend": sp500_trend,
            "ten_year_yield": raw_data["ten_year"],
            "high_yield_spread": raw_data["hy_spread"],
            "source": "FRED & yfinance",
        }
    except Exception as e:
        return {"error": str(e), "source": "None"}


def fetch_stock_data(tickers: list) -> dict:
    """주식 시세 및 재무 데이터 수집 (yfinance)"""
    import yfinance as yf

    result = {}
    for ticker in tickers:
        try:
            info = yf.Ticker(ticker).info
            result[ticker] = {
                "price": info.get("currentPrice", "N/A"),
                "pe_ratio": info.get("trailingPE", "N/A"),
                "market_cap": info.get("marketCap", "N/A"),
                "dividend_yield": info.get("dividendYield", "N/A"),
                "52w_high": info.get("fiftyTwoWeekHigh", "N/A"),
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

        results = TavilyClient(api_key=tavily_api_key).search(query=query, max_results=5)
        return "\n".join(f"- {r['title']}: {r['content'][:200]}" for r in results["results"])
    except Exception as e:
        return f"Tavily 뉴스 검색 중 오류 발생: {str(e)}"


# ─── 기술적 지표 및 상세 시장 신호 (Risk 노드 등에서 사용) ───


def fetch_market_signals(tickers: list) -> dict:
    """여러 티커에 대한 시장 신호(수익률, RSI, 이격도 등)를 병렬로 수집"""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    import yfinance as yf

    def _fetch_one(ticker):
        base = {"ticker": ticker}
        try:
            hist = yf.Ticker(ticker).history(period="3mo", interval="1d")
            closes = hist["Close"].dropna()
            if len(closes) < 20:
                return {**base, "error": "insufficient data"}

            r5 = (closes.iloc[-1] / closes.iloc[-5] - 1) * 100
            r20 = (closes.iloc[-1] / closes.iloc[-20] - 1) * 100
            vol = closes.pct_change().dropna().iloc[-20:].std() * (252**0.5) * 100
            dd = ((closes - closes.cummax()) / closes.cummax() * 100).min()

            # RSI 14
            delta = closes.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] != 0 else 100
            rsi = round(100 - (100 / (1 + rs)), 1)

            # MA 5 Divergence
            ma5 = closes.rolling(5).mean().iloc[-1]
            ma5_div = round((closes.iloc[-1] / ma5 - 1) * 100, 1) if ma5 != 0 else 0

            return {
                **base,
                "return_5d": round(r5, 1),
                "return_20d": round(r20, 1),
                "volatility_20d": round(vol, 1),
                "drawdown_3m": round(float(dd), 1),
                "rsi_14": rsi,
                "ma5_divergence": ma5_div,
            }
        except Exception as e:
            return {**base, "error": str(e)}

    results = {}
    with ThreadPoolExecutor(max_workers=min(len(tickers), 10)) as pool:
        future_to_ticker = {pool.submit(_fetch_one, t): t for t in tickers}
        for future in as_completed(future_to_ticker):
            res = future.result()
            results[res["ticker"]] = res
    return results
