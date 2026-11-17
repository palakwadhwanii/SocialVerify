import unittest
from monitoring.tracing import DistributedTracer


class TestObservabilityAndProvenance(unittest.TestCase):
    def test_distributed_trace_and_spans(self):
        """Requirement 9: Observability - distributed traces, correlated IDs, agent/tool spans."""
        tracer = DistributedTracer()
        inv_id = "inv-obs-trace-01"

        trace_id = tracer.start_trace(inv_id, "Query on battery technologies")
        self.assertEqual(trace_id, inv_id)

        tracer.add_span(trace_id, "crewai_planning", {"q": "battery"}, {"plan": "news"}, 45.2, "agent")
        tracer.add_span(trace_id, "mcp_retrieval", {"tools": ["search_news"]}, {"count": 5}, 120.4, "tool")

        trace_data = tracer.get_trace(trace_id)
        self.assertIsNotNone(trace_data)
        self.assertEqual(len(trace_data["spans"]), 2)
        self.assertEqual(trace_data["spans"][0]["name"], "crewai_planning")

    def test_provenance_records(self):
        """Requirement 9: Provenance - source URLs, timestamps, tool names, and model IDs."""
        tracer = DistributedTracer()
        inv_id = "inv-provenance-02"
        tracer.start_trace(inv_id, "Provenance check")

        record = tracer.record_provenance(
            trace_id=inv_id,
            source_urls=["https://example.com/source1", "https://example.com/source2"],
            tool_names=["SearchMCPServer.search_news", "SearchMCPServer.search_social_posts"],
            model_identifiers=["CrewAI-ResearchCoordinator", "Google-ADK-EvidenceAgent"]
        )

        self.assertEqual(record.trace_id, inv_id)
        self.assertEqual(len(record.source_urls), 2)
        self.assertIn("CrewAI-ResearchCoordinator", record.model_identifiers)

        trace_data = tracer.get_trace(inv_id)
        self.assertEqual(len(trace_data["provenance"]), 1)


if __name__ == "__main__":
    unittest.main()
