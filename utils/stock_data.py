from datetime import datetime, timedelta
from typing import Any, Dict

import yfinance as yf
from pykrx import stock as krx


def get_stock_info(ticker: str, name: str = "") -> Dict[str, Any]:
    """
    한국 주식(KRX)과 해외 주식(Yahoo Finance)의 실시간 데이터를 통합하여 공통 포맷으로 반환합니다.
    """
    is_kr = ticker.endswith(".KS") or ticker.endswith(".KQ")

    current_price = 0.0
    per, pbr = "N/A", "N/A"
    description = "데이터 없음"
    news_snippet = "최근 관련 뉴스 없음"

    try:
        # 1. 한국 주식 처리 (pykrx 우선 사용)
        if is_kr:
            pure_ticker = ticker.split(".")[0]
            # 최근 영업일 데이터 가져오기 (최대 7일 전까지 시도)
            for i in range(7):
                target_date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
                df = krx.get_market_ohlcv_by_date(target_date, target_date, pure_ticker)
                if not df.empty:
                    current_price = float(df["종가"].iloc[-1])
                    break

            # 2. Fundamental 데이터 (PER, PBR) 별도 확보 (최대 14일 전까지 추적)
            for j in range(i, i + 14):
                f_date = (datetime.now() - timedelta(days=j)).strftime("%Y%m%d")
                df_f = krx.get_market_fundamental(f_date, f_date, pure_ticker)
                if not df_f.empty and df_f["PER"].iloc[-1] != 0:
                    per = df_f["PER"].iloc[-1]
                    pbr = df_f["PBR"].iloc[-1]
                    break

        # 2. 공통/해외 및 추가 정보 (yfinance 사용) - 지표 상호 보완
        yf_stock = yf.Ticker(ticker)
        info = yf_stock.info

        # 현재가 보정 (가장 최신 값 우선)
        if current_price == 0:
            current_price = info.get("currentPrice", info.get("regularMarketPrice", 0))
            if not current_price:
                current_price = yf_stock.fast_info.get("lastPrice", 0)
            if not current_price:
                hist = yf_stock.history(period="5d")
                current_price = hist["Close"].iloc[-1] if not hist.empty else 0

        # 지표 상호 보완 (PER, PBR, EPS, BPS, ROE, Debt)
        per = info.get("trailingPE", info.get("forwardPE", info.get("priceEpsCurrentYear", per)))
        pbr = info.get("priceToBook", pbr)
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
