from typing import Any, Dict

import yfinance as yf


def get_stock_info(ticker: str, name: str = "") -> Dict[str, Any]:
    """
    Yahoo Finance(yfinance)를 단일 소스로 사용하여 실시간 데이터를 통합 포맷으로 반환합니다.
    """
    is_kr = ticker.endswith(".KS") or ticker.endswith(".KQ")

    current_price = 0.0
    description = "데이터 없음"
    news_snippet = "최근 관련 뉴스 없음"

    try:
        # 1. 시세 및 기본 정보 수집 (yfinance)
        yf_stock = yf.Ticker(ticker)
        info = yf_stock.info

        # 현재가 확보 (다양한 속성에서 시도)
        current_price = info.get("currentPrice", info.get("regularMarketPrice", 0))
        if not current_price or current_price == 0:
            current_price = yf_stock.fast_info.get("lastPrice", 0)
        if not current_price or current_price == 0:
            hist = yf_stock.history(period="1d")
            current_price = hist["Close"].iloc[-1] if not hist.empty else 0

        # 지표 추출 (PER, PBR, EPS, BPS, ROE, Debt)
        # 지능형 매핑: trailingPE(과거 실적 PER) -> forwardPE(전망 PER) -> priceEpsCurrentYear(올해 목표가/예상 EPS)
        per = info.get("trailingPE", info.get("forwardPE", info.get("priceEpsCurrentYear", "N/A")))
        pbr = info.get("priceToBook", "N/A")
        eps = info.get("trailingEps", info.get("epsCurrentYear", "N/A"))
        bps = info.get("bookValue", "N/A")
        roe = info.get("returnOnEquity", "N/A")
        debt_to_equity = info.get("debtToEquity", "N/A")

        # 배당 및 뉴스
        dps = info.get("dividendRate", info.get("lastDividendValue", "N/A"))
        div_yield = info.get("dividendYield", "N/A")
        news = yf_stock.news[:3]
        news_snippet = "\n".join([f"- {n.get('title')}" for n in news]) if news else news_snippet
        description = info.get("longBusinessSummary", info.get("description", description))

        return {
            "ticker": ticker,
            "name": name if name else info.get("longName", ticker),
            "current_price": f"{current_price:,.0f}" if is_kr else f"{current_price:,.2f}",
            "per": f"{per:,.2f}" if isinstance(per, (int, float)) and per != 0 else per,
            "pbr": f"{pbr:,.2f}" if isinstance(pbr, (int, float)) and pbr != 0 else pbr,
            "eps": f"{eps:,.0f}" if isinstance(eps, (int, float)) else eps,
            "bps": f"{bps:,.0f}" if isinstance(bps, (int, float)) else bps,
            "roe": f"{roe*100:.2f}%" if isinstance(roe, (int, float)) else roe,
            "debt_ratio": f"{debt_to_equity:.2f}" if isinstance(debt_to_equity, (int, float)) else debt_to_equity,
            "dps": f"{dps:,.0f}" if isinstance(dps, (int, float)) else dps,
            "yield": f"{div_yield*100:.2f}%" if isinstance(div_yield, (int, float)) else div_yield,
            "news": news_snippet,
            "description": description[:300] + "...",
            "is_kr": is_kr,
        }
    except Exception as e:
        return {"ticker": ticker, "error": f"데이터 수집 중 오류: {str(e)}"}
