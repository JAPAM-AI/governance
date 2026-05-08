"""prompt_guidance — advisory governance copilot for cross-agent drift.

Public surface:
    bootstrap(repo, lane, task_context) -> dict
        First-window governance context. Call BEFORE starting a task.
    review(prompt, context) -> dict
        Advisory review of a specific prompt / task / PR. Call BEFORE
        risky execution, PR creation, or architecture-changing work.
    SCHEMA: dict
        The parsed I/O JSON schema (covers both functions).
    GUIDANCE_VERSION: str
        Version string included in every output.

The package is stateless, deterministic, non-blocking, and external to
AI_Operation runtime. See AGENTS.md and GUIDANCE.md.
"""
from .bootstrap import bootstrap
from .review import review, SCHEMA, GUIDANCE_VERSION

__all__ = ["bootstrap", "review", "SCHEMA", "GUIDANCE_VERSION"]
__version__ = GUIDANCE_VERSION
