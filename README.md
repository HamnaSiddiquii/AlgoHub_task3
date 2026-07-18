# Multi-Tool Agent (Week 3)

An agent built with LangChain + gemini-3.1-flash-lite that can use four tools — **file reader**,
**sandboxed code executor**, **web search**, and **calculator** — deployed behind
a **FastAPI** backend with a **Streamlit** front end.

## How this maps to the curriculum

| Concept | Where it lives |
|---|---|
| Tool Chaining | `AgentExecutor` in `app/agent.py` — the agent can call several tools in sequence (e.g. read a file, then run code on its contents) |
| Tool Selection Logic | The system prompt in `app/agent.py` + precise `description` strings on each `Tool` in `app/tools/` (this is the main lever for good selection) |
| Error Handling | `run_agent_safely()` (retries + backoff) and `handle_parsing_errors=True` / `max_iterations` / `max_execution_time` on the executor |
| Sandboxed Code Execution | `app/tools/code_executor.py` — AST import-blocking, subprocess isolation, POSIX resource limits, hard timeout |
| Multi-Tool Design | `app/tools/__init__.py` — a clean registry (`ALL_TOOLS`) the agent is built from |
| Safe Execution | Calculator uses AST parsing instead of `eval()`; file reader is jailed to a workspace directory |
| Agent Reliability | Retry/backoff wrapper, iteration/time caps, clean error strings instead of raw tracebacks |

## Project layout

```
multi-tool-agent/
├── app/
│   ├── agent.py          # builds the LangChain agent + reliability wrapper
│   ├── api.py             # FastAPI app exposing POST /agent
│   └── tools/
│       ├── calculator.py      # AST-based safe math evaluator
│       ├── code_executor.py   # sandboxed Python execution
│       ├── file_reader.py     # jailed file reads
│       └── web_search.py      # DuckDuckGo search (no API key needed)
├── streamlit_app.py       # chat UI, calls the FastAPI backend
├── workspace/             # sandbox dir the file_reader tool can read from
├── requirements.txt
└── .env.example
```

## Setup

```bash
cd multi-tool-agent
pip install -r requirements.txt
cp .env.example .env
# edit .env and set OPENAI_API_KEY=sk-...
```

## Run it

**Just one command** — the Streamlit app calls the agent directly in-process,
so there's no separate backend server to start or connection errors to debug:

```bash
streamlit run streamlit_app.py
```
Live Demo: https://algoapptask3-6wpeimmwtc3bpfysyef3kl.streamlit.app/

Then open the URL it prints (usually http://localhost:8501) and try:
- `What is 12 * (7 + sqrt(9))?` → calculator
- `List the files in my workspace, then read sample.txt and tell me the numbers in it` → tool chaining (list_files → file_reader)
- `Write and run Python to compute the 20th Fibonacci number` → code_executor
- `What's the latest news on the James Webb telescope?` → web_search

You can also test the agent from the command line, no UI at all:
```bash
python -m app.agent "What is 5 factorial?"
```

### Optional: a separate FastAPI service

`app/api.py` exposes the same agent as an HTTP endpoint, useful if you want
other clients (not just this Streamlit app) to call it, or you're deploying the
agent as its own microservice:

```bash
uvicorn app.api:app --reload --port 8000
```
```bash
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"query": "What is sqrt(144) plus 10?"}'
```
This is independent of the Streamlit app above — you don't need it running for
the UI to work.


## Notes on the sandbox

`code_executor.py` is a **teaching-grade** sandbox: AST-based import blocking,
subprocess isolation, POSIX resource limits (CPU/memory/file descriptors), and a
hard timeout. It's good enough for a demo/internal agent, but if you ever exposed
this to untrusted third-party users in production, put it inside a real
container/VM sandbox (Docker with seccomp, gVisor, Firecracker, etc.) rather than
relying on the process-level controls alone.

## Extending it

- Add a new tool: create a `Tool(...)` in `app/tools/`, add it to `ALL_TOOLS` in
  `app/tools/__init__.py`, and (optionally) mention it in the system prompt's
  tool-selection rules.
- Swap web search providers: replace the body of `search_web()` in
  `app/tools/web_search.py` with a Tavily/SerpAPI/Bing client call.
- Deploy for real: containerize `app/` (Dockerfile not included) and deploy the
  FastAPI service to any container host; point `AGENT_API_URL` in the Streamlit
  app (or a separately hosted Streamlit Cloud app) at its public URL.
