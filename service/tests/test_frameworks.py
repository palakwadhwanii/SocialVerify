import unittest
import inspect
from agents.crewai_coordinator import SocialVerifyCoordinator
from agents.adk_evidence_agent import adk_agent_instance
from agents.graph import agent_app, SocialVerifyExecutionEngine


class TestRequiredFrameworks(unittest.TestCase):
    def test_crewai_framework_integrated(self):
        """Requirement 7: CrewAI used as agentic coordinator framework."""
        coordinator = SocialVerifyCoordinator()
        self.assertIsNotNone(coordinator.planner_agent)
        self.assertIsNotNone(coordinator.assembler_agent)
        self.assertEqual(coordinator.planner_agent.role, "Research Investigation Planner")

    def test_google_adk_framework_integrated(self):
        """Requirement 7: Google ADK used as evidence analysis agent framework."""
        self.assertIsNotNone(adk_agent_instance)
        self.assertEqual(adk_agent_instance.name, "socialverify_evidence_analyzer")

    def test_langgraph_replaced_in_execution_path(self):
        """Requirement 7: LangGraph replaced in the execution path."""
        # Check that agent_app is an instance of SocialVerifyExecutionEngine, not LangGraph CompiledGraph
        self.assertIsInstance(agent_app, SocialVerifyExecutionEngine)
        
        # Check that agents/graph.py source code does NOT import or use StateGraph
        import agents.graph
        source = inspect.getsource(agents.graph)
        self.assertNotIn("StateGraph", source)
        self.assertNotIn("from langgraph", source)
        self.assertNotIn("import langgraph", source)


if __name__ == "__main__":
    unittest.main()
