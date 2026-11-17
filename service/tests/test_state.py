import unittest
from schemas.state import InvestigationState


class TestInvestigationState(unittest.TestCase):
    def test_investigation_state_fields(self):
        """Requirement 1: Pass the user's query, retrieved evidence, intermediate findings, and status through explicit state."""
        state: InvestigationState = {
            "investigation_id": "inv-test-123",
            "query": "Is nuclear energy lower carbon than solar?",
            "conversation_history": [{"role": "user", "content": "Hello"}],
            "access_token": "bearer-token-abc",
            "input_validation": {"allowed": True, "reason": "Query valid"},
            "search_plan": {"news_query": "nuclear energy carbon emissions"},
            "retrieved_news": [{"title": "Article 1", "url": "https://example.com/nuclear"}],
            "retrieved_social": [{"title": "Post 1", "url": "https://reddit.com/r/energy/1"}],
            "retrieved_database": [{"claim": "Nuclear has low lifecycle emissions"}],
            "crewai_results": {"planned": True},
            "adk_task_id": "a2a-task-456",
            "adk_results": {"claims_count": 1},
            "claim_assessments": [{"claim": "Nuclear energy lifecycle emissions are low", "assessment": "supported"}],
            "evaluation_metrics": {"groundedness": 0.95, "citation_validity": 1.0},
            "provenance": [{"trace_id": "inv-test-123"}],
            "final_report": {"status": "completed"},
            "errors": [],
            "execution_status": "completed"
        }

        self.assertEqual(state["investigation_id"], "inv-test-123")
        self.assertEqual(state["execution_status"], "completed")
        self.assertEqual(len(state["retrieved_news"]), 1)
        self.assertEqual(len(state["retrieved_social"]), 1)
        self.assertEqual(state["claim_assessments"][0]["assessment"], "supported")


if __name__ == "__main__":
    unittest.main()
