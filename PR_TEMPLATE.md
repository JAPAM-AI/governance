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
