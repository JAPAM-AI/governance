"""prompt_guidance.bootstrap — first-window deterministic guidance.

Called by an agent BEFORE work begins on a task / session. Returns
the operating contract the agent should hold while doing the work.

Distinct from `prompt_guidance.review`:
    bootstrap   — "What rules apply before I start?"
    review      — "Is this specific prompt / task / PR aligned?"

Same hard guarantees as review:
    - stateless
    - deterministic (same input → byte-identical output)
    - no I/O outside an optional one-shot read of schema.json at import
    - never raises for normal malformed input (returns WARN)
    - no timestamps, no random IDs, no env-dependent fields except
      explicit input values (repo, lane).
"""
from __future__ import annotations

from typing import Any

from .review import (
    ALLOWED_SOURCES,
    EXTENDED_BRIEF_CLASSES,
    GUIDANCE_VERSION,
    KNOWN_CONTRACT_CLASSES,
    KNOWN_REPOSITORIES,
)

# ── closed-set vocabularies for bootstrap ─────────────────────────────
KNOWN_LANES = {"worker", "claude_code", "codex"}
ALLOWED_BOOTSTRAP_STATUS = {"READY", "WARN"}
_REQUIRED_OUTPUT_KEYS = (
    "guidance_version",
    "repo",
    "lane",
    "status",
    "applicable_governance_rules",
    "task_structure_expectations",
    "git_expectations",
    "orchestration_expectations",
    "mirror_update_expectations",
    "when_to_call_review",
    "when_to_escalate",
    "non_goals",
    "recommended_next_action",
)


# ── core rule blocks (deterministic; built from constants, not I/O) ──

def _general_governance_rules() -> list[str]:
    return [
        "Advisory only — outputs from prompt_guidance never block any pipeline.",
        "AI_Operation does NOT depend on JAPAM-AI/governance at runtime.",
        "Stateless — no DB, no file logging, no telemetry from this package.",
        "Deterministic — same input → byte-identical output.",
        "Closed-set vocabularies; new values require ADR + schema bump in JAPAM-AI/governance.",
        "Tolerance — malformed input must produce status=WARN, never raise.",
        "PR bot is a backstop, not the primary entry point. Call bootstrap + review BEFORE acting.",
    ]


def _general_git_expectations() -> list[str]:
    return [
        "Branch prefix: feature/, fix/, docs/, chore/, or hotfix/ per CONTRIBUTING.md.",
        "PR body sections expected when impact is non-trivial: Summary, Architecture impact, Validation evidence, Rollback notes, Mirror updates.",
        "Side-effects involving database/github/secrets require explicit rollback notes.",
    ]


def _general_non_goals() -> list[str]:
    return [
        "No blocking behavior.",
        "No queue admission hooks.",
        "No worker hooks.",
        "No dashboard, database, registry, or rules engine.",
        "No auto-PR creation, auto-push, auto-commit, or auto-merge.",
        "No mutation of runtime state.",
        "No governance-owned task lookup; agents should consult AI_Operation / DQE / OpenClaw for task state.",
    ]


def _ai_operation_task_structure() -> list[str]:
    return [
        "Declare task_class explicitly for scheduled / task / agent / pr work.",
        f"Known contract task_classes: {sorted(KNOWN_CONTRACT_CLASSES)}.",
        f"Observed-but-not-yet-in-contract: {sorted(EXTENDED_BRIEF_CLASSES)} — these DRIFT from the contract enum until ADR + schema lands.",
        "side_effects must list all material effects: filesystem, database, network, email, github, sharepoint, browser, secrets, none.",
        "declared_impact should pre-flag known governance areas: ai_operation, orchestration, workers, task_schema, mcp_tools, git_rules, governance_docs, other_repos.",
        "task_id: governed claude_code lane uses cc-* prefix (8-char hex); worker uses lt-*; codex uses lt-qc-*.",
    ]


def _generic_task_structure() -> list[str]:
    return [
        "Repo not in JAPAM-AI known set; verify the repo string before proceeding.",
        "Generic JAPAM-AI guidance: declare task_class, side_effects, and declared_impact in the task envelope.",
        "If the repo is in fact a JAPAM-AI repo not yet in the closed set, escalate to add it via ADR + schema bump in JAPAM-AI/governance.",
    ]


def _ai_operation_orchestration() -> list[str]:
    return [
        "Lane choice: 'worker' for CTO worker tasks; 'claude_code' for in-conversation execution; 'codex' for Codex QC review.",
        "Changes to orchestration / workers / task_schema / MCP tools / queues / routing / circuit-breakers / self-healing trigger mirror update guidance.",
        "Pause-gates after substantive change require operator review before merge.",
        "Long-running claude_code work hits the DurableQueue 10-minute lease cap; split into continuation cc-* tasks.",
    ]


def _generic_orchestration() -> list[str]:
    return [
        "Lane should be one of: worker, claude_code, codex (the governed three-lane router).",
        "Verify lane and orchestration expectations against the task context before dispatching work.",
    ]


def _ai_operation_mirror_updates() -> list[str]:
    return [
        "task_class drift (deep_batch / chat) → mirror PR in JAPAM-AI/Ai_operations contracts/schemas/task.schema.json.",
        "Schema-touching changes likely need a follow-up ADR + schema bump in Ai_operations contracts/.",
        "Worker / orchestration / governance-doc changes → mirror updates per area; consult prompt_guidance.review for the symbolic mirror_targets.",
        "Cross-repo work (other JAPAM-AI repos) → consult prompt_guidance.review's recommended_repositories field.",
    ]


