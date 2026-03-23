"""Tool registry — import all tools here so agents can discover them easily."""

from merger_arb.tools.edgar import (
    fetch_filing_text,
    get_company_facts,
    get_recent_filings,
)
from merger_arb.tools.web_search import fetch_url_content, web_search

EQUITY_RESEARCH_TOOLS = [
    get_recent_filings,
    fetch_filing_text,
    get_company_facts,
    web_search,
    fetch_url_content,
]

LEGAL_MNA_TOOLS = [
    fetch_filing_text,   # S-4, DEF 14A, 8-K merger agreement exhibits
    web_search,
    fetch_url_content,
]

ANTITRUST_TOOLS = [
    web_search,
    fetch_url_content,
    get_company_facts,   # for revenue/market share proxies
]
