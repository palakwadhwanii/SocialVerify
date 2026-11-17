import base64
import json
import re
from datetime import datetime, timezone

import pytest

from agents.crewai_coordinator import (
    _append_investigation_data,
    render_markdown_brief,
)
from tools.rumour_analysis import analyze_rumour, generate_search_variations
from schemas.report import (
    ClaimAssessment,
    EvidenceSource,
    EvaluationMetric,
    RumourInvestigationData,
)


def test_search_variations_are_bounded_and_remove_empty_tokens():
    assert generate_search_variations("  River Delta flood warning  ", ["River Delta"]) == [
        "River Delta flood warning",
        "River Delta",
        "River Delta flood warning",
    ][:2]


def test_deduplicates_records_and_finds_earliest_source_without_fabricating_dates():
    result = analyze_rumour(
        "River Delta flood warning",
        news_articles=[
            {
                "title": "River Delta flood warning issued",
                "url": "https://news.example/story?utm_source=feed",
                "publishedAt": "2026-10-30T12:00:00Z",
                "retrievedAt": "2026-11-01T10:00:00Z",
            },
            {
                "title": "River Delta flood warning issued",
                "url": "https://copy.example/story",
                "publishedAt": "2026-10-31T12:00:00Z",
            },
        ],
        social_posts=[
            {
                "platform": "bluesky",
                "content": "River Delta flood warning is being shared",
                "url": "https://bsky.app/profile/a.example/post/1",
                "publishedAt": "2026-10-29T10:00:00Z",
            },
            {
                "platform": "mastodon",
                "content": "An undated River Delta flood warning post",
                "url": "https://mastodon.example/@a/2",
                "publishedAt": None,
            },
        ],
        window_days=7,
        now=datetime(2026, 11, 2, 12, tzinfo=timezone.utc),
    )

    assert result["spread"]["total_unique_records"] == 2
    assert result["spread"]["duplicate_records_removed"] == 1
    assert result["spread"]["records_missing_publication_time"] == 1
    assert result["earliest_source"]["label"] == "Earliest source found"
    assert result["earliest_source"]["platform"] == "bluesky"
    assert result["earliest_source"]["published_at"] == "2026-10-29T10:00:00Z"
    assert result["spread"]["unique_records"] == {"social_media": 1, "news_media": 1}
    assert sum(point["news_media"] for point in result["spread"]["timeline"]) == 1
    assert result["source_records"][0]["retrieved_at"] == "2026-11-01T10:00:00Z"
    assert result["source_records"][0]["duplicate_sources"][0]["url"] == "https://copy.example/story"
    validated = RumourInvestigationData.model_validate(result)
    assert validated.spread.total_unique_records == 2


def test_missing_timestamps_and_empty_results_produce_empty_timeline_counts():
    result = analyze_rumour(
        "No matching records",
        news_articles=[],
        social_posts=[{
            "url": "https://social.example/post/1",
            "content": "No timestamp",
        }],
        window_days=30,
        now=datetime(2026, 11, 2, 12, tzinfo=timezone.utc),
    )
    assert result["earliest_source"] is None
    assert result["spread"]["total_unique_records"] == 0
    assert result["spread"]["records_missing_publication_time"] == 1
    assert result["data_coverage"]["timestamp_coverage"] == 0


def test_out_of_window_records_are_retained_but_excluded_from_spread_and_earliest():
    result = analyze_rumour(
        "River Delta flood warning",
        news_articles=[{
            "title": "River Delta flood warning archive",
            "url": "https://news.example/old",
            "publishedAt": "2026-09-01T10:00:00Z",
        }],
        social_posts=[],
        window_days=7,
        now=datetime(2026, 11, 2, 12, tzinfo=timezone.utc),
    )
    assert result["earliest_source"] is None
    assert result["spread"]["total_unique_records"] == 0
    assert result["spread"]["record_count_outside_window"] == 1
    assert result["source_records"][0]["window_status"] == "outside_window"


def test_window_bounds_are_validated():
    with pytest.raises(ValueError):
        analyze_rumour("claim", [], [], window_days=0)


def test_report_contains_visible_sources_and_recoverable_structured_analysis():
    data = RumourInvestigationData.model_validate(analyze_rumour(
        "River Delta flood warning",
        news_articles=[{
            "title": "River Delta flood warning report",
            "url": "https://news.example/story",
            "publishedAt": "2026-10-30T12:00:00Z",
            "retrievedAt": "2026-11-02T10:00:00Z",
        }],
        social_posts=[],
        window_days=7,
        now=datetime(2026, 11, 2, 12, tzinfo=timezone.utc),
    ))
    data = data.model_copy(update={
        "verification_status": "Unverified",
        "verification_summary": "Available evidence does not establish the claim.",
        "human_review_required": True,
        "review_reasons": ["More independent sources are needed."],
    })
    report = _append_investigation_data("# Brief", data, "Unverified")
    match = re.search(r"<!-- socialverify-investigation:v1:([A-Za-z0-9_-]+) -->", report)

    assert match
    encoded = match.group(1)
    recovered = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
    assert recovered["spread"]["total_unique_records"] == 1
    assert recovered["verification_status"] == "Unverified"
    assert recovered["verification_summary"] == "Available evidence does not establish the claim."
    assert recovered["human_review_required"] is True
    assert recovered["review_reasons"] == ["More independent sources are needed."]
    assert "**Earliest source found:**" in report
    assert "news.example/story" in report
    assert "In everyday language" in report
    assert "publication date" in report
    assert "| Interval (UTC) |" not in report


def test_report_places_graph_after_first_social_post_and_uses_claim_confidence():
    report = render_markdown_brief(
        query="Jio IPO",
        summary="There is not enough evidence to confirm the claim.",
        claims=[ClaimAssessment(
            claim="Jio IPO",
            assessment="insufficient_evidence",
            confidence=0.0,
        )],
        sources=[
            EvidenceSource(
                source_type="news",
                title="News report",
                url="https://news.example/story",
            ),
            EvidenceSource(
                source_type="social",
                title="Public post",
                url="https://social.example/post/1",
            ),
        ],
        metrics=EvaluationMetric(
            groundedness=0.0,
            citation_validity=1.0,
            evidence_coverage=0.2,
            comparison_quality=1.0,
            quality_score=0.55,
        ),
        news_vs_social={},
        human_review=False,
        review_reasons=[],
        beginner_verdict={
            "verdict": "Unverified",
            "plain_english": "We could not confirm or disprove this claim.",
        },
        directed_social_posts=[
            {
                "author": "example",
                "platform": "mastodon",
                "text": "A public post about Jio.",
                "url": "https://social.example/post/1",
            },
        ],
    )

    assert "Confidence in this assessment:** `0%`" in report
    assert "Confidence Level:** `55%`" not in report
    assert report.index("View Original Status") < report.index("<!-- socialverify-graph-slot -->")
    assert report.index("<!-- socialverify-graph-slot -->") < report.index("### News reports")
