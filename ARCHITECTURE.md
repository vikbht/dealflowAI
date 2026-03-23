# Merger Arbitrage AI Agent Pipeline — Architecture

## Overview

A multi-agent system that automates preliminary deal analysis for a merger arbitrage fund. Given a merger announcement, the pipeline fans out to three specialist AI agents, each focused on a distinct analytical domain, then combines their outputs into a unified deal brief.

---

## System Diagram

```
                        ┌─────────────────────────┐
                        │    FastAPI Service        │
                        │   /analyze/equity-research│
                        │   /analyze/legal-mna      │
                        │   /analyze/antitrust      │
                        │   /analyze/full-deal-brief│
                        └────────────┬────────────┘
                                     │ DealInput
                                     ▼
                        ┌─────────────────────────┐
                        │     Orchestrator         │
                        │   (LangGraph StateGraph) │
                        └────┬──────────┬──────────┘
                             │          │          │
               ┌─────────────┘  ┌───────┘  ┌──────┘
               ▼                ▼           ▼
   ┌──────────────────┐ ┌────────────┐ ┌────────────────┐
   │  Equity Research │ │ Legal M&A  │ │   Antitrust    │
   │     Agent        │ │   Agent    │ │     Agent      │
   │ (MVP — Phase 1)  │ │ (Phase 2)  │ │  (Phase 3)     │
   └────────┬─────────┘ └─────┬──────┘ └───────┬────────┘
            │                 │                 │
            ▼                 ▼                 ▼
   ┌─────────────────────────────────────────────────────┐
   │                    Tool Layer                        │
   │  ┌──────────────┐  ┌─────────────┐  ┌───────────┐  │
   │  │ SEC EDGAR    │  │  Tavily Web │  │  Future:  │  │
   │  │ data.sec.gov │  │  Search API │  │  Court DB │  │
   │  │ (filings,    │  │  (news,     │  │  EC/DOJ   │  │
   │  │  XBRL facts) │  │  regulatory │  │  Opinions │  │
   │  │              │  │  commentary)│  │           │  │
   │  └──────────────┘  └─────────────┘  └───────────┘  │
   └─────────────────────────────────────────────────────┘
            │
            ▼
   ┌────────────────────────────────┐
   │     Claude API (Anthropic)     │
   │  claude-sonnet-4-6  (tools)    │
   │  claude-opus-4-6    (reports)  │
   └────────────────────────────────┘
```

---

## Agent Design Pattern: ReAct Loop

Each agent follows the **ReAct (Reason + Act)** pattern via LangGraph:

```
Human prompt (deal context)
        │
        ▼
   [Analyst Node]  ← Claude with tools bound
        │
        ├── Tool call requested? ──YES──► [Tool Node] ──► back to Analyst
        │
        └── No tool calls ──► Final report text ──► END
```

This loop continues until Claude decides it has enough information to write the report. The `recursion_limit=40` cap prevents runaway tool calling.

---

## Data Sources

| Source | Access | Used By | Notes |
|---|---|---|---|
| SEC EDGAR `data.sec.gov` | Free, no key | All agents | 10-K, 8-K, DEF 14A, S-4, XBRL facts |
| Tavily Search API | Free tier: 1k/mo | All agents | Best LLM-native search; returns clean chunks |
| Bloomberg.com | Public web | Equity Research | Scrape sparingly; check ToS |
| FTC.gov / DOJ.gov | Public web | Antitrust | Merger clearance press releases |
| EUR-Lex | Public web | Antitrust | EC decisions (Phase I/II) |

### Key EDGAR Endpoints

```
# Ticker → CIK mapping (download once, cache in memory)
GET https://www.sec.gov/files/company_tickers.json

# All filings for a company
GET https://data.sec.gov/submissions/CIK{10-digit-cik}.json

# Structured XBRL financial facts (revenue, assets, etc.)
GET https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json

# Actual filing document (HTML/XML)
GET https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{primary_doc}
```

---

## Technology Choices

### LangGraph (not CrewAI or AutoGen)

LangGraph was chosen over alternatives for three reasons specific to a financial use case:

1. **Auditability** — the full message history (every tool call, every response) is captured in the graph state and can be logged for compliance review. CrewAI abstracts this away.
2. **Deterministic control flow** — conditional edges let you enforce that certain tools run before report generation (e.g., "always fetch the 10-K before writing the financial snapshot"). AutoGen's conversation model is less controllable.
3. **Production-grade** — LangGraph has a streaming API, persistence layer (LangGraph Platform), and human-in-the-loop support, all useful as you scale beyond MVP.

### Claude Sonnet (tools) + Claude Opus (reports)

- Sonnet handles the ReAct loop — fast, cheap, excellent at tool selection.
- Opus does the final synthesis pass when enabled — measurably better prose quality and multi-source reasoning for complex deals.
- Estimated cost per deal (both agents): ~$0.50–$2.00 depending on deal complexity and filing length.

### FastAPI + uv

- FastAPI gives you async-native HTTP from day one (important since all EDGAR/search calls are async).
- uv resolves and installs dependencies ~10x faster than pip and manages virtual environments cleanly.

---

## File Structure

