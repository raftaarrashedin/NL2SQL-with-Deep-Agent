from __future__ import annotations

import json
from typing import Any

from langchain.tools import ToolRuntime, tool
from sqlalchemy import create_engine, text

from app.agent.chains import sql_generation_chain, synthesis_chain
from app.agent.context import AgentContext
from app.core.config import get_settings
from app.core.llm import build_chat_model


def _normalize_sql(raw_sql: str) -> str:
    sql = raw_sql.strip()
    if "```sql" in sql:
        sql = sql.split("```sql", maxsplit=1)[1].split("```", maxsplit=1)[0].strip()
    elif "```" in sql:
        sql = sql.split("```", maxsplit=1)[1].split("```", maxsplit=1)[0].strip()
    return sql.strip().rstrip(";") + ";"


def _generate_sql_statement(context: AgentContext, user_query: str, previous_error: str | None = None) -> str:
    settings = get_settings()
    llm = build_chat_model(
        settings,
        provider=context.llm_provider,
        model_name=context.model_name,
        temperature=0,
        sql_model=True,
    )
    response = sql_generation_chain(
        llm,
        schema_details=context.schema_details or "",
        summary_instructions=context.summary_instructions or "",
        user_query=user_query,
        previous_error=previous_error,
    ).invoke({})
    return _normalize_sql(response.content)


def _execute_sql_statement(connection_url: str, sql: str) -> tuple[bool, str]:
    engine = create_engine(connection_url, future=True)
    try:
        with engine.connect() as connection:
            result = connection.execute(text(sql))
            rows = result.fetchall()
            serialized_rows = [dict(row._mapping) for row in rows]
            return True, json.dumps(serialized_rows, default=str)
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    finally:
        engine.dispose()


def _synthesize_sql_result(context: AgentContext, user_query: str, sql: str, raw_result: str) -> str:
    settings = get_settings()
    llm = build_chat_model(
        settings,
        provider=context.llm_provider,
        model_name=context.model_name,
        temperature=0,
    )
    response = synthesis_chain(llm, user_query=user_query, sql=sql, raw_result=raw_result).invoke({})
    return response.content.strip()


@tool
def run_sql_workflow(query: str, runtime: ToolRuntime[AgentContext]) -> str:
    """Generate SQL, execute it against the connected PostgreSQL database, retry once on error, and synthesize the final answer."""
    context = runtime.context
    settings = get_settings()

    if context is None or not context.has_database_context:
        return json.dumps(
            {
                "route": "sql",
                "response": "No active database context is available. Connect a database first and try again.",
                "generated_sql": None,
                "raw_result": None,
                "attempts": 0,
                "error": "missing_database_context",
            }
        )

    generated_sql: str | None = None
    raw_result: str | None = None
    last_error: str | None = None

    for attempt in range(1, settings.max_sql_execution_attempts + 1):
        generated_sql = _generate_sql_statement(context, query, previous_error=last_error)
        success, payload = _execute_sql_statement(context.connection_url or "", generated_sql)
        if success:
            raw_result = payload
            response = _synthesize_sql_result(context, query, generated_sql, raw_result)
            return json.dumps(
                {
                    "route": "sql",
                    "response": response,
                    "generated_sql": generated_sql,
                    "raw_result": raw_result,
                    "attempts": attempt,
                    "error": None,
                }
            )
        last_error = payload

    return json.dumps(
        {
            "route": "sql",
            "response": (
                "I could not execute a valid SQL query after "
                f"{settings.max_sql_execution_attempts} attempts. Last error: {last_error}"
            ),
            "generated_sql": generated_sql,
            "raw_result": None,
            "attempts": settings.max_sql_execution_attempts,
            "error": last_error,
        }
    )
