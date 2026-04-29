from __future__ import annotations

from typing import Any

from app.config import settings
from app.services.action_policy import require_allowed_action
from app.services.yandex_client import YandexOAuthClient, YandexResponse


class MetrikaManagementClient:
    base_url = "https://api-metrika.yandex.net"

    def __init__(self, read_token: str | None = None, write_token: str | None = None):
        self.read_client = YandexOAuthClient(read_token or settings.yandex_metrika_read_token, self.base_url)
        self._write_token = write_token or settings.yandex_metrika_write_token

    @property
    def write_client(self) -> YandexOAuthClient:
        return YandexOAuthClient(self._write_token, self.base_url)

    async def counters(self) -> YandexResponse:
        return await self.read_client.request("GET", "/management/v1/counters")

    async def counter(self, counter_id: str, field: list[str] | None = None) -> YandexResponse:
        params = {"field": ",".join(field)} if field else None
        return await self.read_client.request("GET", f"/management/v1/counter/{counter_id}", params=params)

    async def goals(self, counter_id: str) -> YandexResponse:
        return await self.read_client.request("GET", f"/management/v1/counter/{counter_id}/goals")

    async def create_goal(self, counter_id: str, goal: dict[str, Any], *, approved: bool = False) -> YandexResponse:
        require_allowed_action("metrika.goal.create", {"counter_id": counter_id, "goal": goal}, approved)
        return await self.write_client.request("POST", f"/management/v1/counter/{counter_id}/goals", json_body={"goal": goal})

    async def update_goal(self, counter_id: str, goal_id: str, goal: dict[str, Any], *, approved: bool = False) -> YandexResponse:
        require_allowed_action("metrika.goal.update", {"counter_id": counter_id, "goal_id": goal_id, "goal": goal}, approved)
        return await self.write_client.request("PUT", f"/management/v1/counter/{counter_id}/goal/{goal_id}", json_body={"goal": goal})

    async def delete_goal(self, counter_id: str, goal_id: str, *, approved: bool = False) -> YandexResponse:
        require_allowed_action("metrika.goal.delete", {"counter_id": counter_id, "goal_id": goal_id}, approved)
        return await self.write_client.request("DELETE", f"/management/v1/counter/{counter_id}/goal/{goal_id}")

    async def filters(self, counter_id: str) -> YandexResponse:
        return await self.read_client.request("GET", f"/management/v1/counter/{counter_id}/filters")

    async def grants(self, counter_id: str) -> YandexResponse:
        return await self.read_client.request("GET", f"/management/v1/counter/{counter_id}/grants")
