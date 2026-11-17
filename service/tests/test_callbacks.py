import unittest
from monitoring.callbacks import InvestigationCallbackHandler


class TestInvestigationCallbacks(unittest.TestCase):
    def test_callback_monitoring_lifecycle(self):
        """Requirement 5: Callback-based monitoring tracking agent starts/completions, tools, exceptions, latency, tokens."""
        handler = InvestigationCallbackHandler()
        inv_id = "inv-cb-test-01"

        handler.on_investigation_start(inv_id, "Test query")
        handler.on_agent_start(inv_id, "CrewAI Planner", "Formulate search query")
        handler.on_agent_end(inv_id, "CrewAI Planner", {"query": "clean"}, 145.5, {"prompt_tokens": 100, "completion_tokens": 30, "total_tokens": 130})
        handler.on_tool_start(inv_id, "search_news", {"q": "news"})
        handler.on_tool_end(inv_id, "search_news", {"status": "success"}, 210.0)
        handler.on_validation_failure(inv_id, "PydanticSchema", "Missing required field")
        handler.on_exception(inv_id, "NetworkAdapter", "Connection reset")
        handler.on_investigation_complete(inv_id, True, "Investigation done.")

        audit_log = handler.get_audit_log(inv_id)
        events = [e["event"] for e in audit_log]

        self.assertIn("investigation_start", events)
        self.assertIn("agent_start", events)
        self.assertIn("agent_end", events)
        self.assertIn("tool_start", events)
        self.assertIn("tool_end", events)
        self.assertIn("validation_failure", events)
        self.assertIn("exception", events)
        self.assertIn("investigation_complete", events)

        tokens = handler.get_token_usage(inv_id)
        self.assertEqual(tokens["total_tokens"], 130)


if __name__ == "__main__":
    unittest.main()
