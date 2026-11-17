import os
import re
import ipaddress
import urllib.parse
from typing import Any
import httpx
from tools.evidence_processor import EvidenceProcessor
from utils.logger import logger
from security.guardrails import InputGuardrail


# Default allowed instances
DEFAULT_APPROVED_INSTANCES = [
    "mastodon.social",
    "mastodon.online",
    "fosstodon.org",
    "masto.ai",
    "infosec.exchange"
]


def get_approved_instances() -> list[str]:
    raw = os.getenv("MASTODON_INSTANCES", "")
    if raw.strip():
        instances = [i.strip().lower() for i in raw.split(",") if i.strip()]
        return instances
    return DEFAULT_APPROVED_INSTANCES


def is_valid_instance_host(host: str, approved_instances: list[str]) -> bool:
    """Validate that the instance is an approved public hostname and not a private/internal SSRF target."""
    clean_host = host.strip().lower()

    # Disallow IP addresses directly
    try:
        ipaddress.ip_address(clean_host)
        return False  # Direct IP access blocked
    except ValueError:
        pass

    # Disallow localhost and internal domains
    if clean_host in {"localhost", "127.0.0.1", "::1"} or clean_host.endswith(".local") or clean_host.endswith(".internal"):
        return False

    # Standard DNS hostname regex
    if not re.match(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$", clean_host):
        return False

    # Check allowlist
    return clean_host in approved_instances


def strip_html_content(raw_html: str) -> str:
    """Safely convert Mastodon HTML content to clean plain text."""
    if not raw_html:
        return ""
    entities = {
        "amp": "&", "lt": "<", "gt": ">", "quot": '"', "#39": "'", "apos": "'", "nbsp": " "
    }
    cleaned = re.sub(r"</?(?:p|div|br)[^>]*>", "\n", raw_html, flags=re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    cleaned = re.sub(r"&(amp|lt|gt|quot|#39|apos|nbsp);", lambda m: entities.get(m.group(1), m.group(0)), cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


class MastodonProvider:
    """Official Mastodon REST API provider supporting multi-instance public search and normalization."""

    def __init__(
        self,
        instances: list[str] | None = None,
        access_token: str | None = None,
        timeout_seconds: float | None = None,
        timeout: float | None = None
    ):
        self.approved_instances = instances or get_approved_instances()
        self.access_token = access_token or os.getenv("MASTODON_ACCESS_TOKEN", "").strip()
        timeout_val = timeout if timeout is not None else (timeout_seconds if timeout_seconds is not None else float(os.getenv("MASTODON_REQUEST_TIMEOUT", "15")))
        self.timeout = min(max(timeout_val, 2.0), 30.0)

    def _headers(self) -> dict[str, str]:
        headers = {
            "User-Agent": "SocialVerify/1.0 (+https://socialverify.ai; multi-agent evidence engine)",
            "Accept": "application/json"
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    async def search_instance(
        self,
        instance: str,
        query: str,
        limit: int = 10
    ) -> dict[str, Any]:
        """Search a single approved Mastodon instance using official /api/v2/search."""
        clean_instance = instance.strip().lower()
        if not is_valid_instance_host(clean_instance, self.approved_instances):
            return {
                "instance": clean_instance,
                "status": "disallowed_instance",
                "error": f"Instance '{clean_instance}' is not in the approved instances list or is invalid.",
                "posts": []
            }

        endpoint = f"https://{clean_instance}/api/v2/search"
        params = {
            "q": query,
            "type": "statuses",
            "limit": str(min(max(limit, 1), 25)),
            "resolve": "true"
        }

        # Redact token from debug logs
        log_headers = {k: ("REDACTED" if k == "Authorization" else v) for k, v in self._headers().items()}
        logger.debug(f"Mastodon searching https://{clean_instance}/api/v2/search with params {params} (headers: {log_headers})")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(endpoint, params=params, headers=self._headers())

                if resp.status_code == 429:
                    logger.warning(f"Mastodon instance {clean_instance} returned rate limit (429)")
                    return {
                        "instance": clean_instance,
                        "status": "rate_limited",
                        "error": f"Rate limit reached on {clean_instance}",
                        "posts": []
                    }

                if resp.status_code == 401 or resp.status_code == 403:
                    logger.info(f"Mastodon instance {clean_instance} requires authentication for full-text search (HTTP {resp.status_code})")
                    # Fallback to public tag search if full-text search is restricted
                    return await self._search_via_tags(client, clean_instance, query, limit)

                if resp.status_code != 200:
                    return {
                        "instance": clean_instance,
                        "status": "http_error",
                        "error": f"Instance returned HTTP {resp.status_code}",
                        "posts": []
                    }

                data = resp.json()
                statuses = data.get("statuses", [])

                # Normalize statuses and strictly filter against the whole search query
                posts = [self._normalize_status(s, clean_instance) for s in statuses]
                posts = [p for p in posts if EvidenceProcessor.is_post_relevant_to_query(p["text"], query)]

                # If full-text search yielded 0 relevant posts, try tag search as fallback
                if not posts and not self.access_token:
                    logger.debug(f"Full-text search yielded 0 relevant statuses on {clean_instance}; attempting tag timeline fallback.")
                    return await self._search_via_tags(client, clean_instance, query, limit)

                status_str = "success" if posts else "empty"
                return {
                    "instance": clean_instance,
                    "status": status_str,
                    "count": len(posts),
                    "posts": posts
                }

        except httpx.TimeoutException:
            logger.warning(f"Timeout querying Mastodon instance {clean_instance} after {self.timeout}s")
            return {
                "instance": clean_instance,
                "status": "timeout",
                "error": f"Request to {clean_instance} timed out after {self.timeout}s",
                "posts": []
            }
        except Exception as e:
            logger.error(f"Error querying Mastodon instance {clean_instance}: {e}")
            return {
                "instance": clean_instance,
                "status": "error",
                "error": str(e),
                "posts": []
            }

    async def _search_via_tags(
        self,
        client: httpx.AsyncClient,
        instance: str,
        query: str,
        limit: int
    ) -> dict[str, Any]:
        """Fallback to public hashtag search and timeline retrieval when full-text search is unavailable without auth."""
        try:
            # 1. Search hashtags
            tag_resp = await client.get(
                f"https://{instance}/api/v2/search",
                params={"q": query, "type": "hashtags", "limit": "3"},
                headers=self._headers()
            )
            if tag_resp.status_code in {401, 403}:
                return {
                    "instance": instance,
                    "status": "restricted",
                    "error": f"Instance '{instance}' requires authentication or authorization (HTTP {tag_resp.status_code}).",
                    "posts": []
                }

            stopwords = {
                "about", "after", "against", "among", "been", "before", "being", "between",
                "could", "does", "during", "from", "have", "into", "more", "most", "over",
                "same", "some", "than", "that", "their", "there", "these", "they", "this",
                "those", "through", "under", "very", "were", "what", "when", "where", "which",
                "while", "with", "would", "your", "has", "had", "did", "does", "find", "check",
                "tell", "give", "show", "please", "official", "officially", "statement", "statements",
                "filing", "filings", "date", "dates", "the", "and", "for", "with", "news", "latest",
                "update", "updates", "today", "report", "reports", "say", "says", "said", "can",
                "will", "just", "also", "out", "now", "get", "who", "whom", "its", "it", "are",
                "was", "how", "why", "announce", "announces", "announced", "announcing",
                "announcement", "announcements", "unveil", "unveiled", "launch", "launched",
                "confirm", "confirmed", "claim", "claims", "rumour", "rumor"
            }
            meaningful_words = [
                w.lower() for w in re.findall(r"[a-zA-Z0-9]{2,}", query)
                if w.lower() not in stopwords
            ]

            tags_to_query: list[str] = []

            # A. Compound tags for multi-word queries (e.g. nepalfloods, nepalflood, jioipo, reliancejio)
            if len(meaningful_words) >= 2:
                compound = "".join(meaningful_words[:2])
                tags_to_query.append(compound)
                if len(meaningful_words) >= 3:
                    tags_to_query.append("".join(meaningful_words[1:3]))
                if meaningful_words[1].endswith("s") and len(meaningful_words[1]) > 3:
                    tags_to_query.append(meaningful_words[0] + meaningful_words[1][:-1])

            # B. API-suggested tags
            if tag_resp.status_code == 200:
                for t in tag_resp.json().get("hashtags", []):
                    name = t.get("name")
                    if name and name.lower() not in [x.lower() for x in tags_to_query]:
                        tags_to_query.append(name)

            # C. Individual meaningful words
            for w in meaningful_words[:3]:
                if w.lower() not in [x.lower() for x in tags_to_query]:
                    tags_to_query.append(w)

            if not tags_to_query:
                return {"instance": instance, "status": "empty", "posts": []}

            # 2. Retrieve public tag timelines
            collected_statuses = []
            for tag in tags_to_query[:4]:
                timeline_resp = await client.get(
                    f"https://{instance}/api/v1/timelines/tag/{urllib.parse.quote(tag)}",
                    params={"limit": str(limit * 2)},
                    headers=self._headers()
                )
                if timeline_resp.status_code == 200:
                    data = timeline_resp.json()
                    if isinstance(data, list):
                        collected_statuses.extend(data)

            # Deduplicate by ID
            seen_ids = set()
            unique_statuses = []
            for s in collected_statuses:
                sid = (s.get("reblog") or s).get("id")
                if sid and sid not in seen_ids:
                    seen_ids.add(sid)
                    unique_statuses.append(s)

            # Strict relevance check to ensure posts are related to the whole inquiry
            posts = []
            for s in unique_statuses:
                norm = self._normalize_status(s, instance)
                if EvidenceProcessor.is_post_relevant_to_query(norm["text"], query):
                    posts.append(norm)

            status_str = "success" if posts else "empty"
            return {
                "instance": instance,
                "status": status_str,
                "count": len(posts[:limit]),
                "posts": posts[:limit]
            }
        except Exception as e:
            return {
                "instance": instance,
                "status": "error",
                "error": f"Hashtag fallback failed: {e}",
                "posts": []
            }

    def _normalize_status(self, raw_status: dict[str, Any], instance_domain: str) -> dict[str, Any]:
        """Normalize raw Mastodon status into strict SocialVerify evidence schema."""
        status = raw_status.get("reblog") or raw_status
        account = status.get("account") or {}

        # Content parsing & security screening
        raw_content = status.get("content") or ""
        text = strip_html_content(raw_content) or status.get("spoiler_text") or "Public post"

        # Prompt-injection screening on untrusted post body
        is_safe, injection_reason = InputGuardrail.check_for_prompt_injection(text)
        if not is_safe:
            logger.warning(f"Neutralized prompt injection in Mastodon post {status.get('id')}: {injection_reason}")
            text = f"[Untrusted content flagged: {injection_reason}]"

        username = account.get("username", "anonymous")
        acct = account.get("acct") or username
        author_handle = f"@{acct}" if "@" in acct else f"@{acct}@{instance_domain}"

        # Status URL
        status_url = status.get("url") or status.get("uri") or f"https://{instance_domain}/@{username}/{status.get('id')}"

        published_at = status.get("created_at") or ""
        import datetime
        retrieved_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        def _safe_int(val: Any) -> int:
            try:
                return int(val)
            except (ValueError, TypeError):
                return 0

        engagement = {
            "replies": _safe_int(status.get("replies_count")),
            "reblogs": _safe_int(status.get("reblogs_count")),
            "favourites": _safe_int(status.get("favourites_count"))
        }

        # Quality rationale
        quality_rationale = (
            f"Public post retrieved from federated Mastodon instance '{instance_domain}'. "
            f"Visibility depends on local and federated instance timeline indexing. "
            f"Engagement represents individual user interactions, not factual corroboration."
        )

        return {
            "source_type": "social",
            "platform": "mastodon",
            "title": text[:140] if text else "Mastodon post",
            "text": text,
            "url": status_url,
            "instance_domain": instance_domain,
            "author": author_handle,
            "display_name": account.get("display_name") or username,
            "published_at": published_at,
            "retrieved_at": retrieved_at,
            "engagement": engagement,
            "relationship_to_claim": "unassessed",
            "source_quality_rationale": quality_rationale,
            "retrieval_status": "success",
            "provenance": {
                "instance": instance_domain,
                "status_id": str(status.get("id")),
                "api_endpoint": f"https://{instance_domain}/api/v2/search"
            }
        }

    async def search_all_instances(self, query: str, limit_per_instance: int = 5) -> dict[str, Any]:
        """Search across all approved Mastodon instances concurrently."""
        import asyncio
        tasks = [self.search_instance(inst, query, limit_per_instance) for inst in self.approved_instances]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_posts = []
        instance_reports = []

        for inst, res in zip(self.approved_instances, results):
            if isinstance(res, Exception):
                instance_reports.append({"instance": inst, "status": "exception", "error": str(res)})
            else:
                instance_reports.append({
                    "instance": inst,
                    "status": res.get("status"),
                    "count": res.get("count", 0),
                    "error": res.get("error")
                })
                all_posts.extend(res.get("posts", []))

        # Deduplicate posts by URL
        seen_urls = set()
        deduped_posts = []
        for p in all_posts:
            if p["url"] not in seen_urls:
                seen_urls.add(p["url"])
                deduped_posts.append(p)

        return {
            "query": query,
            "total_posts": len(deduped_posts),
            "posts": deduped_posts,
            "instances_searched": instance_reports
        }


mastodon_provider = MastodonProvider()
