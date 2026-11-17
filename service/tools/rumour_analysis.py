from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9'-]{2,}", re.IGNORECASE)
STOP_WORDS = {
    "about", "after", "against", "among", "been", "before", "being", "between",
    "could", "does", "during", "from", "have", "into", "more", "most", "over",
    "same", "some", "than", "that", "their", "there", "these", "they", "this",
    "those", "through", "under", "very", "were", "what", "when", "where", "which",
    "while", "with", "would", "your", "has", "had", "did", "does", "find", "check",
    "tell", "give", "show", "please", "official", "statement", "filing", "date",
}
TRACKING_PARAMETERS = {"fbclid", "gclid", "ref", "source"}


def _tokens(value: str) -> set[str]:
    return {
        token.lower()
        for token in TOKEN_PATTERN.findall(value)
        if token.lower() not in STOP_WORDS
    }


def _clean_url(value: str) -> str:
    try:
        parts = urlsplit(value)
    except ValueError:
        return value.strip()
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return value.strip()
    query = urlencode(
        [
            (key, val)
            for key, val in parse_qsl(parts.query, keep_blank_values=True)
            if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMETERS
        ]
    )
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), query, ""))


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        result = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if result.tzinfo is None:
        return result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _iso_or_none(value: Any) -> str | None:
    parsed = _parse_timestamp(value)
    return parsed.isoformat().replace("+00:00", "Z") if parsed else None


def within_window_or_undated(
    item: dict[str, Any],
    start: datetime,
    end: datetime,
) -> bool:
    timestamp = _parse_timestamp(item.get("published_at") or item.get("publishedAt"))
    return timestamp is None or start <= timestamp <= end


def generate_search_variations(query: str, entities: list[str] | None = None) -> list[str]:
    original = " ".join(query.split())
    variations = [original] if original else []
    entity_query = " ".join(dict.fromkeys((entities or [])[:4])).strip()
    if entity_query and entity_query.lower() != original.lower():
        variations.append(entity_query)
    keywords = [word for word in TOKEN_PATTERN.findall(original) if word.lower() not in STOP_WORDS]
    focused = " ".join(dict.fromkeys(keywords[:6]))
    if focused and focused.lower() not in {item.lower() for item in variations}:
        variations.append(focused)
    return variations[:3]


def _normalize_record(item: dict[str, Any], category: str, now: datetime) -> dict[str, Any] | None:
    url = item.get("url") or item.get("source_url")
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return None
    title = str(item.get("title") or "").strip()
    content = str(
        item.get("text") or item.get("content") or item.get("description") or item.get("body") or title
    ).strip()
    normalized_url = _clean_url(url)
    published_at = _iso_or_none(item.get("published_at") or item.get("publishedAt"))
    retrieved_at = _iso_or_none(item.get("retrieved_at") or item.get("retrievedAt")) or now.isoformat().replace("+00:00", "Z")
    record_id = hashlib.sha256(f"{category}:{normalized_url}".encode()).hexdigest()[:20]
    return {
        "id": record_id,
        "category": category,
        "platform": str(item.get("platform") or (item.get("source") if category == "news" else "social")),
        "title": title or content[:160],
        "content": content,
        "url": url,
        "published_at": published_at,
        "retrieved_at": retrieved_at,
        "author": item.get("author"),
        "publisher": item.get("publisher") or item.get("source"),
        "_normalized_url": normalized_url,
    }


