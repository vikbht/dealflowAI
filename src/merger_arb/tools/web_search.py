"""
Web search tool backed by Tavily.

Tavily is purpose-built for LLM agents — it returns cleaned, chunked text
rather than raw HTML, which avoids the scraping/parsing layer entirely.
Free tier: 1,000 searches/month. Paid: ~$0.01/search.

Docs: https://docs.tavily.com
"""

import json

from langchain_core.tools import tool
from tavily import AsyncTavilyClient

from merger_arb.config import settings

_client = AsyncTavilyClient(api_key=settings.tavily_api_key)


@tool
async def web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web for current information relevant to a merger deal.

    Use this for: recent news, analyst reactions, regulatory press releases,
    market commentary, company announcements not yet in SEC filings.

    Always include the deal name or company names in the query.
    Example queries:
      - "Microsoft Activision Blizzard merger FTC antitrust 2024"
      - "ATVI activist investor pressure regulatory clearance"
      - "Activision Blizzard Q3 2023 earnings revenue"

    Args:
        query:       Natural language search query.
        max_results: Number of results to return (default 5, max 10).

    Returns:
        JSON string with a list of results, each containing title, url, content snippet.
    """
    response = await _client.search(
        query=query,
        max_results=min(max_results, 10),
        search_depth="advanced",   # deeper crawl, better content extraction
        include_answer=False,
        include_raw_content=False,
    )

    results = [
        {
            "title": r.get("title"),
            "url": r.get("url"),
            "published_date": r.get("published_date"),
            "content": r.get("content", "")[:2000],  # cap per-result length
        }
        for r in response.get("results", [])
    ]

    return json.dumps(results, indent=2)


@tool
async def fetch_url_content(url: str) -> str:
    """
    Fetch and extract the clean text content of a specific URL.

    Use this when web_search returns a relevant article URL and you need
    the full content, not just the snippet. Especially useful for:
      - SEC press releases on regulatory decisions
      - DOJ / FTC / EC merger decision documents
      - News articles about deal developments

    Args:
        url: The full URL to fetch.

    Returns:
        Cleaned plain-text content of the page (truncated to ~10,000 chars).
    """
    response = await _client.extract(urls=[url])
    results = response.get("results", [])
    if not results:
        return f"Could not extract content from {url}"

    content = results[0].get("raw_content", "")[:10_000]
    return f"[SOURCE: {url}]\n\n{content}"
