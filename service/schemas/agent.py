from typing import Any
from pydantic import BaseModel, Field
from schemas.report import SocialVerifyReport


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    session_history: list[dict] = Field(default_factory=list)
    access_token: str | None = Field(default=None, exclude=True)


class QueryResponse(BaseModel):
    success: bool
    data: Any
    message: str
    investigation_id: str | None = None
    execution_status: str | None = None
