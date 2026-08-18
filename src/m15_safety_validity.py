"""Module 15 deterministic safety and validity assessment.

This module makes safety decisions from the raw user message and persisted
context. LLM output and retrieved fitness knowledge can explain a result, but
must never determine or override it.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from src.m5_readiness_score import has_hard_pain_flag


POLICY_VERSION = "1"
_URGENT_RULES = {
    "chest_pain": (r"\b(?:chest (?:pain|ache|discomfort)|pain in (?:my )?chest)\b",),
    "fainting": (r"\b(?:fainted|fainting|passed out|lost consciousness)\b",),
    "severe_dizziness": (r"\b(?:severe(?:ly)?|extreme(?:ly)?|intense(?:ly)?)\s+dizz(?:y|iness)\b",),
    "severe_shortness_of_breath": (
        r"\b(?:severe|extreme)\s+(?:shortness of breath|breathlessness)\b",
        r"\b(?:shortness of breath|breathlessness)\s+(?:is\s+)?(?:severe|extreme)\b",
    ),
}
_WORKOUT_TERMS = ("workout", "training", "train", "gym", "lift", "lifting", "hiit", "exercise")
_HARMFUL_SUBSTANCE_TERMS = ("steroid", "anabolic", "testosterone", "sarm", "tren")
_FACILITATING_TERMS = ("cycle", "dose", "dosage", "inject", "source", "buy", "stack")


def assess_safety(
    message: str,
    profile: Mapping[str, Any] | None = None,
    goal: Mapping[str, Any] | None = None,
    active_plan: Mapping[str, Any] | None = None,
    recent_checkin: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return an authoritative, JSON-serializable safety assessment.

    Context arguments deliberately remain optional because a safety-critical
    message can arrive before onboarding or before database context exists.
    """
    del goal, active_plan, recent_checkin
    normalized = _normalize(message)
    urgent_flags = _matching_urgent_flags(normalized)
    if urgent_flags:
        return _assessment(
            urgent_flags,
            "urgent",
            ["recommend_urgent_medical_help"],
            "Stop exercise and seek urgent medical assessment. These symptoms are outside the scope of workout advice.",
        )

    if _is_harmful_substance_request(normalized):
        return _assessment(
            ["harmful_substance_request"],
            "blocked",
            ["offer_safer_general_alternatives", "recommend_licensed_clinician"],
            "I cannot provide instructions for obtaining, dosing, or using harmful performance-enhancing drugs or supplements.",
        )

    if _is_eating_disorder_risk(normalized):
        return _assessment(
            ["eating_disorder_risk"],
            "blocked",
            ["offer_support_resources", "recommend_qualified_support"],
            "I cannot help with dangerously restrictive eating. A qualified health professional can provide appropriate support.",
        )

    if _is_unsafe_rapid_weight_loss(normalized):
        return _assessment(
            ["unsafe_rapid_weight_loss"],
            "blocked",
            ["offer_sustainable_wellness_guidance"],
            "That weight-loss target is too rapid to support safely. I can help with sustainable, general wellness guidance instead.",
        )

    if has_hard_pain_flag(normalized):
        return _assessment(
            ["hard_pain"],
            "restricted",
            ["offer_recovery_guidance", "recommend_qualified_care"],
            "Avoid intense or painful loading. Sharp, worsening, severe, or persistent pain needs appropriate professional guidance.",
        )

    medical_constraints = str((profile or {}).get("medical_constraints") or "").strip()
    if medical_constraints and _requests_workout_guidance(normalized):
        return _assessment(
            ["medical_constraint"],
            "restricted",
            ["ask_for_clinician_constraints", "offer_constraint_aware_guidance"],
            "Your stored medical constraints must be followed before giving specific workout guidance.",
        )

    return _assessment(
        [],
        "allowed",
        ["continue_normal_workflow", "generate_workout"],
        "No Module 15 safety restriction was triggered.",
    )


def _matching_urgent_flags(message: str) -> list[str]:
    return [
        flag
        for flag, patterns in _URGENT_RULES.items()
        if any(_has_unnegated_match(message, pattern) for pattern in patterns)
    ]


def _has_unnegated_match(message: str, pattern: str) -> bool:
    for match in re.finditer(pattern, message):
        preceding = message[max(0, match.start() - 32) : match.start()]
        if not re.search(r"\b(?:no|not|without|deny|denies)\s+(?:\w+\s+){0,3}$", preceding):
            return True
    return False


def _is_harmful_substance_request(message: str) -> bool:
    return any(term in message for term in _HARMFUL_SUBSTANCE_TERMS) and any(
        term in message for term in _FACILITATING_TERMS
    )


def _is_eating_disorder_risk(message: str) -> bool:
    restrictive_calories = bool(re.search(r"\b(?:[0-7]\d{2})\s*(?:kcal|calories|cal)\b", message))
    restrictive_language = any(
        phrase in message
        for phrase in ("starve myself", "stop eating", "not eat", "skip all meals", "purge")
    )
    return restrictive_calories or restrictive_language


def _is_unsafe_rapid_weight_loss(message: str) -> bool:
    return bool(
        re.search(r"\blose\s+\d+(?:\.\d+)?\s*(?:kg|kilos?|pounds?|lbs?)\s+(?:in|within)\s+(?:a|one|1)\s+week\b", message)
    )


def _requests_workout_guidance(message: str) -> bool:
    return any(term in message for term in _WORKOUT_TERMS)


def _normalize(message: str) -> str:
    return re.sub(r"\s+", " ", str(message or "").lower()).strip()


def _assessment(
    flags: list[str], severity: str, allowed_actions: list[str], reason: str
) -> dict[str, Any]:
    return {
        "flags": flags,
        "highest_severity": severity,
        "allowed_actions": allowed_actions,
        "reason": reason,
        "policy_version": POLICY_VERSION,
    }
