"""Tests for the MCP-exposed `prompt_guidance.bootstrap` / `.review` tools.

Verifies that:
  - the MCP layer exposes exactly the two named tools
  - tool discovery returns the canonical names
  - sample bootstrap call returns a valid 13-key dict (status READY for
    JAPAM-AI/Ai_operations + claude_code lane)
  - sample review call returns a valid review dict
  - malformed input does not crash the server (delegates to the
    existing advisory outputs)
  - the MCP wrapper does not duplicate governance logic (its outputs
    are byte-identical to direct calls of the underlying functions)

Stdlib + mcp + pytest only.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from prompt_guidance.bootstrap import bootstrap as _bootstrap_direct  # noqa: E402
from prompt_guidance.review import review as _review_direct  # noqa: E402
from prompt_guidance.mcp_server import (  # noqa: E402
    _BOOTSTRAP_TOOL_NAME,
    _REVIEW_TOOL_NAME,
    _call_tool,
    _list_tools,
)

EXPECTED_BOOTSTRAP_KEYS = {
    "guidance_version", "repo", "lane", "status",
    "applicable_governance_rules", "task_structure_expectations",
    "git_expectations", "orchestration_expectations",
    "mirror_update_expectations", "when_to_call_review",
    "when_to_escalate", "non_goals", "recommended_next_action",
}


def _run(coro):
    return asyncio.run(coro)


def _payload(content_list) -> dict:
    """Tools return [TextContent(...)]; pull out and parse the JSON."""
    assert len(content_list) == 1
    item = content_list[0]
    assert item.type == "text"
    return json.loads(item.text)


# ---------------------------------------------------------------------
# 1. Tool-discovery contract
# ---------------------------------------------------------------------

def test_list_tools_returns_exactly_the_two_governance_tools():
    tools = _run(_list_tools())
    names = {t.name for t in tools}
    assert names == {_BOOTSTRAP_TOOL_NAME, _REVIEW_TOOL_NAME}


def test_tool_names_are_canonical_dotted_form():
    assert _BOOTSTRAP_TOOL_NAME == "prompt_guidance.bootstrap"
    assert _REVIEW_TOOL_NAME == "prompt_guidance.review"


def test_each_tool_has_inputSchema_and_description():
    tools = _run(_list_tools())
    for t in tools:
        assert isinstance(t.description, str) and len(t.description) > 0
        assert isinstance(t.inputSchema, dict)
        assert t.inputSchema.get("type") == "object"


# ---------------------------------------------------------------------
# 2. Bootstrap happy path
# ---------------------------------------------------------------------

_SAMPLE_BOOTSTRAP_INPUT = {
    "repo": "JAPAM-AI/Ai_operations",
    "lane": "claude_code",
    "task_context": {"task_id": "cc-example", "task_type": "cleanup"},
}


def test_bootstrap_call_returns_13_key_dict_with_status_ready():
    result = _payload(_run(_call_tool(_BOOTSTRAP_TOOL_NAME, _SAMPLE_BOOTSTRAP_INPUT)))
    assert set(result.keys()) == EXPECTED_BOOTSTRAP_KEYS
    assert result["status"] == "READY"
    assert result["repo"] == "JAPAM-AI/Ai_operations"
    assert result["lane"] == "claude_code"
    assert isinstance(result["orchestration_expectations"], list)
    assert len(result["orchestration_expectations"]) > 0
    assert isinstance(result["when_to_call_review"], list)
    assert len(result["when_to_call_review"]) > 0
    assert isinstance(result["non_goals"], list)
    assert len(result["non_goals"]) > 0


def test_bootstrap_wrapper_output_matches_direct_call_byte_for_byte():
    """The MCP layer must NOT alter behavior — output must equal direct."""
    via_mcp = _payload(_run(_call_tool(_BOOTSTRAP_TOOL_NAME, _SAMPLE_BOOTSTRAP_INPUT)))
    via_direct = _bootstrap_direct(
        repo=_SAMPLE_BOOTSTRAP_INPUT["repo"],
        lane=_SAMPLE_BOOTSTRAP_INPUT["lane"],
        task_context=_SAMPLE_BOOTSTRAP_INPUT["task_context"],
    )
    assert via_mcp == via_direct


# ---------------------------------------------------------------------
# 3. Review happy path
# ---------------------------------------------------------------------

_SAMPLE_REVIEW_INPUT = {
    "prompt": "Update docs for a low-risk cleanup PR",
    "context": {
        "source": "agent",
        "repo": "JAPAM-AI/Ai_operations",
        "branch": "docs/cleanup",
        "changed_paths": ["docs/governance/KNOWN_ISSUES.md"],
        "task_name": "docs-cleanup",
        "task_class": "standard",
        "priority": 3,
        "timeout_s": 300,
        "side_effects": ["filesystem", "github"],
        "declared_impact": ["governance_docs"],
    },
}


def test_review_call_returns_valid_dict_no_exception():
    result = _payload(_run(_call_tool(_REVIEW_TOOL_NAME, _SAMPLE_REVIEW_INPUT)))
    # review() returns its own contracted dict; verify it's a non-empty
    # dict-shape and contains at least the GUIDANCE_VERSION marker.
    assert isinstance(result, dict)
    assert "guidance_version" in result
    assert "status" in result


def test_review_wrapper_output_matches_direct_call():
    via_mcp = _payload(_run(_call_tool(_REVIEW_TOOL_NAME, _SAMPLE_REVIEW_INPUT)))
    via_direct = _review_direct(
        prompt=_SAMPLE_REVIEW_INPUT["prompt"],
        context=_SAMPLE_REVIEW_INPUT["context"],
    )
    assert via_mcp == via_direct


# ---------------------------------------------------------------------
# 4. Malformed input — must not crash; must produce advisory output
# ---------------------------------------------------------------------

def test_bootstrap_with_missing_args_does_not_crash():
    result = _payload(_run(_call_tool(_BOOTSTRAP_TOOL_NAME, {})))
    assert isinstance(result, dict)
    assert set(result.keys()) == EXPECTED_BOOTSTRAP_KEYS
    assert result["status"] in ("READY", "WARN", "ADVISORY", "UNKNOWN")


def test_bootstrap_with_non_string_args_does_not_crash():
    result = _payload(_run(_call_tool(
        _BOOTSTRAP_TOOL_NAME,
        {"repo": 42, "lane": ["not-a-string"], "task_context": "not-a-dict"},
    )))
    assert isinstance(result, dict)
    assert set(result.keys()) == EXPECTED_BOOTSTRAP_KEYS


def test_review_with_missing_prompt_does_not_crash():
    result = _payload(_run(_call_tool(_REVIEW_TOOL_NAME, {"context": {}})))
    assert isinstance(result, dict)
    assert "guidance_version" in result


def test_review_with_completely_empty_args_does_not_crash():
    result = _payload(_run(_call_tool(_REVIEW_TOOL_NAME, {})))
    assert isinstance(result, dict)


def test_review_with_none_arguments_does_not_crash():
    """The MCP server passes arguments=None when no input is sent."""
    result = _payload(_run(_call_tool(_REVIEW_TOOL_NAME, None)))
    assert isinstance(result, dict)


def test_truthy_non_dict_arguments_do_not_crash():
    """Codex QC HIGH (lt-qc-32690c14): a truthy non-dict ``arguments``
    must NOT crash with AttributeError on ``.get(...)``. The wrapper
    coerces non-dict to {} so the underlying advisory functions still
    produce output."""
    for bad in ([1, 2, 3], "not-a-dict", 42, ("a", "b"), 1.5):
        result = _payload(_run(_call_tool(_BOOTSTRAP_TOOL_NAME, bad)))
        assert isinstance(result, dict)
        assert set(result.keys()) == EXPECTED_BOOTSTRAP_KEYS
        result2 = _payload(_run(_call_tool(_REVIEW_TOOL_NAME, bad)))
        assert isinstance(result2, dict)


# ---------------------------------------------------------------------
# 5. Unknown tool name — structured error, no crash
# ---------------------------------------------------------------------

def test_unknown_tool_name_returns_structured_error_no_raise():
    result = _payload(_run(_call_tool("nonexistent.tool", {})))
    assert result["error"] == "unknown_tool"
    assert result["tool_requested"] == "nonexistent.tool"
    assert _BOOTSTRAP_TOOL_NAME in result["tools_exposed"]
    assert _REVIEW_TOOL_NAME in result["tools_exposed"]


# ---------------------------------------------------------------------
# 6. The MCP layer does not import dashboard / telemetry
# ---------------------------------------------------------------------

def test_mcp_module_imports_only_governance_and_mcp_sdk():
    """Pin the import surface — no dashboard / queue / orchestrator.

    Checks that the module never:
      - imports any dashboard / telemetry / queue module
      - opens any file under japam-docs/system/* (telemetry roots)
      - opens any sqlite db
      - issues subprocess / shell calls
    """
    import ast
    import prompt_guidance.mcp_server as mod
    src = Path(mod.__file__).read_text()
    tree = ast.parse(src)

    forbidden_import_substrings = (
        "coo_dashboard", "canonical_health", "durable_queue",
        "async_tasks", "circuit_breaker", "cto_queue", "telemetry",
        "subprocess", "sqlite3", "socket", "requests", "urllib",
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for tok in forbidden_import_substrings:
                    assert tok not in alias.name, (
                        f"governance MCP layer must not import {alias.name!r}"
                    )
        elif isinstance(node, ast.ImportFrom):
            for tok in forbidden_import_substrings:
                assert tok not in (node.module or ""), (
                    f"governance MCP layer must not import from "
                    f"{node.module!r}"
                )

    # Also check for raw file path strings that would indicate
    # telemetry-source reads, ignoring strings that appear inside
    # docstrings explaining what the module does NOT do.
    forbidden_path_strings = (
        "/japam-docs/system/", "circuit-breaker-state.json",
        "canonical-health.json", "durable-queue.db",
    )
    # Strip module-level docstring before checking.
    body = tree.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        first_lineno_after_docstring = body[0].end_lineno or 0
    else:
        first_lineno_after_docstring = 0
    code_after_docstring = "\n".join(
        src.splitlines()[first_lineno_after_docstring:]
    )
    for path in forbidden_path_strings:
        assert path not in code_after_docstring, (
            f"governance MCP layer must not reference telemetry path "
            f"{path!r} outside its docstring."
        )
