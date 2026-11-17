# SocialVerify Multi-Agent Architecture Guide & Reference Manual


>  Document Version:  2.0.0 
>  Target Project:  SocialVerify (formerly NarrativeX) 
>  Core Architecture:  CrewAI Multi-Agent Coordinator + Google Agent Development Kit (ADK) + Agent2Agent (A2A) Protocol + Model Context Protocol (MCP) + Inshorts API + Mastodon REST API v2 + Pydantic v2 + Next.js 16 Workspace Monitoring


---


## 1. Architectural Philosophy & Overview


SocialVerify is a traceable, secure, multi-agent intelligence platform that verifies public claims by comparing  decentralized social conversations (Mastodon federated network)  against  accredited journalism, Inshorts news, official announcements, and primary-source records .


Rather than relying on a single monolithic LLM prompt or unvetted web searches, SocialVerify implements an  orchestrated multi-agent methodology :
-  CrewAI  acts as the overarching research planner and coordinator.
-  Google ADK  operates as a specialized, delegated evidence-analysis engine.
- Communication between CrewAI and Google ADK is conducted through a  real, network-isolated Agent2Agent (A2A) protocol  (`HTTP/JSON-RPC`).
- Tool execution is divided into modular  Model Context Protocol (MCP)  servers.
-  Inshorts News API  is integrated alongside Google News RSS and NewsAPI to supply fast, reliable categorized journalistic coverage.
- All requests, intermediate state, and final deliverables are strictly validated against  Pydantic v2 schemas  with zero-tolerance output guardrails.
- A  Monitoring Workspace Dashboard  provides real-time, live-streaming visibility into agent execution, pipeline health, evidence coverage, and scenario-level traces.


---


## 2. The 8 Specialized Methodology Agents


SocialVerify divides the verification workflow across 8 distinct agents, each with dedicated roles, goals, and execution boundaries.


| # | Agent Name | Primary Framework | Role / Responsibility | Definition File & Location | Invocation File & Location |
|---|---|---|---|---|---|
|  1  |  Claim Extraction Agent  | CrewAI | Breaks down unstructured user prompts into atomic, testable claims and removes subjective bias. | [service/agents/crewai_coordinator.py](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/service/agents/crewai_coordinator.py) | [service/agents/crewai_coordinator.py](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/service/agents/crewai_coordinator.py) |
|  2  |  Context Analysis Agent  | Python / CrewAI | Extracts named entities, historical dates, organizations, and identifies contextual gaps in the query. | [service/tools/evidence_processor.py](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/service/tools/evidence_processor.py) | [service/agents/crewai_coordinator.py](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/service/agents/crewai_coordinator.py) |
|  3  |  Web Search Agent  | MCP / Python | Executes targeted multi-source queries across public news providers, Inshorts API, and Mastodon instances. | [service/mcp_servers/search_server.py](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/service/mcp_servers/search_server.py) | [service/agents/crewai_coordinator.py](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/service/agents/crewai_coordinator.py) |
|  4  |  Fact-Check Agent  | MCP / Python | Searches established fact-checking databases (Google Fact Check Tools API / ClaimReview schema). | [service/mcp_servers/evidence_server.py](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/service/mcp_servers/evidence_server.py) | [service/agents/crewai_coordinator.py](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/service/agents/crewai_coordinator.py) |
|  5  |  Source Credibility Agent  | Python Rule Engine | Evaluates domain authority, editorial standards, and assigns indexed credibility scores (0.0 to 1.0). | [service/tools/credibility.py](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/service/tools/credibility.py) | [service/agents/crewai_coordinator.py](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/service/agents/crewai_coordinator.py) |
|  6  |  Evidence Analysis Agent  | Google ADK | Synthesizes retrieved evidence, assesses support/contradiction, detects narrative divergence, and computes calibrated confidence. | [service/agents/adk_evidence_agent.py](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/service/agents/adk_evidence_agent.py) | [service/a2a/client.py](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/service/a2a/client.py) (delegated via A2A protocol) |
|  7  |  Verification Agent  | Evaluator-Optimizer | Applies iterative refinement to claims, detects uncorroborated assertions, computes confidence, and flags human review triggers. | [service/agents/crewai_coordinator.py](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/service/agents/crewai_coordinator.py) | [service/agents/crewai_coordinator.py](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/service/agents/crewai_coordinator.py) |
|  8  |  Report & RQ Synthesis Agent  | CrewAI + Groq | Generates dynamic, claim-tailored answers for the 5 Core Research Questions (RQ1 - RQ5), assembles provenance, and formats visual markdown. | [service/agents/crewai_coordinator.py](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/service/agents/crewai_coordinator.py) | [service/agents/crewai_coordinator.py](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/service/agents/crewai_coordinator.py) |


---


