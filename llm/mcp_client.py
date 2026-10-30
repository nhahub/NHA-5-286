"""
Purpose: Connect to the official Playwright MCP server and return per-agent filtered tool lists.
Reads: N/A (spawns MCP subprocess)
Writes: N/A (returns tool objects)
Must not: expose the unfiltered MCP tool list to any agent; each agent receives only its allowed tools (spec §3)
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import threading
from typing import Any

from langchain_core.tools import StructuredTool

logger = logging.getLogger(__name__)

# Per spec §3 — allowed MCP tools per agent. File tools (save/read/get_results) are local
# system functions, never MCP tools: the system saves code itself and the nodes read specs.
AGENT_TOOLS: dict[str, tuple[str, ...]] = {
    "planner": ("browser_navigate", "browser_snapshot", "browser_click", "browser_type"),
    "codegen": ("browser_snapshot", "browser_generate_locator"),
    "analyzer": ("browser_snapshot",),
    "fix_proposal": ("browser_generate_locator",),
}

START_TIMEOUT_S = 120
CALL_TIMEOUT_S = 60


class McpSession:
    """One long-lived Playwright MCP session on its own event loop, so the open page survives between calls."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True, name="playwright-mcp")
        self._thread.start()
        self._started = threading.Event()
        self._error: Exception | None = None
        self._stop: asyncio.Event | None = None
        self._tools: dict[str, Any] = {}
        asyncio.run_coroutine_threadsafe(self._run(), self._loop)
        if not self._started.wait(START_TIMEOUT_S) or self._error is not None:
            error = self._error or TimeoutError("Playwright MCP server did not start in time")
            self.close()
            raise RuntimeError(f"Playwright MCP unavailable: {error}")

    async def _run(self) -> None:
        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
            from langchain_mcp_adapters.tools import load_mcp_tools

            npx = shutil.which("npx")
            if npx is None:
                raise FileNotFoundError("npx was not found; install Node.js.")
            client = MultiServerMCPClient({
                "playwright": {
                    "transport": "stdio",
                    "command": npx,
                    "args": ["-y", "@playwright/mcp@latest", "--headless", "--isolated"],
                    "env": dict(os.environ),
                }
            })
            self._stop = asyncio.Event()
            async with client.session("playwright") as session:
                self._tools = {t.name: t for t in await load_mcp_tools(session)}
                self._started.set()
                await self._stop.wait()
        except Exception as exc:  # reported to the thread waiting in __init__
            self._error = exc
        finally:
            self._started.set()

    def tool(self, name: str) -> StructuredTool | None:
        """A synchronous tool that runs on the MCP loop (the page stays open across calls)."""
        mcp_tool = self._tools.get(name)
        if mcp_tool is None:
            return None

        def call(**kwargs: Any) -> Any:
            future = asyncio.run_coroutine_threadsafe(mcp_tool.ainvoke(kwargs), self._loop)
            return future.result(CALL_TIMEOUT_S)

        return StructuredTool(
            name=mcp_tool.name,
            description=mcp_tool.description,
            args_schema=mcp_tool.args_schema,
            func=call,
        )

    def close(self) -> None:
        if self._stop is not None:
            self._loop.call_soon_threadsafe(self._stop.set)
        self._loop.call_soon_threadsafe(self._loop.stop)


_SESSION: McpSession | None = None
_LOCK = threading.Lock()
_FAILED = False


def get_session() -> McpSession | None:
    """Shared session, or None when the MCP server cannot start (agents then work without browser tools)."""
    global _SESSION, _FAILED
    with _LOCK:
        if _SESSION is None and not _FAILED:
            try:
                _SESSION = McpSession()
            except Exception as exc:
                _FAILED = True
                logger.warning("%s", exc)
        return _SESSION


def reset_session() -> None:
    global _SESSION, _FAILED
    with _LOCK:
        if _SESSION is not None:
            _SESSION.close()
        _SESSION, _FAILED = None, False


def get_agent_tools(agent_name: str) -> list[StructuredTool]:
    """Tools this agent may use; raises KeyError for an unknown agent. Empty list if MCP is unavailable."""
    allowed = AGENT_TOOLS[agent_name]
    session = get_session()
    if session is None:
        return []
    return [t for t in (session.tool(name) for name in allowed) if t is not None]


def _text(output: Any) -> str:
    if isinstance(output, str):
        return output
    if isinstance(output, list):
        return "\n".join(
            str(b.get("text", "")) if isinstance(b, dict) else str(b) for b in output
        )
    return str(output)


def page_snapshot(url: str, max_chars: int = 8000) -> str | None:
    """System-driven navigate + snapshot (not model-chosen). None when MCP is unavailable or the call fails."""
    session = get_session()
    if session is None:
        return None
    navigate, snapshot = session.tool("browser_navigate"), session.tool("browser_snapshot")
    if navigate is None or snapshot is None:
        return None
    try:
        navigate.invoke({"url": url})
        return _text(snapshot.invoke({}))[:max_chars]
    except Exception as exc:
        logger.warning("page snapshot failed: %s", exc)
        return None
