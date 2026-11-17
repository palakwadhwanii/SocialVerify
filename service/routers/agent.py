import uuid
from fastapi import APIRouter, HTTPException
from schemas.agent import QueryRequest, QueryResponse
from agents.graph import agent_app
from a2a.server import a2a_server
from mcp_servers.client import SocialVerifyMCPClient
from monitoring.callbacks import callbacks
from monitoring.tracing import tracer
from utils.logger import logger

router = APIRouter(prefix="/api/agent", tags=["Agent"])
mcp_client = SocialVerifyMCPClient()


@router.post("/query", response_model=QueryResponse)
async def execute_query(request: QueryRequest):
    try:
        inv_id = f"inv-{uuid.uuid4().hex[:12]}"
        initial_state = {
            "investigation_id": inv_id,
            "query": request.query,
            "session_history": request.session_history,
            "access_token": request.access_token,
            "execution_status": "started",
            "errors": [],
        }

        logger.info(f"SocialVerify router starting agent workflow for query: {request.query}")
        result = await agent_app.ainvoke(initial_state)
        final_response = result.get("final_report", {})

        return QueryResponse(
            success=result.get("execution_status") != "failed",
            data=final_response,
            message="Query executed successfully.",
            investigation_id=result.get("investigation_id"),
            execution_status=result.get("execution_status")
        )

    except Exception as e:
        logger.error(f"SocialVerify agent router error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/a2a/agent-card")
def get_a2a_agent_card():
    """Inspectable A2A Agent Card conforming to Agent2Agent protocol."""
    return a2a_server.get_agent_card()


@router.get("/mcp/tools")
def get_mcp_tools():
    """Inspectable list of Model Context Protocol (MCP) tools."""
    return {
        "count": len(mcp_client.list_available_tools()),
        "tools": mcp_client.list_available_tools()
    }


@router.get("/traces/{investigation_id}")
def get_investigation_trace(investigation_id: str):
    """Inspectable distributed trace and provenance record."""
    trace = tracer.get_trace(investigation_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found for investigation")
    return trace


@router.get("/audit/{investigation_id}")
def get_investigation_audit_log(investigation_id: str):
    """Inspectable callback monitoring events and token usage."""
    return {
        "investigation_id": investigation_id,
        "events": callbacks.get_audit_log(investigation_id),
        "token_usage": callbacks.get_token_usage(investigation_id)
    }


@router.get("/methodology")
def get_methodology():
    """Inspectable specification of the 8 methodology agents and 7 tools/APIs."""
    return {
        "section": "5. PROPOSED METHODOLOGY",
        "agents": [
            {"name": "Claim Extraction Agent", "role": "Extracts and structures the main claim."},
            {"name": "Context Analysis Agent", "role": "Identifies context, entities, dates, and missing information."},
            {"name": "Web Search Agent", "role": "Searches the web for relevant information and evidence."},
            {"name": "Fact-Check Agent", "role": "Checks existing fact-checking sources and databases."},
            {"name": "Source Credibility Agent", "role": "Evaluates the reliability and authority of sources."},
            {"name": "Evidence Analysis Agent", "role": "Compares supporting and contradicting evidence."},
            {"name": "Verification Agent", "role": "Determines the overall claim status and confidence."},
            {"name": "Report Generation Agent", "role": "Produces the final user-facing verification report."}
        ],
        "tools_and_apis": [
            {"name": "Google ADK (Agent Development Kit)", "usage": "Agent development and orchestration."},
            {"name": "CrewAI", "usage": "Multi-agent workflow and agent coordination."},
            {"name": "Web Search API", "usage": "Search for evidence related to claims."},
            {"name": "Google Fact Check API", "usage": "Retrieve existing fact-checks."},
            {"name": "News/Article APIs", "usage": "Collect relevant news and reports."},
            {"name": "Website Content Retrieval", "usage": "Extract information from source websites."},
            {"name": "Python Tools", "usage": "Process, compare, and structure evidence."}
        ]
    }
