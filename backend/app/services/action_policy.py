from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.config import settings


class SafetyClass(str, Enum):
    READ_ONLY = "read_only"
    LOW_RISK_WRITE = "low_risk_write"
    HIGH_RISK_WRITE = "high_risk_write"
    DENIED = "denied"


class ActionPolicyError(ValueError):
    pass


DENIED_ACTIONS = {
    "metrika.counter.delete",
    "metrika.counter.restore",
    "metrika.counter.create",
    "metrika.access.grant",
    "metrika.access.revoke",
    "metrika.goal.bulk_delete",
    "webmaster.host.delete",
    "webmaster.owner.modify",
}

HIGH_RISK_ACTIONS = {
    "metrika.counter.update",
    "metrika.goal.delete",
    "metrika.filter.delete",
    "metrika.operation.delete",
    "webmaster.sitemap.delete",
    "webmaster.verification.start",
}

LOW_RISK_WRITE_ACTIONS = {
    "metrika.goal.create",
    "metrika.goal.update",
    "metrika.filter.create",
    "metrika.filter.update",
    "webmaster.recrawl.submit",
    "webmaster.sitemap.add",
    "experiment.update",
    "finding.create",
}


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    safety_class: SafetyClass
    reason: str
    requires_approval: bool = False


def allowed_counter_ids() -> set[str]:
    return {value.strip() for value in settings.analytics_allowed_counter_ids.split(",") if value.strip()}


def allowed_hosts() -> set[str]:
    return {value.strip().lower() for value in settings.analytics_allowed_hosts.split(",") if value.strip()}


def classify_action(action_type: str) -> SafetyClass:
    if action_type in DENIED_ACTIONS:
        return SafetyClass.DENIED
    if action_type in HIGH_RISK_ACTIONS:
        return SafetyClass.HIGH_RISK_WRITE
    if action_type in LOW_RISK_WRITE_ACTIONS:
        return SafetyClass.LOW_RISK_WRITE
    if action_type.endswith(".read") or action_type.startswith("analytics."):
        return SafetyClass.READ_ONLY
    return SafetyClass.HIGH_RISK_WRITE


def _target_allowed(payload: dict[str, Any]) -> tuple[bool, str]:
    counter_id = payload.get("counter_id") or payload.get("counterId")
    if counter_id is not None and str(counter_id) not in allowed_counter_ids():
        return False, f"counter_id {counter_id!r} is not in analytics allowlist"

    host = payload.get("host") or payload.get("host_id") or payload.get("domain")
    if host:
        normalized = str(host).lower()
        if normalized.startswith("https://"):
            normalized = normalized.removeprefix("https://")
        if normalized.startswith("http://"):
            normalized = normalized.removeprefix("http://")
        normalized = normalized.strip("/")
        if normalized not in allowed_hosts() and not normalized.endswith(".forecasteconomy.com"):
            return False, f"host {host!r} is not in analytics allowlist"

    url = payload.get("url")
    if url and "forecasteconomy.com" not in str(url).lower():
        return False, f"url {url!r} is not in analytics allowlist"

    return True, "target is allowed"


def evaluate_action(action_type: str, payload: dict[str, Any] | None, approved: bool = False) -> PolicyDecision:
    payload = payload or {}
    safety = classify_action(action_type)
    if safety == SafetyClass.DENIED:
        return PolicyDecision(False, safety, f"{action_type} is denied by policy")

    target_ok, target_reason = _target_allowed(payload)
    if not target_ok:
        return PolicyDecision(False, safety, target_reason)

    if safety == SafetyClass.READ_ONLY:
        return PolicyDecision(True, safety, "read-only action allowed")

    if not settings.analytics_live_writes_enabled:
        return PolicyDecision(
            False,
            safety,
            "analytics live writes are disabled; store proposal for approval instead",
            requires_approval=True,
        )

    if safety == SafetyClass.HIGH_RISK_WRITE and not approved:
        return PolicyDecision(False, safety, "high-risk action requires explicit approval", requires_approval=True)

    if safety == SafetyClass.LOW_RISK_WRITE and not approved:
        return PolicyDecision(False, safety, "write action requires approval token", requires_approval=True)

    return PolicyDecision(True, safety, "approved write action allowed")


def require_allowed_action(action_type: str, payload: dict[str, Any] | None, approved: bool = False) -> PolicyDecision:
    decision = evaluate_action(action_type, payload, approved)
    if not decision.allowed:
        raise ActionPolicyError(decision.reason)
    return decision
