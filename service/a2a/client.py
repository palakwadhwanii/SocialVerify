import asyncio
import time
from typing import Any
import httpx
from a2a.server import a2a_server, A2ATaskSubmission
from config import A2A_AUTH_TOKEN, A2A_TIMEOUT_SECONDS
from utils.logger import logger


class CrewAIA2AClient:
    """Agent2Agent (A2A) Client invoked by CrewAI to delegate evidence analysis to Google ADK."""

    def __init__(self, server_url: str | None = None, auth_token: str = A2A_AUTH_TOKEN):
        self.server_url = server_url
        self.auth_token = auth_token
        self._cached_agent_card: dict[str, Any] | None = None

    async def discover_agent(self) -> dict[str, Any]:
        """Fetch remote Agent Card to verify identity and skills."""
        if self._cached_agent_card:
            return self._cached_agent_card

        if self.server_url and not self.server_url.startswith("internal://"):
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(f"{self.server_url}/agent-card")
                    if resp.status_code == 200:
                        self._cached_agent_card = resp.json()
                        return self._cached_agent_card
            except Exception as e:
                logger.warning(f"Could not discover A2A agent via HTTP, falling back to local server: {e}")

        # Local A2A server fallback
        self._cached_agent_card = a2a_server.get_agent_card()
        return self._cached_agent_card

    async def delegate_investigation_task(
        self,
        investigation_id: str,
        query: str,
        retrieved_news: list[dict[str, Any]],
        retrieved_social: list[dict[str, Any]],
        retrieved_database: list[dict[str, Any]] | None = None,
        timeout_seconds: float = A2A_TIMEOUT_SECONDS
    ) -> dict[str, Any]:
        """Submit investigation task over A2A protocol and await completed artifacts."""
        await self.discover_agent()

        submission = A2ATaskSubmission(
            investigation_id=investigation_id,
            query=query,
            retrieved_news=retrieved_news,
            retrieved_social=retrieved_social,
            retrieved_database=retrieved_database or []
        )

        logger.info(f"CrewAI A2A Client dispatching task for investigation: {investigation_id}")

        # If remote server URL provided and reachable
        if self.server_url and not self.server_url.startswith("internal://"):
            try:
                async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                    headers = {"Authorization": f"Bearer {self.auth_token}"}
                    resp = await client.post(
                        f"{self.server_url}/tasks",
                        json=submission.model_dump(),
                        headers=headers
                    )
                    if resp.status_code in (200, 201):
                        task_data = resp.json()
                        task_id = task_data["task_id"]
                        
                        # Poll for completion
                        deadline = time.time() + timeout_seconds
                        while time.time() < deadline:
                            status_resp = await client.get(
                                f"{self.server_url}/tasks/{task_id}",
                                headers=headers
                            )
                            if status_resp.status_code == 200:
                                res = status_resp.json()
                                if res["status"] == "completed":
                                    return res.get("artifacts", {})
                                elif res["status"] == "failed":
                                    raise RuntimeError(f"Remote A2A task failed: {res.get('error')}")
                            await asyncio.sleep(0.5)
                        raise TimeoutError(f"A2A task {task_id} timed out after {timeout_seconds}s")
            except Exception as e:
                logger.warning(f"Remote A2A invocation failed, using direct A2A server: {e}")

        # Direct protocol invocation via a2a_server instance
        task_response = await a2a_server.submit_task(submission)
        task_id = task_response.task_id

        # Poll lifecycle until completion or timeout
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            task = a2a_server.get_task(task_id)
            if task.status == "completed":
                return task.artifacts
            elif task.status == "failed":
                raise RuntimeError(f"A2A task {task_id} failed: {task.error}")
            await asyncio.sleep(0.1)

        raise TimeoutError(f"A2A task {task_id} timed out after {timeout_seconds}s")
