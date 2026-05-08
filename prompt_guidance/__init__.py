"""prompt_guidance — advisory governance copilot for cross-agent drift.

Public surface:
    review(prompt, context) -> dict     advisory review function
    SCHEMA: dict                        the I/O JSON schema (parsed)
    GUIDANCE_VERSION: str               the guidance version string

The package is stateless, deterministic, non-blocking, and external to
AI_Operation runtime. See AGENTS.md and GUIDANCE.md.
"""
from .review import review, SCHEMA, GUIDANCE_VERSION

__all__ = ["review", "SCHEMA", "GUIDANCE_VERSION"]
__version__ = GUIDANCE_VERSION
