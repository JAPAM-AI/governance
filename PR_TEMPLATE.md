# PR body template

Copy this into your PR body and fill in each section. The PR-comment bot will call `prompt_guidance.review` and expect these sections to be present when the change is non-trivial.

## Summary

<one or two sentences>

## Architecture impact

- Affected impact areas: `<ai_operation | orchestration | workers | task_schema | mcp_tools | git_rules | governance_docs | other_repos | none>`
- Mirror updates needed: `<yes/no>` (if yes, list target repos)

## Validation evidence

- Test runs: `<command + outcome>`
- Dry-run output / fixtures: `<paths>`

## Rollback notes

- Required when side_effects include `database`, `github`, or `secrets`.
- One revert command + restore steps.
- `<command(s)>`

## Mirror updates

List of follow-up PRs to be opened **separately** in other repositories, if any. The governance tool may suggest these; the tool itself does not open them.

- `<repo>` — `<one-line scope>`

## Codex QC

Repos that ship `.github/workflows/qc-trace-check.yml` (currently `JAPAM-AI/dqe-store` and `JAPAM-AI/Ai_operations`; other JAPAM-AI repos may opt in) require the PR body to match `lt-qc-[a-z0-9-]{2,}`. Two formats are accepted:

**Format A — real Codex QC ran:**

```
Codex QC task: lt-qc-XXXXXXXX (verdict: <verdict>)
```

(or the equivalent inline form `**Codex QC:** lt-qc-XXXXXXXX (verdict: ...)`).

**Format B — documented emergency exemption (no Codex QC ran):**

```
Codex QC task: lt-qc-na (verdict: EMERGENCY_NO_QC — <reason>)

EMERGENCY_NO_QC
```

Format B requires **both** the `lt-qc-na` token AND the standalone `EMERGENCY_NO_QC` marker line. The marker alone fails the regex.

When to use Format B: docs-only PRs (ADRs, governance docs), pure cleanup PRs (deletions / archives), out-of-band reviewed PRs, or when the Codex QC dispatcher is offline (see Format B reason "cto-worker dispatcher offline"). When to use Format A: any code PR that adds, modifies, or replaces logic.

This section can be omitted in repos that do NOT ship `qc-trace-check.yml` — but include it whenever the consuming repo's `qc-trace-check.yml` is active. Reference: `JAPAM-AI/Ai_operations/docs/governance/PR_DISCIPLINE_UPGRADES.md` § Upgrade 5 (the canonical specification).