```
merger-arb-agents/
├── pyproject.toml              # uv project config + dependencies
├── .env.example                # API key template
├── run_example.py              # CLI dev runner (no server needed)
│
└── src/merger_arb/
    ├── config.py               # Pydantic settings (loads from .env)
    ├── main.py                 # FastAPI app + route definitions
    │
    ├── tools/
    │   ├── __init__.py         # Tool registry (EQUITY_RESEARCH_TOOLS, etc.)
    │   ├── edgar.py            # EDGAR API wrapper (3 tools)
    │   └── web_search.py       # Tavily search wrapper (2 tools)
    │
    ├── agents/
    │   ├── __init__.py
    │   └── equity_research.py  # LangGraph ReAct agent (Phase 1 — complete)
    │   # legal_mna.py          ← Phase 2
    │   # antitrust.py          ← Phase 3
    │
    └── prompts/
        └── equity_research.py  # System prompt + human prompt template
        # legal_mna.py          ← Phase 2
        # antitrust.py          ← Phase 3
```

---

## Implementation Phases

### Phase 1 — MVP: Equity Research Agent (now)

**Goal:** A working agent that produces a research-grade initiating coverage report from EDGAR + web search.

Deliverables:
- `tools/edgar.py` — `get_recent_filings`, `fetch_filing_text`, `get_company_facts`
- `tools/web_search.py` — `web_search`, `fetch_url_content`
- `agents/equity_research.py` — LangGraph ReAct graph
- `prompts/equity_research.py` — structured coverage report prompt
- `main.py` — FastAPI with `POST /analyze/equity-research`

**Test it:** Run `uv run python run_example.py` with the MSFT/ATVI deal.

---

### Phase 2 — Legal M&A Agent

**Goal:** Summarise the merger agreement and proxy statement; flag key deal risk clauses.

New work required:
- Add a **RAG layer** for long documents (merger agreements run 100–300 pages, too long for a single context window).
  - Use `langchain` document loaders + `chromadb` as an in-memory vector store.
  - Chunk merger agreements at 2,000 tokens with 200-token overlap.
  - Retrieve the 5 most relevant chunks per question.
- Write `prompts/legal_mna.py` structured around: MAC definition, termination fee, regulatory conditions, outside date, HSR requirements, reverse break fee.
- Wire up `POST /analyze/legal-mna` in `main.py`.

Additional dependencies to add:
```
langchain-community   # document loaders
chromadb              # local vector store
pypdf                 # PDF parsing for SEC filings
```

---

### Phase 3 — Antitrust Agent + Orchestrator

**Goal:** Regulatory risk assessment across DOJ, FTC, EC, SAMR with probability scores.

New work required:
- Build web scrapers for FTC.gov, DOJ press releases, EUR-Lex decision summaries.
- Write `prompts/antitrust.py` structured around: HHI analysis, market definition, vertical vs. horizontal concerns, prior precedent in sector, jurisdiction-by-jurisdiction assessment.
- Implement `orchestrator.py` using LangGraph's `Send` API to run all three agents **in parallel**, then merge outputs in a final synthesis node.
- Wire up `POST /analyze/full-deal-brief`.

Orchestrator parallel pattern:
```python
# LangGraph parallel fan-out using Send API
graph.add_conditional_edges(
    "router",
    lambda _: [
        Send("equity_research", state),
        Send("legal_mna", state),
        Send("antitrust", state),
    ]
)
```

---

## Key Risks & Mitigations

| Risk | Mitigation |
|---|---|
| LLM hallucinating financial figures | Mandatory citation requirement in system prompt; add a validation step that checks cited numbers against raw EDGAR XBRL data |
| EDGAR throttling | `asyncio.Semaphore(5)` + `tenacity` retry with exponential backoff |
| Long merger agreements exceeding context | RAG chunking in Phase 2 (chromadb) |
| Bloomberg.com ToS / scraping blocks | Use Tavily as primary news source; Bloomberg only for supplemental data that's publicly accessible |
| SAMR (China) filings in Chinese | Use web search for English-language summaries from law firm client alerts and financial press |
| High Claude API cost on complex deals | Route tool calls to Sonnet; reserve Opus for final report only (controlled by `final_pass=True` flag) |

---

## Getting Started

```bash
# 1. Install uv if you haven't
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone / init project
cd merger-arb-agents
uv sync

# 3. Set up credentials
cp .env.example .env
# Edit .env with your Anthropic and Tavily API keys

# 4. Run the dev example (no server needed)
uv run python run_example.py

# 5. Start the API server
uv run uvicorn merger_arb.main:app --reload

# 6. Test the endpoint (in another terminal)
curl -X POST http://localhost:8000/analyze/equity-research \
  -H "Content-Type: application/json" \
  -d '{
    "target_ticker": "ATVI",
    "target_name": "Activision Blizzard",
    "acquirer_ticker": "MSFT",
    "acquirer_name": "Microsoft",
    "announcement_date": "2022-01-18",
    "offer_price": "$95.00",
    "deal_value": "$68.7 billion"
  }'
```

---

## Future Enhancements (Post-Phase 3)

- **Deal monitoring agent** — scheduled task that re-runs spread analysis daily and alerts on material changes (new SEC filings, regulatory news, price movement outside normal range).
- **Precedent deal database** — SQLite store of completed analyses; enables the antitrust agent to query "how did regulators treat prior deals in this sector?"
- **Human-in-the-loop** — LangGraph's interrupt mechanism lets a PM review and correct tool outputs mid-run before the report is written.
- **Report export** — pipe final Markdown report through the `docx` skill to produce a formatted Word document for distribution.
