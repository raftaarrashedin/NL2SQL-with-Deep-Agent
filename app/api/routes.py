from __future__ import annotations

import json
from collections.abc import Generator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from sqlalchemy.orm import Session

from app.agent.context import AgentContext
from app.agent.deep_agent import create_nl2sql_deep_agent
from app.core.config import Settings, get_settings
from app.core.llm import resolve_provider_and_model
from app.db.database import get_db
from app.schemas.api import (
    ChatRequest,
    ChatResponse,
    ConnectDBRequest,
    ConnectDBResponse,
    DisconnectDBRequest,
    DisconnectDBResponse,
)
from app.services.chat_history import (
    append_chat_turn,
    create_query_log,
    get_recent_messages,
    last_connection_id_for_chat,
    safe_json_loads,
    safe_json_loads_any,
    to_langchain_messages,
)
from app.services.connections import disconnect_connection, get_active_connection, upsert_connection
from app.services.schema import build_postgres_connection_url, fetch_postgres_schema, generate_schema_summary

router = APIRouter()


def _extract_final_ai_message(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, AIMessage) and message.content:
            return str(message.content)
    return "I could not generate a response."


def _extract_sql_payload(messages: list[BaseMessage]) -> dict[str, Any] | None:
    for message in reversed(messages):
        if isinstance(message, ToolMessage):
            payload = safe_json_loads(str(message.content))
            if payload and payload.get("route") == "sql":
                return payload
    return None


