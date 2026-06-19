from __future__ import annotations

from deepagents import create_deep_agent

from app.agent.context import AgentContext
from app.agent.middleware import tool_logging_middleware
from app.agent.prompts import COORDINATOR_SYSTEM_PROMPT, SQL_SUBAGENT_SYSTEM_PROMPT
from app.agent.tools import run_sql_workflow
from app.core.config import Settings
from app.core.llm import build_chat_model


def create_nl2sql_deep_agent(settings: Settings, provider: str, model_name: str):
    coordinator_model = build_chat_model(settings, provider=provider, model_name=model_name, temperature=0)

    sql_subagent = {
        "name": "sql-workflow-specialist",
        "description": (
            "Handles database-backed questions by generating SQL, executing it, retrying once on failure, "
            "and synthesizing the result."
        ),
        "system_prompt": SQL_SUBAGENT_SYSTEM_PROMPT,
        "tools": [run_sql_workflow],
    }

    return create_deep_agent(
        model=coordinator_model,
        system_prompt=COORDINATOR_SYSTEM_PROMPT,
        subagents=[sql_subagent],
        middleware=[tool_logging_middleware],
        context_schema=AgentContext,
    )