def _cluster_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    parents = list(range(len(records)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for left in range(len(records)):
        left_tokens = _tokens(f"{records[left]['title']} {records[left]['content']}")
        if not left_tokens:
            continue
        for right in range(left + 1, len(records)):
            right_tokens = _tokens(f"{records[right]['title']} {records[right]['content']}")
            shared = left_tokens & right_tokens
            union = left_tokens | right_tokens
            if shared and len(shared) / max(len(union), 1) >= 0.22:
                root_left, root_right = find(left), find(right)
                if root_left != root_right:
                    parents[root_right] = root_left

    groups: dict[int, list[dict[str, Any]]] = {}
    for index, record in enumerate(records):
        groups.setdefault(find(index), []).append(record)

    clusters = []
    for group in groups.values():
        cluster_id = hashlib.sha256("|".join(sorted(item["id"] for item in group)).encode()).hexdigest()[:16]
        clusters.append({
            "id": cluster_id,
            "record_ids": [item["id"] for item in group],
            "record_count": len(group),
        })
    return clusters


def analyze_rumour(
    query: str,
    news_articles: list[dict[str, Any]],
    social_posts: list[dict[str, Any]],
    window_days: int = 30,
    now: datetime | None = None,
    source_errors: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    if not 1 <= window_days <= 365:
        raise ValueError("window_days must be between 1 and 365")

    end = now or datetime.now(timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    end = end.astimezone(timezone.utc)
    start = end - timedelta(days=window_days)
    start_date = start.date()
    end_date = end.date()

    records_by_url: dict[str, dict[str, Any]] = {}
    news_headlines: dict[str, dict[str, Any]] = {}
    duplicate_count = 0
    for category, items in (("news", news_articles), ("social", social_posts)):
        for item in items:
            record = _normalize_record(item, category, end)
            if not record:
                continue
            key = record["_normalized_url"]
            headline_key = " ".join(_tokens(record["title"])) if category == "news" else ""
            duplicate = records_by_url.get(key) or news_headlines.get(headline_key)
            if duplicate:
                duplicate_count += 1
                duplicate["duplicate_sources"].append({
                    "url": record["url"],
                    "published_at": record["published_at"],
                    "retrieved_at": record["retrieved_at"],
                    "publisher": record["publisher"],
                })
                continue
            record["duplicate_sources"] = []
            records_by_url[key] = record
            if headline_key:
                news_headlines[headline_key] = record

    records = list(records_by_url.values())
    for record in records:
        record.pop("_normalized_url", None)
    clusters = _cluster_records(records)
    cluster_by_record = {
        record_id: cluster["id"]
        for cluster in clusters
        for record_id in cluster["record_ids"]
    }
    for record in records:
        record["cluster_id"] = cluster_by_record[record["id"]]

    dated_records: list[tuple[dict[str, Any], datetime]] = []
    missing_timestamp = 0
    outside_window = 0
    for record in records:
        timestamp = _parse_timestamp(record["published_at"])
        if timestamp is None:
            record["window_status"] = "timestamp_unavailable"
            missing_timestamp += 1
        elif start <= timestamp <= end:
            record["window_status"] = "in_window"
            dated_records.append((record, timestamp))
        else:
            record["window_status"] = "outside_window"
            outside_window += 1

    earliest_candidates = [
        (record, timestamp, record["platform"])
        for record, timestamp in dated_records
    ]
    for record in records:
        for duplicate in record["duplicate_sources"]:
            timestamp = _parse_timestamp(duplicate["published_at"])
            if timestamp and start <= timestamp <= end:
                earliest_candidates.append((record, timestamp, duplicate["publisher"] or record["platform"]))
    earliest_pair = min(earliest_candidates, key=lambda pair: pair[1], default=None)
    earliest_source = None
    if earliest_pair:
        record, timestamp, platform = earliest_pair
        earliest_source = {
            "label": "Earliest source found",
            "category": record["category"],
            "platform": str(platform),
            "content": record["content"],
            "published_at": timestamp.isoformat().replace("+00:00", "Z"),
            "url": next(
                (
                    duplicate["url"]
                    for duplicate in record["duplicate_sources"]
                    if duplicate["url"] and _parse_timestamp(duplicate["published_at"]) == timestamp
                ),
                record["url"],
            ),
            "confidence_note": "Earliest timestamp among matching records collected in this investigation window; this does not establish the actual first person or original publication.",
        }

    hourly = window_days <= 3
    if hourly:
        bucket_start = start.replace(minute=0, second=0, microsecond=0)
        bucket_end = end.replace(minute=0, second=0, microsecond=0)
        step = timedelta(hours=1)
    else:
        bucket_start = datetime.combine(start_date, datetime.min.time(), timezone.utc)
        bucket_end = datetime.combine(end_date, datetime.min.time(), timezone.utc)
        step = timedelta(days=1)

    counts: dict[str, dict[str, int]] = {}
    cursor = bucket_start
    while cursor <= bucket_end:
        counts[cursor.isoformat().replace("+00:00", "Z")] = {"social_media": 0, "news_media": 0}
        cursor += step
    for record, timestamp in dated_records:
        bucket = timestamp.replace(minute=0, second=0, microsecond=0) if hourly else datetime.combine(
            timestamp.date(), datetime.min.time(), timezone.utc
        )
        key = bucket.isoformat().replace("+00:00", "Z")
        series = counts.get(key)
        if series is not None:
            series["social_media" if record["category"] == "social" else "news_media"] += 1

    timeline = [
        {"timestamp": timestamp, **values}
        for timestamp, values in counts.items()
    ]
    totals = {
        "social_media": sum(item["social_media"] for item in timeline),
        "news_media": sum(item["news_media"] for item in timeline),
    }
    total_activity = [item["social_media"] + item["news_media"] for item in timeline]
    change = "stable"
    if len(total_activity) > 1:
        if total_activity[-1] > total_activity[-2]:
            change = "increasing"
        elif total_activity[-1] < total_activity[-2]:
            change = "decreasing"

    source_errors = source_errors or []
    return {
        "window": {
            "start": start.isoformat().replace("+00:00", "Z"),
            "end": end.isoformat().replace("+00:00", "Z"),
            "days": window_days,
            "interval": "hour" if hourly else "day",
        },
        "source_records": records,
        "rumour_clusters": clusters,
        "earliest_source": earliest_source,
        "spread": {
            "timeline": timeline,
            "unique_records": totals,
            "total_unique_records": sum(totals.values()),
            "activity_change": change,
            "record_count_outside_window": outside_window,
            "records_missing_publication_time": missing_timestamp,
            "duplicate_records_removed": duplicate_count,
        },
        "data_coverage": {
            "records_collected": len(records),
            "timestamped_records_in_window": len(dated_records),
            "timestamp_coverage": round(
                (len(dated_records) + outside_window) / len(records), 4
            ) if records else 0.0,
            "source_errors": source_errors,
        },
    }
