from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from utils.logger import logger
from utils.exception import SocialVerifyException, NarrativeXException
from config import ALLOWED_ORIGINS, HOST, PORT
from a2a.server import a2a_server, a2a_router
from routers import agent

app = FastAPI(
    title="SocialVerify AI Service",
    description="Multi-agent verification service powered by CrewAI + Google ADK over A2A protocol and MCP tools.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=ALLOWED_ORIGINS != ["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# Include API Routers
app.include_router(agent.router)
app.include_router(a2a_router)


@app.get("/", tags=["Root"])
def root() -> dict:
    return {
        "success": True,
        "service": "SocialVerify AI Service",
        "message": "Welcome to SocialVerify AI Service. Visit /docs for API documentation."
    }


@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
def health() -> dict:
    return {
        "success": True,
        "service": "SocialVerify",
        "message": "SocialVerify AI Service is healthy and running successfully."
    }


@app.get("/.well-known/agent.json", tags=["A2A"])
def root_agent_card() -> dict:
    """A2A protocol discovery endpoint at root standard path."""
    return a2a_server.get_agent_card()


@app.exception_handler(SocialVerifyException)
@app.exception_handler(NarrativeXException)
def socialverify_exception_handler(request, exc: SocialVerifyException):
    logger.error(f"Error occurred in script: {exc.file_name} at line: {exc.line_number} with message: {exc.error_message}")
    return JSONResponse(status_code=500, content={
        "success": False,
        "message": f"Error occurred in script: {exc.file_name} at line: {exc.line_number} with message: {exc.error_message}"
    })


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
