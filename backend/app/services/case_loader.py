"""Load a data-driven case definition (rule logic) from a YAML file.

Separation of concerns:
  - The **world** (facts, evidence, NPCs, epistemic relations) lives in Neo4j
    (neo4j/seed.cypher) and is the narrative source of truth.
  - The **rule logic** (gates, branches, effects, reveal scope) is authored here
    as versioned data. It is the rule engine's deterministic "program", not
    narrative content, so a YAML file is the ergonomic and testable home for it.

A case has ``actions`` and ``intents``. Each maps a trigger name to an ordered
list of branches. The first branch whose ``when`` condition matches wins; a
branch with no ``when`` is the default and always matches (put it last).
"""

from __future__ import annotations

from dataclasses import dataclass
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
class CaseDefinition:
    id: str
    actions: dict[str, Rule]
    intents: dict[str, Rule]


def _parse_section(section: dict | None) -> dict[str, Rule]:
    rules: dict[str, Rule] = {}
    for trigger, spec in (section or {}).items():
        branches = [
            Branch(when=b.get("when"), outcome=b.get("outcome", {}))
            for b in (spec or {}).get("branches", [])
        ]
        rules[trigger] = Rule(trigger=trigger, branches=branches)
    return rules


def load_case_from_path(path: str | Path) -> CaseDefinition:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return CaseDefinition(
        id=data.get("id", "case"),
        actions=_parse_section(data.get("actions")),
        intents=_parse_section(data.get("intents")),
    )


@lru_cache(maxsize=None)
def load_case(case_id: str = "room_314") -> CaseDefinition:
    """Load and cache a case by id from the repo ``cases/`` directory."""
    return load_case_from_path(_CASES_DIR / f"{case_id}.yaml")
