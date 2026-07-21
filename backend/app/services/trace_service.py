"""Auditable NEKG traces.

Every important response carries a trace: which rule fired, which facts were
used, which were hidden, which speech moves were allowed, and how the LLM output
was validated. Traces are returned to the debug panel and persisted in Neo4j.
"""

from __future__ import annotations

from app.models import TraceModel
from app.services.rules_engine import RuleResult


def build_action_trace(result: RuleResult, action: str) -> TraceModel:
    return TraceModel(
        rule_id=result.rule_id,
        action=action,
        intent=None,
        classified_from_text=False,
        facts_used=list(result.new_facts),
        facts_hidden=list(result.forbidden_facts),
        allowed_intents=[],
        claim_type=None,
        reason=result.reason,
        llm_source="n/a",
        validation="n/a",
    )


def build_dialogue_trace(
    *,
    result: RuleResult,
    intent: str,
    classified_from_text: bool,
    allowed_fact_ids: list[str],
    forbidden_fact_ids: list[str],
    allowed_intents: list[str],
    claim_type: str,
    llm_source: str,
    validation: str,
) -> TraceModel:
    return TraceModel(
        rule_id=result.rule_id,
        action=None,
        intent=intent,
        classified_from_text=classified_from_text,
        facts_used=list(allowed_fact_ids),
        facts_hidden=list(forbidden_fact_ids),
        allowed_intents=list(allowed_intents),
        claim_type=claim_type,
        reason=result.reason,
        llm_source=llm_source,
        validation=validation,
    )


def trace_to_dict(trace: TraceModel) -> dict:
    return trace.model_dump()
