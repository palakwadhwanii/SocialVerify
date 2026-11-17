# SocialVerify


>   SocialVerify   is a traceable, secure, multi-agent verification system powered by   CrewAI + Google Agent Development Kit (ADK)   communicating via the open   Agent2Agent (A2A)   protocol, integrating external tools through the   Model Context Protocol (MCP)  , enforcing strict   Pydantic   structured schemas, callback-based monitoring, and continuous end-to-end evaluation.


> [!NOTE]
>   Complete Agent Architecture Guide:   For a file-by-file breakdown of where each agent is defined, where agents are called, Pydantic schemas, A2A endpoints, and tech stack versions, see the dedicated [AGENT_ARCHITECTURE.md](AGENT_ARCHITECTURE.md).


---


## 1. Architectural Overview


```
                                     +------------------------------------+
                                     |   Next.js Client / Workspace UI    |
                                     +-----------------+------------------+
                                                       |
                                                       v
                                     +-----------------+------------------+
                                     |       Express / Bun Server         |
                                     +-----------------+------------------+
                                                       |  HTTP /api/agent/query
                                                       v
+---------------------------------------------------------------------------------------------------------+
|                                      SocialVerify AI Service                                             |
|                                                                                                         |
|   +-------------------------------------------------------------------------------------------------+   |
|   | Input Guardrails (Length checks, prompt-injection defense, abuse filter)                       |   |
|   +------------------------------------------------+------------------------------------------------+   |
|                                                    | Validated Query + State                            |
|                                                    v                                                    |
|   +------------------------------------------------+------------------------------------------------+   |
|   | CrewAI - Research Coordinator (Planner Agent)                                                  |   |
|   | Formulates multi-source search plans, search parameters, and hypotheses                         |   |
|   +------------------------------------------------+------------------------------------------------+   |
|                                                    |                                                    |
|                  +---------------------------------+---------------------------------+                  |
|                  | Parallel Retrieval: MCP + Inshorts + Mastodon                     |                  |
|                  v                                                                   v                  |
|   +-----------------------------+                                     +-----------------------------+   |
|   | Search MCP Server & Inshorts|                                     | Evidence MCP Server         |   |
|   | - Google News RSS & Inshorts|                                     | - lookup_evidence_db        |   |
|   | - Mastodon federated search |                                     | - retrieve_source_context   |   |
|   +--------------+--------------+                                     +--------------+--------------+   |
|                  |                                                                   |                  |
|                  +---------------------------------+---------------------------------+                  |
|                                                    | Retrieved Evidence Sources                         |
|                                                    v                                                    |
|   +-------------------------------------------------------------------------------------------------+   |
|   | Agent2Agent (A2A) Client Boundary                                                               |   |
|   | Agent Card Discovery (/.well-known/agent.json) -> Task Submission (POST /a2a/tasks)            |   |
|   +------------------------------------------------+------------------------------------------------+   |
|                                                    | A2A Protocol (Bearer Auth + Lifecycle)             |
|                                                    v                                                    |
|   +-------------------------------------------------------------------------------------------------+   |
|   | Google Agent Development Kit (ADK) - Evidence Analysis Agent (A2A Server)                       |   |
|   | Extracts atomic claims, checks corroboration & counter-evidence, evaluates uncertainty          |   |
|   +------------------------------------------------+------------------------------------------------+   |
|                                                    | A2A Task Result Artifacts                          |
|                                                    v                                                    |
|   +-------------------------------------------------------------------------------------------------+   |
|   | CrewAI + Groq - Report Assembler & Dynamic RQ Synthesizer                                       |   |
|   | - Dynamic answers for Core Research Questions (RQ1 - RQ5) grounded in real claim data           |   |
|   | - Evaluator-Optimizer Pattern: citation membership verification & confidence calibration        |   |
|   | - Human-Review Pattern: flags low-confidence or contentious contradictory claims                |   |
|   | - Pydantic Output Guardrail: validates SocialVerifyReport schema (extra='forbid')               |   |
|   +------------------------------------------------+------------------------------------------------+   |
|                                                    |                                                    |
|                                                    v                                                    |
|   +-------------------------------------------------------------------------------------------------+   |
|   | Observability, Callbacks & Provenance (Langfuse Traces, Request IDs, Spans, Audit Events)       |   |
|   +-------------------------------------------------------------------------------------------------+   |
+---------------------------------------------------------------------------------------------------------+
```


---


## 2. Project Phases (End-to-End Flow)


The project is made up of three connected applications: a Next.js client, an Express/Bun server, and a FastAPI AI service. A user investigation moves through these phases:


