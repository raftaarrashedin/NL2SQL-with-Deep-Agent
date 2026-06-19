from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentContext:
    chat_id: str
    llm_provider: str
    model_name: str
    connection_id: int | None = None
    connection_name: str | None = None
    connection_url: str | None = None
    schema_details: str | None = None
    summary_instructions: str | None = None

    @property
    def has_database_context(self) -> bool:
        return bool(self.connection_url and self.schema_details and self.summary_instructions)
