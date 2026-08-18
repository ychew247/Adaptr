import math
import re
import statistics


METRICS = {
    "sleep": {
        "field": "sleep_hours",
        "population_mean": 7.0,
        "population_sigma": 1.0,
        "weight": 20,
        "lower_is_worse": True,
    },
    "stress": {
        "field": "stress_level",
        "population_mean": 3.0,
        "population_sigma": 1.0,
        "weight": 15,
        "lower_is_worse": False,
    },
    "energy": {
        "field": "energy_level",
        "population_mean": 3.0,
        "population_sigma": 1.0,
        "weight": 15,
        "lower_is_worse": True,
    },
    "soreness": {
        "field": "soreness_level",
        "population_mean": 3.0,
        "population_sigma": 1.0,
        "weight": 20,
        "lower_is_worse": False,
    },
}


BANDS = [
    (80, "train_as_planned"),
    (60, "reduce_volume"),
    (40, "lighter_session"),
    (0, "recovery_day"),
]

HARD_PAIN_TERMS = ("sharp", "worsening", "severe", "persistent")


def compute_readiness(
    user_history,
    today_checkin,
    shrinkage_k=5,
    ema_alpha=0.4,
    sigmoid_k=2,
    sigmoid_z0=0.5,
    interaction_gamma=10,
):
    z_scores = {}
    penalties = {}
    baselines = {}

    for metric_name, config in METRICS.items():
        field = config["field"]
        history_values = [_to_float(row.get(field)) for row in user_history]
        history_values = [value for value in history_values if value is not None]
        today_value = _to_float(today_checkin.get(field))
        baseline = _blended_baseline(
            history_values,
            config["population_mean"],
            config["population_sigma"],
            shrinkage_k,
        )
        x_value = _ema([*history_values, today_value], ema_alpha)
        if x_value is None:
            x_value = config["population_mean"]

        z_score = (x_value - baseline["mean"]) / baseline["sigma"]
        if config["lower_is_worse"]:
            z_score = -z_score

        penalty = _sigmoid_penalty(z_score, sigmoid_k, sigmoid_z0)
        z_scores[metric_name] = z_score
        penalties[metric_name] = penalty
        baselines[metric_name] = baseline

    deduction = sum(METRICS[name]["weight"] * penalties[name] for name in METRICS)
    interaction = interaction_gamma * penalties["sleep"] * penalties["soreness"]
    readiness = _clip(100 - deduction - interaction, 0, 100)

    pain_gate_applied = has_hard_pain_flag(today_checkin.get("pain_notes") or "")
    if pain_gate_applied:
        readiness = min(readiness, 30)

    return {
        "readiness_score": round(readiness, 2),
        "band": _band_for_score(readiness),
        "safety_triggered": pain_gate_applied,
        "components": {
            "z_scores": {name: round(value, 4) for name, value in z_scores.items()},
            "penalties": {name: round(value, 4) for name, value in penalties.items()},
            "baselines": baselines,
            "deduction": round(deduction, 4),
            "interaction": round(interaction, 4),
            "pain_gate_applied": pain_gate_applied,
        },
    }


def _blended_baseline(values, population_mean, population_sigma, shrinkage_k):
    n = len(values)
    personal_mean = statistics.mean(values) if values else population_mean
    personal_sigma = statistics.pstdev(values) if len(values) > 1 else population_sigma
    personal_sigma = max(personal_sigma, 0.1)
    personal_weight = n / (n + shrinkage_k)
    population_weight = shrinkage_k / (n + shrinkage_k)

    return {
        "mean": round(personal_weight * personal_mean + population_weight * population_mean, 4),
        "sigma": round(
            max(
                personal_weight * personal_sigma + population_weight * population_sigma,
                0.1,
            ),
            4,
        ),
        "n": n,
    }


def _ema(values, alpha):
    values = [value for value in values if value is not None]
    if not values:
        return None

    current = values[0]
    for value in values[1:]:
        current = alpha * value + (1 - alpha) * current
    return current


def _sigmoid_penalty(z_score, sigmoid_k, sigmoid_z0):
    return 1 / (1 + math.exp(-sigmoid_k * (z_score - sigmoid_z0)))


def has_hard_pain_flag(pain_text):
    normalized = str(pain_text or "").lower()
    for term in HARD_PAIN_TERMS:
        for match in re.finditer(rf"\b{re.escape(term)}\b", normalized):
            context = normalized[max(0, match.start() - 32) : match.start()]
            if not re.search(r"\b(?:no|not|without)\s+(?:\w+\s+){0,2}$", context):
                return True
    return False


def _band_for_score(score):
    for threshold, band in BANDS:
        if score >= threshold:
            return band
    return "recovery_day"


def _clip(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def _to_float(value):
    if value is None:
        return None
    return float(value)
