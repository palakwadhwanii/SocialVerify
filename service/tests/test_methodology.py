import pytest
from agents.methodology_agents import (
    claim_extraction_agent,
    context_analysis_agent,
    web_search_agent,
    fact_check_agent,
    source_credibility_agent,
    evidence_analysis_agent,
    verification_agent,
    report_generation_agent,
    MethodologyWorkflowEngine
)
from tools.fact_check import GoogleFactCheckClient
from tools.credibility import SourceCredibilityEvaluator
from tools.evidence_processor import EvidenceProcessor, calculate_cosine_similarity
from mcp_servers.client import SocialVerifyMCPClient


def test_the_eight_methodology_agents():
    """Verify all 8 methodology agents are initialized with explicit roles."""
    assert claim_extraction_agent.role == "Claim Extraction Agent"
    assert context_analysis_agent.role == "Context Analysis Agent"
    assert web_search_agent.role == "Web Search Agent"
    assert fact_check_agent.name == "fact_check_agent"
    assert source_credibility_agent.role == "Source Credibility Agent"
    assert evidence_analysis_agent.name == "evidence_analysis_agent"
    assert verification_agent.role == "Verification Agent"
    assert report_generation_agent.role == "Report Generation Agent"


@pytest.mark.asyncio
async def test_the_seven_tools_and_apis():
    """Verify the 7 tools/APIs: Google ADK, CrewAI, Web Search, Google Fact Check, News API, Website Retrieval, Python Tools."""
    # 1. Google ADK Agent
    assert evidence_analysis_agent.name == "evidence_analysis_agent"

    # 2. CrewAI Multi-Agent Workflow
    assert claim_extraction_agent.goal != ""

    # 3. Web Search API via MCP
    mcp_client = SocialVerifyMCPClient()
    web_res = await mcp_client.call_tool("web_search", {"query": "clean energy growth", "max_results": 3})
    assert web_res["protocol"] == "mcp/1.0"
    assert "results" in web_res

    # 4. Google Fact Check API
    fc_client = GoogleFactCheckClient()
    checks = await fc_client.search_fact_checks("AI regulation conformity assessment")
    assert isinstance(checks, list)

    # 5. News / Article APIs via MCP
    news_res = await mcp_client.call_tool("search_news", {"query": "technology regulation", "page_size": 3})
    assert news_res["protocol"] == "mcp/1.0"
    assert "articles" in news_res

    # 6. Website Content Retrieval via MCP
    retrieve_res = await mcp_client.call_tool("retrieve_source_context", {"url": "https://artificialintelligenceact.eu"})
    assert retrieve_res["protocol"] == "mcp/1.0"
    assert "content_preview" in retrieve_res or "status" in retrieve_res

    # 7. Python Tools (Evidence Processing, NER, Cosine Similarity, Credibility)
    context = EvidenceProcessor.extract_context_entities("In 2024, the European Commission introduced new rules.")
    assert "2024" in context["dates"]
    assert "European Commission" in context["entities"]

    sim = calculate_cosine_similarity("European AI regulation", "The European Union AI Act regulation")
    assert sim > 0.3

    cred = SourceCredibilityEvaluator.evaluate_url("https://reuters.com/news/123", "news")
    assert cred["credibility_score"] >= 0.85


@pytest.mark.asyncio
async def test_full_methodology_pipeline():
    """Verify MethodologyWorkflowEngine connects all 8 agents end-to-end."""
    engine = MethodologyWorkflowEngine()
    result = await engine.run_methodology_pipeline("EU AI Act high risk model assessments")

    assert len(result["agents_involved"]) == 8
    assert "Claim Extraction Agent" in result["agents_involved"]
    assert "Context Analysis Agent" in result["agents_involved"]
    assert "Web Search Agent" in result["agents_involved"]
    assert "fact_check_agent" in result["agents_involved"]
    assert "Source Credibility Agent" in result["agents_involved"]
    assert "evidence_analysis_agent" in result["agents_involved"]
    assert "Verification Agent" in result["agents_involved"]
    assert "Report Generation Agent" in result["agents_involved"]

    assert result["verification"]["status"] in ["supported", "contradicted", "mixed", "insufficient_evidence"]
    assert result["credibility"]["average_source_credibility"] > 0.0
