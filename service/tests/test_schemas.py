import unittest
from pydantic import ValidationError
from schemas.report import (
    EvidenceSource,
    ClaimAssessment,
    EvaluationMetric,
    ProvenanceRecord,
    SocialVerifyReport,
)


class TestPydanticSchemas(unittest.TestCase):
    def test_evidence_source_valid(self):
        """Requirement 3: Pydantic structured output validation."""
        src = EvidenceSource(
            source_type="news",
            title="EU AI Act enters into force",
            url="https://artificialintelligenceact.eu/developments",
            publisher="EU Commission",
            published_at="2024-08-01"
        )
        self.assertEqual(src.source_type, "news")
        self.assertEqual(str(src.url), "https://artificialintelligenceact.eu/developments")

    def test_evidence_source_forbids_extra_fields(self):
        with self.assertRaises(ValidationError):
            EvidenceSource(
                source_type="news",
                title="Invalid",
                url="https://example.com",
                arbitrary_field="not_allowed"  # Forbidden extra field
            )

    def test_claim_assessment_valid(self):
        claim = ClaimAssessment(
            claim="High risk AI systems require conformity assessment",
            assessment="supported",
            supporting_evidence=["https://example.com/law"],
            counter_evidence=[],
            confidence=0.92,
            limitations=["Applies strictly within EU jurisdiction"]
        )
        self.assertEqual(claim.assessment, "supported")
        self.assertEqual(claim.confidence, 0.92)

    def test_claim_assessment_invalid_status(self):
        with self.assertRaises(ValidationError):
            ClaimAssessment(
                claim="Invalid claim",
                assessment="completely_made_up",  # Not in allowed literals
                confidence=0.5
            )

    def test_socialverify_report_complete(self):
        report = SocialVerifyReport(
            investigation_id="inv-test-999",
            query="AI safety regulation",
            summary="Assessment of EU AI Act implementation.",
            claim_assessments=[
                ClaimAssessment(
                    claim="Act is in force",
                    assessment="supported",
                    confidence=0.95
                )
            ],
            evidence_sources=[
                EvidenceSource(
                    source_type="news",
                    title="News title",
                    url="https://reuters.com/article"
                )
            ],
            evaluation_metrics=EvaluationMetric(
                groundedness=0.9,
                citation_validity=1.0,
                evidence_coverage=0.85,
                comparison_quality=0.8,
                quality_score=0.88
            ),
            provenance=[
                ProvenanceRecord(
                    timestamp="2026-10-28T00:00:00Z",
                    source_urls=["https://reuters.com/article"],
                    tool_names=["SearchMCPServer.search_news"],
                    model_identifiers=["CrewAI-Planner"],
                    trace_id="inv-test-999"
                )
            ],
            markdown_report="# Report\n\nContent",
            human_review_required=False,
            status="completed"
        )
        self.assertEqual(report.investigation_id, "inv-test-999")
        self.assertEqual(report.status, "completed")


if __name__ == "__main__":
    unittest.main()
