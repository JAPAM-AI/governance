# Task envelope template

Use this shape when registering a task that an agent will execute. Keys with `null` defaults are optional but improve guidance fidelity.

```json
{
  "lane": "claude_code",
  "task_type": "<short snake_case identifier>",
  "task_name": "<human-readable slug>",
  "priority": 3,
  "task_class": "standard",
  "timeout_s": 300,
  "side_effects": ["filesystem", "github"],
  "declared_impact": [],
  "payload": {
    "scope": "<one-paragraph description of what will be done>",
    "risk": "<low | medium | high — with one-line justification>",
    "production_impact": "<none | <description>>",
    "predecessor_task": null
  },
  "metadata": {
    "phase": "<phase tag>",
    "stops": ["<pause-gate description>"]
  }
}
```

## Fields the guidance tool looks at

The fields below are the ones `prompt_guidance.review` reads from `context`:

- `lane` (mapped to `source`)
- `task_class`
- `priority`
- `timeout_s`
- `side_effects`
- `declared_impact`
- `task_name`

The remaining fields (`payload`, `metadata`) are not consumed by the guidance tool; they belong to the caller's task-tracking system.

## Side-effect taxonomy

Use the shortest list that is still complete:

- `filesystem` — writes a file
- `database` — writes to any DB
- `network` — calls an external HTTP / TCP service
- `email` — sends an email
- `github` — opens / comments / pushes via GitHub API
- `sharepoint` — touches SharePoint
- `browser` — drives a browser
- `secrets` — reads or writes a credential
- `none` — pure compute / read-only
