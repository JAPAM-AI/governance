# GUIDANCE.md — the rules `prompt_guidance` encodes

This is the human-readable form of the deterministic logic in `prompt_guidance/review.py` and `prompt_guidance/bootstrap.py`. If you read only this document and follow it, your output will be consistent with what the tools would have recommended.

## Two functions, one operating contract

- `prompt_guidance.bootstrap(repo, lane, task_context)` — returns first-window startup guidance: the rules, expectations, and non-goals that hold for every action in the session. Call **once at the start** of a task / session.
- `prompt_guidance.review(prompt, context)` — returns per-action guidance: status, risk, missing fields, mirror targets, suggested follow-up PR. Call **before each risky action** (PR creation, architecture-changing edit, secret-touching work, new task_class).

The PR-comment bot is a backstop. Bootstrap and review are the primary entry points.

## Inputs the tool considers

- `prompt` — the natural-language description of the work
- `context.source` — `human | agent | scheduler | pr | task`
- `context.repo` — e.g. `JAPAM-AI/Ai_operations`
- `context.branch` — branch name; expected to begin with `feature/`, `fix/`, `docs/`, `chore/`, or `hotfix/`
- `context.changed_paths` — file paths the work will touch
- `context.task_name` — short slug
- `context.task_class` — `simple | standard | deep | deep_batch | restricted | chat | codex_qc_review`
- `context.priority` — `1..4`
- `context.timeout_s` — seconds (sanity-checked against task_class default)
- `context.side_effects` — subset of `filesystem, database, network, email, github, sharepoint, browser, secrets, none`
- `context.declared_impact` — subset of `ai_operation, orchestration, workers, task_schema, mcp_tools, git_rules, governance_docs, other_repos`

## Status semantics

- **PASS** — no missing fields, no drift warnings, no recommendations
- **RECOMMEND** — advisory recommendations exist, no structural / drift warning
- **WARN** — missing important fields, or task-class drift, or risky side effects without a rollback note in the prompt, or malformed input, or impact declared without enough repository context

`BLOCK` is **not** a valid status. The tool never returns it.

## Risk semantics

- **UNKNOWN** — malformed or empty input
- **HIGH** — `side_effects ∩ {database, secrets, github}` AND `impact ∩ {ai_operation, orchestration, task_schema, governance_docs}`
- **MEDIUM** — any impact, OR `side_effects ∩ {network, email, browser}`
- **LOW** — otherwise

## Intent classification

Order of precedence:

1. `context.source == "pr"` → `pr`
2. prompt mentions ADR / schema / contract / task class / execution lane → `architecture_change`
3. prompt mentions AGENTS.md / GUIDANCE.md / PR_TEMPLATE / policy / governance → `governance_change`
4. prompt mentions new/rename/archive/delete repo → `repo_change`
5. prompt mentions fix bug / regression / broken / hotfix / stack trace → `bug_fix`
6. prompt mentions README / docstring / documentation → `documentation_change`
7. `context.source == "task"` → `task`
8. otherwise → `unknown`

## Mirror Strategy

`mirror_required = true` iff any of:

- `impact_areas` is non-empty
- `detected_intent ∈ {architecture_change, governance_change, repo_change}`
- `task_class ∈ EXTENDED_BRIEF_CLASSES` (drift vs Ai_operations contract; currently `{chat}`)

When `mirror_required = true`, the tool returns:

- `mirror_targets` — symbolic, drawn from a closed set of 8: `architecture_docs, task_schema_contract, orchestration_rules, mcp_contracts, git_pr_template, governance_docs, runbook, validation_evidence`
- `recommended_repositories` — drawn from the closed set: `JAPAM-AI/Ai_operations, JAPAM-AI/governance, JAPAM-AI/dqe-store, JAPAM-AI/dqecoverage, JAPAM-AI/japam-trading`, plus `context.repo` if set, plus `"other (specify in PR body)"` for impacts that match `other_repos`
- `suggested_pr_title` — conventional-commits-style title (`contracts: …`, `orchestration: …`, `governance: …`, `repo: …`, `fix: …`, `docs: …`, `chore: …`)
- `suggested_pr_scope` — short prose enumerating mirror targets, affected repos, what to change, and rollback / validation expectations if relevant

When `mirror_required = false`, `recommended_repositories = []`, and `suggested_pr_title` / `suggested_pr_scope` are empty strings (never `null`).

The tool never opens the suggested PR. An agent or operator does.

## Git guidance

- Branch name should begin with `feature/`, `fix/`, `docs/`, `chore/`, or `hotfix/`.
- `side_effects ∩ {database, github, secrets}` → include rollback notes in PR body.
- `impact_areas` non-empty → include "Architecture impact" section in PR body.
- Always → include "Validation evidence" section pointing to test runs or dry-run output.

## Orchestration guidance

Known AI_Operation contract task classes (from `Ai_operations/contracts/schemas/task.schema.json`):

- `simple` (default timeout 120s)
- `standard` (default timeout 300s)
- `deep` (default timeout 900s)
- `deep_batch` (long-running, multi-hour, governed-batch; checkpointed/resumable; see `Ai_operations/docs/architecture/task_classes.md`)
- `restricted`
- `codex_qc_review`

Extended observed / desired vocabulary that is **not yet** in the contract (drift cases — `review` emits schema-drift `WARN` and `bootstrap` flags them):

- `chat` — appears as a circuit-breaker bucket in `services/worker_dispatch/self_healing/sla_daemon.py` but has no documented timeout / model / retry / lease semantics. Add to the contract enum only after an ADR confirms intended semantics.

If `task_class ∈ EXTENDED_BRIEF_CLASSES` (currently `{chat}`):

- `status = WARN`,
- `mirror_required = true`,
- `recommended_repositories` includes `JAPAM-AI/Ai_operations`,
- `suggested_pr_title` recommends a docs/contracts alignment PR,
- the tool **does not** auto-fix anything.

`side_effects` containing `secrets` usually requires `task_class = "restricted"`. `priority` outside `1..4` triggers a recommendation.

## Repository contract (the same one in AGENTS.md)

- governance is advisory only
- AI_Operation does NOT depend on governance at runtime
- governance does NOT block execution
- governance detects drift and recommends mirror updates
- PR bot comments are advisory only
- consuming repos opt in with the reusable workflow
- no automatic changes are made by governance
