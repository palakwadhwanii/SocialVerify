import asyncio
import uuid
from typing import Any
from agents.crewai_coordinator import SocialVerifyCoordinator
from security.guardrails import InputGuardrail
from schemas.state import InvestigationState
from utils.logger import logger


class SocialVerifyExecutionEngine:
    """Multi-agent execution engine powered by CrewAI + Google ADK over A2A protocol."""

    def __init__(self):
        self.coordinator = SocialVerifyCoordinator()

    async def ainvoke(self, state: InvestigationState, config: dict[str, Any] | None = None) -> dict[str, Any]:
        query = state.get("query", "")
        investigation_id = state.get("investigation_id") or f"inv-{uuid.uuid4().hex[:12]}"
        access_token = state.get("access_token")

        logger.info(f"SocialVerify Execution Engine starting for query: '{query}'")

        # Step 1: Input Guardrail validation (Requirement 8)
        allowed, reason = InputGuardrail.validate_query(query)
        if not allowed:
            logger.warning(f"Query rejected by input guardrail: {reason}")
            state["execution_status"] = "security_rejection"
            state["final_report"] = {
                "response": f"# Request Blocked by Security Guardrail\n\n**Reason:** {reason}\n\nPlease revise your query according to acceptable use policies.",
                "reasoning": reason,
                "status": "failed"
            }
            return state

        # Step 2: Multi-agent execution via CrewAI + Google ADK over A2A
        report = await self.coordinator.execute_investigation(
            query=query,
            investigation_id=investigation_id,
            access_token=access_token
        )

        state["investigation_id"] = report.investigation_id
        state["execution_status"] = report.status
        state["claim_assessments"] = [c.model_dump() for c in report.claim_assessments]
        state["evaluation_metrics"] = report.evaluation_metrics.model_dump()
        state["provenance"] = [p.model_dump() for p in report.provenance]
        state["final_report"] = {
            "response": report.markdown_report,
            "reasoning": report.summary,
            "report": report.model_dump(),
            "status": report.status,
            "human_review_required": report.human_review_required,
            "review_reasons": report.review_reasons
        }

        return state

    def invoke(self, state: InvestigationState, config: dict[str, Any] | None = None) -> dict[str, Any]:
        """Synchronous wrapper for invoke."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If already running inside an asyncio loop
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    return pool.submit(asyncio.run, self.ainvoke(state, config)).result()
            else:
                return loop.run_until_complete(self.ainvoke(state, config))
        except RuntimeError:
            return asyncio.run(self.ainvoke(state, config))


# Primary agent app replacing LangGraph in the execution path
agent_app = SocialVerifyExecutionEngine()
