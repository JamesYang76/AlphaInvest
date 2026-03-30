"""호환성용 데이터 수집 facade."""

from data.llm_client import get_llm
from data.macro_data_source import fetch_macro_data, macro_numeric_source_links
from data.market_signals import fetch_market_signals, fetch_stock_data
from data.news_source import (
    fetch_news,
    fetch_news_with_sources,
    format_report_sources_markdown,
    merge_report_source_links,
)

__all__ = [
    "fetch_macro_data",
    "fetch_market_signals",
    "fetch_news",
    "fetch_news_with_sources",
    "fetch_stock_data",
    "format_report_sources_markdown",
    "get_llm",
    "macro_numeric_source_links",
    "merge_report_source_links",
]
