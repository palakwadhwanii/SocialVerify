import time
from typing import Any
from utils.logger import logger


class InvestigationCallbackHandler:
    """Callback-based monitoring tracking agent lifecycles, tool calls, and latencies."""

    def __init__(self):
        self._audit_logs: dict[str, list[dict[str, Any]]] = {}
        self._token_usage: dict[str, dict[str, int]] = {}

    def get_audit_log(self, investigation_id: str) -> list[dict[str, Any]]:
        return self._audit_logs.get(investigation_id, [])

    def get_token_usage(self, investigation_id: str) -> dict[str, int]:
        return self._token_usage.get(investigation_id, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})

    def on_investigation_start(self, investigation_id: str, query: str) -> None:
        event = {
            "event": "investigation_start",
            "investigation_id": investigation_id,
            "query": query,
            "timestamp": time.time(),
        }
        self._audit_logs.setdefault(investigation_id, []).append(event)
        self._token_usage[investigation_id] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        logger.info(f"[{investigation_id}] Investigation started: {query}")

    def on_agent_start(self, investigation_id: str, agent_name: str, task: str) -> None:
        event = {
            "event": "agent_start",
            "agent": agent_name,
            "task": task,
            "timestamp": time.time(),
        }
        self._audit_logs.setdefault(investigation_id, []).append(event)
        logger.info(f"[{investigation_id}] Agent started: {agent_name} - Task: {task}")

    def on_agent_end(
        self,
        investigation_id: str,
        agent_name: str,
        output: Any,
        latency_ms: float,
        tokens: dict[str, int] | None = None
    ) -> None:
        event = {
            "event": "agent_end",
            "agent": agent_name,
            "output_preview": str(output)[:200],
            "latency_ms": latency_ms,
            "timestamp": time.time(),
        }
        self._audit_logs.setdefault(investigation_id, []).append(event)

        if tokens:
            usage = self._token_usage.setdefault(investigation_id, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
            usage["prompt_tokens"] += tokens.get("prompt_tokens", 0)
            usage["completion_tokens"] += tokens.get("completion_tokens", 0)
            usage["total_tokens"] += tokens.get("total_tokens", 0)

        logger.info(f"[{investigation_id}] Agent completed: {agent_name} in {latency_ms:.2f}ms")

    def on_tool_start(self, investigation_id: str, tool_name: str, arguments: dict[str, Any]) -> None:
        event = {
            "event": "tool_start",
            "tool": tool_name,
            "arguments": arguments,
            "timestamp": time.time(),
        }
        self._audit_logs.setdefault(investigation_id, []).append(event)
        logger.info(f"[{investigation_id}] Tool started: {tool_name}")

    def on_tool_end(self, investigation_id: str, tool_name: str, result: Any, latency_ms: float) -> None:
        event = {
            "event": "tool_end",
            "tool": tool_name,
            "status": result.get("status", "completed") if isinstance(result, dict) else "completed",
            "latency_ms": latency_ms,
            "timestamp": time.time(),
        }
        self._audit_logs.setdefault(investigation_id, []).append(event)
        logger.info(f"[{investigation_id}] Tool completed: {tool_name} in {latency_ms:.2f}ms")

    def on_validation_failure(self, investigation_id: str, step: str, error: str) -> None:
        event = {
            "event": "validation_failure",
            "step": step,
            "error": error,
            "timestamp": time.time(),
        }
        self._audit_logs.setdefault(investigation_id, []).append(event)
        logger.warning(f"[{investigation_id}] Validation failure in {step}: {error}")

    def on_exception(self, investigation_id: str, component: str, error: str) -> None:
        event = {
            "event": "exception",
            "component": component,
            "error": error,
            "timestamp": time.time(),
        }
        self._audit_logs.setdefault(investigation_id, []).append(event)
        logger.error(f"[{investigation_id}] Exception in {component}: {error}")

    def on_investigation_complete(self, investigation_id: str, success: bool, summary: str) -> None:
        event = {
            "event": "investigation_complete",
            "success": success,
            "summary_preview": summary[:200],
            "timestamp": time.time(),
        }
        self._audit_logs.setdefault(investigation_id, []).append(event)
        logger.info(f"[{investigation_id}] Investigation complete: Success={success}")


# Global callbacks instance
callbacks = InvestigationCallbackHandler()
