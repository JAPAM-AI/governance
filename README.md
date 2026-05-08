# JAPAM-AI/governance

A minimal, advisory **Guidance Layer** that reduces drift across execution agents (Claude Code, OpenAI agents, Claude AI, Codex QC) by giving them deterministic, shared guidance for task structure, Git/PR expectations, orchestration impact, and AI_Operation contract drift.

## What this is

- **Two callable functions** for execution agents:
  - `prompt_guidance.bootstrap(repo, lane, task_context) -> dict` — first-window startup contract; call **before** beginning a task / session.
  - `prompt_guidance.review(prompt, context) -> dict` — review of a specific planned action; call **before** risky execution, PR creation, or architecture-changing work.
- A reusable GitHub Actions workflow that posts an advisory Markdown comment on PRs in consuming repositories — used as a **backstop**, not the primary entry point.
- Markdown templates and an operating manual for agents.

The intended flow is:

```
Agent starts task
  → call bootstrap(repo, lane, task_context)
  → read returned guidance, internalize the contract
  → for each risky action: call review(prompt, context)
  → proceed, revise, or escalate
  → PR bot later acts as backstop
```

## What this is NOT

- ❌ Not a runtime dependency of `JAPAM-AI/Ai_operations`
- ❌ Not a merge gate. The PR comment is advisory.
- ❌ Not a service. No DB, dashboard, registry, or rules engine.
- ❌ Not auto-fix. The tool never opens PRs, pushes code, edits files, or modifies repositories.

## Quick start

### Call bootstrap at the start of a session

```python
from prompt_guidance import bootstrap

ctx = bootstrap(
    repo="JAPAM-AI/Ai_operations",
    lane="claude_code",
    task_context={"task_id": "cc-abcdef01", "task_type": "schema_change"},
)
print(ctx["status"])                      # "READY"
for line in ctx["task_structure_expectations"]:
    print(" -", line)
print("next:", ctx["recommended_next_action"])
```

### Call review before each risky action

```python
from prompt_guidance import review

out = review(
    prompt="Add task_class 'deep_batch' for the nightly index refresh job.",
    context={
        "source": "agent",
        "repo": "JAPAM-AI/Ai_operations",
        "branch": "feature/deep-batch-class",
        "changed_paths": ["services/coo_orchestrator/scheduler.py"],
        "task_name": "introduce-deep-batch",
        "task_class": "deep_batch",
        "priority": 3,
        "timeout_s": 1800,
        "side_effects": ["filesystem", "github"],
        "declared_impact": ["orchestration", "task_schema"]
    },
)
print(out["status"], out["risk"], out["mirror_required"])
print(out["suggested_pr_title"])
```

### Use the reusable PR-comment workflow

In each consuming repo (e.g. `JAPAM-AI/Ai_operations`), add this 12-line file:

```yaml
# JAPAM-AI/Ai_operations/.github/workflows/guidance.yml
name: Guidance review
on:
  pull_request:
    types: [opened, synchronize, reopened]
jobs:
  guidance:
    uses: JAPAM-AI/governance/.github/workflows/guidance-review.yml@main
    permissions:
      pull-requests: write
      contents: read
```

The reusable workflow runs on every PR open / push, calls `prompt_guidance.review`, and posts (or updates in place) a single PR comment. It exits 0 even when the review returns `WARN`. It is **not** a required status check and never blocks merge.

## Output contract (always present)

```json
{
  "guidance_version": "1.0.0",
  "status": "PASS|WARN|RECOMMEND",
  "risk": "LOW|MEDIUM|HIGH|UNKNOWN",
  "detected_intent": "task|pr|architecture_change|bug_fix|governance_change|repo_change|documentation_change|unknown",
  "impact_areas": [...],
  "missing_fields": [...],
  "recommendations": [...],
  "git_guidance": [...],
  "orchestration_guidance": [...],
  "mirror_targets": [...],
  "ai_operation_contract_notes": [...],
  "mirror_required": true,
  "recommended_repositories": [...],
  "suggested_pr_title": "...",
  "suggested_pr_scope": "..."
}
```

Same input → byte-identical output. `BLOCK` is not a valid status. Malformed input never raises.

## Files

| Path | Role |
|---|---|
| `prompt_guidance/bootstrap.py` | First-window startup-context function. Call BEFORE work begins. |
| `prompt_guidance/review.py` | Per-action review function. Call BEFORE each risky action. |
| `prompt_guidance/schema.json` | I/O JSON Schema (covers both functions). |
| `prompt_guidance/__init__.py` | Public re-exports (`bootstrap`, `review`, `SCHEMA`, `GUIDANCE_VERSION`). |
| `scripts/review_pr.py` | CI wrapper: PR metadata → `review()` → comment. |
| `.github/workflows/guidance-review.yml` | Reusable workflow consumed by other repos. |
| `AGENTS.md` | Per-agent operating manual. |
| `GUIDANCE.md` | Human-readable form of the rules `review.py` encodes. |
| `TASK_TEMPLATE.md` | Canonical task envelope. |
| `PR_TEMPLATE.md` | Canonical PR body sections. |
| `tests/test_review_contract.py` | Contract + determinism tests. |
| `examples/review_examples.json` | Worked input/output pairs. |

## Run the tests

```bash
python -m pytest tests/
```

Stdlib-only. No third-party packages required.

## Contract with AI_Operation and other repositories

- governance is **advisory only**
- AI_Operation does **NOT** depend on governance at runtime
- governance does **NOT** block execution
- governance **detects drift and recommends mirror updates**
- the PR bot comments are **advisory only**
- consuming repos **opt in** with the reusable workflow
- **no automatic changes** are made by governance to any repository

See `AGENTS.md` and `GUIDANCE.md` for the full normative contract.
