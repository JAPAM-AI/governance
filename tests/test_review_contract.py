"""Contract + determinism tests for prompt_guidance.review and review_pr renderer.

Stdlib-only. No network. No gh CLI. No third-party packages required by
the test logic itself; pytest is used as the runner.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Make the repo root importable so `from prompt_guidance.review ...` works
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from prompt_guidance.review import (  # noqa: E402
    review,
    GUIDANCE_VERSION,
    KNOWN_REPOSITORIES,
)
import scripts.review_pr as review_pr  # noqa: E402


REQUIRED_OUTPUT_KEYS = {
    "guidance_version", "status", "risk", "detected_intent",
    "impact_areas", "missing_fields", "recommendations",
    "git_guidance", "orchestration_guidance", "mirror_targets",
    "ai_operation_contract_notes", "mirror_required",
    "recommended_repositories", "suggested_pr_title",
    "suggested_pr_scope",
}

ALLOWED_PR_TITLE_PREFIXES = (
    "contracts:", "orchestration:", "governance:",
    "repo:", "fix:", "docs:", "chore:",
)


# ── output completeness ───────────────────────────────────────────────

def test_review_returns_all_required_keys_minimal():
    out = review("hello", {"source": "human", "side_effects": ["none"]})
    assert set(out.keys()) == REQUIRED_OUTPUT_KEYS


def test_review_returns_all_required_keys_empty():
    out = review("", None)
    assert set(out.keys()) == REQUIRED_OUTPUT_KEYS


def test_review_returns_all_required_keys_garbage():
    out = review(123, "not a dict")
    assert set(out.keys()) == REQUIRED_OUTPUT_KEYS


def test_guidance_version_present_and_string():
    out = review("hi", None)
    assert out["guidance_version"] == GUIDANCE_VERSION
    assert isinstance(out["guidance_version"], str)


# ── tolerance: never raise on malformed input ─────────────────────────

def test_no_throw_on_garbage_input():
    review(None, None)
    review(123, "not a dict")
    review([], 42)
    review({"prompt": "stuffed"}, ["nope"])


def test_status_warn_on_malformed_or_empty():
    out = review("", None)
    assert out["status"] == "WARN"
    assert out["risk"] == "UNKNOWN"

    out2 = review("anything", "not-a-dict")
    assert out2["status"] == "WARN"
    assert out2["risk"] == "UNKNOWN"


# ── determinism ───────────────────────────────────────────────────────

def test_same_input_byte_identical_output():
    inp_prompt = "Add task_class 'deep_batch' for the nightly job."
    inp_ctx = {
        "source": "agent",
        "repo": "JAPAM-AI/Ai_operations",
        "branch": "feature/deep-batch-class",
        "changed_paths": ["services/coo_orchestrator/scheduler.py"],
        "task_name": "introduce-deep-batch",
        "task_class": "deep_batch",
        "priority": 3,
        "timeout_s": 1800,
        "side_effects": ["filesystem", "github"],
        "declared_impact": ["orchestration", "task_schema"],
    }
    a = json.dumps(review(inp_prompt, inp_ctx), sort_keys=True)
    b = json.dumps(review(inp_prompt, inp_ctx), sort_keys=True)
    assert a == b


# ── deep_batch drift contract ─────────────────────────────────────────

def test_deep_batch_triggers_warn_and_mirror_required():
    out = review(
        "Add task_class 'deep_batch' for the nightly index refresh job.",
        {
            "source": "agent",
            "repo": "JAPAM-AI/Ai_operations",
            "branch": "feature/deep-batch-class",
            "changed_paths": ["services/coo_orchestrator/scheduler.py"],
            "task_class": "deep_batch",
            "side_effects": ["filesystem", "github"],
            "declared_impact": ["orchestration", "task_schema"],
        },
    )
    assert out["status"] == "WARN"
    assert out["mirror_required"] is True
    assert "JAPAM-AI/Ai_operations" in out["recommended_repositories"]
    assert any("deep_batch" in r for r in out["recommendations"])
    assert out["suggested_pr_title"].startswith(ALLOWED_PR_TITLE_PREFIXES)


def test_chat_class_triggers_warn_and_mirror_required():
    out = review(
        "Introduce task_class 'chat' for conversational tasks.",
        {
            "source": "agent",
            "repo": "JAPAM-AI/Ai_operations",
            "branch": "feature/chat-class",
            "task_class": "chat",
            "side_effects": ["network"],
            "declared_impact": [],
        },
    )
    assert out["status"] == "WARN"
    assert out["mirror_required"] is True
    assert "JAPAM-AI/Ai_operations" in out["recommended_repositories"]


# ── PASS case ─────────────────────────────────────────────────────────

def test_pass_low_risk_human_input():
    out = review(
        "trivial reply, nothing changes",
        {
            "source": "human",
            "side_effects": ["none"],
            "declared_impact": [],
        },
    )
    assert out["status"] == "PASS"
    assert out["risk"] == "LOW"
    assert out["mirror_required"] is False
    assert out["recommended_repositories"] == []
    assert out["suggested_pr_title"] == ""
    assert out["suggested_pr_scope"] == ""


# ── mirror_required semantics ─────────────────────────────────────────

def test_mirror_required_false_when_no_impact_no_drift():
    out = review(
        "say hi",
        {"source": "human", "side_effects": ["none"], "declared_impact": []},
    )
    assert out["mirror_required"] is False
    assert out["recommended_repositories"] == []
    assert out["suggested_pr_title"] == ""
    assert out["suggested_pr_scope"] == ""


def test_recommended_repositories_closed_set():
    allowed = KNOWN_REPOSITORIES | {"other (specify in PR body)"}
    cases = [
        ("Edit Ai_operations/services/coo_orchestrator/scheduler.py",
            {"source": "agent", "repo": "JAPAM-AI/Ai_operations",
             "changed_paths": ["services/coo_orchestrator/scheduler.py"],
             "side_effects": ["filesystem"], "declared_impact": []}),
        ("Touch dqe-store coverage logic",
            {"source": "agent", "repo": "JAPAM-AI/dqe-store",
             "changed_paths": ["docs/governance/KNOWN_ISSUES.md"],
             "side_effects": ["filesystem"], "declared_impact": ["governance_docs"]}),
    ]
    for prompt, ctx in cases:
        out = review(prompt, ctx)
        for r in out["recommended_repositories"]:
            assert r in allowed or r == ctx.get("repo"), (
                f"unexpected repo {r!r}; allowed={sorted(allowed)} ctx_repo={ctx.get('repo')!r}"
            )


# ── PR comment renderer ───────────────────────────────────────────────

def test_render_comment_includes_marker():
    out = review("hello", {"source": "human", "side_effects": ["none"]})
    body = review_pr.render_comment(out, "abc1234")
    assert body.startswith(review_pr.MARKER)
    assert "Prompt Guidance Review" in body
    assert "advisory only" in body.lower()


def test_render_comment_deterministic():
    out = review(
        "Add task_class deep_batch.",
        {"source": "agent", "repo": "JAPAM-AI/Ai_operations",
         "branch": "feature/x", "task_class": "deep_batch",
         "side_effects": ["github"], "declared_impact": ["task_schema"]},
    )
    a = review_pr.render_comment(out, "abc1234")
    b = review_pr.render_comment(out, "abc1234")
    assert a == b


def test_render_comment_includes_status_and_mirror_fields():
    out = review(
        "Add task_class deep_batch.",
        {"source": "agent", "repo": "JAPAM-AI/Ai_operations",
         "branch": "feature/x", "task_class": "deep_batch",
         "side_effects": ["github"], "declared_impact": ["task_schema"]},
    )
    body = review_pr.render_comment(out, "abc1234")
    assert "Status" in body
    assert "Risk" in body
    assert "Mirror required" in body
    assert "Detected intent" in body
    assert "Recommended mirror targets" in body
    assert "Recommended repositories" in body
    assert "Suggested follow-up PR" in body
    assert "Scope" in body
    assert "Git guidance" in body
    assert "Orchestration guidance" in body
    assert "Missing fields" in body
    assert "advisory only" in body.lower()
    assert "does not block merge" in body.lower()


# ── malformed-input coercion (QC HIGH #1 fix) ─────────────────────────

def test_non_iterable_changed_paths_does_not_raise():
    out = review(
        "x",
        {"source": "agent", "repo": "JAPAM-AI/governance",
         "changed_paths": 5, "side_effects": ["filesystem"]},
    )
    assert isinstance(out, dict)
    assert set(out.keys()) == REQUIRED_OUTPUT_KEYS


def test_non_iterable_side_effects_does_not_raise():
    out = review(
        "x",
        {"source": "agent", "repo": "JAPAM-AI/governance",
         "changed_paths": [], "side_effects": 7},
    )
    assert isinstance(out, dict)
    assert set(out.keys()) == REQUIRED_OUTPUT_KEYS


def test_non_iterable_declared_impact_does_not_raise():
    out = review(
        "x",
        {"source": "agent", "repo": "JAPAM-AI/governance",
         "side_effects": ["none"], "declared_impact": 42},
    )
    assert isinstance(out, dict)
    assert set(out.keys()) == REQUIRED_OUTPUT_KEYS


def test_dict_for_list_field_does_not_raise():
    """Even more pathological: pass a dict where a list is expected."""
    out = review(
        "x",
        {"source": "agent", "side_effects": {"foo": "bar"},
         "changed_paths": {"a": 1}, "declared_impact": "not a list"},
    )
    assert isinstance(out, dict)
    assert set(out.keys()) == REQUIRED_OUTPUT_KEYS
    # Coerced fields should treat as empty
    assert out["impact_areas"] == []


# ── naked drift contract (QC HIGH #2 fix) ────────────────────────────

def test_deep_batch_naked_drift_recommends_ai_operations():
    """task_class=deep_batch with NO impact, NO repo, NO declared_impact
    must still recommend JAPAM-AI/Ai_operations per rule 6."""
    out = review(
        "do nightly job",
        {
            "source": "agent",
            "repo": None,
            "branch": None,
            "changed_paths": [],
            "task_class": "deep_batch",
            "side_effects": ["none"],
            "declared_impact": [],
        },
    )
    assert out["mirror_required"] is True
    assert "JAPAM-AI/Ai_operations" in out["recommended_repositories"]
    assert out["status"] == "WARN"
    assert out["suggested_pr_title"].startswith("contracts:")


def test_chat_naked_drift_recommends_ai_operations():
    out = review(
        "introduce chat-style class",
        {
            "source": "agent",
            "repo": None,
            "branch": None,
            "changed_paths": [],
            "task_class": "chat",
            "side_effects": ["none"],
            "declared_impact": [],
        },
    )
    assert out["mirror_required"] is True
    assert "JAPAM-AI/Ai_operations" in out["recommended_repositories"]
    assert out["status"] == "WARN"


# ── review_pr.main always exits 0 (QC MEDIUM #3 fix) ──────────────────

def test_review_pr_main_returns_0_when_pr_metadata_raises(monkeypatch):
    """Even when the gh CLI / subprocess layer raises, main() must
    return 0 so the calling workflow does not fail."""
    def _boom(*args, **kwargs):
        raise RuntimeError("simulated gh CLI failure")
    monkeypatch.setattr(review_pr, "_pr_metadata", _boom)
    monkeypatch.setenv("GITHUB_REPOSITORY", "JAPAM-AI/governance")
    monkeypatch.setenv("GITHUB_PR_NUMBER", "1")
    monkeypatch.setenv("GITHUB_SHA", "deadbee" + "f" * 33)
    rc = review_pr.main()
    assert rc == 0


def test_review_pr_main_returns_0_when_upsert_raises(monkeypatch):
    """Same guarantee for the comment-posting path."""
    monkeypatch.setattr(review_pr, "_pr_metadata", lambda pr: {
        "title": "x", "body": "y", "headRefName": "feature/x",
        "number": 1, "files": [], "baseRefName": "main", "comments": [],
    })
    def _boom(*args, **kwargs):
        raise RuntimeError("simulated comment upsert failure")
    monkeypatch.setattr(review_pr, "_upsert_comment", _boom)
    monkeypatch.setenv("GITHUB_REPOSITORY", "JAPAM-AI/governance")
    monkeypatch.setenv("GITHUB_PR_NUMBER", "1")
    monkeypatch.setenv("GITHUB_SHA", "deadbee" + "f" * 33)
    rc = review_pr.main()
    assert rc == 0


def test_review_pr_main_returns_0_when_env_missing(monkeypatch):
    """Missing env vars should not raise; wrapper exits 0."""
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("GITHUB_PR_NUMBER", raising=False)
    rc = review_pr.main()
    assert rc == 0


# ── examples roundtrip ────────────────────────────────────────────────

def test_examples_match_review_output():
    examples_path = _ROOT / "examples" / "review_examples.json"
    if not examples_path.exists():
        return  # examples are generated at build time; skip if absent
    data = json.loads(examples_path.read_text())
    for name, pair in data.items():
        actual = review(pair["input"]["prompt"], pair["input"].get("context"))
        expected = pair["output"]
        assert actual == expected, (
            f"example {name} drifted from review() output"
        )