1.   User workspace and sign-in - Next.js client   
  Users sign in, open or create an investigation, and ask a research question in the dashboard. The client also displays previous messages and the resulting research brief.


2.   Request handling and investigation storage - Express/Bun server   
  The server handles authentication and the application APIs. For a chat request, it checks the conversation, saves the user's message, and forwards the question and conversation history to the AI service.


3.   Request checks and workflow setup - FastAPI AI service   
  The service receives the query, assigns an investigation ID, and validates the input with its security guardrails. Rejected requests stop here; accepted requests continue into the research workflow.


4.   Research planning and evidence collection - CrewAI, MCP, Inshorts & Mastodon   
  The research coordinator organizes the investigation and gathers relevant material. Search tools collect news (Google News RSS, Inshorts News API) and public Mastodon posts across federated instances; evidence tools look up fact-checks (Google Fact Check Tools API) and retrieve context from sources. Independent retrievals run in parallel.


5.   Claim and evidence analysis - Google ADK over A2A   
  The coordinator sends the collected evidence to the evidence-analysis agent using the A2A task protocol. The agent examines claims, supporting and contradicting evidence, citations, and uncertainty, then returns structured results with calibrated confidence.


6.   Report construction and dynamic RQ evaluation - CrewAI & Groq   
  The service combines the analysis into a typed report and dynamically synthesizes evidence-grounded answers for the 5 Core Research Questions (RQ1 - RQ5) tailored specifically to the claim. It checks structure and citations, refines confidence, and flags cases that may need human review.


7.   Saving and presenting the result - server and client   
  The server saves the generated response as part of the conversation and returns it to the client. The user can read the brief in the investigation and continue with a follow-up question using the conversation history.


8.   Monitoring and quality checks - cross-cutting   
  The dedicated   Monitoring Tab   inside the workspace streams pipeline health, agent executions, and scenario records in real time. Callbacks, traces, audit events, and evaluation metrics help inspect how an investigation ran.


  In one line:   the client collects a question -> the server manages identity and conversation -> the AI service gathers and evaluates evidence -> a validated brief is saved and shown to the user.


---


## 3. Requirements & Implementation Checklist


| # | Requirement | Implementation Component | Visible / Inspectable Output | Automated Test |
|---|---|---|---|---|
|   1   |   Context Sharing and State   | `service/schemas/state.py` (`InvestigationState`) | `execution_status`, state transitions across boundaries | `tests/test_state.py` |
|   2   |   MCP Tool Integration   | `service/mcp_servers/` (`search_server.py`, `evidence_server.py`, `client.py`) | `GET /api/agent/mcp/tools`, parallel retrieval payloads | `tests/test_mcp.py` |
|   3   |   Pydantic Structured Output   | `service/schemas/report.py` (`SocialVerifyReport`, `ClaimAssessment`, `EvidenceSource`) | Typed report payload, formatted Markdown tables | `tests/test_schemas.py` |
|   4   |   Agentic Design Patterns   | `service/agents/crewai_coordinator.py` | Planner-executor, parallel tools, evaluator-optimizer, human review flag | `tests/test_patterns.py` |
|   5   |   Callback-Based Monitoring   | `service/monitoring/callbacks.py` (`InvestigationCallbackHandler`) | `GET /api/agent/audit/{investigation_id}` audit logs & token counters | `tests/test_callbacks.py` |
|   6   |   A2A Interoperability   | `service/a2a/` (`server.py`, `client.py`) | `GET /.well-known/agent.json`, `POST /a2a/tasks`, task lifecycle | `tests/test_a2a.py` |
|   7   |   CrewAI + ADK Frameworks   | `service/agents/` (`crewai_coordinator.py`, `adk_evidence_agent.py`) | CrewAI coordinator + Google ADK agent; zero LangGraph in execution path | `tests/test_frameworks.py` |
|   8   |   Security and Guardrails   | `service/security/guardrails.py` | Blocked prompt injection, length bounds, citation membership check | `tests/test_security.py` |
|   9   |   Observability and Provenance   | `service/monitoring/tracing.py` | `GET /api/agent/traces/{investigation_id}`, Langfuse spans, `ProvenanceRecord` | `tests/test_observability.py` |
|   10   |   End-to-End Evaluation   | `service/benchmark.py` | Median & p95 latency, 100% validation rate, estimated token costs | `tests/test_e2e_evaluation.py` |


---


## 4. The Agent2Agent (A2A) Protocol Implementation


The   Agent2Agent (A2A)   protocol enables communication between the CrewAI Research Coordinator and the Google ADK Evidence Analysis Agent as independent, remotely callable services.


