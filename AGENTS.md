# AGENTS.md — operating manual for execution agents

This file is read by every execution agent (Claude Code, OpenAI agents, Claude AI, Codex QC, scheduled bots) before performing tasks, opening PRs, or making architecture-changing edits in any JAPAM-AI repository.

## Roles addressed

- **Claude Code** — engineering, scripts, builds, fixes
- **OpenAI agents** — analysis, drafting
- **Claude AI** — planning, routing, summarization
- **Codex QC** — static analysis review
- **Other agents / schedulers** — anything that writes to a queue or repo

## Before you act — two-step pattern

### Step 1: bootstrap (called ONCE per task / session)

```python
from prompt_guidance import bootstrap
ctx = bootstrap(
    repo="JAPAM-AI/Ai_operations",
    lane="claude_code",
    task_context={"task_id": "cc-abcdef01", "task_type": "..."},
)
# Internalise:
#   ctx["applicable_governance_rules"]      # the contract you must hold
#   ctx["task_structure_expectations"]      # what the task envelope should look like
#   ctx["git_expectations"]                 # branch + PR shape
#   ctx["orchestration_expectations"]       # lane + drift implications
#   ctx["mirror_update_expectations"]       # follow-up PR triggers
#   ctx["when_to_call_review"]              # the gate set
#   ctx["when_to_escalate"]                 # the operator-handoff gate
#   ctx["non_goals"]                        # what governance MUST NOT do
#   ctx["recommended_next_action"]          # the literal next step
```

`bootstrap` is the **first-window** entry point — call it at the start of every task / session, before any other governance call. Output is deterministic; same input → byte-identical output. WARN is not a failure; it surfaces a verification gap.

### Step 2: review (called BEFORE each risky action)

```python
from prompt_guidance import review
out = review(prompt, context)
```

Call before opening a PR, before architecture-changing edits, before secret-touching work, and before suggesting a new task_class. The `out` dict is advisory. Do **not** treat `WARN` as a failure.

### Why two functions, not one?

- `bootstrap` answers **"What rules apply before I start?"** — read once, then act.
- `review` answers **"Is this specific prompt / task / PR aligned?"** — call per-action.

The PR-comment bot is a **backstop**, not the primary governance entry point. Always prefer the bootstrap → review path during the work itself.

## Repository contract (normative)

1. **Advisory only.** `prompt_guidance.review` returns advice. No output blocks any pipeline.
2. **One-way import.** `JAPAM-AI/Ai_operations` does NOT import `governance`. `governance` MAY optionally import `architect_tools.prompt_validator` from `Ai_operations` for structural hints. Failure to import is silent.
3. **No mutation.** `governance` MUST NEVER push code, open PRs, modify any repository, dispatch worker tasks, write to DurableQueue, or interact with `coo-gateway` / `cto-worker` / `coo-orchestrator`.
4. **Drift detection, not enforcement.** When the tool detects a change crossing repository / contract surfaces, it sets `mirror_required=true` and returns advisory data. Acting on that data is operator/agent responsibility.
5. **Non-blocking failure.** If an optional dependency is unavailable, the tool degrades gracefully. `status` never becomes `BLOCK`.
6. **Stateless.** Every call is independent. No state persists between calls. The tool does not log to disk.
7. **Closed-set vocabularies.** `detected_intent`, `mirror_targets`, `recommended_repositories` use closed sets defined in `prompt_guidance/schema.json`. New values require an ADR + schema bump in `JAPAM-AI/governance`.
8. **Tolerance.** Normal malformed input does NOT raise. Output is `status=WARN`, `risk=UNKNOWN`, with explanatory `recommendations`.
9. **PR-bot subordination.** The reusable PR-comment workflow at `.github/workflows/guidance-review.yml` reuses `prompt_guidance.review` verbatim. The bot has no separate decision logic, is not a required status check, and never blocks merge.

## Agent rules

- **Read** `GUIDANCE.md` and this file before tasks/PRs/architecture changes.
- **Call** `prompt_guidance.review(prompt, context)` and read the output before tasks/PRs/architecture changes.
- **Treat `WARN` as guidance, not failure.** It surfaces a risk for you to address, not a refusal.
- **Open a follow-up mirror PR only when explicitly instructed** by the user/operator or when the task context calls for it. The tool itself does not open PRs.
- **Never bypass governance** by skipping the call when the change is large or risky — that is when the call is most valuable.
- **Never expand scope to make `WARN` go away** without operator approval.

## PR bot — opt-in

A reusable GitHub Actions workflow lives at `.github/workflows/guidance-review.yml`. Consuming repositories opt in by adding a 12-line caller workflow:

```yaml
# JAPAM-AI/<consumer>/.github/workflows/guidance.yml
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

Add this file to the consuming repo via a **separate PR** opened by that repo's maintainer. It is not added by `governance` and not auto-installed.

The bot:
- runs on every PR open / push,
- posts (and edits in place) **one** PR comment using the marker `<!-- prompt-guidance:v1 -->`,
- always exits 0 (does not fail the workflow on `WARN`),
- has only `pull-requests: write` and `contents: read` permissions,
- uses `GITHUB_TOKEN` only (no PATs, no secrets),
- depends on **stdlib + `gh` CLI** only (no third-party Python packages).
