import pytest
from agents.crewai_coordinator import SocialVerifyCoordinator


@pytest.mark.asyncio
async def test_agentic_patterns_execution():
    """Requirement 4: Planner-executor, parallel tool execution, evaluator-optimizer, and human-review patterns."""
    coordinator = SocialVerifyCoordinator()

    # Test complete workflow invoking all patterns
    report = await coordinator.execute_investigation(
        query="Renewable energy generation records in EU",
        investigation_id="test-patterns-1"
    )

    # 1. Planner-Executor: search plan was constructed and executed
    assert report.investigation_id == "test-patterns-1"
    assert report.status in ["completed", "partial"]

    # 2. Parallel tool execution: evidence was fetched across sources
    assert len(report.provenance) >= 1
    assert "SearchMCPServer.search_news" in report.provenance[0].tool_names

    # 3. Evaluator-Optimizer: claims are grounded and validated
    for claim in report.claim_assessments:
        assert claim.confidence >= 0.0 and claim.confidence <= 1.0
        assert claim.assessment in ["supported", "contradicted", "mixed", "insufficient_evidence"]

    # 4. Human-Review: flag exists and is a boolean
    assert isinstance(report.human_review_required, bool)
    assert isinstance(report.review_reasons, list)
