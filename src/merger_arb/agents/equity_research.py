"""
Equity Research Analyst Agent

Uses LangGraph's ReAct pattern: the agent iteratively calls tools (EDGAR,
web search) until it has enough data, then writes the full coverage report.

Graph shape:
  START → analyst → [tools ↔ analyst loop] → END
"""

from typing import Annotated, TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from merger_arb.config import settings
from merger_arb.prompts.equity_research import SYSTEM_PROMPT, format_human_prompt
from merger_arb.tools import EQUITY_RESEARCH_TOOLS


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class EquityResearchState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


# ---------------------------------------------------------------------------
# LLM setup
# ---------------------------------------------------------------------------

def _build_llm() -> ChatAnthropic:
    """Bind tools to the LLM so it can call them in a ReAct loop."""
    llm = ChatAnthropic(
        model=settings.fast_model,          # sonnet for tool calls (speed + cost)
        api_key=settings.anthropic_api_key,
        max_tokens=8192,
    )
    return llm.bind_tools(EQUITY_RESEARCH_TOOLS)


# ---------------------------------------------------------------------------
# Node: analyst (calls LLM, optionally invokes tools)
# ---------------------------------------------------------------------------

def analyst_node(state: EquityResearchState) -> dict:
    """Core reasoning node — invokes Claude with the full message history."""
    llm_with_tools = _build_llm()

    # Prepend system message on first turn only
    messages = state["messages"]
    if not any(isinstance(m, SystemMessage) for m in messages):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages

    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def build_equity_research_graph() -> StateGraph:
    graph = StateGraph(EquityResearchState)

    tool_node = ToolNode(tools=EQUITY_RESEARCH_TOOLS)

    graph.add_node("analyst", analyst_node)
    graph.add_node("tools", tool_node)

    graph.add_edge(START, "analyst")

    # After analyst runs: if it called tools → go to tools node; else → END
    graph.add_conditional_edges(
        "analyst",
        tools_condition,  # LangGraph built-in: checks for tool_calls in last message
    )

    # After tools execute → always go back to analyst for next reasoning step
    graph.add_edge("tools", "analyst")

    return graph.compile()


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

async def run_equity_research(
    target_ticker: str,
    target_name: str,
    acquirer_ticker: str,
    acquirer_name: str,
    announcement_date: str,
    offer_price: str = "Unknown",
    current_price: str = "Unknown",
    deal_value: str = "Unknown",
    additional_context: str = "",
) -> str:
    """
    Run the full equity research agent and return the completed coverage report.

    Example usage:
        report = await run_equity_research(
            target_ticker="ATVI",
            target_name="Activision Blizzard",
            acquirer_ticker="MSFT",
            acquirer_name="Microsoft",
            announcement_date="2022-01-18",
            offer_price="$95.00",
            deal_value="$68.7 billion",
        )
    """
    app = build_equity_research_graph()

    human_prompt = format_human_prompt(
        target_name=target_name,
        target_ticker=target_ticker,
        acquirer_name=acquirer_name,
        acquirer_ticker=acquirer_ticker,
        announcement_date=announcement_date,
        offer_price=offer_price,
        current_price=current_price,
        deal_value=deal_value,
        additional_context=additional_context,
    )

    initial_state: EquityResearchState = {
        "messages": [HumanMessage(content=human_prompt)]
    }

    # Stream events so the caller can observe tool calls in real time
    final_state = await app.ainvoke(
        initial_state,
        config={"recursion_limit": 40},  # max tool-call iterations
    )

    # The last message is the final report from the analyst
    last_message = final_state["messages"][-1]
    return last_message.content


# ---------------------------------------------------------------------------
# Switch to the high-quality model for the final report synthesis
# ---------------------------------------------------------------------------

async def run_equity_research_final_pass(draft_report: str) -> str:
    """
    Optional second-pass: run the draft through claude-opus for a quality upgrade.

    Useful if you ran the research phase on Sonnet (fast + cheap) and want
    Opus-quality prose for the final report delivered to the PM.
    """
    llm = ChatAnthropic(
        model=settings.analysis_model,   # claude-opus-4-6
        api_key=settings.anthropic_api_key,
        max_tokens=16384,
    )

    polish_prompt = f"""You are a senior equity research editor. Below is a draft initiating \
coverage report written by an analyst. Your task is to:

1. Improve the prose quality — make it punchy, precise, institutional grade.
2. Ensure the Deal Summary Box is clearly formatted.
3. Verify the Spread Analysis section is numerically coherent.
4. Do NOT add, remove, or change any factual claims or citations.
5. Do NOT invent new data.

Return the polished report only — no commentary, no preamble.

DRAFT REPORT:
{draft_report}
"""

    response = await llm.ainvoke([HumanMessage(content=polish_prompt)])
    return response.content