## 3. Deep Dive: Agent Definitions vs. Invocations


### Agent 1: Claim Extraction Agent
-  Definition:  [service/agents/crewai_coordinator.py](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/service/agents/crewai_coordinator.py)
 ```python
 self.planner_agent = CrewAgent(
    role="Research Investigation Planner",
    goal="Formulate comprehensive multi-source search plans for social and news fact verification.",
    backstory="Senior fact-checking lead skilled at identifying core claims, bias indicators, and search parameters.",
    verbose=False,
    allow_delegation=False,
 )
 ```
-  Action:  Takes user query `query`, cleans whitespace, and formats targeted search queries for news, Mastodon, and reference databases.


### Agent 2: Context Analysis Agent
-  Definition:  [service/tools/evidence_processor.py](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/service/tools/evidence_processor.py)
 ```python
 class EvidenceProcessor:
    @staticmethod
    def extract_context_entities(query: str) -> dict[str, Any]:
        ...
 ```
-  Action:  Extracts named entities, temporal anchors (years, months), and highlights contextual gaps (e.g. missing geographic scope).


### Agent 3: Web & News Search Agent (MCP Tool Integration)
-  Definition:  [service/mcp_servers/search_server.py](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/service/mcp_servers/search_server.py), [service/tools/inshorts.py](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/service/tools/inshorts.py), and [service/tools/mastodon.py](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/service/tools/mastodon.py)
-  Action:  Concurrently retrieves news articles (Google News RSS, DuckDuckGo, Inshorts API) and authentic Mastodon posts across configured instances (`mastodon.social`, `fosstodon.org`, etc.).


### Agent 4: Fact-Check Agent
-  Definition:  [service/mcp_servers/evidence_server.py](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/service/mcp_servers/evidence_server.py)
-  Action:  Queries Google Fact Check Tools API / ClaimReview records to identify if professional fact-checkers (Reuters, AP, PolitiFact, Snopes) have already audited this claim.


### Agent 5: Source Credibility Agent
-  Definition:  [service/tools/credibility.py](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/service/tools/credibility.py)
-  Action:  Parses domain extensions and registries to assign indexed credibility scores and classification tiers (`High Authority`, `Moderate Authority`, `Unverified Community`).


### Agent 6: Evidence Analysis Agent (Google ADK)
-  Definition:  [service/agents/adk_evidence_agent.py](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/service/agents/adk_evidence_agent.py)
 ```python
 adk_agent_instance = ADKAgent(
    name="socialverify_evidence_analyzer",
    description="Cross-source evidence analyzer for SocialVerify multi-agent architecture.",
    instruction=ADK_INSTRUCTION,
 )
 ```
-  Action:  Performs cross-source synthesis, evaluates calibrated confidence (even with minimum available data), assesses claim support/contradiction, detects narrative divergence phases, and returns structured analysis artifacts over the A2A network interface.


### Agent 7: Verification Agent (Evaluator-Optimizer)
-  Definition:  [service/agents/crewai_coordinator.py](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/service/agents/crewai_coordinator.py)
-  Action:  Implements the  Evaluator-Optimizer agentic pattern :
 1. Compares raw claims against verified retrieved URLs.
 2. If a claim is marked `supported` but lacks corroborating citations, downgrades status to `mixed` and clips confidence.
 3. Evaluates average confidence: if `< 65%` or contradictions exist, flags `human_review_required = True`.


### Agent 8: Report & Dynamic RQ Synthesis Agent
-  Definition:  [service/agents/crewai_coordinator.py](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/service/agents/crewai_coordinator.py)
-  Action:  Dynamically evaluates and answers the 5 Core Research Questions (RQ1 - RQ5) tailored to the specific query, headlines, and social posts using Groq (`openai/gpt-oss-120b`). Assembles provenance telemetry and validates the entire report against the `SocialVerifyReport` Pydantic model.


---


## 4. Agent2Agent (A2A) Protocol Integration


### What is A2A and Why is it Used?
Agent2Agent (A2A) is an open communication standard allowing autonomous agents built on different frameworks (e.g. CrewAI in the LangChain ecosystem and Google ADK in the Google Cloud/Vertex ecosystem) to delegate tasks, pass state, and return structured artifacts through authenticated HTTP/JSON-RPC protocols.


### File Locations:
1.  A2A Server Endpoint:  [service/a2a/server.py](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/service/a2a/server.py)
  - Exposes `POST /a2a/tasks` to receive delegated tasks from CrewAI.
  - Exposes `GET /a2a/tasks/{task_id}` to check task lifecycle status (`pending`, `running`, `completed`, `failed`).
  - Router registered in [service/app.py](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/service/app.py).
