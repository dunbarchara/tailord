"""Task definitions shared by every adapter, so models are compared on identical inputs."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EvalItem:
    id: str
    input: dict[str, Any]
    # Gold-ish labels keyed by label source ("silver:sonnet-5-5", "silver:opus-5-5",
    # "agreed"). Quality is always reported per source, never against a blend.
    labels: dict[str, Any]


@dataclass(frozen=True)
class ClassificationTask:
    """A closed-set classification task: one label per item, from `labels`."""

    name: str
    labels: dict[str, str]  # label -> description (the same text every adapter shows a model)
    instructions: str
    render_state: Callable[[dict[str, Any]], str]  # item input -> the text a model reads
