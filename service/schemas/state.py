from typing import Any, TypedDict


class InvestigationState(TypedDict, total=False):
    investigation_id: str
    query: str
    conversation_history: list[dict[str, Any]]
    access_token: str | None
    input_validation: dict[str, Any]
    search_plan: dict[str, Any]
    retrieved_news: list[dict[str, Any]]
    retrieved_social: list[dict[str, Any]]
    retrieved_database: list[dict[str, Any]]
    crewai_results: dict[str, Any]
    adk_task_id: str
    adk_results: dict[str, Any]
    claim_assessments: list[dict[str, Any]]
    evaluation_metrics: dict[str, Any]
    provenance: list[dict[str, Any]]
    final_report: dict[str, Any]
    errors: list[dict[str, Any]]
    execution_status: str


# Backwards compatibility alias
AgentState = InvestigationState