2.  A2A Client Delegate:  [service/a2a/client.py](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/service/a2a/client.py)
  - `CrewAIA2AClient`: Formulates the task submission payload, sets Bearer authentication (`A2A_AUTH_TOKEN`), transmits HTTP requests, polls/awaits completion, and extracts ADK artifacts.
3.  A2A Contract Schemas:  [service/a2a/models.py](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/service/a2a/models.py)
  - `A2ATaskSubmission`: Strict Pydantic model validating query, news, social, and database collections.
  - `A2ATaskResult`: Validates completed execution artifacts and error payloads.


---


## 5. Dynamic Core Research Questions (RQ1 - RQ5) Engine


The verification engine dynamically synthesizes structured empirical findings for the 5 foundational Research Questions:


-  RQ1 - News vs. Social Media (Lead vs Follow):  Evaluates whether authoritative journalism or decentralized social chatter led the propagation, referencing exact publication timestamps.
-  RQ2 - Information Correlation:  Analyzes the semantic and entity-level correlation between news headlines and social discourse.
-  RQ3 - Virality vs. Evidence:  Assesses verification lag time and tracks whether primary evidence caught up with rapid social sharing.
-  RQ4 - Origin of Information:  Pinpoints the earliest observed public documentation, identifying the seed platform, date, and link.
-  RQ5 - Narrative Propagation:  Models the multi-stage lifecycle from initial post or news report to community reactions and mainstream framing.


Implementation: Powered by Groq's `openai/gpt-oss-120b` JSON schema completion with an automatic entity-heuristic fallback.


---


## 6. Live Workspace Monitoring Architecture


The SocialVerify Workspace includes a dedicated  Monitoring Tab  integrated directly below Visual Studio in the workspace navigation sidebar.


### Architecture Highlights:
-  Real-Time Polling Stream:  Polls every 3 seconds for active research workflows, system status, and pipeline execution logs.
-  Live / Mock Mode Toggle:  Allows switching between real-time database records and benchmark simulation traces.
-  Pipeline Stage Cards: 
 1. Research Planning / Router
 2. News Retrieval
 3. Social Media Retrieval
 4. Claim & Narrative Analysis
 5. Evidence Matching
 6. Cross-media Evaluation / Judge
 7. Report Generation
