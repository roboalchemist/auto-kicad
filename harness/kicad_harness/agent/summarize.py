"""Few-word LLM summaries of what a revision changed.

The prompt is built from the real entity diff (added/removed/moved/nets) plus the commit
subject, and the answer is trimmed hard so version rows stay one glance long.
"""

from __future__ import annotations

import re
from typing import Any

INSTRUCTIONS = (
    "You write terse changelogs for PCB revisions. Reply with AT MOST six words, lowercase, "
    "no punctuation, no quotes, no prefix. Describe what physically changed (for example "
    "'moved D1 to left edge' or 'rerouted B.Cu traces'). Never invent changes."
)

MAX_WORDS = 8


def _refs(entities: list[dict[str, Any]], limit: int = 6) -> str:
    names: list[str] = []
    for entity in entities:
        label = entity.get("ref") or (f"net:{entity['net']}" if entity.get("net") else entity.get("kind"))
        if entity.get("pad") and entity.get("ref"):
            label = f"{entity['ref']}.{entity['pad']}"
        if label and label not in names:
            names.append(str(label))
    if len(names) > limit:
        return ", ".join(names[:limit]) + f", +{len(names) - limit} more"
    return ", ".join(names)


def describe(diff: dict[str, Any] | None) -> str:
    """A compact, deterministic description of the diff for the prompt."""
    if not diff:
        return "no geometric change"
    parts: list[str] = []
    for kind in ("added", "removed"):
        items = diff.get(kind) or []
        if items:
            parts.append(f"{len(items)} {kind} ({_refs(items)})")
    moved = diff.get("moved") or []
    if moved:
        parts.append(f"{len(moved)} moved ({_refs(moved)})")
    nets = diff.get("net_changed") or []
    if nets:
        parts.append(f"{len(nets)} net changes")
    outline = diff.get("outline")
    if outline:
        before = "x".join(str(v) for v in outline["from"])
        after = "x".join(str(v) for v in outline["to"])
        parts.append(f"board outline {before} mm to {after} mm")
    silk = diff.get("silkscreen") or []
    if silk:
        parts.append(f"{len(silk)} silkscreen labels moved ({_refs(silk)})")
    return "; ".join(parts) or "no geometric change"


def clean(text: str) -> str:
    """Collapse to at most MAX_WORDS lowercase words."""
    words = re.sub(r"[\"'`\n\r\t]+", " ", text or "").strip().split()
    words = [w.strip(".,;:!?()[]{}") for w in words]
    words = [w for w in words if w]
    return " ".join(words[:MAX_WORDS]).lower()


async def summarize_diff(model: str, subject: str, diff: dict[str, Any] | None) -> str:
    """Ask the model for a few-word description of ``diff``."""
    from pydantic_ai import Agent
    from pydantic_ai.settings import ModelSettings

    agent: Agent[None, str] = Agent(
        model,
        output_type=str,
        instructions=INSTRUCTIONS,
        # Reasoning models spend the budget thinking before they answer; the answer itself is
        # trimmed to MAX_WORDS, so allow room to think.
        model_settings=ModelSettings(max_tokens=512, temperature=0),
        defer_model_check=True,
    )
    prompt = (
        f"Commit subject: {subject}\n"
        f"Changed entities: {describe(diff)}\n"
        "Write the changelog note."
    )
    result = await agent.run(prompt)
    return clean(result.output)
