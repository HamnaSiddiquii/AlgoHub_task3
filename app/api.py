"""
FastAPI service for the multi-tool agent.

Run with:
    uvicorn app.api:app --reload --port 8000

Then:
    curl -X POST http://localhost:8000/agent -H "Content-Type: application/json" \
         -d '{"query": "What is sqrt(144) plus 10?"}'
"""

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.agent import run_agent_safely

app = FastAPI(
    title="Multi-Tool Agent API",
    description="Week 3 project: an agent with file reader, code executor, web search, and calculator tools.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this for real deployments
    allow_methods=["*"],
    allow_headers=["*"],
)


class AgentRequest(BaseModel):
    query: str = Field(..., min_length=1, description="The user's natural-language request")


class AgentResponse(BaseModel):
    output: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/agent", response_model=AgentResponse)
def run_agent(req: AgentRequest):
    output = run_agent_safely(req.query)
    return AgentResponse(output=output)
