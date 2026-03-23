"""
SEC EDGAR API tools.

Wraps the free EDGAR data API (data.sec.gov) with helpers for:
  - Ticker → CIK resolution
  - Fetching recent filings (10-K, 8-K, DEF 14A, S-4)
  - Extracting filing document text

No API key required; EDGAR only needs a User-Agent header.
"""

import asyncio
import json
import re
from functools import lru_cache
from typing import Literal

import httpx
from langchain_core.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential

from merger_arb.config import settings

EDGAR_BASE = "https://data.sec.gov"
SEC_BASE = "https://www.sec.gov"

FilingType = Literal["10-K", "8-K", "DEF 14A", "S-4", "SC 13E-3"]


# ---------------------------------------------------------------------------
# HTTP client (shared, rate-limited via asyncio.Semaphore)
# ---------------------------------------------------------------------------

_semaphore = asyncio.Semaphore(5)  # max 5 concurrent EDGAR requests

def _headers() -> dict[str, str]:
    return {
        "User-Agent": settings.edgar_user_agent,
        "Accept-Encoding": "gzip, deflate",
    }


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def _get(url: str) -> httpx.Response:
    async with _semaphore:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=_headers())
            resp.raise_for_status()
            return resp


# ---------------------------------------------------------------------------
# Ticker → CIK resolution (cached in memory for the session)
# ---------------------------------------------------------------------------

_ticker_map: dict[str, str] = {}  # ticker.upper() → zero-padded 10-digit CIK


async def _load_ticker_map() -> None:
    """Download EDGAR's full ticker→CIK JSON once and cache it."""
    global _ticker_map
    if _ticker_map:
        return
    resp = await _get(f"{SEC_BASE}/files/company_tickers.json")
    raw: dict[str, dict] = resp.json()
    _ticker_map = {
        v["ticker"].upper(): str(v["cik_str"]).zfill(10)
        for v in raw.values()
    }


async def ticker_to_cik(ticker: str) -> str:
    """Resolve a ticker symbol to a zero-padded 10-digit EDGAR CIK."""
    await _load_ticker_map()
    cik = _ticker_map.get(ticker.upper())
    if not cik:
        raise ValueError(f"Ticker '{ticker}' not found in EDGAR ticker map.")
    return cik


# ---------------------------------------------------------------------------
# Filing search
# ---------------------------------------------------------------------------

@tool
async def get_recent_filings(ticker: str, form_type: str = "10-K", count: int = 5) -> str:
    """
    Return metadata for the most recent SEC filings of a given type for a company.

    Args:
        ticker:    Stock ticker (e.g. 'ATVI', 'MSFT').
        form_type: SEC form type — '10-K', '8-K', 'DEF 14A', 'S-4', etc.
        count:     How many recent filings to return (default 5).

    Returns:
        JSON string with a list of filing metadata dicts, each containing:
        accession_number, filing_date, report_date, primary_document, filing_url.
    """
    cik = await ticker_to_cik(ticker)
    resp = await _get(f"{EDGAR_BASE}/submissions/CIK{cik}.json")
    data = resp.json()

    recent = data.get("filings", {}).get("recent", {})
    forms   = recent.get("form", [])
    dates   = recent.get("filingDate", [])
    accnums = recent.get("accessionNumber", [])
    docs    = recent.get("primaryDocument", [])

    results = []
    for form, date, acc, doc in zip(forms, dates, accnums, docs):
        if form.strip().upper() == form_type.upper():
            acc_clean = acc.replace("-", "")
            filing_url = (
                f"{SEC_BASE}/Archives/edgar/data/{int(cik)}"
                f"/{acc_clean}/{doc}"
            )
            results.append({
                "form_type": form,
                "filing_date": date,
                "accession_number": acc,
                "primary_document": doc,
                "filing_url": filing_url,
                "index_url": (
                    f"{SEC_BASE}/cgi-bin/browse-edgar?action=getcompany"
                    f"&CIK={cik}&type={form_type}&dateb=&owner=include&count=1"
                ),
            })
            if len(results) >= count:
                break

    return json.dumps(results, indent=2)


@tool
async def fetch_filing_text(ticker: str, form_type: str = "10-K", max_chars: int = 80_000) -> str:
    """
    Fetch the full text of the most recent filing of a given type for a company.

    Strips HTML tags, collapses whitespace, and truncates to max_chars to
    stay within LLM context limits. Cite the source URL in your analysis.

    Args:
        ticker:    Stock ticker symbol.
        form_type: '10-K', '8-K', 'DEF 14A', 'S-4', etc.
        max_chars: Maximum characters to return (default 80,000 ≈ ~20k tokens).

    Returns:
        Plain text of the filing, truncated if necessary, with source URL prepended.
    """
    # Get the most recent filing metadata
    filings_json = await get_recent_filings.ainvoke(  # type: ignore[attr-defined]
        {"ticker": ticker, "form_type": form_type, "count": 1}
    )
    filings = json.loads(filings_json)
    if not filings:
        return f"No {form_type} filings found for {ticker} on EDGAR."

    filing = filings[0]
    url = filing["filing_url"]

    resp = await _get(url)
    raw_html = resp.text

    # Strip HTML tags
    text = re.sub(r"<[^>]+>", " ", raw_html)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    source_header = f"[SOURCE: {url}]\n[FILING DATE: {filing['filing_date']}]\n\n"
    body = text[:max_chars]
    if len(text) > max_chars:
        body += f"\n\n[TRUNCATED — original length {len(text):,} chars]"

    return source_header + body


@tool
async def get_company_facts(ticker: str) -> str:
    """
    Retrieve key financial facts for a company from EDGAR's structured data API.

    Returns recent annual revenue, net income, total assets, and shares outstanding
    as reported in SEC filings. Data is sourced from XBRL disclosures.

    Args:
        ticker: Stock ticker symbol.

    Returns:
        JSON string with the most recent values for core financial metrics.
    """
    cik = await ticker_to_cik(ticker)
    resp = await _get(f"{EDGAR_BASE}/api/xbrl/companyfacts/CIK{cik}.json")
    facts = resp.json()

    us_gaap = facts.get("facts", {}).get("us-gaap", {})

    def _latest_annual(concept: str) -> dict | None:
        """Pull the most recent 10-K annual value for a GAAP concept."""
        entries = us_gaap.get(concept, {}).get("units", {}).get("USD", [])
        annual = [e for e in entries if e.get("form") == "10-K"]
        return annual[-1] if annual else None

    def _latest_shares(concept: str) -> dict | None:
        entries = us_gaap.get(concept, {}).get("units", {}).get("shares", [])
        annual = [e for e in entries if e.get("form") == "10-K"]
        return annual[-1] if annual else None

    summary = {
        "ticker": ticker.upper(),
        "cik": cik,
        "revenue": _latest_annual("Revenues") or _latest_annual("RevenueFromContractWithCustomerExcludingAssessedTax"),
        "net_income": _latest_annual("NetIncomeLoss"),
        "total_assets": _latest_annual("Assets"),
        "shares_outstanding": _latest_shares("CommonStockSharesOutstanding"),
    }

    return json.dumps(summary, indent=2)
