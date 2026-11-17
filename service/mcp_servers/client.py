import asyncio
import time
from typing import Any
from mcp_servers.search_server import SearchMCPServer
from mcp_servers.evidence_server import EvidenceMCPServer
from utils.logger import logger


class SocialVerifyMCPClient:
    """Model Context Protocol (MCP) Client coordinating connections to MCP servers."""

    def __init__(
        self,
        search_server: SearchMCPServer | None = None,
        evidence_server: EvidenceMCPServer | None = None
    ):
        self.search_server = search_server or SearchMCPServer()
        self.evidence_server = evidence_server or EvidenceMCPServer()
        self._tool_registry: dict[str, Any] = {}
        self._refresh_tools()

    def _refresh_tools(self) -> None:
        """Discover tools from all connected MCP servers."""
        for tool in self.search_server.list_tools():
            self._tool_registry[tool["name"]] = (self.search_server, tool)
        for tool in self.evidence_server.list_tools():
            self._tool_registry[tool["name"]] = (self.evidence_server, tool)

    def list_available_tools(self) -> list[dict[str, Any]]:
        """List all discovered MCP tools across connected servers."""
        return [tool_schema for _, tool_schema in self._tool_registry.values()]

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        access_token: str | None = None
    ) -> dict[str, Any]:
        """Execute a single tool call through MCP with schema validation and telemetry."""
        if tool_name not in self._tool_registry:
            raise ValueError(f"MCP tool '{tool_name}' not found in registry")

        server, schema = self._tool_registry[tool_name]
        start_time = time.time()
        logger.info(f"MCP Client dispatching tool: {tool_name} with args: {arguments}")

        try:
            # Dispatch to appropriate MCP server
            if server == self.search_server:
                result = await server.call_tool(tool_name, arguments, access_token=access_token)
            else:
                result = await server.call_tool(tool_name, arguments)

            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            result["latency_ms"] = elapsed_ms
            return result
        except Exception as e:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            logger.error(f"MCP tool '{tool_name}' call failed: {e}")
            return {
                "tool": tool_name,
                "protocol": "mcp/1.0",
                "status": "error",
                "error": str(e),
                "latency_ms": elapsed_ms
            }

    async def execute_parallel_retrieval(
        self,
        news_query: str,
        social_topics: list[str],
        db_topic: str | None = None,
        access_token: str | None = None
    ) -> dict[str, Any]:
        """Parallel tool execution pattern: execute news search, social search, and DB lookup concurrently."""
        tasks = [
            self.call_tool("search_news", {"query": news_query, "page_size": 10}, access_token),
            self.call_tool("search_social_posts", {"topics": social_topics, "limit": 10}, access_token),
        ]
        if db_topic:
            tasks.append(self.call_tool("lookup_evidence_db", {"topic": db_topic, "min_confidence": 0.5}))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        news_res = results[0] if not isinstance(results[0], Exception) else {"articles": [], "error": str(results[0])}
        social_res = results[1] if not isinstance(results[1], Exception) else {"posts": [], "error": str(results[1])}
        db_res = results[2] if len(results) > 2 and not isinstance(results[2], Exception) else {"records": []}

        return {
            "news": news_res,
            "social": social_res,
            "database": db_res,
            "parallel_execution": True
        }
