"""Native MCP exposure of `prompt_guidance.bootstrap` and `.review`.

A minimal stdio MCP server that wraps the existing two governance
functions. The MCP layer:

  - imports the existing functions and calls them unchanged
  - never duplicates governance logic in this module
  - never raises on malformed input (delegates to the existing
    advisory outputs that bootstrap/review already produce)
  - exposes exactly two tools, named:
      * ``prompt_guidance.bootstrap``
      * ``prompt_guidance.review``

Run as:

    python3 -m prompt_guidance.mcp_server

… or as a stdio binary registered in an MCP client's config (e.g.
Claude Desktop's ``claude_desktop_config.json``):

    {
      "mcpServers": {
        "prompt_guidance": {
          "command": "python3",
          "args": ["-m", "prompt_guidance.mcp_server"],
          "env": {"PYTHONPATH": "/home/ubuntu/governance"}
        }
      }
    }

For HTTP/SSE access (e.g. Claude.ai remote integrations), wrap with
``mcp-proxy`` per the existing ``memory-mcp.service`` pattern:

    /home/ubuntu/.nvm/.../bin/mcp-proxy --port 9003 --apiKey <token> -- \\
        python3 -m prompt_guidance.mcp_server

This module performs **no** I/O beyond importing the governance
package, reading stdin, and writing to stdout/stderr per MCP. It does
not read `coo-dashboard.json`, durable-queue, telemetry, or any
runtime state. Telemetry is observational, not normative.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

# Direct import of the existing governance functions. The MCP wrapper
# MUST NOT replicate or amend their logic.
from prompt_guidance.bootstrap import bootstrap as _bootstrap
from prompt_guidance.review import review as _review

logger = logging.getLogger("prompt_guidance.mcp_server")

server: Server = Server("prompt_guidance")


_BOOTSTRAP_TOOL_NAME = "prompt_guidance.bootstrap"
_REVIEW_TOOL_NAME = "prompt_guidance.review"


_BOOTSTRAP_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "repo": {
            "type": ["string", "null"],
            "description": (
                'Repository identifier, e.g. "JAPAM-AI/Ai_operations". '
                "Non-string is coerced to empty by the underlying function."
            ),
        },
        "lane": {
            "type": ["string", "null"],
            "description": (
                "Execution lane: one of {worker, claude_code, codex}. "
                "Non-string is coerced to empty."
            ),
        },
        "task_context": {
            "type": ["object", "null"],
            "description": (
                "Optional dict reserved for future per-task hints (e.g. "
                "task_id, task_type). v1 of bootstrap does not branch on "
                "task_context. Non-dict is coerced to {}."
            ),
        },
    },
    "additionalProperties": False,
}

_REVIEW_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "prompt": {
            "type": "string",
            "description": "The proposed prompt / action description being reviewed.",
        },
        "context": {
            "type": "object",
            "description": (
                "Per-action context: source, repo, branch, changed_paths, "
                "task_class, side_effects, declared_impact, etc. Schema is "
                "tolerant — review() returns advisory output for malformed input."
            ),
        },
    },
    "required": ["prompt"],
    "additionalProperties": True,
}


@server.list_tools()
async def _list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name=_BOOTSTRAP_TOOL_NAME,
            description=(
                "First-window governance bootstrap. Call before any other "
                "governance step or risky action. Returns the existing "
                "13-key bootstrap dict from prompt_guidance.bootstrap "
                "(applicable rules, git/orchestration/escalation/mirror "
                "expectations, non-goals, recommended next action). "
                "Telemetry is observational, not normative — governance "
                "doctrine comes from this tool + AGENTS/GUIDANCE."
            ),
            inputSchema=_BOOTSTRAP_INPUT_SCHEMA,
        ),
        types.Tool(
            name=_REVIEW_TOOL_NAME,
            description=(
                "Per-action governance review. Call before PRs, risky "
                "execution, architecture/orchestration/schema changes. "
                "Returns the existing review dict from "
                "prompt_guidance.review (advisory; never raises on "
                "malformed input)."
            ),
            inputSchema=_REVIEW_INPUT_SCHEMA,
        ),
    ]


def _tool_result(payload: dict[str, Any]) -> list[types.TextContent]:
    """Wrap a dict as a single MCP TextContent JSON blob.

    Using TextContent (not StructuredContent) keeps the wire-format
    minimal and identical across MCP client versions; clients parse the
    JSON in the text field.
    """
    return [types.TextContent(type="text", text=json.dumps(payload, default=str))]


@server.call_tool()
async def _call_tool(name: str, arguments: dict[str, Any] | None) -> list[types.TextContent]:
    # Defensive: an MCP client could send a truthy non-dict (list, str,
    # int) for ``arguments``. ``args.get(...)`` on those would crash and
    # break M3 (malformed input must not crash). Coerce to {} on type
    # mismatch — the underlying bootstrap/review functions already
    # produce advisory output for missing/bad fields.
    args = arguments if isinstance(arguments, dict) else {}
    if name == _BOOTSTRAP_TOOL_NAME:
        result = _bootstrap(
            repo=args.get("repo"),
            lane=args.get("lane"),
            task_context=args.get("task_context"),
        )
        return _tool_result(result)
    if name == _REVIEW_TOOL_NAME:
        result = _review(
            prompt=args.get("prompt"),
            context=args.get("context"),
        )
        return _tool_result(result)
    # Unknown tool — return a structured error in the existing
    # advisory shape rather than raising.
    return _tool_result({
        "error": "unknown_tool",
        "tool_requested": name,
        "tools_exposed": [_BOOTSTRAP_TOOL_NAME, _REVIEW_TOOL_NAME],
    })


async def _amain() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
