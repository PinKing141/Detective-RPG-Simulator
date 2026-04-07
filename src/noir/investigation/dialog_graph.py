"""Minimal dialog graph helpers for interview flow."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from functools import lru_cache
from typing import Iterable


@dataclass(frozen=True)
class DialogChoice:
    text: str
    leads_to_id: str
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DialogNode:
    node_id: str
    text: str
    choices: tuple[DialogChoice, ...] = field(default_factory=tuple)


class DialogGraph:
    def __init__(self, root_node_id: str, nodes: Iterable[DialogNode]):
        if not root_node_id:
            raise ValueError("Dialog graph root ID is required.")
        self.root_node_id = root_node_id
        self._nodes_by_id: dict[str, DialogNode] = {}
        for node in nodes:
            if node.node_id in self._nodes_by_id:
                raise ValueError(f"Duplicate dialog node ID: {node.node_id}")
            self._nodes_by_id[node.node_id] = node
        if root_node_id not in self._nodes_by_id:
            raise ValueError(f"Missing dialog root node: {root_node_id}")

    def node(self, node_id: str) -> DialogNode:
        return self._nodes_by_id[node_id]

    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes_by_id


def _parse_choice(raw: dict) -> DialogChoice:
    tags = tuple(raw.get("tags", []) or [])
    return DialogChoice(
        text=str(raw.get("text", "")),
        leads_to_id=str(raw.get("leads_to", "")),
        tags=tags,
    )


def _parse_node(raw: dict) -> DialogNode:
    return DialogNode(
        node_id=str(raw.get("id", "")),
        text=str(raw.get("text", "")),
        choices=tuple(_parse_choice(choice) for choice in raw.get("choices", [])),
    )


def load_dialog_graph(path: Path) -> DialogGraph | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    graph = data.get("graph", data)
    root = str(graph.get("root", ""))
    nodes = [_parse_node(node) for node in graph.get("nodes", [])]
    if not root or not nodes:
        return None
    return DialogGraph(root_node_id=root, nodes=nodes)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@lru_cache(maxsize=1)
def load_default_interview_graph() -> DialogGraph | None:
    path = _repo_root() / "assets" / "dialogue" / "interview_default.json"
    return load_dialog_graph(path)


def select_choice_index(node: DialogNode, tags: Iterable[str]) -> int | None:
    tag_set = set(tags)
    if not node.choices:
        return None
    for idx, choice in enumerate(node.choices):
        if tag_set.intersection(choice.tags):
            return idx
    return 0


def choice_label_for(graph: DialogGraph, node_id: str, index: int) -> str | None:
    if not graph.has_node(node_id):
        node_id = graph.root_node_id
    node = graph.node(node_id)
    if not node.choices:
        node = graph.node(graph.root_node_id)
    if not node.choices:
        return None
    if 0 <= index < len(node.choices):
        return node.choices[index].text
    return None


def render_dialog_text(template: str, context: dict[str, str]) -> str:
    class _SafeDict(dict):
        def __missing__(self, key: str) -> str:
            return ""

    return template.format_map(_SafeDict(context)).strip()
