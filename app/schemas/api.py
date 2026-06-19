from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ConnectDBRequest(BaseModel):
    name: str = Field(..., description="Friendly name for the target database connection")
    host: str
    port: int = 5432
    user: str
    password: str
    database: str
    db_type: Literal["postgresql"] = "postgresql"
    llm_provider: str | None = None
    model_name: str | None = None


class ConnectDBResponse(BaseModel):
    status: str
    message: str
    connection_id: int
    schema_summary: str


class DisconnectDBRequest(BaseModel):
    connection_id: int


class DisconnectDBResponse(BaseModel):
    status: str
    message: str
    connection_id: int


class ChatRequest(BaseModel):
    chat_id: str
    query: str
    connection_id: int | None = None
    llm_provider: str | None = None
    model_name: str | None = None


class ChatResponse(BaseModel):
    response: str
    chat_id: str
    route: Literal["general", "sql"]
    connection_id: int | None = None
    query_executed: str | None = None
    raw_result: Any | None = None
    attempts: int = 0
    error_message: str | None = None
