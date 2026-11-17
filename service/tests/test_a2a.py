import pytest
from a2a.server import a2a_server, A2ATaskSubmission
from a2a.client import CrewAIA2AClient
from google.genai.errors import ServerError
from agents import adk_evidence_agent
from agents.adk_evidence_agent import (
    ADKClaimAssessment,
    AnalysisResult,
    execute_adk_analysis,
)


def test_adk_response_schema_omits_unsupported_additional_properties():
    schema = AnalysisResult.model_json_schema()

    def contains_additional_properties(value):
        if isinstance(value, dict):
            return any(
                key.lower() in {"additional_properties", "additionalproperties"}
                or contains_additional_properties(child)
                for key, child in value.items()
            )
        if isinstance(value, list):
            return any(contains_additional_properties(item) for item in value)
        return False

    assert not contains_additional_properties(schema)


@pytest.mark.asyncio
async def test_a2a_agent_card_discovery():
    """Requirement 6: A2A Interoperability - Agent Card discovery."""
    client = CrewAIA2AClient()
    card = await client.discover_agent()

    assert card["protocol"] == "a2a/v1"
    assert card["agent_id"] == "socialverify-adk-evidence-agent"
    assert "evidence-analysis" in card["capabilities"]["skills"]
    assert "claim-extraction" in card["capabilities"]["skills"]


@pytest.mark.asyncio
async def test_a2a_task_lifecycle_execution():
    """Requirement 6: A2A Interoperability - Submit task and retrieve structured artifacts."""
    client = CrewAIA2AClient()
    
    artifacts = await client.delegate_investigation_task(
        investigation_id="a2a-e2e-test",
        query="Electric vehicle battery recycling mandates",
        retrieved_news=[
            {
                "title": "EU mandates minimum recycled content in new EV batteries",
                "url": "https://example.com/ev-battery-mandates",
                "source": "TechNews"
            }
        ],
        retrieved_social=[
            {
                "title": "Discussion on battery supply chain bottlenecks",
                "url": "https://reddit.com/r/electricvehicles/comments/1",
                "platform": "reddit"
            }
        ],
        retrieved_database=[]
    )

    assert "summary" in artifacts
    assert "claim_assessments" in artifacts
    assert len(artifacts["claim_assessments"]) >= 1
    assert artifacts["claim_assessments"][0]["assessment"] in ["supported", "contradicted", "mixed", "insufficient_evidence"]
    assert "evidence_sources" in artifacts
    assert len(artifacts["evidence_sources"]) == 2


@pytest.mark.asyncio
async def test_adk_without_credentials_does_not_invent_a_verdict(monkeypatch):
    monkeypatch.setattr("agents.adk_evidence_agent.ADK_MODEL_API_KEY", "")
    artifacts = await execute_adk_analysis(A2ATaskSubmission(
        investigation_id="adk-no-credentials",
        query="A claim with insufficient evidence",
        retrieved_news=[{
            "title": "A report without a publication timestamp",
            "url": "https://example.com/report",
        }],
    ))

    assert artifacts["claim_assessments"][0]["assessment"] == "insufficient_evidence"
    assert artifacts["claim_assessments"][0]["confidence"] == 0.0
    assert artifacts["evidence_sources"][0]["published_at"] is None
    assert "ASSESSMENT UNAVAILABLE" in artifacts["beginner_verdict"]["verdict"]


@pytest.mark.asyncio
async def test_adk_retries_once_after_temporary_provider_overload(monkeypatch):
    attempts = 0

    async def flaky_analysis(query, sources):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ServerError(503, {"error": {"message": "Temporary overload"}})
        return AnalysisResult(
            summary="The source does not establish whether the claim is true.",
            plain_english="This source alone is not enough to confirm the claim.",
            claim_assessments=[
                ADKClaimAssessment(
                    claim=query,
                    assessment="insufficient_evidence",
                    confidence=0.0,
                    limitations=["Only one source was supplied."],
                )
            ],
        )

    monkeypatch.setattr(adk_evidence_agent, "_run_adk_analysis", flaky_analysis)
    artifacts = await execute_adk_analysis(A2ATaskSubmission(
        investigation_id="adk-temporary-overload",
        query="A specific claim",
        retrieved_news=[{
            "title": "A report",
            "url": "https://example.com/report",
        }],
    ))

    assert attempts == 2
    assert "ASSESSMENT UNAVAILABLE" not in artifacts["beginner_verdict"]["verdict"]
    assert artifacts["claim_assessments"][0]["assessment"] == "insufficient_evidence"
