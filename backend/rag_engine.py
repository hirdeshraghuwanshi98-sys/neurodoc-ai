"""
rag_engine.py
--------------
Handles document ingestion (PDF / TXT), chunking, embedding, and
similarity search using a local FAISS index.

Why local embeddings? Using sentence-transformers keeps the RAG
pipeline free to run (no per-call API cost) and fast enough for a
student-scale document set. Only the *generation* step calls the LLM.
"""

import os
import uuid
import faiss
import numpy as np
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
CHUNK_SIZE = 800          # characters per chunk
CHUNK_OVERLAP = 120       # overlap between chunks to preserve context


class RAGEngine:
    def __init__(self):
        self.model = SentenceTransformer(EMBED_MODEL_NAME)
        self.dimension = self.model.get_sentence_embedding_dimension()
        self.index = faiss.IndexFlatL2(self.dimension)
        self.chunks = []          # parallel array: text of each chunk
        self.sources = []         # parallel array: originating filename
        self.doc_registry = {}    # filename -> chunk count

    # ---------- Ingestion ----------

    def _extract_text(self, filepath: str) -> str:
        if filepath.lower().endswith(".pdf"):
            reader = PdfReader(filepath)
            return "\n".join((page.extract_text() or "") for page in reader.pages)
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    def _chunk_text(self, text: str):
        text = " ".join(text.split())  # normalize whitespace
        chunks = []
        start = 0
        while start < len(text):
            end = start + CHUNK_SIZE
            chunks.append(text[start:end])
            start = end - CHUNK_OVERLAP
        return [c for c in chunks if len(c.strip()) > 40]

    def add_document(self, filepath: str, filename: str) -> int:
        text = self._extract_text(filepath)
        new_chunks = self._chunk_text(text)
        if not new_chunks:
            return 0

        embeddings = self.model.encode(new_chunks, convert_to_numpy=True)
        self.index.add(np.array(embeddings, dtype="float32"))
        self.chunks.extend(new_chunks)
        self.sources.extend([filename] * len(new_chunks))
        self.doc_registry[filename] = self.doc_registry.get(filename, 0) + len(new_chunks)
        return len(new_chunks)

    # ---------- Retrieval ----------

    def search(self, query: str, top_k: int = 4):
        if self.index.ntotal == 0:
            return []
        query_vec = self.model.encode([query], convert_to_numpy=True).astype("float32")
        distances, indices = self.index.search(query_vec, min(top_k, self.index.ntotal))
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue
            results.append({
                "text": self.chunks[idx],
                "source": self.sources[idx],
                "score": float(1 / (1 + dist)),  # convert distance to a 0-1-ish similarity
            })
        return results

    def has_documents(self) -> bool:
        return self.index.ntotal > 0

    def stats(self):
        return {
            "total_chunks": len(self.chunks),
            "documents": self.doc_registry,
        }
