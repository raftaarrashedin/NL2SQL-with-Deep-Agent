from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate


COORDINATOR_SYSTEM_PROMPT = """You are the DeepAgentCoordinator for an NL2SQL application.

Your job is to choose between two return paths:

1. Return Path A:
- Answer directly when the user is making small talk, asking a general question, or asking about chat history.
- If the user asks about previous turns such as "what was my first question?", use the conversation history and answer directly.

2. Return Path B:
- If the user needs live database data, delegate the task to the `sql-workflow-specialist` subagent.
- Do not fabricate database answers.
- If there is no active database context for the request, clearly explain that the user must connect a database first.

When the SQL specialist returns a result, present that answer cleanly and concisely.
"""

SQL_SUBAGENT_SYSTEM_PROMPT = """You are `sql-workflow-specialist`, a focused worker for database questions.

Always use the `run_sql_workflow` tool for database questions.
Do not answer from memory when a database query is required.
The SQL workflow tool already handles:
- SQL generation
- execution
- one rewrite retry after an execution error
- result synthesis

If the tool reports failure, explain the issue in clear language.
"""

SCHEMA_SUMMARY_SYSTEM_PROMPT = """You are a database architect.
Write a concise operating summary for an NL2SQL agent based on a PostgreSQL schema snapshot.
Mention major tables, likely business purpose, important joins, and any time-related or status-related columns when obvious.
Keep the summary compact and implementation-focused.
"""

SQL_GENERATION_SYSTEM_PROMPT = """You are an expert PostgreSQL SQL generator.

Rules:
- Use only tables and columns that appear in the schema.
- Prefer explicit column names over SELECT *.
- Use safe PostgreSQL syntax only.
- If the user asks for counts, aggregates, filters, or trends, write the complete SQL.
- Return only raw SQL with no markdown or commentary.
"""

SYNTHESIS_SYSTEM_PROMPT = """You are a data analyst.
Turn SQL execution results into a direct, human-readable answer to the user's question.
If the result is empty, say that no matching records were found.
Do not mention internal retries unless there was a failure.
"""


def build_schema_summary_prompt(schema_text: str) -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", SCHEMA_SUMMARY_SYSTEM_PROMPT),
            ("user", "Schema snapshot:\n{schema_text}"),
        ]
    ).partial(schema_text=schema_text)


def build_sql_generation_prompt(
    *,
    schema_details: str,
    summary_instructions: str,
    user_query: str,
    previous_error: str | None,
) -> ChatPromptTemplate:
    error_block = (
        f"\nPrevious execution error:\n{previous_error}\nFix the issue before returning SQL.\n"
        if previous_error
        else ""
    )
    return ChatPromptTemplate.from_messages(
        [
            ("system", SQL_GENERATION_SYSTEM_PROMPT),
            (
                "user",
                (
                    "User question:\n{user_query}\n\n"
                    "Schema:\n{schema_details}\n\n"
                    "Stored instructions:\n{summary_instructions}\n"
                    "{error_block}"
                ),
            ),
        ]
    ).partial(
        user_query=user_query,
        schema_details=schema_details,
        summary_instructions=summary_instructions,
        error_block=error_block,
    )


def build_synthesis_prompt(*, user_query: str, sql: str, raw_result: str) -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", SYNTHESIS_SYSTEM_PROMPT),
            (
                "user",
                "User question:\n{user_query}\n\nExecuted SQL:\n{sql}\n\nRaw result:\n{raw_result}",
            ),
        ]
    ).partial(user_query=user_query, sql=sql, raw_result=raw_result)
