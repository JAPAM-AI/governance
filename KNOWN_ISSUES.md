# KNOWN_ISSUES.md — JAPAM-AI/governance

A short, deliberately-deferred-or-known list. Each entry is something an agent / operator can **bump into** and we want them to know is intentional or pending, not a bug to file.

This file is not a backlog. It is the list of *visible* gaps in the current rollout that agents may notice. New entries should be small and self-contained.

## Deferred by design

### `chat` task_class — drift case

`chat` appears as a circuit-breaker bucket label in `JAPAM-AI/Ai_operations` (`services/worker_dispatch/self_healing/sla_daemon.py:461,1039,1706,1723`) but has **no documented timeout / model / retry / lease semantics** anywhere. It is **not** in `Ai_operations/contracts/schemas/task.schema.json` and not in governance's `KNOWN_CONTRACT_CLASSES`. Governance treats `chat` as drift (`prompt_guidance.review` emits schema-drift `WARN`; bootstrap flags it under `Observed-but-not-yet-in-contract`).

**To accept `chat`**: open an ADR confirming intended semantics (interactive low-latency vs. multi-turn streaming vs. something else), then a small contracts PR mirroring the `deep_batch` pattern (PR #50 / governance PR #5).

### MCP-native sidecar

The original Phase 3 plan included a stdio MCP server in `governance/mcp/server.py` exposing `prompt_guidance.bootstrap` and `prompt_guidance.review` as MCP tools. Deferred until measured usage warrants it. Today, agents call the functions via Python import (pattern documented in `AGENTS.md` and `Ai_operations/docs/governance/AGENTS.md`).

**To enable**: see PR #4's body, "PR B inspection findings". Pattern A (stdio sidecar, ~250 LOC, introduces `mcp` Python dep) is the recommended starting point.

### External-worker routing — documentation only

Routing rules for `ext-lapt-*` and `ext-winp-*` workers live in `Ai_operations/docs/architecture/governed_lane.md` and the policy_engine's `_WRK_PREFIX_CLASSES` allowlist. Governance does not own this routing; the bootstrap output points agents at AI_Operation paths for worker dispatch.

**To formalize**: a contract schema for cross-machine routing could move some of this into `contracts/`. Out of scope for the current rollout.

## Partial / advisory

### `deep_batch` runtime semantics — partially advisory

After PR #50 (`Ai_operations`) and PR #5 (`governance`):

| Surface | `deep_batch` support |
|---|---|
| `Ai_operations/contracts/schemas/task.schema.json` enum | **YES** (6 values: simple, standard, deep, deep_batch, restricted, codex_qc_review) |
| `Ai_operations/services/cto_worker/scheduler.py` `MAX_SLOTS` | **YES** (slot=2; was already in place pre-PR-50) |
| `Ai_operations/services/cto_worker/scheduler.py` `TIMEOUTS` / `MODELS` / `RETRY_POLICY` | **NO** (uses fallbacks; runtime PR pending) |
| `Ai_operations/services/policy_engine/policy_check.py` `_WRK_PREFIX_CLASSES["lt-"]` | **YES** (already includes deep_batch) |
| `governance` `KNOWN_CONTRACT_CLASSES` | **YES** (PR #5) |

**To finalize runtime**: add `deep_batch` to `TIMEOUTS`, `MODELS`, `RETRY_POLICY` in `Ai_operations/services/cto_worker/scheduler.py` after operator confirms the multi-hour timeout / model / retry semantics. Until then, a `deep_batch` task uses the dict-`.get(...)` fallback (likely the `'standard'` entry from `RETRY_POLICY.get(self.task_class, RETRY_POLICY['standard'])` pattern at `scheduler.py:702`).

### `deep_live` — observed, not documented

`Ai_operations/services/cto_worker/scheduler.py:93` defines `MAX_SLOTS['deep_live'] = 2` with comment "deep_live=2 reserved for COO/urgent ops." `deep_live` is **not** in the contract enum, **not** in governance's `KNOWN_CONTRACT_CLASSES`, and **not** in `Ai_operations/docs/architecture/task_classes.md`.

**Status**: same drift shape as `chat` — runtime references, no contract or doc. Agents calling `prompt_guidance.review(task_class="deep_live")` will receive an "unrecognised task_class" recommendation (because `deep_live` is in neither `KNOWN_CONTRACT_CLASSES` nor `EXTENDED_BRIEF_CLASSES`).

**To accept `deep_live`**: same path as `chat` — ADR + small contracts PR + governance constant move.

## Operating-model reminders

### Startup `bootstrap` is the primary first-window mechanism

PR #4 added `prompt_guidance.bootstrap`. PR #49 (`Ai_operations`) added `docs/governance/AGENTS.md` pointing at it. Agents should call `bootstrap` at session start. The PR-comment workflow shipped in PR #1 is a **backstop** — by the time it fires, the work is done.

### PR comments are advisory and edit-in-place

The bot upserts a single PR comment per PR (REST issue-comment id, not GraphQL node id, after PR #3). It always exits 0; CI never fails because of bot output. Treat the comment as guidance, not as a merge gate.

### No runtime coupling

Verified at every cleanup pass (last: `cc-3870419b`):

- governance does not dispatch workers
- governance does not mutate queues / DurableQueue
- governance does not invoke `cto-worker` / `coo-orchestrator` / `coo-gateway`
- governance does not own orchestration
- governance is **advisory only**

If a future PR appears to introduce any of the above, treat as a regression and revert.

---

## Observation-phase questions (for agents to answer after tasks)

When an agent finishes substantive work governed by `prompt_guidance`, it should reflect on these questions and surface the answers in the task's wrap-up notes (or a TASK_STATUS.md if one exists). The aim is to feed real-world friction back into the next governance iteration without instrumenting anything.

1. **Where were you confused?** What guidance did you re-read? What did you have to infer because the docs were ambiguous or silent?
2. **What did you infer?** Where did you fill a gap with a best guess rather than an explicit rule? Cite the inferred decision so a future agent or operator can validate or correct it.
3. **What path was unclear?** Routing (lane, worker family, repo), schema choice (which task_class), guidance (review vs. bootstrap vs. PR backstop), escalation (when to stop) — which of these felt under-specified?
4. **What did you search for?** Identifier / file / phrase you grepped or asked about that wasn't in the obvious doc. (These are candidates for cross-link additions in `AGENTS.md` / `GUIDANCE.md` / `Ai_operations/docs/governance/AGENTS.md`.)
5. **What should future agents be told explicitly?** Which one or two sentences would have saved you time if they had been in the docs at the surface you read first?
6. **Did you know when to escalate?** Did `bootstrap`'s `when_to_escalate` and `review`'s `WARN` / `risk=HIGH` give you a clear stop-and-ask signal, or did you have to invent the threshold?

These questions are intentionally not enforced by any tooling. They are an honest channel from agent to operator. Wrap-up notes that include them feed the next round of governance evolution; wrap-up notes that don't aren't a defect.
