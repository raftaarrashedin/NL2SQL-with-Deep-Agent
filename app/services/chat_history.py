from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import ChatMessage, QueryLog


def get_recent_messages(db: Session, chat_id: str, limit: int) -> list[ChatMessage]:
    messages = db.execute(
        select(ChatMessage)
        .where(ChatMessage.chat_id == chat_id)
        .order_by(ChatMessage.message_order.desc())
        .limit(limit)
    ).scalars().all()
    return list(reversed(messages))


def to_langchain_messages(messages: list[ChatMessage]) -> list[BaseMessage]:
    formatted: list[BaseMessage] = []
    for message in messages:
        if message.role == "user":
            formatted.append(HumanMessage(content=message.content))
        else:
            formatted.append(AIMessage(content=message.content))
    return formatted


def next_message_order(db: Session, chat_id: str) -> int:
    current_max = db.execute(select(func.max(ChatMessage.message_order)).where(ChatMessage.chat_id == chat_id)).scalar()
    return 0 if current_max is None else int(current_max) + 1


def append_chat_turn(
    db: Session,
    *,
    chat_id: str,
    connection_id: int | None,
    user_message: str,
    assistant_message: str,
) -> None:
    order = next_message_order(db, chat_id)
    db.add(
        ChatMessage(
            chat_id=chat_id,
            connection_id=connection_id,
            role="user",
            content=user_message,
            message_order=order,
        )
    )
    db.add(
        ChatMessage(
            chat_id=chat_id,
            connection_id=connection_id,
            role="assistant",
            content=assistant_message,
            message_order=order + 1,
        )
    )
    db.commit()


def last_connection_id_for_chat(db: Session, chat_id: str) -> int | None:
    last_message = db.execute(
        select(ChatMessage)
        .where(ChatMessage.chat_id == chat_id, ChatMessage.connection_id.is_not(None))
        .order_by(ChatMessage.message_order.desc())
        .limit(1)
    ).scalar_one_or_none()
    return last_message.connection_id if last_message else None


def create_query_log(
    db: Session,
    *,
    chat_id: str,
    connection_id: int | None,
    user_query: str,
    route: str,
    generated_sql: str | None,
    raw_result: str | None,
    synthesized_response: str | None,
    error_message: str | None,
    attempts: int,
) -> QueryLog:
    query_log = QueryLog(
        chat_id=chat_id,
        connection_id=connection_id,
        user_query=user_query,
        route=route,
        generated_sql=generated_sql,
        raw_result=raw_result,
        synthesized_response=synthesized_response,
        error_message=error_message,
        attempts=attempts,
    )
    db.add(query_log)
    db.commit()
    db.refresh(query_log)
    return query_log


def safe_json_loads(payload: str | None) -> dict[str, Any] | None:
    if not payload:
        return None
    try:
        parsed = json.loads(payload)
        return parsed if isinstance(parsed, dict) else None
    except Exception:  # noqa: BLE001
        return None


def safe_json_loads_any(payload: str | None) -> Any | None:
    if not payload:
        return None
    try:
        return json.loads(payload)
    except Exception:  # noqa: BLE001
        return None
