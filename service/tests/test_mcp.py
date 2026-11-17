import pytest
from mcp_servers.search_server import SearchMCPServer
from mcp_servers.evidence_server import EvidenceMCPServer
from mcp_servers.client import SocialVerifyMCPClient


@pytest.mark.asyncio
async def test_mcp_servers_tool_discovery():
    """Requirement 2: Integrate at least two real tools through MCP (news/social search and database/evidence tool)."""
    search_server = SearchMCPServer()
    evidence_server = EvidenceMCPServer()

    search_tools = search_server.list_tools()
    search_names = {t["name"] for t in search_tools}
    assert "search_news" in search_names
    assert "search_social_posts" in search_names

    evidence_tools = evidence_server.list_tools()
    evidence_names = {t["name"] for t in evidence_tools}
    assert "lookup_evidence_db" in evidence_names
    assert "retrieve_source_context" in evidence_names

    client = SocialVerifyMCPClient(search_server, evidence_server)
    available = client.list_available_tools()
    available_names = {t["name"] for t in available}
    assert "search_news" in available_names
    assert "search_social_posts" in available_names
    assert "lookup_evidence_db" in available_names


@pytest.mark.asyncio
async def test_mcp_evidence_lookup_execution():
    """Requirement 2: Execute lookup_evidence_db over MCP."""
    client = SocialVerifyMCPClient()
    result = await client.call_tool("lookup_evidence_db", {"topic": "ai regulation", "min_confidence": 0.5})

    assert result["protocol"] == "mcp/1.0"
    assert result["status"] == "success"
    assert result["count"] >= 1
    assert any("AI Act" in r["claim"] for r in result["records"])


@pytest.mark.asyncio
async def test_mcp_parallel_retrieval():
    """Requirement 2 & 4: Parallel tool execution through MCP Client."""
    client = SocialVerifyMCPClient()
    results = await client.execute_parallel_retrieval(
        news_query="AI technology",
        social_topics=["AI technology"],
        db_topic="ai regulation"
    )

    assert results["parallel_execution"] is True
    assert "news" in results
    assert "social" in results
    assert "database" in results
    assert results["database"]["status"] == "success"
