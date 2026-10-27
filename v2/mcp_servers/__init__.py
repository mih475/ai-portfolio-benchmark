"""
MCP Tool Registry
Central registry of all available tools. Maps tool names to their implementations
and provides the tool definitions for LLM function calling.
"""

import logging
from datetime import date as _date
from typing import Any

from . import fred_server
from . import web_search_server
from . import url_fetch_server
from . import finnhub_news_server
from . import stock_data_server

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Run-level point-in-time context
# ─────────────────────────────────────────────
# Set by the agent runner to the simulation date. When it's a PAST date, the
# registry makes tools honor it so an agent "trading" that date can't read the
# present/future:
#   - date-aware tools get the as_of injected (point-in-time data);
#   - tools that can only return "now" are disabled (prevents look-ahead).
# None (or today/future) = live: every tool behaves exactly as before.
_RUN_AS_OF = None

# Tools that accept an `as_of` kwarg and can serve point-in-time data.
_ASOF_TOOLS = {"get_macro", "get_technicals"}
# Tools that can only return present-day data; disabled during a past-date run.
_LIVE_ONLY_TOOLS = {"web_search", "fetch_url", "get_market_news", "get_fundamentals"}


def set_run_context(as_of=None) -> None:
    """Set (or clear, with None) the simulation date for tool point-in-time behaviour."""
    global _RUN_AS_OF
    _RUN_AS_OF = as_of


def get_run_as_of():
    return _RUN_AS_OF


def _is_historical() -> bool:
    return _RUN_AS_OF is not None and _RUN_AS_OF < _date.today()

# ─────────────────────────────────────────────
# Tool Registry
# ─────────────────────────────────────────────

TOOLS = {
    "get_macro": {
        "definition": fred_server.TOOL_DEFINITION,
        "execute": fred_server.execute,
    },
    "web_search": {
        "definition": web_search_server.TOOL_DEFINITION,
        "execute": web_search_server.execute,
    },
    "fetch_url": {
        "definition": url_fetch_server.TOOL_DEFINITION,
        "execute": url_fetch_server.execute,
    },
    "get_market_news": {
        "definition": finnhub_news_server.TOOL_DEFINITION,
        "execute": finnhub_news_server.execute,
    },
    "get_technicals": {
        "definition": stock_data_server.TECHNICALS_TOOL,
        "execute": stock_data_server.get_technicals,
    },
    "get_fundamentals": {
        "definition": stock_data_server.FUNDAMENTALS_TOOL,
        "execute": stock_data_server.get_fundamentals,
    },
}


def get_tool_definitions() -> list[dict]:
    """Get all tool definitions formatted for LLM function calling."""
    return [tool["definition"] for tool in TOOLS.values()]


def get_active_tool_definitions() -> list[dict]:
    """Tool definitions to expose to the LLM for the current run context.

    In a historical (past-date) run, tools that can only return present-day data
    are hidden entirely — not just disabled on call — so the model doesn't waste
    its limited tool-call budget repeatedly invoking tools that return "disabled".
    """
    defs = get_tool_definitions()
    if _is_historical():
        defs = [d for d in defs if d.get("name") not in _LIVE_ONLY_TOOLS]
    return defs


def execute_tool(tool_name: str, arguments: dict[str, Any]) -> dict:
    """
    Execute a tool by name with the given arguments.
    
    Args:
        tool_name: Name of the tool to execute
        arguments: Tool arguments as a dict
        
    Returns:
        Tool result as a dict
    """
    if tool_name not in TOOLS:
        return {"error": f"Unknown tool: {tool_name}. Available: {list(TOOLS.keys())}"}

    # Point-in-time gating for historical (past-date) runs.
    if _is_historical():
        if tool_name in _LIVE_ONLY_TOOLS:
            msg = (f"'{tool_name}' is disabled during a historical backtest "
                   f"(simulation date {_RUN_AS_OF}) because it can only return "
                   f"present-day data, which would be look-ahead. Rely on the "
                   f"snapshot and point-in-time tools instead.")
            logger.info(f"Blocked look-ahead tool {tool_name} (as_of={_RUN_AS_OF})")
            return {"disabled": msg, "results": []}
        if tool_name in _ASOF_TOOLS:
            arguments = {**arguments, "as_of": _RUN_AS_OF.isoformat()}

    tool = TOOLS[tool_name]
    try:
        result = tool["execute"](**arguments)
        logger.info(f"Tool {tool_name} executed successfully")
        return result
    except TypeError as e:
        logger.error(f"Tool {tool_name} argument error: {e}")
        return {"error": f"Invalid arguments for {tool_name}: {e}"}
    except Exception as e:
        logger.error(f"Tool {tool_name} execution error: {e}")
        return {"error": f"Tool {tool_name} failed: {e}"}
