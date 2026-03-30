from utils import stock_data


def test_enrich_portfolio_data_preserves_input_order(monkeypatch):
    def fake_get_stock_info(ticker: str, name: str = ""):
        prices = {
            "MSFT": "400.00",
            "AAPL": "200.00",
            "NVDA": "900.00",
        }
        return {
            "ticker": ticker,
            "name": name or ticker,
            "current_price": prices[ticker],
        }

    monkeypatch.setattr(stock_data, "get_stock_info", fake_get_stock_info)

    enriched = stock_data.enrich_portfolio_data(
        [
            {"ticker": "MSFT", "avg_price": 350},
            {"ticker": "AAPL", "avg_price": 180},
            {"ticker": "NVDA", "avg_price": 800},
        ]
    )

    assert [item["ticker"] for item in enriched] == ["MSFT", "AAPL", "NVDA"]
    assert enriched[0]["profit_rate"] == "+14.29%"
    assert enriched[1]["profit_rate"] == "+11.11%"
    assert enriched[2]["profit_rate"] == "+12.50%"
