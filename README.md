# NeuroDoc AI — Multi-Agent RAG Research Assistant

NeuroDoc AI is a document-aware chat assistant that **routes every question through an agent**
before answering. The agent decides — live, in view of the user — whether to pull context from
uploaded documents (RAG), run a calculation, or answer directly from the model's own knowledge.
The decision path is rendered in real time in the **Agent Trace** panel, which makes the internals
of the system visible rather than a black box.

## Why this project stands out

Most student RAG demos are "upload a PDF, ask a question." NeuroDoc AI adds a genuine **agentic
routing layer** on top: the LLM itself decides which tool to use per-message, and that decision —
plus the retrieved context and generation step — streams to the UI as a live log. This maps
directly onto the curriculum modules you can point to during a review:

| Feature in NeuroDoc AI | Curriculum module it demonstrates |
|---|---|
| Groq-hosted Llama 3.3 for generation | Section 3 — Accessing LLMs in Python (Groq LLMs) |
| Chunking + embeddings + FAISS similarity search | Section 6 — RAG |
| LLM-based tool routing (`rag` / `calculator` / `direct`) | Section 7 — AI Agents |
| Streaming FastAPI backend, deployed on an EC2 instance | Section 8 — LLM Deployment |
| Clear tool → server boundary (extendable to MCP) | Section 9 — MCP, natural next step |

## Architecture

```
┌─────────────┐      upload PDF/TXT       ┌───────────────────┐
│   Browser    │ ────────────────────────▶│   rag_engine.py    │
│  (index.html)│                           │  chunk → embed →   │
│              │◀──── SSE token stream ────│  FAISS index        │
└──────┬───────┘                           └─────────┬─────────┘
       │ POST /api/chat                               │ similarity search
       ▼                                               ▼
┌─────────────────────────────────────────────────────────────┐
│                         agent.py                              │
│  1. route(query)   -> "rag" | "calculator" | "direct"          │
│  2. tool.run(query) -> gathers context                          │
│  3. LLM generate(context + query) -> streamed answer             │
└─────────────────────────────────────────────────────────────┘
```

## Tech stack

- **Backend:** FastAPI, Server-Sent Events for streaming
- **LLM:** Groq API (`llama-3.3-70b-versatile`) — free tier available
- **Embeddings:** `sentence-transformers/all-MiniLM-L6-v2` (runs locally, no API cost)
- **Vector store:** FAISS (in-memory, flat L2 index)
- **Frontend:** Vanilla HTML/CSS/JS — no build step, easy to deploy anywhere

## Running locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # then paste your free Groq API key into .env
uvicorn main:app --reload --port 8000
```

Open `http://localhost:8000` in your browser.

Get a free Groq API key at https://console.groq.com/keys — no credit card required.

## Explaining it in a viva (quick talking points)

1. **"It's not just RAG — it's agentic."** The model itself chooses the tool per message; you can
   show this live by asking a math question ("what's 45*12?") vs a document question vs a general
   knowledge question, and watch the trace panel pick a different tool each time.
2. **"Retrieval is local and free."** Embeddings run on-device via sentence-transformers, so the
   only paid/API-metered call is the final generation step — keeps cost near zero.
3. **"It streams."** Server-Sent Events push tokens to the browser as they're generated, the same
   pattern production chat products use.
4. **"It's extensible to MCP."** Because each tool is a small, isolated class with a `run()`
   method, swapping a tool for an MCP-server-backed tool call is a drop-in change — a natural
   next step tying into the MCP module.

## License

MIT — use it, extend it, ship it.
