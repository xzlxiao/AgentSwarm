"""Gateway 远程回调客户端：快照和 Agent 管理工具通过 HTTP 回调 Gateway API"""

import httpx

from worker.config import WorkerSettings


class GatewayClient:
    def __init__(self, settings: WorkerSettings) -> None:
        self._base_url = settings.gateway_url
        self._agent_key = settings.agent_internal_key
        self._client = httpx.AsyncClient(timeout=30.0)

    def _headers(self) -> dict[str, str]:
        return {"X-Agent-Key": self._agent_key}

    async def snapshot(self, name: str, workspace_id: str, volume_name: str) -> str:
        resp = await self._client.post(
            f"{self._base_url}/api/v1/internal/snapshots/create",
            json={"name": name, "workspace_id": workspace_id, "volume_name": volume_name},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()["snapshot_id"]

    async def restore(self, snapshot_id: str, workspace_id: str, volume_name: str) -> None:
        resp = await self._client.post(
            f"{self._base_url}/api/v1/internal/snapshots/restore",
            json={"snapshot_id": snapshot_id, "workspace_id": workspace_id, "volume_name": volume_name},
            headers=self._headers(),
        )
        resp.raise_for_status()

    async def spawn_agent(self, name: str, role: str, workspace_id: str) -> dict[str, object]:
        resp = await self._client.post(
            f"{self._base_url}/api/v1/agents",
            json={"name": name, "role": role, "workspace_id": workspace_id},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def list_agents(self, workspace_id: str) -> list[dict[str, object]]:
        resp = await self._client.get(
            f"{self._base_url}/api/v1/agents",
            params={"workspace_id": workspace_id},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def acquire_lock(
        self, workspace_id: str, node_id: str, container_id: str, timeout_seconds: int | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "workspace_id": workspace_id,
            "node_id": node_id,
            "container_id": container_id,
        }
        if timeout_seconds is not None:
            payload["timeout_seconds"] = timeout_seconds
        resp = await self._client.post(
            f"{self._base_url}/api/v1/internal/locks/acquire",
            json=payload,
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def release_lock(self, workspace_id: str, node_id: str) -> dict[str, object]:
        resp = await self._client.post(
            f"{self._base_url}/api/v1/internal/locks/release",
            json={"workspace_id": workspace_id, "node_id": node_id},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def aclose(self) -> None:
        await self._client.aclose()
