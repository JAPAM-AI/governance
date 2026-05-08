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
from prompt_guidance.bootstrap import bootstrap, KNOWN_LANES  # noqa: E402

REQUIRED_BOOTSTRAP_KEYS = {
    "guidance_version", "repo", "lane", "status",
    "applicable_governance_rules", "task_structure_expectations",
    "git_expectations", "orchestration_expectations",
    "mirror_update_expectations", "when_to_call_review",
    "when_to_escalate", "non_goals", "recommended_next_action",
}


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


# ── PR-comment upsert via REST ids (fix for duplicate-comment bug) ───

def test_existing_comment_id_returns_int_when_marker_present(monkeypatch):
    """REST returns numeric ids; helper must return that int verbatim."""
    fake_comments = [
        {"id": 4403433188, "body": review_pr.MARKER + "\n### Prompt Guidance Review\n..."},
        {"id": 4403433200, "body": "unrelated user comment"},
    ]
    monkeypatch.setattr(review_pr, "_list_pr_comments_rest",
                        lambda pr, repo: fake_comments)
    cid = review_pr._existing_comment_id("48", "JAPAM-AI/Ai_operations")
    assert cid == 4403433188


def test_existing_comment_id_returns_none_when_marker_absent(monkeypatch):
    fake_comments = [
        {"id": 1, "body": "first user comment"},
        {"id": 2, "body": "second user comment"},
    ]
    monkeypatch.setattr(review_pr, "_list_pr_comments_rest",
                        lambda pr, repo: fake_comments)
    cid = review_pr._existing_comment_id("48", "JAPAM-AI/Ai_operations")
    assert cid is None


def test_existing_comment_id_returns_none_when_id_missing(monkeypatch):
    fake_comments = [
        {"body": review_pr.MARKER + "\n### Prompt Guidance Review\n..."},
    ]
    monkeypatch.setattr(review_pr, "_list_pr_comments_rest",
                        lambda pr, repo: fake_comments)
    cid = review_pr._existing_comment_id("48", "JAPAM-AI/Ai_operations")
    assert cid is None


def test_existing_comment_id_returns_none_when_id_not_int(monkeypatch):
    """REST should return numeric ids; defensively handle non-int."""
    fake_comments = [
        {"id": "IC_kwDOLNQ_M88AAAABAA", "body": review_pr.MARKER + "\n..."},
    ]
    monkeypatch.setattr(review_pr, "_list_pr_comments_rest",
                        lambda pr, repo: fake_comments)
    cid = review_pr._existing_comment_id("48", "JAPAM-AI/Ai_operations")
    assert cid is None


def test_existing_comment_id_handles_non_list_response(monkeypatch):
    monkeypatch.setattr(review_pr, "_list_pr_comments_rest",
                        lambda pr, repo: [])
    assert review_pr._existing_comment_id("48", "JAPAM-AI/Ai_operations") is None


def test_upsert_comment_edits_existing_when_id_found(monkeypatch):
    """When _existing_comment_id returns an int, _upsert_comment must
    PATCH that exact REST id, not create a new comment."""
    monkeypatch.setattr(review_pr, "_existing_comment_id",
                        lambda pr, repo: 4403433188)

    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["input"] = kwargs.get("input")

        class _R:
            returncode = 0
        return _R()

    monkeypatch.setattr(review_pr.subprocess, "run", fake_run)
    review_pr._upsert_comment("48", "BODY", "JAPAM-AI/Ai_operations")
    args = captured["args"]
    # Must be a PATCH on the specific REST id, NOT `gh pr comment create`.
    assert "api" in args, f"expected REST PATCH, got args={args}"
    assert "PATCH" in args
    assert "repos/JAPAM-AI/Ai_operations/issues/comments/4403433188" in args
    assert "comment" not in args  # not the `gh pr comment` create path


def test_upsert_comment_creates_new_when_id_none(monkeypatch):
    """When no existing comment, _upsert_comment must call `gh pr comment`."""
    monkeypatch.setattr(review_pr, "_existing_comment_id",
                        lambda pr, repo: None)

    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["input"] = kwargs.get("input")

        class _R:
            returncode = 0
        return _R()

    monkeypatch.setattr(review_pr.subprocess, "run", fake_run)
    review_pr._upsert_comment("48", "BODY", "JAPAM-AI/Ai_operations")
    args = captured["args"]
    assert "pr" in args and "comment" in args
    assert "48" in args


# ── bootstrap (first-window governance) ──────────────────────────────

def test_bootstrap_returns_all_required_keys():
    out = bootstrap("JAPAM-AI/Ai_operations", "claude_code", {})
    assert set(out.keys()) == REQUIRED_BOOTSTRAP_KEYS


def test_bootstrap_returns_all_required_keys_for_unknown_repo():
    out = bootstrap("some-other/repo", "worker", {})
    assert set(out.keys()) == REQUIRED_BOOTSTRAP_KEYS


