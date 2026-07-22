"""Load a data-driven case definition (rule logic) from a YAML file.

Separation of concerns:
  - The **world** (facts, evidence, NPCs, epistemic relations) lives in Neo4j
    (neo4j/seed.cypher) and is the narrative source of truth.
  - The **rule logic** (gates, branches, effects, reveal scope) is authored here
    as versioned data. It is the rule engine's deterministic "program".

Structure:
  - ``actions``: global world actions (not tied to an NPC).
  - ``npcs``: per-NPC dialogue. Each NPC has ``stats`` (initial psychology),
    ``intents`` (dialogue rules), ``sensitive_facts`` (hidden until unlocked)
    and ``always_forbidden`` (that NPC's buried secret — never revealed).

Branch selection: the first branch whose ``when`` condition matches wins; a
branch with no ``when`` is the default (always matches) and must be last.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

# Repo root: services -> app -> backend -> root
_CASES_DIR = Path(__file__).resolve().parents[3] / "cases"


@dataclass
class Branch:
    when: dict | None
    outcome: dict


@dataclass
class Rule:
    trigger: str
    branches: list[Branch]


@dataclass
class NpcDef:
    id: str
    stats: dict[str, int] = field(default_factory=dict)
    intents: dict[str, Rule] = field(default_factory=dict)
    sensitive_facts: list[str] = field(default_factory=list)
    always_forbidden: list[str] = field(default_factory=list)


@dataclass
class CaseDefinition:
    id: str
    default_npc: str
    actions: dict[str, Rule]
    npcs: dict[str, NpcDef]

    def npc(self, npc_id: str | None) -> NpcDef | None:
        return self.npcs.get(npc_id or self.default_npc)


def _parse_section(section: dict | None) -> dict[str, Rule]:
    rules: dict[str, Rule] = {}
    for trigger, spec in (section or {}).items():
        branches = [
            Branch(when=b.get("when"), outcome=b.get("outcome", {}))
            for b in (spec or {}).get("branches", [])
        ]
        rules[trigger] = Rule(trigger=trigger, branches=branches)
    return rules


def _parse_npcs(section: dict | None) -> dict[str, NpcDef]:
    npcs: dict[str, NpcDef] = {}
    for npc_id, spec in (section or {}).items():
        spec = spec or {}
        npcs[npc_id] = NpcDef(
            id=npc_id,
            stats=dict(spec.get("stats", {})),
            intents=_parse_section(spec.get("intents")),
            sensitive_facts=list(spec.get("sensitive_facts", [])),
            always_forbidden=list(spec.get("always_forbidden", [])),
        )
    return npcs


def load_case_from_path(path: str | Path) -> CaseDefinition:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    npcs = _parse_npcs(data.get("npcs"))
    default_npc = data.get("default_npc") or next(iter(npcs), "")
    return CaseDefinition(
        id=data.get("id", "case"),
        default_npc=default_npc,
        actions=_parse_section(data.get("actions")),
        npcs=npcs,
    )


@lru_cache(maxsize=None)
def load_case(case_id: str = "room_314") -> CaseDefinition:
    """Load and cache a case by id from the repo ``cases/`` directory."""
    return load_case_from_path(_CASES_DIR / f"{case_id}.yaml")
