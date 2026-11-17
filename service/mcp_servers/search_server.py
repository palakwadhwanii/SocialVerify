import asyncio
import re
from html import unescape
from datetime import datetime, timezone
from typing import Any
import httpx
from duckduckgo_search import DDGS
from config import SERVER_BASE_URL, MCP_TOOL_TIMEOUT_SECONDS
from utils.logger import logger
from tools.evidence_processor import EvidenceProcessor
from tools.mastodon import mastodon_provider
from tools.inshorts_provider import inshorts_provider

# MCP Tool definitions conforming to Model Context Protocol specification
SEARCH_TOOLS_SCHEMA = [
    {
        "name": "search_news",
        "description": "Collect recent journalism and news articles for a given topic via MCP.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search topic or claim to investigate."},
                "page_size": {"type": "integer", "description": "Number of articles to retrieve (1-20).", "default": 10},
                "language": {"type": "string", "description": "ISO language code, e.g. 'en'.", "default": "en"},
                "sort_by": {"type": "string", "enum": ["relevancy", "popularity", "publishedAt"], "default": "publishedAt"},
                "from": {"type": "string", "description": "Inclusive publication date (YYYY-MM-DD)."},
                "to": {"type": "string", "description": "Inclusive publication date (YYYY-MM-DD)."}
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_inshorts_news",
        "description": "Collect verified short news summaries, primary publisher sources, and breaking reports from Inshorts via Inshorts-News-API.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search topic or claim to investigate."},
                "category": {"type": "string", "description": "News category (e.g. all, national, business, sports, technology, world).", "default": "all"},
                "limit": {"type": "integer", "description": "Max articles to retrieve (1-20).", "default": 10}
            }
        }
    },
    {
        "name": "search_social_posts",
        "description": "Collect public social media posts across Mastodon and Reddit via MCP.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of search terms or claim keywords."
                },
                "platforms": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["mastodon", "reddit", "bluesky"]},
                    "description": "Target social platforms."
                },
                "limit": {"type": "integer", "description": "Max posts to retrieve (1-25).", "default": 10}
            },
            "required": ["topics"]
        }
    },
    {
        "name": "web_search",
        "description": "General web search API for finding evidence, reporting, and documents related to claims via MCP.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query terms."},
                "max_results": {"type": "integer", "description": "Number of results to return (1-20).", "default": 10}
            },
            "required": ["query"]
        }
    }
]


