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
            today = datetime.now().strftime("%Y%m%d")
            # OHLCV에서 현재가(종가) 가져오기
            try:
                df = krx.get_market_ohlcv_by_date(today, today, pure_ticker)
                if df.empty:
                    # 장 전이거나 공휴일이면 전일 데이터 시도
                    yesterday = (datetime.now() - timedelta(days=3)).strftime("%Y%m%d")
                    df = krx.get_market_ohlcv_by_date(yesterday, today, pure_ticker)

                if not df.empty:
                    current_price = float(df["종가"].iloc[-1])

                # Fundamental 데이터 (PER, PBR)
                df_f = krx.get_market_fundamental(today, today, pure_ticker)
                if not df_f.empty:
                    per = df_f["PER"].iloc[-1]
                    pbr = df_f["PBR"].iloc[-1]
            except Exception:
                pass

        # 2. 공통/해외 및 추가 정보 (yfinance 사용)
        yf_stock = yf.Ticker(ticker)

        # 해외 주식 가격 또는 한국 주식 백업 가격
        if current_price == 0:
            current_price = yf_stock.fast_info.get("lastPrice", 0)
            if not current_price:
                hist = yf_stock.history(period="1d")
                current_price = hist["Close"].iloc[-1] if not hist.empty else 0

        # 지표 백업
        if per == "N/A" or pbr == "N/A":
            info = yf_stock.info
            per = info.get("trailingPE", per)
            pbr = info.get("priceToBook", pbr)

        # 뉴스 및 설명 (yfinance가 더 풍부함)
        news = yf_stock.news[:3]
        news_snippet = "\n".join([f"- {n.get('title')}" for n in news]) if news else news_snippet
        description = yf_stock.info.get("longBusinessSummary", yf_stock.info.get("description", description))

        return {
            "ticker": ticker,
            "name": name if name else ticker,
            "current_price": current_price,
            "per": per,
            "pbr": pbr,
            "news": news_snippet,
            "description": description[:500],
            "is_kr": is_kr,
        }
    except Exception as e:
        return {"ticker": ticker, "error": str(e)}