def _resolve_connection(
    db: Session,
    request: ChatRequest,
) -> tuple[int | None, str | None, str | None, str | None]:
    connection_id = request.connection_id or last_connection_id_for_chat(db, request.chat_id)
    if connection_id is None:
        return None, None, None, None

    resolved = get_active_connection(db, connection_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Active database connection not found.")

    return (
        resolved.connection.id,
        resolved.connection.name,
        resolved.connection_url,
        resolved.schema_record.schema_details if resolved.schema_record else None,
    )


def _resolve_summary(db: Session, connection_id: int | None) -> str | None:
    if connection_id is None:
        return None
    resolved = get_active_connection(db, connection_id)
    if resolved is None or resolved.schema_record is None:
        return None
    return resolved.schema_record.summary_instructions


def _build_agent_context(
    *,
    settings: Settings,
    request: ChatRequest,
    db: Session,
) -> AgentContext:
    provider, model_name = resolve_provider_and_model(
        settings,
        provider=request.llm_provider,
        model_name=request.model_name,
    )

    connection_id, connection_name, connection_url, schema_details = _resolve_connection(db, request)
    summary_instructions = _resolve_summary(db, connection_id)

    return AgentContext(
        chat_id=request.chat_id,
        llm_provider=provider,
        model_name=model_name,
        connection_id=connection_id,
        connection_name=connection_name,
        connection_url=connection_url,
        schema_details=schema_details,
        summary_instructions=summary_instructions,
    )


def _invoke_agent(
    *,
    settings: Settings,
    request: ChatRequest,
    db: Session,
) -> tuple[list[BaseMessage], dict[str, Any] | None]:
    context = _build_agent_context(settings=settings, request=request, db=db)
    history = to_langchain_messages(get_recent_messages(db, request.chat_id, settings.max_chat_history_messages))
    messages: list[BaseMessage] = [*history, HumanMessage(content=request.query)]

    agent = create_nl2sql_deep_agent(settings, provider=context.llm_provider, model_name=context.model_name)
    result = agent.invoke({"messages": messages}, context=context)
    result_messages = result.get("messages", []) if isinstance(result, dict) else []
    sql_payload = _extract_sql_payload(result_messages)
    return result_messages, sql_payload


@router.post("/connect", response_model=ConnectDBResponse)
def connect_database(
    request: ConnectDBRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if request.db_type != "postgresql":
        raise HTTPException(status_code=400, detail="Only PostgreSQL target connections are supported in this build.")

    connection_url = build_postgres_connection_url(
        host=request.host,
        port=request.port,
        username=request.user,
        password=request.password,
        database_name=request.database,
    )

    try:
        schema_text = fetch_postgres_schema(connection_url)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Failed to connect or introspect schema: {exc}") from exc

    schema_summary = generate_schema_summary(
        settings,
        schema_text=schema_text,
        provider=request.llm_provider,
        model_name=request.model_name,
    )

    connection = upsert_connection(
        db,
        name=request.name,
        host=request.host,
        port=request.port,
        username=request.user,
        password=request.password,
        database_name=request.database,
        db_type=request.db_type,
        schema_details=schema_text,
        summary_instructions=schema_summary,
    )

    return ConnectDBResponse(
        status="success",
        message="Database connected, schema extracted, and summary instructions stored.",
        connection_id=connection.id,
        schema_summary=schema_summary,
    )


@router.post("/disconnect", response_model=DisconnectDBResponse)
def disconnect_database(request: DisconnectDBRequest, db: Session = Depends(get_db)):
    connection = disconnect_connection(db, request.connection_id)
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found.")

    return DisconnectDBResponse(
        status="success",
        message="Database connection marked inactive.",
        connection_id=connection.id,
    )


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    result_messages, sql_payload = _invoke_agent(settings=settings, request=request, db=db)
    response_text = _extract_final_ai_message(result_messages)

    route = "sql" if sql_payload else "general"
    effective_connection_id = request.connection_id or last_connection_id_for_chat(db, request.chat_id)

    append_chat_turn(
        db,
        chat_id=request.chat_id,
        connection_id=effective_connection_id,
        user_message=request.query,
        assistant_message=response_text,
    )

    create_query_log(
        db,
        chat_id=request.chat_id,
        connection_id=effective_connection_id,
        user_query=request.query,
        route=route,
        generated_sql=sql_payload.get("generated_sql") if sql_payload else None,
        raw_result=sql_payload.get("raw_result") if sql_payload else None,
        synthesized_response=response_text,
        error_message=sql_payload.get("error") if sql_payload else None,
        attempts=int(sql_payload.get("attempts", 0)) if sql_payload else 0,
    )

    return ChatResponse(
        response=response_text,
        chat_id=request.chat_id,
        route=route,
        connection_id=effective_connection_id,
        query_executed=sql_payload.get("generated_sql") if sql_payload else None,
        raw_result=safe_json_loads_any(sql_payload.get("raw_result")) if sql_payload else None,
        attempts=int(sql_payload.get("attempts", 0)) if sql_payload else 0,
        error_message=sql_payload.get("error") if sql_payload else None,
    )


@router.post("/chat/stream")
def chat_stream(
    request: ChatRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    context = _build_agent_context(settings=settings, request=request, db=db)
    history = to_langchain_messages(get_recent_messages(db, request.chat_id, settings.max_chat_history_messages))
    input_messages: list[BaseMessage] = [*history, HumanMessage(content=request.query)]
    agent = create_nl2sql_deep_agent(settings, provider=context.llm_provider, model_name=context.model_name)

    captured_sql_payload: dict[str, Any] | None = None
    final_response: str = ""
    effective_connection_id = context.connection_id

    def event_stream() -> Generator[str, None, None]:
        nonlocal captured_sql_payload, final_response

        for chunk in agent.stream(
            {"messages": input_messages},
            context=context,
            stream_mode="updates",
            subgraphs=True,
            version="v2",
        ):
            yield f"data: {json.dumps(chunk, default=str)}\n\n"

            data = chunk.get("data") if isinstance(chunk, dict) else None
            if isinstance(data, dict):
                maybe_messages = data.get("messages")
                if isinstance(maybe_messages, list):
                    extracted_payload = _extract_sql_payload(maybe_messages)
                    if extracted_payload:
                        captured_sql_payload = extracted_payload
                    final_response = _extract_final_ai_message(maybe_messages)

        append_chat_turn(
            db,
            chat_id=request.chat_id,
            connection_id=effective_connection_id,
            user_message=request.query,
            assistant_message=final_response or "Streaming run completed.",
        )
        create_query_log(
            db,
            chat_id=request.chat_id,
            connection_id=effective_connection_id,
            user_query=request.query,
            route="sql" if captured_sql_payload else "general",
            generated_sql=captured_sql_payload.get("generated_sql") if captured_sql_payload else None,
            raw_result=captured_sql_payload.get("raw_result") if captured_sql_payload else None,
            synthesized_response=final_response or "Streaming run completed.",
            error_message=captured_sql_payload.get("error") if captured_sql_payload else None,
            attempts=int(captured_sql_payload.get("attempts", 0)) if captured_sql_payload else 0,
        )
        yield "event: done\ndata: {\"status\": \"completed\"}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
