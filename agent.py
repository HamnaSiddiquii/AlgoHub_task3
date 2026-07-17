import os
import time
from typing import Optional

# 1. Import the Google Generative AI chat model
from langchain_google_genai import ChatGoogleGenerativeAI

# 2. Use langchain_classic to prevent import errors in newer LangChain versions
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.tools import ALL_TOOLS

SYSTEM_PROMPT = """You are a careful, tool-using assistant with access to:
- calculator: for arithmetic/math expressions
- code_executor: for running short Python snippets in a sandbox
- file_reader / list_files: for reading files from a sandboxed workspace
- web_search: for looking up current information on the web

Tool selection rules:
1. Prefer the calculator for pure arithmetic; only use code_executor
   when the task genuinely needs code (loops, data structures, string
   processing, etc).
2. Use list_files before file_reader if you're not sure a file exists.
3. Use web_search only when the question needs current/external
   information you can't already answer confidently.
4. If a tool call fails, read the error message, adjust your approach
   (e.g. fix a syntax error, try a different file name), and retry at
   most once before explaining the issue to the user.
5. Chain tools when needed: e.g. read a file, then compute something
   about its contents with code_executor.
6. After a tool returns a result, state the final answer directly and
   plainly (e.g. "The result is 120"). Never describe your own process,
   never say things like "the model didn't finalize an answer" — just
   give the answer.
Be concise in your final answer.
"""

# Global cache to prevent heavy re-initialization on every single run
_CACHED_AGENT_EXECUTOR: Optional[AgentExecutor] = None


def build_agent_executor(model: str = "gemini-3.1-flash-lite", temperature: float = 0.0) -> AgentExecutor:
    global _CACHED_AGENT_EXECUTOR

    # If we already built it once, return it instantly!
    if _CACHED_AGENT_EXECUTOR is not None:
        return _CACHED_AGENT_EXECUTOR

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY or GOOGLE_API_KEY is not set. Please set it in your environment or .env file."
        )

    llm = ChatGoogleGenerativeAI(
        model=model,
        temperature=temperature,
        google_api_key=api_key,
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    agent = create_tool_calling_agent(llm, ALL_TOOLS, prompt)

    _CACHED_AGENT_EXECUTOR = AgentExecutor(
        agent=agent,
        tools=ALL_TOOLS,
        verbose=True,
        max_iterations=6,  # Reduced slightly to fail faster if looping
        max_execution_time=15,  # Fast, snappy UI limit
        handle_parsing_errors=True,
    )

    return _CACHED_AGENT_EXECUTOR


def _extract_text(value):
    """
    Normalize whatever the agent/LLM returned into a plain string.
    """
    if isinstance(value, str):
        return value

    if isinstance(value, dict):
        if "text" in value:
            return _extract_text(value["text"])
        return str(value)

    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                if "text" in item:
                    parts.append(_extract_text(item["text"]))
            else:
                parts.append(_extract_text(item))

        # Collapse consecutive duplicate parts
        deduped = []
        for p in parts:
            if not deduped or deduped[-1] != p:
                deduped.append(p)

        return "\n".join(p for p in deduped if p)

    return str(value)


def run_agent_safely(query: str, max_retries: int = 1) -> str:
    """
    Reliability wrapper around the agent executor.
    - Uses pre-warmed cached executor instance.
    - Only retries if hit by a true API rate limit (429 Resource Exhausted).
    - Avoids wasting execution cycles on standard tool failures.
    """
    last_error: Optional[Exception] = None
    executor = build_agent_executor()

    for attempt in range(1, max_retries + 2):
        try:
            result = executor.invoke({"input": query})

            if isinstance(result, dict):
                output = result.get("output", "")
            else:
                output = result

            output = _extract_text(output)
            return output.strip() or "(agent returned no output)"

        except Exception as e:  # noqa: BLE001
            last_error = e
            err_msg = str(e).upper()

            # Retry ONLY if rate limited
            if "RESOURCE_EXHAUSTED" in err_msg or "429" in err_msg:
                if attempt <= max_retries:
                    print(f"\n[Rate Limit Hit] Waiting 3s before retrying (attempt {attempt})...\n")
                    time.sleep(3)
                    continue

            # If it's a logic error, parsing error, or tool error, break immediately.
            # Retrying won't change the outcome and only wastes another 15-20 seconds.
            break

    return (
        "Agent Error: The agent failed to complete the task.\n\n"
        f"**Last error recorded:** `{last_error}`"
    )