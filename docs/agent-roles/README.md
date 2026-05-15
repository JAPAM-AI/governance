# Agent role policies (governance repo mirror)

Focused role-boundary summaries for the two LLM-class agents the operator engages with on the JAPAM-AI ecosystem. **The binding source-of-truth for these role policies is `JAPAM-AI/Ai_operations/docs/governance/agent-roles/`.** This directory mirrors that content for convenient access during advisory bootstrap — `prompt_guidance.bootstrap` and operator-paste workflows that touch the governance repo first.

If the files here and the files in `JAPAM-AI/Ai_operations/docs/governance/agent-roles/` disagree, the `Ai_operations` versions win.

## Files

- [`CHATGPT_ADVISOR_ACCESS_POLICY.md`](CHATGPT_ADVISOR_ACCESS_POLICY.md) — ChatGPT / OpenAI advisory sessions. Advisory-first, read-only by default. Dispatch only with operator approval via `gateway_api_shim`.
- [`CLAUDE_AI_ORCHESTRATION_POLICY.md`](CLAUDE_AI_ORCHESTRATION_POLICY.md) — Claude AI / Claude Code. Execution-capable when authorized. Reads + writes per canonical governance and repo-local `CLAUDE.md`. Cannot silently override `Ai_operations` governance.

## Authority hierarchy (both roles)

When two sources disagree, the earlier-numbered source wins:

1. **Operator instructions** (current session — highest)
2. **`/home/ubuntu/Ai_operations` canonical governance**
3. **Repo-local `CLAUDE.md` / `AGENTS.md`** repo-specific rules
4. **Task-local instructions** (kickoff prompts, register payloads — lowest)

These role files sit at level 2.

## How this directory fits with `prompt_guidance.bootstrap`

`JAPAM-AI/governance/prompt_guidance/bootstrap.py` already returns a deterministic operating contract that includes the applicable governance rules. These role-policy files are the human-readable, paste-friendly version of the role boundary in that bootstrap output. New sessions can either:

- Call `prompt_guidance.bootstrap(...)` and consume the machine-readable contract, or
- Paste the relevant file from this directory into the session to set role context.

Both paths converge on the same authority model. The `prompt_guidance` package and the canonical `Ai_operations` governance docs remain the binding sources.

## Not in scope of these files

The role-policy files deliberately omit:

- Product specs and business strategy.
- Implementation details unrelated to authority / orchestration.
- Debugging notes and conversational history.
- Broad SDLC doctrine unrelated to operational role boundaries.
- PII / secrets rules (those live in the global + repo-local `CLAUDE.md` files and `SECURITY.md`).
- Repo-specific build / test / deploy procedure.

If you find yourself wanting to add such material here, put it in the appropriate canonical doc in `Ai_operations` and add a pointer.
