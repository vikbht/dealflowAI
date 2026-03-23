# DealFlowAI 🚀
**(Merger Arbitrage AI Agent Pipeline)**

A multi-agent system that automates preliminary deal analysis for a merger arbitrage fund. Given a merger announcement, the pipeline fans out to specialist AI agents, each focused on a distinct analytical domain, and combines their outputs into a unified deal brief.

## 🏗️ Architecture & Approach
The system uses the **ReAct (Reason + Act)** pattern powered by **LangGraph** and Anthropic's **Claude** models. 

For deep technical and architecture details, see [ARCHITECTURE.md](ARCHITECTURE.md).

## 🌟 Key Features
- **Equity Research Agent (Phase 1 MVP):** Scrapes SEC EDGAR and web data to produce a research-grade initiating coverage report.
- **Legal M&A Agent (Phase 2):** Summarizes merger agreements and flags key deal risk clauses using RAG for long documents.
- **Antitrust Agent (Phase 3):** Performs regulatory risk assessment across DOJ, FTC, EC, SAMR with probability scores.

## 🛠️ Technology Stack
- **Framework:** `FastAPI` for async REST endpoints.
- **AI/LLM:** `LangGraph` for orchestrating agents, Anthropic `Claude-3.5-Sonnet` (for fast tool use) and `Claude-3-Opus` (for synthesis).
- **Package Manager:** `uv` for blazing-fast dependency management and environments.
- **Data Sources:** SEC EDGAR (Free), Tavily Search API. 

## 🚀 Getting Started

### 1. Prerequisites
Ensure you have `uv` installed:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/vikbht/dealflowAI.git
cd dealflowAI
uv sync
```

### 3. Environment Variables
Copy the template and add your API keys (e.g., Anthropic, Tavily):
```bash
cp .env.example .env
```
*Edit `.env` to include your specific tokens.*

### 4. Running the Dev Example
You can test the pipeline locally using the CLI script (no server needed):
```bash
uv run python run_example.py
```

### 5. Running the API Server
Start the FastAPI server:
```bash
uv run uvicorn merger_arb.main:app --reload
```
You can then hit the endpoint:
```bash
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
