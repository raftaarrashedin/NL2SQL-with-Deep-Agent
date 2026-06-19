from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from app.core.config import Settings


def resolve_provider_and_model(
    settings: Settings,
    provider: str | None = None,
    model_name: str | None = None,
    *,
    sql_model: bool = False,
) -> tuple[str, str]:
    resolved_provider = (provider or settings.default_llm_provider).strip().lower()
    fallback_model = settings.default_sql_model if sql_model and settings.default_sql_model else settings.default_model
    resolved_model = (model_name or fallback_model).strip()
    return resolved_provider, resolved_model


def build_chat_model(
    settings: Settings,
    provider: str | None = None,
    model_name: str | None = None,
    *,
    temperature: float = 0,
    sql_model: bool = False,
) -> BaseChatModel:
    resolved_provider, resolved_model = resolve_provider_and_model(
        settings,
        provider=provider,
        model_name=model_name,
        sql_model=sql_model,
    )

    if resolved_provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=resolved_model, temperature=temperature)

    if resolved_provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(model=resolved_model, temperature=temperature)

    if resolved_provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(model=resolved_model, base_url=settings.ollama_host, temperature=temperature)

    if resolved_provider == "huggingface":
        from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

        endpoint = HuggingFaceEndpoint(
            repo_id=resolved_model,
            task="text-generation",
            max_new_tokens=1024,
            do_sample=False,
            temperature=temperature,
            huggingfacehub_api_token=settings.huggingfacehub_api_token,
        )
        return ChatHuggingFace(llm=endpoint)

    raise ValueError(
        "Unsupported LLM provider. Expected one of: openai, groq, huggingface, ollama."
    )
