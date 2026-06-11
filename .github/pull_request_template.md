<!--
This repository operates under AI-driven development.
See JAPAM-AI/Ai_operations/docs/governance/OPERATING_MODEL.md.
The checkboxes below are mandatory.
-->

## Summary

[1-3 sentences in plain English: what this PR does and why.]

## Architecture impact

The `prompt_guidance.review` PR-comment bot expects this section to be present and to enumerate the impact areas it touches.

- Affected impact areas: `<ai_operation | orchestration | workers | task_schema | mcp_tools | git_rules | governance_docs | other_repos | none>`
- Mirror updates needed: `<yes / no>` (if `yes`, list target repos in the **Mirror updates** section below)

## Operating model compliance

- [ ] This PR was authored by an AI agent (Claude Code or other governed implementer); no human wrote code in it
- [ ] If a human modified any file in this PR, that's a violation of `JAPAM-AI/Ai_operations/docs/governance/OPERATING_MODEL.md` and the PR must be closed

## Credential / secret hygiene

- [ ] **No secret values in this diff** (verified by `gitleaks protect --staged --config .gitleaks.toml` — "no leaks found")
- [ ] Class A runtime/API/env values: stay in `/home/ubuntu/.env.scripts` (or the repo's documented secret store)
- [ ] Class B browser/portal/human credentials: live in **Bitwarden Secrets Manager**
- [ ] Class C SSH keys: stay in `/home/ubuntu/.ssh/`

## Risk

- [ ] Low (docs-only, parallel install, no production behavior change)
- [ ] Medium (code changes, tests cover new behavior)
- [ ] High (production behavior change, cutover, irreversible)

## Validation evidence

The `prompt_guidance.review` bot expects this section to be present and to point at concrete test runs / dry-run output / fixture paths.

- Test runs: `<command + outcome — e.g. "pytest tests/...: 4 passed">`
- Dry-run output / fixtures: `<paths or "n/a — docs-only">`
- Live host evidence (if applicable): `<systemctl status / curl /health / /proc/<pid>/cmdline>`

## Trace IDs

- Claude Code task: `cc-________`
- Codex QC task: `lt-qc-________` (verdict: ___________)

CI (`.github/workflows/qc-trace-check.yml`) will fail if the `lt-qc-*` reference is missing. See `JAPAM-AI/Ai_operations/docs/governance/PR_DISCIPLINE_UPGRADES.md` § Upgrade 5.

## QC findings classification

Per `JAPAM-AI/Ai_operations/docs/governance/PR_DISCIPLINE_UPGRADES.md` § Upgrade 1 (mandatory medium-severity classification):

- **0** `real_defect_requires_fix` (REQUIRED — any real defect blocks this PR)
- **___** `non_blocking_design_property`
- **___** `acknowledged_in_adr`

## ADR

- [ ] ADR required: `docs/adr/<NNNN>-________________.md`
- [ ] No ADR required because: ___________________

## Discipline upgrades active for this PR

- [ ] **Upgrade 1** — Mandatory medium-severity QC classification
- [ ] **Upgrade 2** — Systemd unit diff verification (if any `infra/systemd/*` modified)
- [ ] **Upgrade 3** — First-class discipline-failure surfacing in DQE
- [ ] **Upgrade 4** — `docs/adr/INDEX.md` consultation for ADR numbers (if ADR included)
- [ ] **Upgrade 5** — Codex QC trace verification (this PR has a valid `lt-qc-*` reference above)

## Rollback notes

Required when `side_effects` include `database`, `github`, or `secrets`. For docs-only PRs: "revert this PR; no production state to undo."

## Mirror updates

List of follow-up PRs to be opened **separately** in other repositories, if any. The governance bot may suggest these; this template does not auto-open them.

- `<repo>` — `<one-line scope>`

## Decision audit

Per `JAPAM-AI/Ai_operations/docs/governance/CLAUDE_GUARDIAN_POLICY.md`:

- decision_id:
- timestamp_utc:
- agent: claude_code
- role: implementer (operator-supervised)
- change_ref: <branch name>
- risk_level:
- decision:
- evidence:
- policy_checks:
- adr_refs:
- rollback_plan:
- human_required: yes / no
- human_approval_ref:

## DQE trace

- Governing task: `cc-________` — full trace at `${DQE_TRACE_DIR}/cc-________.jsonl` (see `JAPAM-AI/Ai_operations` `docs/architecture/governed_lane.md` § "DQE Trace"; current runtime location is a LEGACY_RUNTIME_EXCEPTION tracked in `docs/governance/SOURCE_OF_TRUTH.md` § Migration status)
- Codex QC task: `lt-qc-________` — full trace + verdict artefacts under `cto-queue/qc/<original_task_id>/<qc_task_id>/codex/`




## Codex QC loop

Per `JAPAM-AI/Ai_operations/docs/governance/PR_DISCIPLINE_UPGRADES.md` §
Upgrade 6 (mandatory Codex QC loop — policy is canonical in `Ai_operations`).

CI here is a lightweight text backstop, not a verdict validator. It requires
the cycle-count field to hold a number, and then either the converged closure
(answered yes, zero open real defects, and a cycle count of 1–4) or the
operator-gated closure (a deliberate human-decision bypass — the operator, who
merges every PR, owns the rest). The cycle IDs and the convergence statement
are for the operator's review and are not CI-enforced; fill them in anyway.

- Codex QC cycles run: ___ &nbsp; (target 2, max 4 without operator; then operator-gate)
- Codex QC cycle IDs:
  - Cycle 1: `lt-qc-________`
  - Cycle 2: `lt-qc-________`
  - Cycle 3 (if used): `lt-qc-________`
  - Cycle 4 (if used): `lt-qc-________`
- Open real Codex defects: ___ &nbsp; (must be `0` to merge, unless this PR is operator-gated)
- Convergence reached: ___ &nbsp; (answer `yes`, `no`, or `operator-gated`)
- Convergence statement: ________
  &nbsp; (one sentence: why the loop is done, or why this PR is operator-gated)