def test_bootstrap_is_deterministic():
    a = bootstrap("JAPAM-AI/Ai_operations", "claude_code", {"task_id": "cc-1"})
    b = bootstrap("JAPAM-AI/Ai_operations", "claude_code", {"task_id": "cc-1"})
    assert a == b
    # serialised form is also identical
    import json as _json
    assert _json.dumps(a, sort_keys=True) == _json.dumps(b, sort_keys=True)


def test_bootstrap_does_not_raise_on_garbage_input():
    # Each call must not raise; output dict must always have required keys
    for repo, lane, ctx in [
        (None, None, None),
        (123, [], "not-a-dict"),
        ("", "", {}),
        ({"weird": "shape"}, 999, []),
    ]:
        out = bootstrap(repo, lane, ctx)
        assert isinstance(out, dict)
        assert set(out.keys()) == REQUIRED_BOOTSTRAP_KEYS


def test_bootstrap_ai_operations_includes_specific_guidance():
    out = bootstrap("JAPAM-AI/Ai_operations", "claude_code", {})
    assert out["status"] == "READY"
    assert out["repo"] == "JAPAM-AI/Ai_operations"
    assert out["lane"] == "claude_code"
    # Must mention task_class and the contract enum
    joined = " ".join(out["task_structure_expectations"])
    assert "task_class" in joined
    assert "deep_batch" in joined or "chat" in joined  # mention drift class
    # Mirror guidance must mention the contract path or schema
    mirror = " ".join(out["mirror_update_expectations"])
    assert "task_class" in mirror or "task.schema.json" in mirror


def test_bootstrap_unknown_repo_returns_warn():
    out = bootstrap("acme/foo", "claude_code", {})
    assert out["status"] == "WARN"
    # Output is still useful (non-empty)
    assert len(out["applicable_governance_rules"]) > 0
    assert len(out["task_structure_expectations"]) > 0
    # Recommended action explicitly mentions verifying the repo
    assert "repo" in out["recommended_next_action"].lower() or "verify" in out["recommended_next_action"].lower()


def test_bootstrap_unknown_lane_returns_warn():
    out = bootstrap("JAPAM-AI/Ai_operations", "schedule_v2", {})
    assert out["status"] == "WARN"
    # The orchestration block must call out the unknown lane
    joined = " ".join(out["orchestration_expectations"])
    assert "schedule_v2" in joined or "not a known governed lane" in joined


def test_bootstrap_recommended_action_is_a_string():
    """Even WARN cases must return a non-empty string action."""
    for status_ctx in [
        ("JAPAM-AI/Ai_operations", "claude_code"),  # READY
        ("acme/foo", "claude_code"),                # WARN unknown repo
        ("JAPAM-AI/Ai_operations", "weird"),        # WARN unknown lane
        ("acme/foo", "weird"),                      # WARN both
        ("", ""),                                   # WARN both empty
    ]:
        out = bootstrap(*status_ctx, {})
        assert isinstance(out["recommended_next_action"], str)
        assert out["recommended_next_action"].strip()


def test_bootstrap_does_not_call_review_internally(monkeypatch):
    """bootstrap and review are independent surfaces."""
    import importlib
    review_mod = importlib.import_module("prompt_guidance.review")
    calls = {"count": 0}

    def _track(*args, **kwargs):
        calls["count"] += 1
        return {}

    monkeypatch.setattr(review_mod, "review", _track)
    bootstrap("JAPAM-AI/Ai_operations", "claude_code", {})
    assert calls["count"] == 0, f"bootstrap unexpectedly called review() {calls['count']} times"


def test_bootstrap_non_goals_match_documented_invariants():
    """non_goals must enumerate the canonical hard-noes."""
    out = bootstrap("JAPAM-AI/Ai_operations", "claude_code", {})
    joined = " ".join(out["non_goals"]).lower()
    for needle in ("blocking", "queue", "worker", "auto-pr", "auto-merge"):
        # accept either direct mention or a reasonable variant
        assert any(n in joined for n in (needle, needle.replace("-", " "))), (
            f"non_goals missing concept: {needle}"
        )


def test_bootstrap_known_lanes_all_yield_ready_for_known_repo():
    for lane in sorted(KNOWN_LANES):
        out = bootstrap("JAPAM-AI/Ai_operations", lane, {})
        assert out["status"] == "READY", f"lane={lane} did not yield READY"


# ── examples roundtrip ────────────────────────────────────────────────

def test_examples_match_review_output():
    """Examples are byte-identical to live function output. Handles
    BOTH review-shaped examples (input has 'prompt') and bootstrap-
    shaped examples (input has 'repo' + 'lane')."""
    examples_path = _ROOT / "examples" / "review_examples.json"
    if not examples_path.exists():
        return  # generated at build time
    data = json.loads(examples_path.read_text())
    for name, pair in data.items():
        inp = pair["input"]
        expected = pair["output"]
        if "prompt" in inp:
            actual = review(inp["prompt"], inp.get("context"))
        else:
            actual = bootstrap(inp.get("repo"), inp.get("lane"),
                               inp.get("task_context"))
        assert actual == expected, (
            f"example {name} drifted from live function output"
        )
