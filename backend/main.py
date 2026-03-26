from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import json

from database import get_db, execute_query, get_schema_info
from graph import build_graph, get_graph_data, get_node_neighbors
from llm import query_llm
from guardrails import is_domain_query, OUT_OF_SCOPE_RESPONSE
from ingest import ingest_data

app = FastAPI(title="Order to Cash Graph API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Build graph on startup
@app.on_event("startup")
async def startup_event():
    ingest_data()
    build_graph()
    print("Data ingested and graph built.")

class ChatRequest(BaseModel):
    message: str
    history: Optional[list] = []

class ChatResponse(BaseModel):
    answer: str
    sql: Optional[str] = None
    data: Optional[list] = None
    highlighted_nodes: Optional[list] = []

@app.get("/")
def root():
    return {"status": "ok", "message": "Order to Cash API running"}

@app.get("/graph")
def get_graph():
    """Return full graph nodes and edges for visualization."""
    return get_graph_data()

@app.get("/graph/node/{node_id}")
def get_node(node_id: str):
    """Return a node and its immediate neighbors."""
    return get_node_neighbors(node_id)

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Accept natural language query, return data-backed answer."""
    message = req.message.strip()

    # Guardrail: reject off-topic queries
    if not is_domain_query(message):
        return ChatResponse(answer=OUT_OF_SCOPE_RESPONSE)

    schema = get_schema_info()
    result = await query_llm(message, schema, req.history)

    return ChatResponse(
        answer=result["answer"],
        sql=result.get("sql"),
        data=result.get("data"),
        highlighted_nodes=result.get("highlighted_nodes", []),
    )

@app.get("/schema")
def schema():
    return {"schema": get_schema_info()}

@app.get("/health")
def health():
    return {"status": "healthy"}
