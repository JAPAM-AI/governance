# Claude Code — Project Rules for JAPAM-AI/governance

**Scope**: every operation in this repo. Inherits from `~/.claude/CLAUDE.md` (global) and from `JAPAM-AI/Ai_operations` governance (see § Governance below).

The rules below are non-negotiable. They were established after a 2026-05-12 PII exposure incident in `JAPAM-AI/taxops` — see that repo's `SECURITY.md` for incident history.

## Canonical Governance

`/home/ubuntu/Ai_operations` is the canonical source-of-truth for governance, execution discipline, branching, QC, escalation, operator approval, ADR interpretation, deployment discipline, repository policy, workflow rules, handoff procedure, task registration, lane routing, security policy, and PII handling.

If unsure how to proceed in any of those areas, stop and read the canonical Ai_operations documents before acting — do not improvise from memory.

Start with (absolute paths):

- `/home/ubuntu/Ai_operations/CLAUDE.md` — master orchestration rules
- `/home/ubuntu/Ai_operations/CONTRIBUTING.md` — branch + PR conventions
- `/home/ubuntu/Ai_operations/docs/governance/SOURCE_OF_TRUTH.md` — canonical path policy
- `/home/ubuntu/Ai_operations/docs/governance/PR_DISCIPLINE_UPGRADES.md` — Codex QC trace rules
- `/home/ubuntu/Ai_operations/docs/governance/EXECUTION_AUTHORITY_POLICY.md` — who may execute what
- `/home/ubuntu/Ai_operations/docs/adr/0029-ai-ops-path-ambiguity-elimination.md` — canonical-path ADR
- `/home/ubuntu/Ai_operations/docs/adr/0030-workspace-discipline-policy.md` — where agents may WRITE
- `/home/ubuntu/ops/EXECUTION_PROTOCOL.md` — operator-workspace execution discipline

This repo (`JAPAM-AI/governance`) is **advisory-only**; it does not host runtime orchestration. Its outputs (`prompt_guidance.bootstrap`, `prompt_guidance.review`, the MCP wrapper) reflect orchestration decisions made in `/home/ubuntu/Ai_operations/` — never modify policy unilaterally here.

### Authority hierarchy

When two sources disagree, the earlier-numbered source wins:

1. **Operator instructions** (this session — highest)
2. **`/home/ubuntu/Ai_operations` canonical governance**
3. **Repo-local CLAUDE.md** repo-specific rules (this file)
4. **Task-local instructions** (kickoff prompts, register payloads — lowest)

Repo-local CLAUDE.md files may define repo-specific behavior **only**. They do not silently override canonical Ai_operations governance unless explicitly authorized by operator instruction or canonical ADR.

---

## Hard rules — same as global

### 1. Never print sensitive values

Never print to terminal, logs, chat output, error messages, GitHub Actions logs, task-queue records, run histories, shared state files, or any displayed/persisted text:

- US SSNs
- Bank account numbers
- Routing numbers (ABA)
- Credit card numbers (PAN)
- Passwords, API keys, OAuth tokens, JWTs
- Tax IDs (EIN, ITIN, PTIN)
- Singapore FINs / UENs / NRIC
- Foreign tax IDs (PAN India, etc.)
- Private keys (SSH, GPG, TLS)

If a value must be referenced, mask all but the last 4 digits:

- ✅ `account ****4899`, `SSN ***-**-2531`, `EIN **-***6271`
- ❌ Any full value

### 2. Never commit sensitive values

Not in source code, configs, tests, fixtures, notebooks, markdown, comments, commit messages, PR descriptions, or any working directory. Use environment variables or a secrets manager. Reference by variable name only.

### 3. Don't echo identifiers from user-shared documents

When the user shares a sensitive document (tax PDF, bank statement, government ID, payroll file), extract structural data only (aggregate $-figures, doc-type, counts). Never echo raw identifiers back to chat or write them to intermediate files.

### 4. Toxic-by-default for sensitive doc types

