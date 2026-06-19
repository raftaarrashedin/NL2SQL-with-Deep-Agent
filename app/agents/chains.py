from __future__ import annotations

from app.agent.prompts import (
    build_schema_summary_prompt,
    build_sql_generation_prompt,
    build_synthesis_prompt,
)


def schema_summary_chain(llm, schema_text: str):
    return build_schema_summary_prompt(schema_text) | llm


def sql_generation_chain(llm, *, schema_details: str, summary_instructions: str, user_query: str, previous_error: str | None):
    return (
        build_sql_generation_prompt(
            schema_details=schema_details,
            summary_instructions=summary_instructions,
            user_query=user_query,
            previous_error=previous_error,
        )
        | llm
    )


def synthesis_chain(llm, *, user_query: str, sql: str, raw_result: str):
    return build_synthesis_prompt(user_query=user_query, sql=sql, raw_result=raw_result) | llm
