"""Tool contract shared by the ReAct agent and the deterministic pipeline.

Each tool is a plain callable with a name, a description and a JSON-ish
argument schema.  That is enough for two consumers:

  * LangChain's ``AgentExecutor``, which binds them as StructuredTools and lets
    Gemini select them dynamically, and
  * the deterministic fallback orchestrator, which invokes the same callables
    in a fixed order when no LLM is configured.

Keeping one implementation behind both paths means the offline pipeline
exercises exactly the code the live agent runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolResult:
    """Uniform envelope so an Observation always carries provenance."""

    ok: bool
    data: Any
    summary: str
    source: str = "internal"
    degraded: bool = False
    error: str | None = None

    def as_observation(self) -> str:
        """Render the result as the Observation text fed back to the model."""
        if not self.ok:
            return f"ERROR: {self.error or 'tool failed'}"
        flag = " (degraded: offline/sample data)" if self.degraded else ""
        return f"{self.summary}{flag}"


@dataclass
class Tool:
    name: str
    description: str
    func: Callable[..., ToolResult]
    args_schema: dict[str, str] = field(default_factory=dict)

    def __call__(self, **kwargs: Any) -> ToolResult:
        try:
            return self.func(**kwargs)
        except Exception as exc:  # a failing tool must not abort the agent loop
            return ToolResult(
                ok=False,
                data=None,
                summary=f"{self.name} failed",
                error=f"{type(exc).__name__}: {exc}",
            )