Tax docs, bank statements, government IDs, payroll docs, insurance policies, mortgage docs — treat as toxic from the moment they enter context. Read once, use aggregate data, never persist plaintext content (or substantial excerpts with identifiers) anywhere in this repo or its history. Shred scratch copies at end of session.

### 5. Pre-commit / pre-push verification

Before any `git commit` or `git push`:

1. Run `git diff --cached` and visually verify no sensitive values.
2. The repo pre-commit hook (`gitleaks` via `.gitleaks.toml`) is the authoritative check.
3. Don't `--no-verify` to bypass.
4. PR descriptions and commit messages get the same masking treatment.

### 6. Tooling in this repo

- **`.gitleaks.toml`** at repo root — same custom rules + standard ruleset + allowlist as `JAPAM-AI/Ai_operations` (the orchestrator's canonical config).
- **`.git/hooks/pre-commit`** runs `gitleaks protect --staged` on every commit. Reinstall after fresh clone:

  ```bash
  cp .githooks-template/pre-commit-pii-scan.sh .git/hooks/pre-commit
  chmod +x .git/hooks/pre-commit
  ```

- **`.gitignore`** must block `.env`, `*.pem`, `*.key`, `*.kubeconfig`, `*credentials*`, `*secret*`, `*token-store*`.

If gitleaks is not installed locally:

```bash
curl -sSL -o /tmp/gl.tar.gz https://github.com/gitleaks/gitleaks/releases/download/v8.21.2/gitleaks_8.21.2_linux_x64.tar.gz
tar -xzf /tmp/gl.tar.gz -C /tmp gitleaks
mv /tmp/gitleaks ~/.local/bin/gitleaks
chmod +x ~/.local/bin/gitleaks
```

### 7. Incident response

If sensitive data is detected anywhere in this repo's history, in PR descriptions, or in any artifact this repo produced:

1. STOP all other work.
2. Notify operator (`@rrekhi-debug`) with a masked summary of exposure.
3. Plan history rewrite via `git filter-repo --replace-text` + `--replace-message`.
4. Get explicit operator authorization before destructive force-push.
5. Force-push cleaned history, scrub PR descriptions via `gh pr edit`, delete stale feature branches.
6. Verify clean via `gitleaks detect` on fresh clone.
7. Provide operator a masked inventory for credential rotation / fraud alerts / third-party notifications.

---

## Governance — source of truth lives in JAPAM-AI/Ai_operations

This repo is governed by the AI-driven SDLC defined in `JAPAM-AI/Ai_operations`. See:

| What | Where |
|---|---|
| Roles (operator / implementer / reviewer) | `docs/governance/OPERATING_MODEL.md` |
| Implementer rules (Claude Code, `cc-*` lane) | `docs/runbooks/governed_lane_claude_code.md` |
| Reviewer rules (Codex QC, `lt-qc-*` lane) | `docs/runbooks/governed_lane_codex.md` |
| Guardian rules (rejection + approval) | `docs/governance/CLAUDE_GUARDIAN_POLICY.md` |
| Five mandatory PR discipline upgrades | `docs/governance/PR_DISCIPLINE_UPGRADES.md` |
| Branch + PR conventions | `CONTRIBUTING.md` |
| PR template (risk + classification) | `.github/pull_request_template.md` |
| Hypothesis-not-fact verification | `docs/governance/HYPOTHESIS_NOT_FACT.md` |
| ADR procedure | `docs/governance/ADR_GUIDELINES.md` |
| Multi-session coordination | `docs/governance/PARALLEL_SESSION_PROTOCOL.md` |
| Branch-protection + Git mechanics | `docs/governance/sdlc/GIT_MECHANICS_STANDARD.md` |

### Quick reference

- **Branch prefixes:** `feature/`, `fix/`, `docs/`, `chore/`, `hotfix/`, `security/`, `ci/`, `policy/`, `migration/`.
- **Commit style:** Conventional Commits (`feat: …`, `fix: …`, `docs: …`); include `Co-Authored-By: <agent>` trailer.
- **PR body must include** a `lt-qc-*` Codex QC trace ID (CI-enforced by `.github/workflows/qc-trace-check.yml`).
- **Operator merges all PRs.** Never push directly to `main`.
- **No `task_id` = no work.** Register a `cc-*` governed task in DurableQueue via `JAPAM-AI/Ai_operations/packages/governed_lane/router.py` before any meaningful work in this repo.

---

## Repo-specific notes

This repo is **advisory-only**. It does not host runtime orchestration. Its outputs are:

- `prompt_guidance.bootstrap(...)` — the first-window contract delivered to every execution agent at task start. Output is deterministic; tests in `tests/test_bootstrap_contract.py` are the binding spec.
- `prompt_guidance.review(...)` — the non-blocking PR-comment backstop. Output is advisory; CI's `guidance-review.yml` posts findings to PRs but never blocks merge.
- The MCP wrapper at `deploy/prompt-guidance-mcp.service` — HTTP/SSE sidecar so agents can call bootstrap/review as MCP tools.

### What this repo does NOT do

- Submit tasks to DurableQueue (never imports `JAPAM-AI/Ai_operations` runtime modules)
- Execute work, dispatch workers, write to DQE trace
- Modify operating policy unilaterally — operator authors major changes to `AGENTS.md` / `GUIDANCE.md` in this repo, but they reflect orchestration decisions made in `JAPAM-AI/Ai_operations` (e.g. shim contracts per ADR 0031, role model per `OPERATING_MODEL.md`)

### Sister-repo dependency model

- Consumer repos (`Ai_operations`, `taxops`, `dqe-store`, `japam-trading`, `Analytical`, `investmentoutput`, etc.) call `prompt_guidance.bootstrap` at task start. They bind to its output via their own `AGENTS.md`.
- This repo never imports from consumers. The one optional touch-point is `architect_tools.prompt_validator` (in `Ai_operations`), invoked from `review.py` via `try/except ImportError` — failure is silent.

### Deployment workflow

`deploy/prompt-guidance-mcp.service` is staged via PR #8; activation is operator-driven (manual `systemctl enable --now`); CI does not deploy. See `deploy/MCP_WRAPPER_RUNBOOK.md` for the recipe.

### Cross-repo policy references

Major policy decisions that affect this repo's outputs live in `JAPAM-AI/Ai_operations`:

- **Canonical path policy** (which paths agents may search/read) — `Ai_operations/docs/governance/SOURCE_OF_TRUTH.md` § Canonical Path Policy. Bootstrap surfaces this in `applicable_governance_rules`.
- **Shim / gateway standardization** (request/result/event envelopes) — `Ai_operations/docs/adr/0031-shim-gateway-standardization.md` + `Ai_operations/docs/architecture/shim_contract.md`.
- **Managed-agent shim** — `Ai_operations/docs/adr/0032-managed-agent-shim.md`. Bootstrap may add a managed-agent advisory in `applicable_governance_rules` once live wiring proceeds; until then, no governance output change.
- **Execution-authority policy** (forbidden-submitter blocklist + operator-approval gate) — `Ai_operations/docs/governance/EXECUTION_AUTHORITY_POLICY.md`.
- **QUICK fast-path policy** — `Ai_operations/docs/governance/QUICK_FAST_PATH_POLICY.md`.
- **Agent role model** (Operator / Implementer / Reviewer + OpenAI advisory / Claude AI / managed agents / CTO workers / external workers) — `Ai_operations/docs/governance/OPERATING_MODEL.md` § The full agent role model.
- **External workers** (laptop-primary, win-primary; execution-location variants of the worker lane) — `Ai_operations/docs/runbooks/external_workers.md`.

Updates to those policies happen in `Ai_operations`; mirror them here only when they affect the bootstrap output contract.

### Agent role policies (mirror)

Focused role-boundary summaries for ChatGPT (advisory-first, read-only by default) and Claude AI / Claude Code (execution-capable when authorized) live at `docs/agent-roles/` in this repo. They mirror the canonical files at `JAPAM-AI/Ai_operations/docs/governance/agent-roles/`; on any conflict, the `Ai_operations` versions win. See `docs/agent-roles/README.md` for the index. These role files are convenience entry points for advisory bootstrap and operator-paste workflows — they do not redefine policy.
