from __future__ import annotations

from typing import Any

from app.models import AgentActionAudit
from app.services.action_policy import evaluate_action
from app.services.yandex_metrika_management import MetrikaManagementClient
from app.services.yandex_webmaster_client import YandexWebmasterClient


class ActionExecutionError(RuntimeError):
    pass


async def execute_approved_action(action: AgentActionAudit, *, approval_token: str) -> dict[str, Any]:
    payload = {**(action.target_json or {}), **(action.payload_json or {})}
    decision = evaluate_action(action.action_type, payload, approved=True)
    if not decision.allowed:
        raise ActionExecutionError(decision.reason)

    if action.action_type == "metrika.goal.create":
        client = MetrikaManagementClient()
        response = await client.create_goal(str(payload["counter_id"]), payload["goal"], approved=True)
        return {"response": response.data, "request_hash": response.request_hash}

    if action.action_type == "metrika.goal.update":
        client = MetrikaManagementClient()
        response = await client.update_goal(
            str(payload["counter_id"]),
            str(payload["goal_id"]),
            payload["goal"],
            approved=True,
        )
        return {"response": response.data, "request_hash": response.request_hash}

    if action.action_type == "webmaster.recrawl.submit":
        client = YandexWebmasterClient()
        response = await client.submit_recrawl(
            str(payload["user_id"]),
            str(payload["host_id"]),
            str(payload["url"]),
            approved=True,
        )
        return {"response": response.data, "request_hash": response.request_hash}

    if action.action_type == "finding.create":
        return {"response": {"stored": True}, "request_hash": None}

    raise ActionExecutionError(f"No executor registered for action type {action.action_type!r}")
