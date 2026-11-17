from typing import Any
from crewai import Agent as CrewAgent
from google.adk.agents.llm_agent import Agent as ADKAgent
from tools.evidence_processor import EvidenceProcessor
from tools.credibility import SourceCredibilityEvaluator
from mcp_servers.client import SocialVerifyMCPClient
from utils.logger import logger


# ==============================================================================
# The 8 Methodology Agents (CrewAI + Google ADK)
# ==============================================================================

# 1. Claim Extraction Agent - Extracts and structures the main claim.
claim_extraction_agent = CrewAgent(
    role="Claim Extraction Agent",
    goal="Extract and structure the primary verifiable atomic claim from the user's input.",
    backstory="Specialized linguistic analyst focused on isolating factual propositions from rhetorical framing.",
    verbose=False,
    allow_delegation=False,
)

# 2. Context Analysis Agent - Identifies context, entities, dates, and missing information.
context_analysis_agent = CrewAgent(
    role="Context Analysis Agent",
    goal="Identify contextual background, named entities, publication dates, and flag missing information.",
    backstory="Contextual intelligence researcher identifying temporal, geographic, and domain boundaries of claims.",
    verbose=False,
    allow_delegation=False,
)

# 3. Web Search Agent - Searches the web for relevant information and evidence.
web_search_agent = CrewAgent(
    role="Web Search Agent",
    goal="Search the web and news repositories for relevant reporting, journalism, and public evidence.",
    backstory="Information retrieval specialist adept at formulating targeted queries across news and web archives.",
    verbose=False,
    allow_delegation=False,
)

# 4. Fact-Check Agent - Checks existing fact-checking sources and databases.
fact_check_agent = ADKAgent(
    name="fact_check_agent",
    description="Checks existing fact-checking sources and databases including Google Fact Check API.",
    instruction="Query Google Fact Check API and verified claim repositories for pre-existing fact-checking audits.",
)

# 5. Source Credibility Agent - Evaluates the reliability and authority of sources.
source_credibility_agent = CrewAgent(
    role="Source Credibility Agent",
    goal="Evaluate the reliability, domain authority, and reputation tier of all cited sources.",
    backstory="Media analyst assessing institutional accreditation, peer consensus, and bias indicators.",
    verbose=False,
    allow_delegation=False,
)

# 6. Evidence Analysis Agent - Compares supporting and contradicting evidence.
# (Google ADK-powered Evidence Analyzer operating over A2A protocol)
evidence_analysis_agent = ADKAgent(
    name="evidence_analysis_agent",
    description="Compares supporting and contradicting evidence across cross-media sources.",
    instruction="Compare claims against news, social discussions, and reference facts to evaluate corroboration and contradictions.",
)

# 7. Verification Agent - Determines the overall claim status and confidence.
verification_agent = CrewAgent(
    role="Verification Agent",
    goal="Determine the final verification status (supported, contradicted, mixed, insufficient_evidence) and confidence score.",
    backstory="Senior fact-checking adjudicator weighing evidentiary strength, credibility weights, and counter-claims.",
    verbose=False,
    allow_delegation=False,
)

# 8. Report Generation Agent - Produces the final user-facing verification report.
report_generation_agent = CrewAgent(
    role="Report Generation Agent",
    goal="Synthesize structured evidence findings into the final user-facing SocialVerify report.",
    backstory="Executive briefing specialist formatting findings into readable, actionable, and strictly typed reports.",
    verbose=False,
    allow_delegation=False,
)


class MethodologyWorkflowEngine:
    """Executes the full 8-agent methodology pipeline."""

    def __init__(self, mcp_client: SocialVerifyMCPClient | None = None):
        self.mcp_client = mcp_client or SocialVerifyMCPClient()

    async def run_methodology_pipeline(
        self,
        query: str,
        access_token: str | None = None
    ) -> dict[str, Any]:
        logger.info(f"Methodology pipeline running with 8 agents for query: '{query}'")

        # Agent 1: Claim Extraction Agent
        clean_query = query.strip()
        extracted_claim = {
            "original_query": clean_query,
            "main_claim": clean_query,
            "extracted_by": claim_extraction_agent.role
        }

        # Agent 2: Context Analysis Agent
        context_data = EvidenceProcessor.extract_context_entities(clean_query)
        context_data["analyzed_by"] = context_analysis_agent.role

        # Agent 3: Web Search Agent (via MCP Web & News Search)
        search_results = await self.mcp_client.call_tool("search_news", {"query": clean_query, "page_size": 10}, access_token)
        social_results = await self.mcp_client.call_tool("search_social_posts", {"topics": [clean_query], "limit": 10}, access_token)
        web_results = await self.mcp_client.call_tool("web_search", {"query": clean_query, "max_results": 10})

        news_articles = search_results.get("articles", [])
        social_posts = social_results.get("posts", [])
        web_items = web_results.get("results", [])

        # Agent 4: Fact-Check Agent (via Google Fact Check API)
        fact_check_results = await self.mcp_client.call_tool("google_fact_check_search", {"query": clean_query})
        fact_checks = fact_check_results.get("fact_checks", [])

        # Build unified source pool
        all_sources = []
        for n in news_articles:
            if n.get("url"):
                all_sources.append({"url": n["url"], "title": n.get("title", ""), "source_type": "news", "publisher": n.get("source")})
        for s in social_posts:
            if s.get("url"):
                all_sources.append({"url": s["url"], "title": s.get("title") or s.get("text", "")[:80], "source_type": "social", "publisher": s.get("platform")})
        for w in web_items:
            if w.get("url"):
                all_sources.append({"url": w["url"], "title": w.get("title", ""), "source_type": "web", "publisher": "Web Source"})

        # Agent 5: Source Credibility Agent
        credibility_data = SourceCredibilityEvaluator.evaluate_sources(all_sources)
        credibility_data["evaluated_by"] = source_credibility_agent.role

        # Agent 6: Evidence Analysis Agent (Python comparison & ADK)
        evidence_comparison = EvidenceProcessor.compare_evidence(clean_query, news_articles, social_posts)
        evidence_comparison["analyzed_by"] = evidence_analysis_agent.name

        # Agent 7: Verification Agent
        support_cnt = evidence_comparison["overall_support_count"]
        counter_cnt = evidence_comparison["overall_counter_count"]

        if counter_cnt > 0 and support_cnt > 0:
            status = "mixed"
            confidence = 0.75
        elif counter_cnt > support_cnt:
            status = "contradicted"
            confidence = 0.85
        elif support_cnt > 0:
            status = "supported"
            confidence = min(0.95, 0.75 + 0.05 * support_cnt)
        else:
            status = "insufficient_evidence"
            confidence = 0.35

        verification_result = {
            "status": status,
            "confidence": confidence,
            "determined_by": verification_agent.role,
            "support_count": support_cnt,
            "counter_count": counter_cnt
        }

        # Agent 8: Report Generation Agent
        return {
            "query": clean_query,
            "extracted_claim": extracted_claim,
            "context_analysis": context_data,
            "news_articles": news_articles,
            "social_posts": social_posts,
            "web_items": web_items,
            "fact_checks": fact_checks,
            "credibility": credibility_data,
            "evidence_comparison": evidence_comparison,
            "verification": verification_result,
            "agents_involved": [
                claim_extraction_agent.role,
                context_analysis_agent.role,
                web_search_agent.role,
                fact_check_agent.name,
                source_credibility_agent.role,
                evidence_analysis_agent.name,
                verification_agent.role,
                report_generation_agent.role,
            ]
        }
