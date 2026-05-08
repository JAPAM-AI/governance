"""prompt_guidance.review — advisory governance copilot.

Stateless, non-blocking, deterministic. All decision logic for the
Guidance Layer lives in this single module. See AGENTS.md, GUIDANCE.md,
and ../README.md for the contract surface.

Public:
    review(prompt: str, context: dict | None) -> dict
    SCHEMA: dict          (the parsed schema.json content)
    GUIDANCE_VERSION: str

Guarantees:
    - Same (prompt, context) -> byte-identical output dict.
    - Never raises for normal malformed input; produces WARN/UNKNOWN.
    - All output fields always present.
    - No I/O outside an optional one-shot read of schema.json at import.
    - Optional architect_tools.prompt_validator is consulted via
      try/except; failure is silent.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

GUIDANCE_VERSION = "1.0.0"

# ── closed-set vocabularies ───────────────────────────────────────────
ALLOWED_SOURCES = {"human", "agent", "scheduler", "pr", "task"}
ALLOWED_SIDE_EFFECTS = {
    "filesystem", "database", "network", "email", "github",
    "sharepoint", "browser", "secrets", "none",
}
ALLOWED_DECLARED_IMPACT = {
    "ai_operation", "orchestration", "workers", "task_schema",
    "mcp_tools", "git_rules", "governance_docs", "other_repos",
}
ALLOWED_INTENTS = {
    "task", "pr", "architecture_change", "bug_fix",
    "governance_change", "repo_change", "documentation_change", "unknown",
}
KNOWN_CONTRACT_CLASSES = {
    "simple", "standard", "deep", "restricted", "codex_qc_review",
}
EXTENDED_BRIEF_CLASSES = {"deep_batch", "chat"}
ALLOWED_TASK_CLASSES = KNOWN_CONTRACT_CLASSES | EXTENDED_BRIEF_CLASSES
ALLOWED_BRANCH_PREFIXES = ("feature/", "fix/", "docs/", "chore/", "hotfix/")
SYMBOLIC_MIRROR_TARGETS = {
    "architecture_docs", "task_schema_contract", "orchestration_rules",
    "mcp_contracts", "git_pr_template", "governance_docs", "runbook",
    "validation_evidence",
}
KNOWN_REPOSITORIES = {
    "JAPAM-AI/Ai_operations",
    "JAPAM-AI/governance",
    "JAPAM-AI/dqe-store",
    "JAPAM-AI/dqecoverage",
    "JAPAM-AI/japam-trading",
}
MIRROR_INTENTS = {"architecture_change", "governance_change", "repo_change"}
HIGH_RISK_SIDE_EFFECTS = {"database", "secrets", "github"}
HIGH_RISK_IMPACTS = {"ai_operation", "orchestration", "task_schema", "governance_docs"}
MEDIUM_RISK_SIDE_EFFECTS = {"network", "email", "browser"}

# ── schema (parsed once at import) ────────────────────────────────────
_SCHEMA_PATH = Path(__file__).with_name("schema.json")
try:
    SCHEMA: dict = json.loads(_SCHEMA_PATH.read_text())
except Exception:
    SCHEMA = {}

# ── optional structural-hint dependency (architect_tools) ─────────────
# Narrow exception: import-time failure is the only thing this guard is
# for. Runtime failures of the validator are swallowed inside
# _structural_hints, which keeps the tool non-blocking even if
# architect_tools is present but partially broken.
try:
    from architect_tools.prompt_validator import validate_prompt as _arch_validate
except ImportError:
    _arch_validate = None


# ── helpers (pure functions) ──────────────────────────────────────────

def _as_str_list(value: Any) -> list[str]:
    """Coerce a context field into a list[str], swallowing malformed
    input.

    The ``review()`` function must never raise on normal malformed
    input. ``list(value or [])`` violates that for non-iterable values
    like ``int``: ``list(5)`` raises ``TypeError``. This helper returns
    an empty list for any non-list value, and filters non-string
    elements from a list (so ``[1, 'foo', None]`` becomes ``['foo']``).
    """
    if isinstance(value, list):
        return [x for x in value if isinstance(x, str)]
    return []


def _classify_intent(prompt: str, source: str | None) -> str:
    if source == "pr":
        return "pr"
    p = prompt.lower()
    if (re.search(r"\badr-?\d+\b", p)
            or "schema" in p or "contract" in p
            or "task_type" in p or "worker capability" in p
            or "task class" in p or "execution lane" in p):
        return "architecture_change"
    if ("agents.md" in p or "guidance.md" in p
            or "pr_template" in p or "policy" in p
            or "governance" in p):
        return "governance_change"
    if ("new repo" in p or "rename repo" in p
            or "archive repo" in p or "delete repo" in p):
        return "repo_change"
    if ("fix bug" in p or "regression" in p or "broken" in p
            or "hotfix" in p or "stack trace" in p):
        return "bug_fix"
    if ("readme" in p or "docstring" in p or "documentation" in p):
        return "documentation_change"
    if source == "task":
        return "task"
    return "unknown"


_PATH_RULES = (
    (re.compile(r"contracts/(schemas|task-types|worker-capabilities)/"),
        ("task_schema", "workers")),
    (re.compile(r"services/(coo_orchestrator|coo_gateway|cto_worker|"
                r"durable_queue|worker_dispatch|policy_engine)/"),
        ("orchestration", "workers", "ai_operation")),
    (re.compile(r"packages/(governed_lane|architect_tools|codex_qc)/"),
        ("ai_operation", "orchestration")),
    (re.compile(r"\.github/|CONTRIBUTING\.md|BRANCHING\.md"),
        ("git_rules",)),
    (re.compile(r"AGENTS\.md|GUIDANCE\.md|GOVERNANCE\.md|"
                r"docs/(governance|adr)/"),
        ("governance_docs",)),
)


def _detect_impact(prompt: str, changed_paths: list[str],
                   declared: list[str]) -> list[str]:
    found: set[str] = set(declared)
    paths_blob = "\n".join(changed_paths)
    for regex, areas in _PATH_RULES:
        if regex.search(paths_blob):
            found.update(areas)
    p = prompt.lower()
    if "mcp" in p or "mcp.json" in p or "tool manifest" in p:
        found.add("mcp_tools")
    return sorted(found & ALLOWED_DECLARED_IMPACT)


def _classify_risk(impact_areas: list[str], side_effects: list[str],
                   malformed: bool) -> str:
    if malformed:
        return "UNKNOWN"
    se = set(side_effects)
    ia = set(impact_areas)
    if (se & HIGH_RISK_SIDE_EFFECTS) and (ia & HIGH_RISK_IMPACTS):
        return "HIGH"
    if ia or (se & MEDIUM_RISK_SIDE_EFFECTS):
        return "MEDIUM"
    return "LOW"


def _find_missing_fields(prompt: str, context: dict | None) -> list[str]:
    missing: list[str] = []
    if not prompt:
        missing.append("prompt")
    if context is None or not isinstance(context, dict):
        missing.append("context")
        return missing
    source = context.get("source")
    if source not in ALLOWED_SOURCES:
        missing.append("source")
    if context.get("side_effects") in (None, []):
        missing.append("side_effects")
    if not context.get("changed_paths") and source in {"agent", "scheduler", "pr", "task"}:
        missing.append("changed_paths")
    if context.get("task_class") is None and source in {"scheduler", "task"}:
        missing.append("task_class")
    if not context.get("branch") and source == "pr":
        missing.append("branch")
    if not context.get("repo") and source in {"pr", "task", "agent"}:
        missing.append("repo")
    return missing


def _generate_git_guidance(branch: str | None, side_effects: list[str],
                           impact_areas: list[str],
                           source: str | None) -> list[str]:
    """Git guidance lines.

    Validation-evidence and "set branch" advice are only emitted when
    the input is in a PR context (source == 'pr' or impact_areas
    non-empty). Otherwise low-risk human/doc inputs would never reach
    PASS — see GUIDANCE.md "Status semantics".
    """
    out: list[str] = []
    is_pr_context = (source == "pr") or bool(impact_areas)
    if branch is None or branch == "":
        if is_pr_context:
            out.append(
                "Set branch field; expected feature/, fix/, docs/, chore/, "
                "or hotfix/ prefix per CONTRIBUTING.md."
            )
    elif not any(branch.startswith(p) for p in ALLOWED_BRANCH_PREFIXES):
        out.append(
            f"Branch '{branch}' does not match standard prefix; expected "
            f"feature/<scope>, fix/<scope>, docs/<scope>, chore/<scope>, "
            f"or hotfix/<scope>."
        )
    if set(side_effects) & {"database", "github", "secrets"}:
        out.append(
            "Include rollback notes in PR body (revert command + restore steps)."
        )
    if impact_areas:
        out.append(
            "PR body should include 'Architecture impact' section listing impact_areas."
        )
    if is_pr_context:
        out.append(
            "PR body should include 'Validation evidence' section pointing to "
            "test runs / dry-run output."
        )
    return out


def _generate_orchestration_guidance(task_class, timeout_s, side_effects,
                                     priority, source) -> list[str]:
    out: list[str] = []
    if task_class is None and source in {"scheduler", "task"}:
        out.append("Declare task_class for orchestrator routing.")
    elif task_class in EXTENDED_BRIEF_CLASSES:
        out.append(
            f"task_class '{task_class}' is not in Ai_operations/contracts/"
            f"schemas/task.schema.json (current contract: "
            f"{sorted(KNOWN_CONTRACT_CLASSES)}). Open a separate "
            f"docs/contracts alignment PR before relying on it. "
            f"v1 of governance does not auto-fix this."
        )
    elif task_class is not None and task_class not in ALLOWED_TASK_CLASSES:
        out.append(
            f"task_class '{task_class}' is not recognised. Allowed: "
            f"{sorted(ALLOWED_TASK_CLASSES)}."
        )
    if isinstance(timeout_s, int):
        if task_class == "simple" and timeout_s > 120:
            out.append(
                "task_class 'simple' default timeout is 120s; override needs explicit reason."
            )
        elif task_class == "standard" and timeout_s > 300:
            out.append(
                "task_class 'standard' default timeout is 300s; override needs explicit reason."
            )
        elif task_class == "deep" and timeout_s > 900:
            out.append(
                "task_class 'deep' default timeout is 900s; override needs explicit reason."
            )
    if "secrets" in (side_effects or []) and task_class != "restricted":
        out.append(
            "side_effects include 'secrets'; task_class 'restricted' is "
            "conventional for secret-touching work."
        )
    if priority is not None and isinstance(priority, int) and not (1 <= priority <= 4):
        out.append("priority should be 1..4 per concurrency policy.")
    return out


def _suggest_mirror_targets(impact_areas: list[str]) -> list[str]:
    targets: set[str] = set()
    for area in impact_areas:
        if area == "task_schema":
            targets.update({"task_schema_contract", "validation_evidence"})
        elif area == "orchestration":
            targets.update({"orchestration_rules", "runbook"})
        elif area == "workers":
            targets.update({"task_schema_contract", "runbook"})
        elif area == "mcp_tools":
            targets.update({"mcp_contracts", "architecture_docs"})
        elif area == "ai_operation":
            targets.update({"architecture_docs", "runbook"})
        elif area == "git_rules":
            targets.add("git_pr_template")
        elif area == "governance_docs":
            targets.add("governance_docs")
        elif area == "other_repos":
            targets.add("architecture_docs")
    return sorted(targets & SYMBOLIC_MIRROR_TARGETS)


def _compute_mirror_required(impact_areas: list[str], intent: str,
                             task_class) -> bool:
    if impact_areas:
        return True
    if intent in MIRROR_INTENTS:
        return True
    if task_class in EXTENDED_BRIEF_CLASSES:
        return True
    return False


def _recommend_repositories(mirror_required: bool, impact_areas: list[str],
                            prompt: str, changed_paths: list[str],
                            ctx_repo, task_class) -> list[str]:
    if not mirror_required:
        return []
    repos: set[str] = set()
    # Rule 6: task_class drift (deep_batch / chat) MUST always recommend
    # an Ai_operations alignment PR, even when impact_areas is empty,
    # context.repo is missing, and declared_impact is empty.
    if task_class in EXTENDED_BRIEF_CLASSES:
        repos.add("JAPAM-AI/Ai_operations")
    ia = set(impact_areas)
    if ia & {"ai_operation", "orchestration", "task_schema",
             "workers", "mcp_tools"}:
        repos.add("JAPAM-AI/Ai_operations")
    if "governance_docs" in ia or "git_rules" in ia:
        repos.add("JAPAM-AI/governance")
    if "other_repos" in ia:
        repos.add("other (specify in PR body)")
    hay = (prompt or "").lower() + " " + " ".join(changed_paths or []).lower()
    if "dqe-store" in hay or "dqe_store" in hay:
        repos.add("JAPAM-AI/dqe-store")
    if "dqecoverage" in hay or "coverage engine" in hay:
        repos.add("JAPAM-AI/dqecoverage")
    if any(k in hay for k in ("japam-trading", "japam_trading", "ibkr", "tws ")):
        repos.add("JAPAM-AI/japam-trading")
    if isinstance(ctx_repo, str) and ctx_repo:
        repos.add(ctx_repo)
    return sorted(repos)


def _first_n_words(text: str, n: int = 6, cap: int = 60) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"[^\w\s'-]", " ", text)
    words = cleaned.split()[:n]
    out = " ".join(words).strip()
    return out[:cap]


def _suggest_pr_title(mirror_required: bool, intent: str,
                      impact_areas: list[str], task_class,
                      task_name, prompt: str) -> str:
    if not mirror_required:
        return ""
    scope_hint = (task_name or _first_n_words(prompt, 6) or "review item").strip()
    if task_class in EXTENDED_BRIEF_CLASSES:
        return f"contracts: align task_class enum to add '{task_class}'"
    if intent == "architecture_change":
        if "task_schema" in impact_areas:
            return f"contracts: extend task schema for {scope_hint}"
        if "mcp_tools" in impact_areas:
            return f"contracts: update MCP tool surface ({scope_hint})"
        if "orchestration" in impact_areas:
            return f"orchestration: {scope_hint}"
        return f"contracts: {scope_hint}"
    if intent == "governance_change":
        return f"governance: update {scope_hint}"
    if intent == "repo_change":
        return f"repo: {scope_hint}"
    if intent == "bug_fix":
        return f"fix: {scope_hint}"
    if intent == "documentation_change":
        return f"docs: {scope_hint}"
    primary = impact_areas[0] if impact_areas else "mirror update"
    return f"chore: mirror update for {primary}"


def _suggest_pr_scope(mirror_required: bool, mirror_targets: list[str],
                      recommended_repositories: list[str],
                      impact_areas: list[str], task_class, risk: str) -> str:
    if not mirror_required:
        return ""
    parts: list[str] = []
    if mirror_targets:
        parts.append("Mirror targets: " + ", ".join(mirror_targets) + ".")
    if recommended_repositories:
        parts.append("Affected repositories: " + ", ".join(recommended_repositories) + ".")
    if task_class in EXTENDED_BRIEF_CLASSES:
        parts.append(
            f"Includes ADR + schema bump in JAPAM-AI/Ai_operations to add "
            f"task_class '{task_class}' to contracts/schemas/task.schema.json "
            f"with timeouts, model, retry policy, lease TTL, and worker "
            f"family routing decided."
        )
    if "task_schema" in impact_areas:
        parts.append(
            "Update task.schema.json and any affected worker capability list; "
            "add ADR documenting the new contract surface."
        )
    if risk == "HIGH":
        parts.append("Include rollback notes (revert commands, restore steps).")
    parts.append("This tool does not open the PR; an agent or operator must.")
    return " ".join(parts)


def _structural_hints(prompt: str) -> list[str]:
    if _arch_validate is None or len(prompt) <= 200:
        return []
    try:
        result = _arch_validate(prompt)
        out: list[str] = []
        for check in result.checks:
            if not check.passed:
                msg = (check.failure_messages[0].message
                       if check.failure_messages else "structural check failed")
                out.append(
                    f"Structural check '{check.name}' (architect_tools): {msg}"
                )
        return out
    except Exception:
        return []


# ── public ────────────────────────────────────────────────────────────

def review(prompt: Any, context: Any = None) -> dict:
    """Advisory governance review. Never raises for normal malformed input."""
    # 1. tolerate malformed input
    if not isinstance(prompt, str):
        prompt = "" if prompt is None else str(prompt)
    ctx_malformed = context is not None and not isinstance(context, dict)
    ctx = context if isinstance(context, dict) else {}

    source        = ctx.get("source") if ctx.get("source") in ALLOWED_SOURCES else None
    branch        = ctx.get("branch")
    ctx_repo      = ctx.get("repo")
    changed_paths = _as_str_list(ctx.get("changed_paths"))
    task_name     = ctx.get("task_name")
    task_class    = ctx.get("task_class")
    timeout_s     = ctx.get("timeout_s")
    priority      = ctx.get("priority")
    side_effects  = _as_str_list(ctx.get("side_effects"))
    declared      = [d for d in _as_str_list(ctx.get("declared_impact"))
                     if d in ALLOWED_DECLARED_IMPACT]

    # 2. compute fields
    missing_fields = _find_missing_fields(prompt, context if not ctx_malformed else None)
    if ctx_malformed and "context" not in missing_fields:
        missing_fields.append("context")

    intent = _classify_intent(prompt, source) if prompt else "unknown"
    impact_areas = _detect_impact(prompt, changed_paths, declared)

    malformed = (not prompt) or ctx_malformed
    risk = _classify_risk(impact_areas, side_effects, malformed=malformed)

    mirror_targets = _suggest_mirror_targets(impact_areas)
    git_guidance = _generate_git_guidance(branch, side_effects, impact_areas, source)
    orch_guidance = _generate_orchestration_guidance(
        task_class, timeout_s, side_effects, priority, source)

    recommendations: list[str] = []
    recommendations.extend(_structural_hints(prompt))
    if task_class in EXTENDED_BRIEF_CLASSES:
        recommendations.append(
            f"task_class '{task_class}' is not in Ai_operations contract "
            f"enum ({sorted(KNOWN_CONTRACT_CLASSES)}). Open a separate "
            f"alignment PR; v1 governance does not auto-fix this."
        )

    contract_notes = [
        "AI_Operation does not depend on prompt_guidance.review at runtime.",
        "Output is advisory; callers decide whether to act on WARN / RECOMMEND.",
    ]
    if task_class in EXTENDED_BRIEF_CLASSES:
        contract_notes.append(
            f"Defer Ai_operations PR adding '{task_class}' to "
            f"contracts/schemas/task.schema.json."
        )
    if "task_schema" in impact_areas:
        contract_notes.append(
            "Schema-impact change: follow-up PR in JAPAM-AI/Ai_operations "
            "is likely needed; this tool does not open that PR."
        )

    mirror_required = _compute_mirror_required(impact_areas, intent, task_class)
    recommended_repositories = _recommend_repositories(
        mirror_required, impact_areas, prompt, changed_paths, ctx_repo,
        task_class)
    suggested_pr_title = _suggest_pr_title(
        mirror_required, intent, impact_areas, task_class, task_name, prompt)
    suggested_pr_scope = _suggest_pr_scope(
        mirror_required, mirror_targets, recommended_repositories,
        impact_areas, task_class, risk)

    # 3. status determination
    status = "PASS"
    if malformed:
        status = "WARN"
    elif "context" in missing_fields or any(
            f in missing_fields for f in ("source", "side_effects", "branch", "task_class")):
        status = "WARN"
    elif task_class in EXTENDED_BRIEF_CLASSES:
        status = "WARN"
    elif risk == "HIGH" and not re.search(r"\b(rollback|revert)\b", prompt, re.IGNORECASE):
        status = "WARN"
    elif (mirror_required and not recommended_repositories and impact_areas):
        status = "WARN"
    elif (recommendations or git_guidance or orch_guidance or mirror_targets):
        status = "RECOMMEND"

    return {
        "guidance_version": GUIDANCE_VERSION,
        "status": status,
        "risk": risk,
        "detected_intent": intent,
        "impact_areas": impact_areas,
        "missing_fields": sorted(set(missing_fields)),
        "recommendations": recommendations,
        "git_guidance": git_guidance,
        "orchestration_guidance": orch_guidance,
        "mirror_targets": mirror_targets,
        "ai_operation_contract_notes": contract_notes,
        "mirror_required": mirror_required,
        "recommended_repositories": recommended_repositories,
        "suggested_pr_title": suggested_pr_title,
        "suggested_pr_scope": suggested_pr_scope,
    }