def _generic_mirror_updates() -> list[str]:
    return [
        "Run prompt_guidance.review on the planned change to get symbolic mirror_targets and recommended_repositories.",
        "Mirror updates are advisory; the tool does not open follow-up PRs — an agent or operator does.",
    ]


def _ai_operation_when_to_call_review() -> list[str]:
    return [
        "Before opening any PR.",
        "Before any task whose side_effects exceed {none, filesystem}.",
        "Before architecture-changing edits (schema, contracts, services, packages, MCP tools).",
        "Before suggesting a new task_class or task_type.",
        "Before risky execution touching secrets / database / github.",
    ]


def _generic_when_to_call_review() -> list[str]:
    return [
        "Before opening any PR.",
        "Before any task whose side_effects exceed {none, filesystem}.",
        "Before architecture-changing edits.",
    ]


def _general_when_to_escalate() -> list[str]:
    return [
        "If review returns risk=HIGH and you do not have explicit operator approval.",
        "If review returns missing_fields you cannot fill from the task context.",
        "If task_class drift (deep_batch / chat) is required — open separate alignment PR; do not auto-fix.",
        "If you discover a new repo, contract surface, or vocabulary not in the closed set — escalate; do not invent.",
        "If the planned change crosses three or more repositories — escalate before opening any PR.",
    ]


# ── public ────────────────────────────────────────────────────────────

def bootstrap(repo: Any, lane: Any, task_context: Any = None) -> dict:
    """First-window governance context for an agent.

    Returns a 13-key deterministic dict. Same input -> byte-identical
    output. Never raises for normal malformed input.

    Args:
        repo: e.g. "JAPAM-AI/Ai_operations". Non-string -> "".
        lane: one of {"worker", "claude_code", "codex"}. Non-string -> "".
        task_context: optional dict (currently used only to decide
            recommended_next_action wording; never raises if non-dict).

    Returns:
        dict with the 13 keys defined by ALLOWED_BOOTSTRAP_STATUS docs.
    """
    repo_s = repo if isinstance(repo, str) else ""
    lane_s = lane if isinstance(lane, str) else ""
    ctx = task_context if isinstance(task_context, dict) else {}

    is_ai_operation = repo_s == "JAPAM-AI/Ai_operations"
    is_known_repo = repo_s in KNOWN_REPOSITORIES
    is_known_lane = lane_s in KNOWN_LANES

    # Status: READY only when we have BOTH a known repo and a known lane.
    status = "READY" if (is_known_repo and is_known_lane) else "WARN"

    # Per-area rule selection.
    if is_ai_operation:
        task_struct = _ai_operation_task_structure()
        orch = _ai_operation_orchestration()
        mirror = _ai_operation_mirror_updates()
        when_review = _ai_operation_when_to_call_review()
    elif is_known_repo:
        task_struct = _generic_task_structure()
        orch = _ai_operation_orchestration()  # known JAPAM-AI repo: same lanes
        mirror = _generic_mirror_updates()
        when_review = _generic_when_to_call_review()
    else:
        task_struct = _generic_task_structure()
        orch = _generic_orchestration()
        mirror = _generic_mirror_updates()
        when_review = _generic_when_to_call_review()

    # Lane-specific footnote (advisory; appears in orchestration_expectations).
    if not is_known_lane:
        orch = list(orch) + [
            f"Lane '{lane_s or '<missing>'}' is not a known governed lane "
            f"({sorted(KNOWN_LANES)}); verify the task context before dispatching."
        ]

    # Recommended next action — deterministic by status.
    if status == "READY":
        rec = (
            "Proceed with task. Call prompt_guidance.review(prompt, context) "
            "before risky execution, PR creation, or architecture-changing work. "
            "Treat WARN as guidance, not failure."
        )
    elif not is_known_repo and not is_known_lane:
        rec = (
            "Verify both the repo string and the lane against the closed sets "
            "in prompt_guidance.review (KNOWN_REPOSITORIES, KNOWN_LANES). Then "
            "re-run bootstrap and call prompt_guidance.review with concrete "
            "prompt + context."
        )
    elif not is_known_repo:
        rec = (
            f"Verify the repo string '{repo_s}'. The closed set is "
            f"{sorted(KNOWN_REPOSITORIES)}. If the repo is genuinely new, "
            f"escalate via ADR + schema bump in JAPAM-AI/governance before "
            f"proceeding with substantive work."
        )
    else:  # known repo, unknown lane
        rec = (
            f"Verify the lane string '{lane_s}'. The governed lanes are "
            f"{sorted(KNOWN_LANES)}. Re-run bootstrap with the corrected lane "
            f"and call prompt_guidance.review on the planned action."
        )

    return {
        "guidance_version": GUIDANCE_VERSION,
        "repo": repo_s,
        "lane": lane_s,
        "status": status,
        "applicable_governance_rules": _general_governance_rules(),
        "task_structure_expectations": task_struct,
        "git_expectations": _general_git_expectations(),
        "orchestration_expectations": orch,
        "mirror_update_expectations": mirror,
        "when_to_call_review": when_review,
        "when_to_escalate": _general_when_to_escalate(),
        "non_goals": _general_non_goals(),
        "recommended_next_action": rec,
    }
