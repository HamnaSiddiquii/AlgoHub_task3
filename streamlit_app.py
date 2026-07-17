"""
Streamlit UI for the multi-tool agent (Gemini Edition).

Visual style matches the "search bar" mockup: a peach-to-coral rounded
card, a fake browser-dot bar, a pill-shaped search-style input, and
message rows styled like search suggestions.

Run with:
    streamlit run streamlit_app.py
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

import streamlit as st

# ---- 1. ROBUST BACKEND INITIALIZATION (Resolves local app.agent import issue) ----

# Adaptable AgentExecutor imports
try:
    from langchain.agents import AgentExecutor, create_tool_calling_agent
except ImportError:
    try:
        from langchain.agents.agent import AgentExecutor
        from langchain.agents import create_tool_calling_agent
    except ImportError:
        try:
            from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
        except ImportError:
            st.error("Could not import AgentExecutor. Please run: pip install langchain-classic")
            st.stop()

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import tool

import math
import re

# Native Tool: Calculator
@tool("calculator")
def calculator_tool(expression: str) -> str:
    """Useful for solving math problems or evaluating mathematical expressions,
    including functions like sqrt, sin, cos, tan, log, log10, exp, pow, abs,
    and the constants pi and e.
    Input should be a mathematical expression like '12 * (7 + sqrt(9))'."""
    expression = expression.strip()

    allowed_names = {
        'sqrt': math.sqrt,
        'sin': math.sin,
        'cos': math.cos,
        'tan': math.tan,
        'log': math.log,
        'log10': math.log10,
        'exp': math.exp,
        'pi': math.pi,
        'e': math.e,
        'pow': pow,
        'abs': abs,
    }

    # Verify any alphabetic words are explicitly whitelisted
    words = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', expression)
    for word in words:
        if word not in allowed_names:
            return f"Error: Unsafe or unsupported function or variable '{word}' in expression."

    # Only allow safe characters
    if not re.match(r'^[a-zA-Z0-9_.\s+\-*/()%,]+$', expression):
        return "Error: Invalid characters in mathematical expression."

    try:
        result = eval(expression, {"__builtins__": None}, allowed_names)
        return str(result)
    except Exception as e:
        return f"Calculation Error: {str(e)}"

# Native Tool: File Reader / Listing
@tool("file_reader")
def file_reader_tool(filepath: str = "") -> str:
    """Useful for reading the contents of a local text file, or for listing
    the files available in the workspace. To list files, pass an empty
    string, '.', or 'list' as input. To read a file, pass its filepath."""
    # 1. Handle directory listing requests
    if not filepath or filepath.strip().lower() in ('.', 'list', 'ls', 'workspace'):
        try:
            ignored = {'.git', '__pycache__', '.venv', 'venv', '.streamlit', '.DS_Store'}
            files = [f for f in os.listdir('.') if f not in ignored and not f.startswith('.')]
            if not files:
                return "The workspace is currently empty."
            return "Files in workspace:\n" + "\n".join(f"- {f}" for f in files)
        except Exception as e:
            return f"Error listing workspace files: {str(e)}"

    # 2. Sanitize and resolve the path, but don't allow escaping the workspace
    base_dir = os.path.abspath('.')
    target_path = os.path.abspath(filepath)
    if not target_path.startswith(base_dir):
        target_path = os.path.join(base_dir, os.path.basename(filepath))

    if not os.path.exists(target_path):
        try:
            files = [f for f in os.listdir('.') if f not in {'.git', '__pycache__', '.venv', 'venv'}]
            return f"Error: File '{filepath}' not found. Available files: {', '.join(files)}"
        except Exception:
            return f"Error: File '{filepath}' not found."

    if os.path.isdir(target_path):
        try:
            return f"Directory '{filepath}' contains:\n" + "\n".join(f"- {f}" for f in os.listdir(target_path))
        except Exception as e:
            return f"Error reading directory: {str(e)}"

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            return f.read()[:2000]
    except Exception as e:
        return f"File Reading Error: {str(e)}"

# Native Tool: Python Executor
@tool("python_executor")
def python_executor_tool(code: str) -> str:
    """Useful for running short Python snippets in a sandboxed subprocess.
    Input should be clean Python code. IMPORTANT: use print() for anything
    you want returned - only stdout/stderr are captured, not local variables."""
    import subprocess
    import sys
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=10,  # guard against infinite loops
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += f"\nRuntime Error:\n{result.stderr}"

        return output.strip() or "Code executed successfully with no printed output."
    except subprocess.TimeoutExpired:
        return "Error: Code execution timed out (10 second limit exceeded)."
    except Exception as e:
        return f"Execution Error: {str(e)}"
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass

# Native Tool: Web Search
web_search_tool = DuckDuckGoSearchRun(name="web_search", description="Useful for finding real-time information on the web.")

ALL_TOOLS = [calculator_tool, file_reader_tool, python_executor_tool, web_search_tool]

# Initialize cached Agent Executor with high speed (REST transport)
@st.cache_resource
def get_agent_executor(api_key: str):
    #  UPDATED CODE
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=api_key,
        temperature=0.0
    )

    system_prompt = (
        "You are a helpful, extremely fast AI assistant equipped with tools.\n"
        "Always choose the correct tool for the task.\n"
        "After a tool returns a result, you MUST always respond with a final "
        "answer in plain, direct language (e.g. 'The result is 120'). "
        "Never leave your final response empty, and never just stop after a "
        "tool call without summarizing the result for the user.\n"
        "Keep your final answers concise and clean."
    )

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    agent = create_tool_calling_agent(llm, ALL_TOOLS, prompt_template)

    return AgentExecutor(
        agent=agent,
        tools=ALL_TOOLS,
        verbose=True,
        max_iterations=4,
        handle_parsing_errors=True,
        return_intermediate_steps=True,
    )

def _extract_text(value):
    """Normalize whatever the agent/LLM returned into a plain string."""
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

        deduped = []
        for p in parts:
            if not deduped or deduped[-1] != p:
                deduped.append(p)

        return "\n".join(p for p in deduped if p)

    return str(value)


def run_agent_safely(query: str) -> str:
    """Acts as a drop-in replacement for the original app.agent import function."""
    current_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not current_key:
        return "Error: API Key is missing. Please provide it before running queries."

    try:
        executor = get_agent_executor(current_key)
        response = executor.invoke({"input": query})
        output = response.get("output", "") if isinstance(response, dict) else response
        output = _extract_text(output).strip()

        # Safety net: some models occasionally stop right after a tool call
        # without producing a summarizing final answer. If that happens,
        # surface the last tool's raw result instead of leaving the UI blank.
        if not output and isinstance(response, dict):
            steps = response.get("intermediate_steps") or []
            if steps:
                last_action, last_observation = steps[-1]
                tool_name = getattr(last_action, "tool", "tool")
                observation_text = _extract_text(last_observation).strip()
                if observation_text:
                    output = f"({tool_name} result) {observation_text}"

        return output or "(agent returned no output)"
    except Exception as err:
        return f"Error executing agent task: {str(err)}"


# ---------------------------------------------------------------------------
# Design tokens (peach / coral mockup palette) - UNTOUCHED FRONTEND
# ---------------------------------------------------------------------------
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');

:root{
    --peach:        #FBD9C8;
    --coral-wave:   #F2795F;
    --coral:        #EE6B54;
    --coral-tint:   #FDEAE4;
    --ink:          #4A3F3B;
    --muted:        #A8938C;
    --white:        #FFFFFF;
}

html, body, [data-testid="stAppViewContainer"]{
    font-family: 'Inter', sans-serif;
    background:
        radial-gradient(ellipse 120% 55% at 50% 100%, var(--coral-wave) 42%, transparent 43%),
        var(--peach);
    background-attachment: fixed;
}

#MainMenu, footer, header[data-testid="stHeader"]{ visibility: hidden; height: 0; }

/* --- the rounded "phone card" that holds everything --- */
.block-container{
    max-width: 480px;
    margin-top: 4vh;
    margin-bottom: 4vh;
    background: transparent;
    border-radius: 36px;
    padding: 0 0 28px 0;
    position: relative;
}

/* title block, sits in the peach area like the mockup's placeholder text */
.mock-title{
    text-align: center;
    padding: 26px 30px 26px 30px;
}
.mock-title h1{
    font-family: 'Poppins', sans-serif;
    font-weight: 700;
    font-size: 1.5rem;
    color: var(--ink);
    margin: 0 0 6px 0;
}
.mock-title p{
    font-family: 'Inter', sans-serif;
    font-weight: 500;
    font-size: 0.85rem;
    color: rgba(74,63,59,0.65);
    margin: 0;
}

/* clear-chat pill button */
div[data-testid="stButton"]{
    display: flex;
    justify-content: flex-end;
}
div[data-testid="stButton"] button{
    background: var(--white) !important;
    color: var(--coral) !important;
    border: 1.5px solid var(--coral) !important;
    border-radius: 14px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.78rem !important;
    padding: 6px 16px !important;
    white-space: nowrap !important;
    min-height: 0 !important;
    line-height: 1.2 !important;
    box-shadow: 0 4px 10px rgba(190, 90, 60, 0.10) !important;
    transition: background 0.15s ease, transform 0.1s ease;
}
div[data-testid="stButton"] button:hover{
    background: var(--coral-tint) !important;
}
div[data-testid="stButton"] button:active{
    transform: scale(0.97);
}
div[data-testid="stButton"] button p{
    font-size: 0.78rem !important;
    margin: 0 !important;
    white-space: nowrap !important;
}

/* chat messages styled as suggestion rows */
[data-testid="stChatMessage"]{
    border-radius: 16px !important;
    padding: 12px 16px !important;
    margin: 6px 22px !important;
    box-shadow: none !important;
    border: 1px solid transparent;
    justify-content: center !important;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]){
    background: var(--coral-tint) !important;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]){
    background: var(--white) !important;
    border: 1px solid #F3E6DF;
}
[data-testid="stChatMessageAvatarUser"], [data-testid="stChatMessageAvatarAssistant"]{
    display: none !important;
}
[data-testid="stChatMessageContent"]{
    text-align: center !important;
    width: 100% !important;
}
[data-testid="stChatMessageContent"] p{
    font-family: 'Inter', sans-serif;
    color: var(--ink);
    font-size: 0.95rem;
    margin: 0;
    text-align: left !important;
}

/* Streamlit renders stChatInput inside a fixed full-width footer that
   otherwise shows its own theme background (the "black bar"). Strip that
   back to transparent so only our page gradient shows through, and cap
   its inner width to match the card above it. */
[data-testid="stBottom"],
[data-testid="stBottom"] > div,
[data-testid="stBottomBlockContainer"]{
    background: transparent !important;
    box-shadow: none !important;
    border: none !important;
}
[data-testid="stBottomBlockContainer"]{
    max-width: 480px !important;
    padding: 14px 22px 28px 22px !important;
}

[data-testid="stChatInput"]{
    background: var(--white) !important;
    border-radius: 999px;
    border: 1.5px solid #F0DED5;
    padding: 2px 4px 2px 18px;
    margin: 0;
    box-shadow: 0 10px 24px rgba(190, 90, 60, 0.12);
}
/* neutralize any dark-theme background on inner wrapper layers first... */
[data-testid="stChatInput"] *{
    background-color: transparent !important;
}
/* ...then force the visible surfaces back to a single solid white */
[data-testid="stChatInput"] textarea,
[data-testid="stChatInput"] > div{
    background-color: var(--white) !important;
    font-family: 'Inter', sans-serif;
    color: var(--ink) !important;
}
[data-testid="stChatInput"] textarea::placeholder{
    color: var(--muted) !important;
}
[data-testid="stChatInput"] button{
    background-color: var(--coral) !important;
    border-radius: 50% !important;
    width: 34px !important;
    height: 34px !important;
}
[data-testid="stChatInput"] button svg{ fill: var(--white) !important; }

hr{ border-color: rgba(255,255,255,0.4) !important; margin: 22px 40px !important; }

.mock-watermark{
    text-align: center;
    font-family: 'Inter', sans-serif;
    font-size: 0.72rem;
    font-weight: 500;
    letter-spacing: 0.02em;
    color: rgba(255,255,255,0.85);
    margin-top: 6px;
}

div[data-testid="stAlert"]{
    margin: 0 22px 14px 22px;
    border-radius: 16px;
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Fake browser chrome + title (mirrors the mockup's top bar & headline area) - UNTOUCHED FRONTEND
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="mock-title">
        <h1>Multi-Tool Agent</h1>
        <p>File reader · Sandboxed code executor · Web search · Calculator</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# Check for required API keys to show a friendly reminder in the UI
api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
if not api_key:
    st.warning(
        "**API Key Missing:** Neither `GEMINI_API_KEY` nor `GOOGLE_API_KEY` was found in your environment. "
        "Please set it in your `.env` file or export it in your terminal before running the app."
    )

col1, col2 = st.columns([4, 1])
with col2:
    if st.button("Clear chat"):
        st.session_state.history = []
        st.rerun()

st.divider()

if "history" not in st.session_state:
    st.session_state.history = []

for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

query = st.chat_input("How to...")

if query:
    st.session_state.history.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                output = run_agent_safely(query)
            except Exception as e:  # noqa: BLE001
                output = f"Something went wrong: {e}"
        st.markdown(output)

    st.session_state.history.append({"role": "assistant", "content": output})

st.markdown('<div class="mock-watermark">Powered by Gemini</div>', unsafe_allow_html=True)