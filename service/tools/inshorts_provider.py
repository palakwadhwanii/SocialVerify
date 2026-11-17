import asyncio
import datetime
from datetime import timezone
import re
from typing import Any
import httpx
from tools.evidence_processor import EvidenceProcessor
from utils.logger import logger

INSHORTS_BASE_URL = "https://inshorts.com/api/en"

INSHORTS_HEADERS = {
    "authority": "inshorts.com",
    "accept": "*/*",
    "accept-language": "en-GB,en;q=0.5",
    "content-type": "application/json",
    "referer": "https://inshorts.com/en/read",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


class InshortsProvider:
    """Unofficial Inshorts News API wrapper based on cyberboysumanjay/Inshorts-News-API.
    
    Provides high-reliability, short 60-word verified news blurbs and primary
    publisher source URLs for cross-media claim verification and debunking.
    """

    def __init__(self, timeout_seconds: float = 10.0):
        self.timeout = timeout_seconds

    def _normalize_entry(self, news_obj: dict[str, Any]) -> dict[str, Any] | None:
        if not news_obj:
            return None
        title = (news_obj.get("title") or "").strip()
        url = news_obj.get("source_url") or news_obj.get("shortened_url")
        if not title or not url:
            return None

        content = (news_obj.get("content") or "").strip()
        author = news_obj.get("author_name") or "Inshorts Desk"
        source_name = news_obj.get("source_name") or "Inshorts Verified"

        # Convert epoch ms timestamp to ISO 8601 UTC
        published_at = None
        created_at = news_obj.get("created_at")
        if created_at and isinstance(created_at, (int, float)):
            try:
                published_at = datetime.datetime.fromtimestamp(created_at / 1000, tz=timezone.utc).isoformat()
            except Exception:
                published_at = None

        return {
            "title": title,
            "url": url,
            "source": source_name,
            "publisher": source_name,
            "body": content,
            "snippet": content,
            "published_at": published_at or "",
            "retrieved_at": datetime.datetime.now(timezone.utc).isoformat(),
            "author": author,
            "image": news_obj.get("image_url"),
            "inshorts_link": news_obj.get("shortened_url"),
            "read_more_url": news_obj.get("source_url"),
        }

    async def get_news_by_category(self, category: str = "all", limit: int = 10) -> list[dict[str, Any]]:
        """Fetch news by category conforming to Inshorts-News-API."""
        clean_cat = category.strip().lower()
        endpoint = f"{INSHORTS_BASE_URL}/news?category=all_news&max_limit={limit}&include_card_data=true"
        params = None

        if clean_cat not in {"all", "all_news", ""}:
            endpoint = f"{INSHORTS_BASE_URL}/search/trending_topics/{clean_cat}"
            params = {
                "category": "top_stories",
                "max_limit": str(limit),
                "include_card_data": "true",
            }

        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=INSHORTS_HEADERS) as client:
                resp = await client.get(endpoint, params=params)
                if resp.status_code != 200:
                    logger.warning(f"Inshorts category request failed with HTTP {resp.status_code}")
                    return []
                data = resp.json()
                news_list = data.get("data", {}).get("news_list", [])
                articles = []
                for entry in news_list:
                    norm = self._normalize_entry(entry.get("news_obj", {}))
                    if norm:
                        articles.append(norm)
                return articles[:limit]
        except Exception as e:
            logger.warning(f"Inshorts category '{category}' error: {e}")
            return []

    async def search_news(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search Inshorts trending topics and news headlines for a claim inquiry."""
        clean_query = query.strip()
        if not clean_query:
            return await self.get_news_by_category("all", limit)

        # Extract meaningful subject words
        words = [w.lower() for w in re.findall(r"[a-zA-Z0-9]{3,}", clean_query)]
        stopwords = {
            "the", "and", "for", "with", "news", "what", "when", "where", "which",
            "from", "have", "been", "official", "statement", "filing", "date", "find",
            "tell", "show", "check", "verify", "about", "this", "that", "these", "those"
        }
        search_terms = [w for w in words if w not in stopwords]
        if not search_terms:
            search_terms = words[:2]

        all_entries: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        async with httpx.AsyncClient(timeout=self.timeout, headers=INSHORTS_HEADERS) as client:
            # 1. Search trending topics for up to 3 topical terms
            for term in search_terms[:3]:
                try:
                    resp = await client.get(
                        f"{INSHORTS_BASE_URL}/search/trending_topics/{term}",
                        params={"category": "top_stories", "max_limit": str(limit), "include_card_data": "true"}
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        for entry in data.get("data", {}).get("news_list", []):
                            norm = self._normalize_entry(entry.get("news_obj", {}))
                            if norm and norm["url"] not in seen_urls:
                                seen_urls.add(norm["url"])
                                all_entries.append(norm)
                except Exception as ex:
                    logger.debug(f"Inshorts trending topic '{term}' query skipped: {ex}")

            # 2. Also check latest top_stories to find breaking news
            try:
                resp = await client.get(
                    f"{INSHORTS_BASE_URL}/news?category=top_stories&max_limit=15&include_card_data=true"
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for entry in data.get("data", {}).get("news_list", []):
                        norm = self._normalize_entry(entry.get("news_obj", {}))
                        if norm and norm["url"] not in seen_urls:
                            seen_urls.add(norm["url"])
                            all_entries.append(norm)
            except Exception as ex:
                logger.debug(f"Inshorts top_stories retrieval skipped: {ex}")

        # 3. Filter against inquiry relevance
        relevant_articles: list[dict[str, Any]] = []
        for art in all_entries:
            combined_text = f"{art['title']} {art['body']}"
            if EvidenceProcessor.is_post_relevant_to_query(combined_text, clean_query):
                relevant_articles.append(art)

        # If strict relevance gave 0, keep articles that match at least 1 keyword
        if not relevant_articles and all_entries:
            for art in all_entries:
                combined_lower = f"{art['title']} {art['body']}".lower()
                if any(t in combined_lower for t in search_terms):
                    relevant_articles.append(art)

        return relevant_articles[:limit]


inshorts_provider = InshortsProvider()

