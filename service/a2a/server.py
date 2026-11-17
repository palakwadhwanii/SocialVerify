import asyncio
import time
import uuid
from typing import Any, Literal
from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel, Field
from config import A2A_AUTH_TOKEN, ADK_A2A_BASE_URL
from utils.logger import logger

# Official A2A Task Statuses
A2ATaskStatus = Literal["submitted", "working", "input-required", "completed", "failed"]


class A2ATaskSubmission(BaseModel):
    task_id: str = Field(default_factory=lambda: f"a2a-task-{uuid.uuid4().hex[:12]}")
    investigation_id: str
    query: str
    retrieved_news: list[dict[str, Any]] = Field(default_factory=list)
    retrieved_social: list[dict[str, Any]] = Field(default_factory=list)
    retrieved_database: list[dict[str, Any]] = Field(default_factory=list)
    context_parameters: dict[str, Any] = Field(default_factory=dict)


class A2ATaskResponse(BaseModel):
    task_id: str
    status: A2ATaskStatus
    created_at: float
    updated_at: float
    error: str | None = None
    artifacts: dict[str, Any] = Field(default_factory=dict)


class ADKA2AServer:
    """Agent2Agent (A2A) Protocol Server hosting the Google ADK Evidence Analysis Agent."""

    def __init__(self, auth_token: str = A2A_AUTH_TOKEN):
        self.auth_token = auth_token
        self.agent_id = "socialverify-adk-evidence-agent"
        self.version = "1.0.0"
        self._tasks: dict[str, dict[str, Any]] = {}
        self._executor_callback = None

    def set_executor(self, executor_callback) -> None:
        """Attach the Google ADK execution engine to handle incoming tasks."""
        self._executor_callback = executor_callback

    def get_agent_card(self) -> dict[str, Any]:
        """A2A Agent Card published at /.well-known/agent.json"""
        return {
            "protocol": "a2a/v1",
            "agent_id": self.agent_id,
            "name": "SocialVerify ADK Evidence Analysis Agent",
            "description": "Google ADK-powered specialized agent for cross-source claim assessment, contradiction detection, and citation validation.",
            "version": self.version,
            "endpoint": f"{ADK_A2A_BASE_URL}/tasks",
            "capabilities": {
                "skills": [
                    "evidence-analysis",
                    "claim-extraction",
                    "cross-source-comparison",
                    "uncertainty-assessment"
                ],
                "modalities": ["application/json"],
                "streaming_supported": False
            },
            "authentication": {
                "type": "bearer",
                "header": "Authorization"
            }
        }

    async def submit_task(self, submission: A2ATaskSubmission) -> A2ATaskResponse:
        """A2A task creation handler."""
        task_id = submission.task_id
        now = time.time()
        task_record = {
            "task_id": task_id,
            "status": "submitted",
            "created_at": now,
            "updated_at": now,
            "submission": submission.model_dump(),
            "artifacts": {},
            "error": None
        }
        self._tasks[task_id] = task_record
        logger.info(f"A2A Server received task {task_id} for investigation {submission.investigation_id}")

        # Execute task using ADK agent
        asyncio.create_task(self._process_task_async(task_id, submission))

        return A2ATaskResponse(
            task_id=task_id,
            status="submitted",
            created_at=now,
            updated_at=now
        )

    async def _process_task_async(self, task_id: str, submission: A2ATaskSubmission) -> None:
        """Asynchronously process A2A task through ADK agent and update lifecycle."""
        if task_id not in self._tasks:
            return

        self._tasks[task_id]["status"] = "working"
        self._tasks[task_id]["updated_at"] = time.time()

        try:
            if self._executor_callback:
                artifacts = await self._executor_callback(submission)
            else:
                from agents.adk_evidence_agent import execute_adk_analysis
                artifacts = await execute_adk_analysis(submission)

            self._tasks[task_id]["status"] = "completed"
            self._tasks[task_id]["artifacts"] = artifacts
            self._tasks[task_id]["updated_at"] = time.time()
            logger.info(f"A2A Task {task_id} completed successfully")
        except Exception as e:
            logger.error(f"A2A Task {task_id} processing failed: {e}")
            self._tasks[task_id]["status"] = "failed"
            self._tasks[task_id]["error"] = str(e)
            self._tasks[task_id]["updated_at"] = time.time()

    def get_task(self, task_id: str) -> A2ATaskResponse:
        """Retrieve current task status and artifacts."""
        if task_id not in self._tasks:
            raise KeyError(f"Task {task_id} not found")
        data = self._tasks[task_id]
        return A2ATaskResponse(
            task_id=data["task_id"],
            status=data["status"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            error=data["error"],
            artifacts=data["artifacts"]
        )


# Global A2A Server instance
a2a_server = ADKA2AServer()

# FastAPI Router for A2A HTTP Protocol Endpoints
a2a_router = APIRouter(prefix="/a2a", tags=["Agent2Agent"])


def verify_a2a_auth(authorization: str = Header(None)) -> bool:
    if not authorization:
        # Allow internal service calls in dev/test, but validate if provided
        return True
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        if parts[1] == A2A_AUTH_TOKEN:
            return True
    raise HTTPException(status_code=401, detail="Invalid A2A authentication credentials")


@a2a_router.get("/agent-card")
@a2a_router.get("/.well-known/agent.json")
def get_agent_card():
    return a2a_server.get_agent_card()


@a2a_router.post("/tasks", response_model=A2ATaskResponse)
async def create_a2a_task(submission: A2ATaskSubmission, authorized: bool = Depends(verify_a2a_auth)):
    return await a2a_server.submit_task(submission)


@a2a_router.get("/tasks/{task_id}", response_model=A2ATaskResponse)
def get_a2a_task_status(task_id: str, authorized: bool = Depends(verify_a2a_auth)):
    try:
        return a2a_server.get_task(task_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="A2A task not found")