class SearchMCPServer:
    """MCP Server exposing news, social-media, and web search tools."""

    def __init__(self, server_base_url: str = SERVER_BASE_URL):
        self.server_base_url = server_base_url
        self.name = "socialverify-search-mcp"
        self.version = "1.0.0"

    def list_tools(self) -> list[dict[str, Any]]:
        """MCP tools/list handler."""
        return SEARCH_TOOLS_SCHEMA

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        access_token: str | None = None
    ) -> dict[str, Any]:
        """MCP tools/call handler."""
        if name == "search_news":
            return await self._execute_search_news(arguments, access_token)
        elif name == "search_inshorts_news":
            return await self._execute_search_inshorts(arguments)
        elif name == "search_social_posts":
            return await self._execute_search_social(arguments, access_token)
        elif name == "web_search":
            return await self._execute_web_search(arguments)
        else:
            raise ValueError(f"Unknown MCP tool: {name}")

    async def _execute_web_search(self, args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("query", "")).strip()
        max_results = min(max(int(args.get("max_results", 10)), 1), 20)
        try:
            loop = asyncio.get_running_loop()
            def _ddgs_web():
                with DDGS() as ddgs:
                    return list(ddgs.text(query, max_results=max_results))
            results = await loop.run_in_executor(None, _ddgs_web)
            items = []
            for r in results:
                items.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", "")
                })
            return {
                "tool": "web_search",
                "protocol": "mcp/1.0",
                "status": "success",
                "count": len(items),
                "results": items
            }
        except Exception as e:
            logger.error(f"MCP web_search error: {e}")
            return {
                "tool": "web_search",
                "protocol": "mcp/1.0",
                "status": "partial",
                "count": 0,
                "results": [],
                "error": str(e)
            }

    async def _execute_search_news(
        self,
        args: dict[str, Any],
        access_token: str | None
    ) -> dict[str, Any]:
        query = str(args.get("query", "")).strip()
        page_size = min(max(int(args.get("page_size", 10)), 1), 20)
        language = str(args.get("language", "en"))
        sort_by = str(args.get("sort_by", "publishedAt"))
        from_date = args.get("from")
        to_date = args.get("to")

        # First try Server API if authenticated
        if access_token:
            try:
                async with httpx.AsyncClient(timeout=MCP_TOOL_TIMEOUT_SECONDS) as client:
                    resp = await client.get(
                        f"{self.server_base_url}/api/news/search",
                        headers={"Authorization": f"Bearer {access_token}"},
                        params={
                            "q": query,
                            "pageSize": page_size,
                            "language": language,
                            "sortBy": sort_by,
                            **({"from": from_date} if from_date else {}),
                            **({"to": to_date} if to_date else {}),
                        }
                    )
                    if resp.status_code == 200:
                        data = resp.json().get("data", {})
                        articles = data.get("articles", [])
                        if articles:
                            return {
                                "tool": "search_news",
                                "protocol": "mcp/1.0",
                                "status": "success",
                                "count": len(articles),
                                "articles": articles,
                                "errors": data.get("errors", []),
                            }
            except Exception as e:
                logger.warning(f"Server API news search failed, falling back to direct Bing News search: {e}")

        combined_articles: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        # 1. Primary news search using Inshorts API wrapper (cyberboysumanjay/Inshorts-News-API)
        try:
            inshorts_articles = await inshorts_provider.search_news(query, limit=page_size)
            for art in inshorts_articles:
                url = art.get("url")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    combined_articles.append(art)
        except Exception as e:
            logger.debug(f"Inshorts search encountered an issue: {e}")

        # 2. Web news search using direct Bing News card extraction
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            }
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(
                    "https://www.bing.com/news/search",
                    params={"q": query},
                    headers=headers
                )
                if resp.status_code == 200:
                    html_text = resp.text
                    card_pattern = re.compile(
                        r'<div[^>]*class=\"[^\"]*news-card[^\"]*\"[^>]*data-url=\"([^\"]+)\"[^>]*data-title=\"([^\"]+)\"[^>]*data-author=\"([^\"]+)\"(.*?)(?=<div[^>]*class=\"[^\"]*news-card|\Z)',
                        re.DOTALL | re.IGNORECASE
                    )
                    for m in card_pattern.finditer(html_text):
                        url = m.group(1).strip()
                        title = unescape(m.group(2).strip())
                        author = unescape(m.group(3).strip())
                        rest = m.group(4)
                        snippet_match = re.search(r'<div[^>]*class=\"[^\"]*snippet[^\"]*\"[^>]*title=\"([^\"]+)\"', rest)
                        if not snippet_match:
                            snippet_match = re.search(r'<div[^>]*class=\"[^\"]*snippet[^\"]*\"[^>]*>(.*?)</div>', rest, re.DOTALL)
                            snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip() if snippet_match else ""
                        else:
                            snippet = snippet_match.group(1).strip()

                        if url and title and url not in seen_urls:
                            seen_urls.add(url)
                            combined_articles.append({
                                "title": title,
                                "url": url,
                                "source": author or "Authoritative News",
                                "publisher": author or "Authoritative News",
                                "published_at": "",
                                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                                "body": snippet,
                                "snippet": snippet,
                            })
                            if len(combined_articles) >= page_size:
                                break

        except Exception as e:
            logger.warning(f"Direct Bing news search encountered an issue: {e}")

        if combined_articles:
            return {
                "tool": "search_news",
                "protocol": "mcp/1.0",
                "status": "success",
                "count": len(combined_articles[:page_size]),
                "articles": combined_articles[:page_size],
                "errors": [],
            }

        # Fallback to DDGS text/news search
        try:
            loop = asyncio.get_running_loop()
            def _ddgs_fallback():
                with DDGS() as ddgs:
                    try:
                        return list(ddgs.news(query, max_results=page_size))
                    except Exception:
                        return list(ddgs.text(f"{query} news", max_results=page_size))
            results = await loop.run_in_executor(None, _ddgs_fallback)
            
            articles = []
            for item in results:
                title = item.get("title", "")
                url = item.get("url") or item.get("href", "")
                if url and title:
                    articles.append({
                        "title": title,
                        "url": url,
                        "source": item.get("source", "Web News"),
                        "publisher": item.get("source", "Web News"),
                        "published_at": item.get("date", ""),
                        "retrieved_at": datetime.now(timezone.utc).isoformat(),
                        "body": item.get("body", ""),
                        "snippet": item.get("body", "")
                    })
            return {
                "tool": "search_news",
                "protocol": "mcp/1.0",
                "status": "success",
                "count": len(articles),
                "articles": articles,
                "errors": [
                    "Authenticated news API unavailable; using fallback news search."
                ],
            }
        except Exception as e:
            logger.error(f"MCP search_news execution error: {e}")
            return {
                "tool": "search_news",
                "protocol": "mcp/1.0",
                "status": "partial",
                "count": 0,
                "articles": [],
                "error": str(e)
            }

    async def _execute_search_inshorts(self, args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("query", "")).strip()
        category = str(args.get("category", "all")).strip()
        limit = min(max(int(args.get("limit", 10)), 1), 20)
        try:
            if query:
                articles = await inshorts_provider.search_news(query, limit=limit)
            else:
                articles = await inshorts_provider.get_news_by_category(category, limit=limit)
            return {
                "tool": "search_inshorts_news",
                "protocol": "mcp/1.0",
                "status": "success",
                "count": len(articles),
                "articles": articles,
                "errors": [],
            }
        except Exception as e:
            logger.error(f"Inshorts tool execution error: {e}")
            return {
                "tool": "search_inshorts_news",
                "protocol": "mcp/1.0",
                "status": "partial",
                "count": 0,
                "articles": [],
                "error": str(e),
            }

    async def _execute_search_social(
        self,
        args: dict[str, Any],
        access_token: str | None
    ) -> dict[str, Any]:
        topics = args.get("topics", [])
        if isinstance(topics, str):
            topics = [topics]
        platforms = args.get("platforms") or ["mastodon", "reddit", "bluesky"]
        limit = min(max(int(args.get("limit", 10)), 1), 25)

        # Use the primary whole search inquiry as the search keyword
        clean_topics = [t.strip() for t in topics if t.strip()]
        query_str = clean_topics[0] if clean_topics else ""

        # First try Server API if authenticated
        if access_token:
            try:
                async with httpx.AsyncClient(timeout=MCP_TOOL_TIMEOUT_SECONDS) as client:
                    resp = await client.post(
                        f"{self.server_base_url}/api/social/search",
                        headers={"Authorization": f"Bearer {access_token}"},
                        json={"topics": [query_str] if query_str else topics, "platforms": platforms, "limit": limit}
                    )
                    if resp.status_code == 200:
                        data = resp.json().get("data", {})
                        posts = data.get("posts", [])
                        return {
                            "tool": "search_social_posts",
                            "protocol": "mcp/1.0",
                            "status": "success",
                            "count": len(posts),
                            "posts": posts,
                            "errors": data.get("errors", []),
                        }
            except Exception as e:
                logger.warning(f"Server API social search failed, falling back to direct Mastodon provider: {e}")

        # Real Mastodon REST API provider execution
        try:
            mastodon_results = await mastodon_provider.search_all_instances(query_str, limit_per_instance=max(2, limit // 2))
            posts = list(mastodon_results.get("posts", []))

            # If additional social context is helpful, search public forum discussions
            if len(posts) < limit and query_str:
                try:
                    loop = asyncio.get_running_loop()
                    ddg_query = f"{query_str} (site:mastodon.social OR site:reddit.com)"
                    def _ddgs_text():
                        with DDGS() as ddgs:
                            return list(ddgs.text(ddg_query, max_results=limit - len(posts)))
                    extra_results = await loop.run_in_executor(None, _ddgs_text)
                    for item in extra_results:
                        url = item.get("href", "")
                        body = item.get("body", "")
                        title = item.get("title", "")
                        combined = f"{title} {body}"
                        if not EvidenceProcessor.is_post_relevant_to_query(combined, query_str):
                            continue
                        platform = "reddit" if "reddit.com" in url else "mastodon"
                        inst = "reddit.com" if platform == "reddit" else "mastodon.social"
                        posts.append({
                            "source_type": "social",
                            "platform": platform,
                            "title": title,
                            "url": url,
                            "text": body,
                            "instance_domain": inst,
                            "author": "public_user@" + inst,
                            "published_at": "",
                            "retrieved_at": datetime.now(timezone.utc).isoformat(),
                            "engagement": {"replies": 0, "reblogs": 0, "favourites": 0}
                        })
                except Exception as ex:
                    logger.debug(f"DDGS supplementary search omitted: {ex}")

            return {
                "tool": "search_social_posts",
                "protocol": "mcp/1.0",
                "status": "success",
                "count": len(posts),
                "posts": posts,
                "instances_searched": mastodon_results.get("instances_searched", []),
                "errors": [
                    {"platform": "mastodon", "message": item.get("error")}
                    for item in mastodon_results.get("instances_searched", [])
                    if item.get("error")
                ],
            }
        except Exception as e:
            logger.error(f"MCP search_social_posts execution error: {e}")
            return {
                "tool": "search_social_posts",
                "protocol": "mcp/1.0",
                "status": "partial",
                "count": 0,
                "posts": [],
                "error": str(e)
            }