### Agent Card
Exposed at `GET /.well-known/agent.json` and `GET /a2a/agent-card`:
```json
{
 "protocol": "a2a/v1",
 "agent_id": "socialverify-adk-evidence-agent",
 "name": "SocialVerify ADK Evidence Analysis Agent",
 "endpoint": "http://localhost:8010/a2a/tasks",
 "capabilities": {
   "skills": [
     "evidence-analysis",
     "claim-extraction",
     "cross-source-comparison",
     "uncertainty-assessment"
   ],
   "modalities": ["application/json"]
 },
 "authentication": {
   "type": "bearer",
   "header": "Authorization"
 }
}
```


### Task Lifecycle
1.   Submission  : CrewAI client sends `POST /a2a/tasks` with investigation topic and retrieved evidence.
2.   State Progression  : Task status moves through `submitted` -> `working` -> `completed` (or `failed`).
3.   Artifact Retrieval  : CrewAI client retrieves structured assessment artifacts (`claim_assessments`, `counter_evidence`, `citations`, `uncertainty`).


---


## 5. Tool Integration (MCP, Inshorts & Mastodon)


SocialVerify combines real Model Context Protocol servers and direct multi-source connectors:


1.   Search MCP Server (`SearchMCPServer`)  :
  - `search_news`: Searches verified news reporting with language and sort filters.
  - `search_social_posts`: Searches Reddit, Bluesky, and Mastodon public discussions.
2.   Inshorts News Provider (`InshortsClient`)  :
  - Fetches high-volume categorized journalistic items (`national`, `business`, `world`, etc.) with titles, summaries, and source URLs.
3.   Evidence MCP Server (`EvidenceMCPServer`)  :
  - `lookup_evidence_db`: Looks up archived fact-checks and verified claim databases.
  - `retrieve_source_context`: Fetches context from cited URLs.


The `SocialVerifyMCPClient` executes independent tools concurrently via `execute_parallel_retrieval`.


---


## 6. Security & Guardrails


-   Input Guardrail  : Inspects queries for length bounds, adversarial prompt injections (regex + heuristic scanning for jailbreaks, system prompt overrides, and roleplay exploits), and abusive requests.
-   Tool Guardrail  : Restricts tool calls to an allowlist, limits page sizes, enforces execution timeouts, and protects against unauthorized command injection.
-   Output Guardrail  : Validates strict Pydantic schemas (`extra="forbid"`), validates URL formats, and verifies that cited URLs exist in the retrieved evidence pool.
-   Secrets Protection  : Credentials are read strictly from environment variables and never logged or exposed to the client.


---


## 7. Workspace Monitoring Tab & Dynamic RQ Engine


### Workspace Monitoring Tab
A native   Monitoring   tab is located in the workspace sidebar directly below Visual Studio:
-   Live KPI Cards:   Displays total research workflows, completion/failure rates, retrieved news/social counts, and average latency.
-   Agent Pipeline Performance:   Visual progress bars, executions, and correctness metrics for all 7 pipeline stages.
-   Scenario-Level Results:   Interactive, filterable execution table with detailed modal drawers for each investigation scenario.
-   Live Stream (3s):   Real-time background polling with a live/mock toggle switch.


### Dynamic Core Research Questions (RQ1 - RQ5) Engine
Every investigation brief synthesizes dynamic, evidence-grounded answers for the 5 research questions:
-   RQ1 (News vs. Social Media):   Evaluates who led and who followed based on empirical timestamps.
-   RQ2 (Information Correlation):   Analyzes narrative entity overlaps and divergence.
-   RQ3 (Virality vs. Evidence):   Measures verification lag time and arrival of official evidence.
-   RQ4 (Origin of Information):   Pinpoints the earliest observed documentation and seed link.
-   RQ5 (Narrative Propagation):   Tracks lifecycle progression across online communities and newsdesks.


---


## 8. Quickstart


### Prerequisites
- Python 3.12+
- Bun 1.1+ or Node.js 20+


### Setup & Installation


1.   Setup Python AI Service:  
```bash
cd service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```


2.   Run Tests:  
```bash
PYTHONPATH=. pytest -v tests/
```


3.   Run Benchmark Suite:  
```bash
PYTHONPATH=. python benchmark.py
```


4.   Start the AI Service (Port 8010):  
```bash
python app.py
```


5.   Start Server (Port 9000) & Client (Port 3000):  
```bash
# In server/
bun install && bun run src/index.ts


# In client/
bun install && bun run dev
```


Visit `http://localhost:3000` to interact with SocialVerify.





