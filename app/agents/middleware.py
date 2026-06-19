from __future__ import annotations

import logging

from langchain.agents.middleware import wrap_tool_call

logger = logging.getLogger(__name__)


@wrap_tool_call
def tool_logging_middleware(request, handler):
    tool_name = getattr(request, "name", "unknown_tool")
    logger.info("Calling tool: %s", tool_name)
    result = handler(request)
    logger.info("Tool completed: %s", tool_name)
    return result
