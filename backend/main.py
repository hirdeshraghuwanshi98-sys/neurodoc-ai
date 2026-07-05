"""
main.py
-------
NeuroDoc AI backend: FastAPI server exposing:
  POST /api/upload   -> ingest a PDF/TXT into the RAG index
  POST /api/chat      -> stream an agent response (Server-Sent Events)
  GET  /api/stats      -> document/chunk counters for the sidebar
  /                    -> serves the static frontend (index.html)

Run locally:
    uvicorn main:app --reload --port 8000
"""

import os
import json
import shutil
import uuid
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from rag_engine import RAGEngine
from agent import Agent

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="NeuroDoc AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

rag_engine = RAGEngine()
agent = Agent(api_key=GROQ_API_KEY)

# in-memory chat history per session (demo-scale; swap for Redis/DB in production)
sessions = {}


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    save_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}_{file.filename}")
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    chunk_count = rag_engine.add_document(save_path, file.filename)
    return {
        "filename": file.filename,
        "chunks_indexed": chunk_count,
        "status": "indexed" if chunk_count else "no_extractable_text",
    }


@app.get("/api/stats")
async def stats():
    return rag_engine.stats()


@app.post("/api/chat")
async def chat(request: Request):
    body = await request.json()
    query = body.get("message", "").strip()
    session_id = body.get("session_id", "default")

    if session_id not in sessions:
        sessions[session_id] = []
    history = sessions[session_id]

    def event_stream():
        collected = ""
        for event in agent.stream_answer(query, rag_engine, history):
            if event["type"] == "done":
                collected = event["full_text"]
            yield f"data: {json.dumps(event)}\n\n"

        history.append({"role": "user", "content": query})
        history.append({"role": "assistant", "content": collected})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# Serve the frontend last so /api routes above take priority
app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")
