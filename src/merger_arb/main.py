"""
FastAPI entrypoint for the Merger Arb Agent Pipeline.

Run with:
    uv run uvicorn merger_arb.main:app --reload

Endpoints:
    POST /analyze/equity-research   → runs the Equity Research agent
    GET  /health                    → liveness check
"""

import time
from datetime import datetime

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field

from merger_arb.agents.equity_research import (
    run_equity_research,
    run_equity_research_final_pass,
)

app = FastAPI(
    title="Merger Arb AI Agents",
    description="AI-powered deal analysis pipeline for merger arbitrage.",
    version="0.1.0",
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class DealInput(BaseModel):
    target_ticker: str = Field(..., description="Target company ticker, e.g. 'ATVI'")
    target_name: str = Field(..., description="Target company full name")
    acquirer_ticker: str = Field(..., description="Acquirer ticker, e.g. 'MSFT'")
    acquirer_name: str = Field(..., description="Acquirer full name")
    announcement_date: str = Field(..., description="Deal announcement date, ISO format YYYY-MM-DD")
    offer_price: str = Field(default="Unknown", description="Per-share offer price, e.g. '$95.00'")
    current_price: str = Field(default="Unknown", description="Current target share price")
    deal_value: str = Field(default="Unknown", description="Total deal value, e.g. '$68.7 billion'")
    additional_context: str = Field(default="", description="Any extra context for the analyst")
    final_pass: bool = Field(
        default=False,
        description="If true, run a second Opus pass to polish the final report (slower, more expensive)"
    )


class AnalysisResponse(BaseModel):
    target_ticker: str
    acquirer_ticker: str
    announcement_date: str
    report: str
    generated_at: str
    elapsed_seconds: float


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.post("/analyze/equity-research", response_model=AnalysisResponse)
async def equity_research(deal: DealInput):
    """
    Run the Equity Research Analyst agent on a merger deal.

    Fetches SEC filings, searches the web, and produces a structured
    initiating coverage report. Typical runtime: 60–120 seconds.
    """
    start = time.monotonic()

    try:
        report = await run_equity_research(
            target_ticker=deal.target_ticker,
            target_name=deal.target_name,
            acquirer_ticker=deal.acquirer_ticker,
            acquirer_name=deal.acquirer_name,
            announcement_date=deal.announcement_date,
            offer_price=deal.offer_price,
            current_price=deal.current_price,
            deal_value=deal.deal_value,
            additional_context=deal.additional_context,
        )

        if deal.final_pass:
            report = await run_equity_research_final_pass(report)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    elapsed = time.monotonic() - start

    return AnalysisResponse(
        target_ticker=deal.target_ticker,
        acquirer_ticker=deal.acquirer_ticker,
        announcement_date=deal.announcement_date,
        report=report,
        generated_at=datetime.utcnow().isoformat(),
        elapsed_seconds=round(elapsed, 2),
    )


# ---------------------------------------------------------------------------
# Future endpoints (stubs — Phase 2 / 3)
# ---------------------------------------------------------------------------

@app.post("/analyze/legal-mna")
async def legal_mna_stub(deal: DealInput):
    raise HTTPException(status_code=501, detail="Legal M&A agent — coming in Phase 2.")


@app.post("/analyze/antitrust")
async def antitrust_stub(deal: DealInput):
    raise HTTPException(status_code=501, detail="Antitrust agent — coming in Phase 3.")


@app.post("/analyze/full-deal-brief")
async def full_deal_brief_stub(deal: DealInput):
    raise HTTPException(status_code=501, detail="Orchestrated full brief — coming in Phase 3.")
