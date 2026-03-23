"""
Quick dev runner — test the equity research agent from the command line.

Usage:
    uv run python run_example.py

Edit the DEAL dict below to test with different deals.
"""

import asyncio
from rich.console import Console
from rich.markdown import Markdown

from merger_arb.agents.equity_research import run_equity_research

console = Console()

# ── Edit this to test different deals ─────────────────────────────────────
DEAL = {
    "target_ticker": "ATVI",
    "target_name": "Activision Blizzard",
    "acquirer_ticker": "MSFT",
    "acquirer_name": "Microsoft",
    "announcement_date": "2022-01-18",
    "offer_price": "$95.00",
    "deal_value": "$68.7 billion",
    "current_price": "Unknown — search for it",
    "additional_context": (
        "Deal faced extended FTC challenge; was ultimately cleared in 2023. "
        "This is a retrospective analysis for model evaluation purposes."
    ),
}
# ──────────────────────────────────────────────────────────────────────────


async def main():
    console.rule("[bold blue]Merger Arb — Equity Research Agent")
    console.print(f"[cyan]Analyzing:[/cyan] {DEAL['acquirer_name']} / {DEAL['target_name']}")
    console.print(f"[cyan]Announced:[/cyan] {DEAL['announcement_date']}")
    console.print()

    with console.status("[bold green]Running agent (fetching EDGAR + web data)..."):
        report = await run_equity_research(**DEAL)

    console.rule("[bold green]Report")
    console.print(Markdown(report))


if __name__ == "__main__":
    asyncio.run(main())
