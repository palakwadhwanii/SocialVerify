import os

PORT = int(os.getenv("PORT", 8000))
HOST = os.getenv("HOST", "0.0.0.0")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "http://localhost:9000")

# LLM Providers
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CREWAI_MODEL_API_KEY = os.getenv("CREWAI_MODEL_API_KEY", GROQ_API_KEY)
ADK_MODEL_API_KEY = os.getenv("ADK_MODEL_API_KEY") or GEMINI_API_KEY
ADK_MODEL = os.getenv("ADK_MODEL", "gemini-3.5-flash")

# MCP Configuration
SEARCH_MCP_URL = os.getenv("SEARCH_MCP_URL", "http://localhost:8001")
EVIDENCE_MCP_URL = os.getenv("EVIDENCE_MCP_URL", "http://localhost:8002")

# A2A Configuration
ADK_A2A_BASE_URL = os.getenv("ADK_A2A_BASE_URL", f"http://localhost:{PORT}/a2a")
A2A_AUTH_TOKEN = os.getenv("A2A_AUTH_TOKEN", "socialverify-a2a-secret-token")
A2A_TIMEOUT_SECONDS = float(os.getenv("A2A_TIMEOUT_SECONDS", 60.0))

# Observability
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_BASE_URL = os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")

# Security & limits
MAX_INPUT_LENGTH = int(os.getenv("MAX_INPUT_LENGTH", 2000))
MAX_TOOL_RESULTS = int(os.getenv("MAX_TOOL_RESULTS", 20))
MCP_TOOL_TIMEOUT_SECONDS = float(os.getenv("MCP_TOOL_TIMEOUT_SECONDS", 10.0))
INVESTIGATION_WINDOW_DAYS = int(os.getenv("INVESTIGATION_WINDOW_DAYS", 30))

# Mastodon Configuration
MASTODON_INSTANCES = [i.strip().lower() for i in os.getenv("MASTODON_INSTANCES", "mastodon.social,mastodon.online,fosstodon.org,masto.ai,infosec.exchange").split(",") if i.strip()]
MASTODON_ACCESS_TOKEN = os.getenv("MASTODON_ACCESS_TOKEN", "").strip()
MASTODON_REQUEST_TIMEOUT = float(os.getenv("MASTODON_REQUEST_TIMEOUT", "15"))
