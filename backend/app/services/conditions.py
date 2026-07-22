"""Pure, data-driven condition evaluator for the NEKG rule engine.

A condition is a small JSON/dict predicate over session state. It is authored in
case files (YAML) and evaluated deterministically here — no strings like
``"trust >= 70"`` are ever ``eval``-ed. Combinators (``all_of``/``any_of``/
``not``) allow arbitrary boolean trees.

Supported leaves:
  - {"has_evidence": "<id>"}
  - {"knows_fact": "<id>"}
  - {"has_item": "<id>"}
  - {"at_location": "<id>"}
  - {"flag": "<name>"}                      (e.g. corridor_unlocked, ended)
  - {"npc_stat": {"npc": "<id>", "stat": "<name>", "op": ">=", "value": 70}}

Combinators:
  - {"all_of": [ <cond>, ... ]}
  - {"any_of": [ <cond>, ... ]}
  - {"not": <cond>}

An empty/None condition means "always true" (used for default branches).
"""

from __future__ import annotations

import operator
from typing import Any

_OPS = {
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
    "==": operator.eq,
    "!=": operator.ne,
}


class StateView:
    """Adapter exposing condition primitives over a GameState-like object.

    Kept intentionally small so the evaluator stays storage-agnostic and
    forward-compatible with multiple NPCs (npc_stat currently maps to the
    single canonical NPC's stats).
    """

    def __init__(self, state: Any) -> None:
        self._s = state

    def has_evidence(self, eid: str) -> bool:
        return eid in self._s.discovered_evidence

    def knows_fact(self, fid: str) -> bool:
        return fid in self._s.known_facts

    def has_item(self, iid: str) -> bool:
        return iid in self._s.inventory

    def at_location(self, loc: str) -> bool:
        return self._s.location == loc

    def flag(self, name: str) -> bool:
        if name == "corridor_unlocked":
            return bool(getattr(self._s, "corridor_unlocked", False))
        if name == "ended":
            return bool(getattr(self._s, "ended", False))
        return name in getattr(self._s, "flags", set())

    def npc_stat(self, npc: str, stat: str) -> int:
        # Single-NPC for the current slice; multi-NPC state comes in P3.
        stats = getattr(self._s, "npc_stats", None)
        if isinstance(stats, dict) and npc in stats:
            return int(stats[npc].get(stat, 0))
        return int(self._s.mara.get(stat, 0))


def evaluate_condition(cond: dict | None, view: StateView) -> bool:
    """Recursively evaluate a condition tree against a :class:`StateView`."""

    if not cond:  # None or empty dict => default branch, always matches
        return True
    if not isinstance(cond, dict):
        raise ValueError(f"Condition must be a dict, got {type(cond).__name__}")

    # Multiple keys at one level are treated as an implicit all_of.
    if len(cond) > 1:
        return all(evaluate_condition({k: v}, view) for k, v in cond.items())

    (key, val), = cond.items()

    if key == "all_of":
        return all(evaluate_condition(c, view) for c in val)
    if key == "any_of":
        return any(evaluate_condition(c, view) for c in val)
    if key == "not":
        return not evaluate_condition(val, view)
    if key == "has_evidence":
        return view.has_evidence(val)
    if key == "knows_fact":
        return view.knows_fact(val)
    if key == "has_item":
        return view.has_item(val)
    if key == "at_location":
        return view.at_location(val)
    if key == "flag":
        return view.flag(val)
    if key == "npc_stat":
        op = _OPS.get(val["op"])
        if op is None:
            raise ValueError(f"Unknown operator: {val['op']!r}")
        return bool(op(view.npc_stat(val["npc"], val["stat"]), val["value"]))

    raise ValueError(f"Unknown condition type: {key!r}")
