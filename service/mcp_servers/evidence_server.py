from typing import Any
import httpx
from tools.fact_check import GoogleFactCheckClient
from utils.logger import logger

EVIDENCE_TOOLS_SCHEMA = [
    {
        "name": "lookup_evidence_db",
        "description": "Lookup historical evidence, verified claims, and fact-checking records from the SocialVerify evidence repository via MCP.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Investigation claim or entity name."},
                "min_confidence": {"type": "number", "description": "Minimum confidence threshold (0.0 - 1.0).", "default": 0.5}
            },
            "required": ["topic"]
        }
    },
    {
        "name": "retrieve_source_context",
        "description": "Fetch and extract text content from an evidence URL via MCP (Website Content Retrieval).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The HTTP/HTTPS URL of the article or post to inspect."}
            },
            "required": ["url"]
        }
    },
    {
        "name": "google_fact_check_search",
        "description": "Query Google Fact Check Tools API and verified databases for existing claim reviews via MCP.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The claim text or keywords to retrieve existing fact-checks for."}
            },
            "required": ["query"]
        }
    }
]

# Baseline historical evidence database
HISTORICAL_EVIDENCE_DB = [
    {
        "topic": "ai regulation",
        "claim": "EU AI Act enforces strict conformity assessments for high-risk artificial intelligence models.",
        "status": "supported",
        "confidence": 0.95,
        "source": "https://artificialintelligenceact.eu",
        "publisher": "European Union Law",
        "supporting_facts": ["Act entered into force with phased compliance deadlines starting 2024-2026."]
    },
    {
        "topic": "global trade",
        "claim": "Supply chain nearshoring has increased bilateral trade agreements in North America.",
        "status": "supported",
        "confidence": 0.88,
        "source": "https://wto.org/trade-monitoring",
        "publisher": "World Trade Organization",
        "supporting_facts": ["USMCA trade volume reached record highs while Asian transit corridors diversified."]
    },
    {
        "topic": "renewable energy",
        "claim": "Solar photovoltaics and wind power generated over 30 percent of EU electricity in recent quarters.",
        "status": "supported",
        "confidence": 0.92,
        "source": "https://ember-climate.org/insights",
        "publisher": "Ember Energy Research",
        "supporting_facts": ["Wind and solar combined output surpassed fossil fuel generation for multiple consecutive months."]
    }
]


class EvidenceMCPServer:
    """MCP Server exposing evidence database lookups, document retrieval, and Google Fact Check API."""

    def __init__(self):
        self.name = "socialverify-evidence-mcp"
        self.version = "1.0.0"
        self.fact_check_client = GoogleFactCheckClient()

    def list_tools(self) -> list[dict[str, Any]]:
        """MCP tools/list handler."""
        return EVIDENCE_TOOLS_SCHEMA

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """MCP tools/call handler."""
        if name == "lookup_evidence_db":
            return await self._execute_lookup_evidence(arguments)
        elif name == "retrieve_source_context":
            return await self._execute_retrieve_context(arguments)
        elif name == "google_fact_check_search":
            return await self._execute_google_fact_check(arguments)
        else:
            raise ValueError(f"Unknown MCP tool: {name}")

    async def _execute_lookup_evidence(self, args: dict[str, Any]) -> dict[str, Any]:
        topic = str(args.get("topic", "")).lower().strip()
        min_confidence = float(args.get("min_confidence", 0.5))

        matches = []
        for record in HISTORICAL_EVIDENCE_DB:
            if any(term in record["topic"] or term in record["claim"].lower() for term in topic.split()):
                if record["confidence"] >= min_confidence:
                    matches.append(record)

        return {
            "tool": "lookup_evidence_db",
            "protocol": "mcp/1.0",
            "status": "success",
            "query_topic": topic,
            "count": len(matches),
            "records": matches
        }

    async def _execute_retrieve_context(self, args: dict[str, Any]) -> dict[str, Any]:
        url = str(args.get("url", "")).strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            return {
                "tool": "retrieve_source_context",
                "protocol": "mcp/1.0",
                "status": "failed",
                "error": "Invalid URL scheme"
            }

        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "SocialVerify-MCP-Fetcher/1.0"})
                content_preview = resp.text[:2000] if resp.status_code == 200 else ""
                return {
                    "tool": "retrieve_source_context",
                    "protocol": "mcp/1.0",
                    "status": "success" if resp.status_code == 200 else "failed",
                    "url": url,
                    "status_code": resp.status_code,
                    "content_length": len(resp.text),
                    "content_preview": content_preview
                }
        except Exception as e:
            logger.warning(f"Failed to retrieve context for {url}: {e}")
            return {
                "tool": "retrieve_source_context",
                "protocol": "mcp/1.0",
                "status": "partial",
                "url": url,
                "error": str(e)
            }

    async def _execute_google_fact_check(self, args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("query", "")).strip()
        results = await self.fact_check_client.search_fact_checks(query)
        return {
            "tool": "google_fact_check_search",
            "protocol": "mcp/1.0",
            "status": "success",
            "query": query,
            "count": len(results),
            "fact_checks": results
        }