-  Scenario-Level Execution History:  Searchable, filterable table tracking scenario ID, research topic, execution status, latency, and detailed trace logs.
-  Endpoints: 
 - `GET /api/monitoring` in Node/Bun server ([server/src/controllers/monitoringController.ts](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/server/src/controllers/monitoringController.ts))
 - `GET /api/agent/monitoring/status` in FastAPI AI service ([service/app.py](file:///Users/palakwadhwanii/Desktop/NarrativeX-main/service/app.py))


---


## 7. Complete Directory & File Map


```
NarrativeX-main/
├── compose.yaml                    # Docker container configuration
├── README.md                       # Project overview and setup instructions
├── AGENT_ARCHITECTURE.md           # This comprehensive architecture manual
│
├── service/                        # Python Multi-Agent AI Microservice (Port 8010)
│   ├── app.py                      # FastAPI application entrypoint & routing
│   ├── config/                     # Configuration and environment loaders
│   ├── a2a/                        # Agent2Agent Protocol Implementation
│   │   ├── client.py               # CrewAIA2AClient for delegating tasks to ADK
│   │   ├── server.py               # A2A task submission and polling endpoints
│   │   └── models.py               # A2A task schemas (Pydantic)
│   ├── agents/                     # Specialized Agent Modules
│   │   ├── crewai_coordinator.py   # Master Research Coordinator & Dynamic RQ Synthesizer
│   │   ├── adk_evidence_agent.py   # Google ADK Evidence Analysis Agent & Confidence Calibration
│   │   ├── methodology_agents.py   # Registry of the 8 methodology agents
│   │   ├── research.py             # Research extraction agent
│   │   └── router.py               # Fast-path intent router
│   ├── mcp_servers/                # Model Context Protocol (MCP) Tool Servers
│   │   ├── client.py               # Unified MCP Client interface
│   │   ├── search_server.py        # Search MCP Server (News, Mastodon, Inshorts)
│   │   └── evidence_server.py      # Evidence MCP Server (DB, Fact Check, Context)
│   ├── security/                   # Security Filters & Guardrails
│   │   └── guardrails.py           # InputGuardrail, ToolGuardrail, OutputGuardrail
│   ├── tools/                      # Dedicated Tool & Provider Implementations
│   │   ├── inshorts.py             # Official Inshorts News API client
│   │   ├── mastodon.py             # Official Mastodon REST API provider (SSRF, search)
│   │   ├── credibility.py          # Source Credibility Evaluator (Domain authority scoring)
│   │   └── evidence_processor.py   # Entity and context extraction processor
│   ├── monitoring/                 # Distributed Tracing & Callbacks
│   │   ├── callbacks.py            # Event callbacks for agent starts, ends, errors
│   │   └── tracing.py              # Langfuse tracer and provenance logger
│   └── tests/                      # Automated Pytest Suite
│       ├── test_inshorts.py        # Inshorts News API unit tests
│       ├── test_rumour_analysis.py # Rumour analysis and brief verification
│       ├── test_mastodon.py        # Mastodon REST API tests
│       ├── test_frameworks.py      # CrewAI + Google ADK validation
│       ├── test_a2a.py             # A2A protocol integration tests
│       └── test_security.py        # Prompt injection and guardrail tests
│
├── server/                         # Express & TypeScript Backend API (Port 9000)
│   ├── src/
│   │   ├── index.ts                # Express server bootstrapper
│   │   ├── controllers/            # REST API endpoints (Chat, Monitoring, Social, News, Auth)
│   │   │   ├── chatController.ts   # Forwards queries to Python service, persists reports
│   │   │   └── monitoringController.ts # Streams real-time pipeline KPIs and scenario runs
│   │   ├── services/               # Business logic services
│   │   │   ├── aiService.ts        # Typed HTTP client to FastAPI AI Service
│   │   │   ├── newsService.ts      # Google News RSS and provider integration
│   │   │   └── reportService.ts    # PDF research brief generation (PDFKit)
│   │   └── prisma/                 # Database persistence
│   │       ├── db.ts               # Resilient DB wrapper with fallback logic
│   │       └── localStore.ts       # Embedded JSON storage engine (getAllConversations, getAllChats)
│   └── data/socialverify_db.json   # Local investigation database records
│
└── client/                         # Next.js 16 Frontend Web Application (Port 3000)
   ├── src/app/                    # Next.js App Router pages
   │   ├── page.tsx                # Homepage & Source explorer
   │   ├── dashboard/page.tsx      # Research Studio main view
   │   └── dashboard/monitoring/   # Dedicated Monitoring Dashboard route
   ├── src/components/             # UI Components
   │   ├── dashboard/              # Research Studio, MonitoringDashboard, chat threads
   │   └── home/                   # SourceExplorer, interactive feature showcases
   └── src/lib/                    # Frontend utilities (workspace.ts, api.ts, markdown parser)
```


---


## 8. Technology Stack & API Reference


| Component | Technology | Version | Purpose & Definition |
|---|---|---|---|
| Multi-Agent Orchestration  |  CrewAI  | `>= 0.102.0` | Orchestrates specialized planner, researcher, and report assembler agents with goal-oriented roles. |
| Evidence Analysis  |  Google ADK  | `>= 0.1.0` | Google Agent Development Kit framework specialized for complex multi-modal and cross-source evidence reasoning. |
| Agent Communication  |  A2A Protocol  | `1.0.0 (Custom RPC)` | Agent2Agent standard interface decoupling CrewAI from Google ADK over authenticated HTTP REST endpoints. |
| Tool Protocol  |  Model Context Protocol (MCP)  | `v1.0 Specification` | Exposes news search, social search, and database access as standard discoverable tool servers. |
| Fast LLM Inference  |  Groq API (`openai/gpt-oss-120b`)  | `Latest` | Powers dynamic synthesis of the 5 Core Research Questions and evidence verdicts. |
| News Providers  |  Inshorts API + Google News RSS  | `v1` | Multi-category news ingestion delivering reliable journalistic coverage. |
| Social Provider API  |  Mastodon REST API  | `v2 (/api/v2/search)` | Official decentralized REST API retrieving public posts, instance domains, and engagement metrics. |
| Fact-Check API  |  Google Fact Check Tools API  | `v1alpha1` | Structured fact-checking database using schema.org `ClaimReview` standard. |
| Schema Validation  |  Pydantic  | `>= 2.10.0` | Enforces runtime data validation, forbids unexpected fields, and bounds numerical evaluation scores. |
| Observability  |  Langfuse SDK & Monitoring Dashboard  | `>= 2.59.0` | Real-time workspace dashboard, distributed tracing, token usage, and provenance recording. |
|  Web Frontend  |  Next.js  | `16.3.5` | React 19 framework providing the Research Studio, Monitoring tab, and streaming UI. |
|  Backend Server  |  Express on Bun  | `4.21.2 / Bun 1.4` | TypeScript REST API handling user sessions, monitoring aggregation, and PDF report creation. |
|  Database & ORM  |  Prisma & Embedded JSON Store  | `6.4.1` | Resilient persistence engine automatically falling back to localized JSON storage when external DB is offline. |
|  Runtime Environments  |  Python 3.12 & Bun 1.4  | `3.12 / 1.4.2` | High-performance runtimes executing the microservice and full-stack application. |



