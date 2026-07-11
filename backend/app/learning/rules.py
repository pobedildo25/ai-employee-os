"""Helpers for formatting learning rules into agent-facing context."""

from app.learning.models import LearningRule


def format_rule_for_context(rule: LearningRule) -> dict:
    return {
        "category": rule.category,
        "key": rule.key,
        "value": rule.value,
        "rule": f"{rule.key}: {rule.value}",
        "confidence": rule.confidence,
        "scope": rule.scope.value,
    }


def format_rules_for_context(rules: list[LearningRule]) -> list[dict]:
    return [format_rule_for_context(rule) for rule in rules]
