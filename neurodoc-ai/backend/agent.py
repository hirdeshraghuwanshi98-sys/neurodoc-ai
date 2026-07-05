"""
agent.py
--------
A lightweight multi-tool agent (in the spirit of the "AI Agents" module:
LangChain/CrewAI-style tool routing, but hand-rolled so every line is
explainable in a viva).

Flow for every user message:
  1. ROUTE   -> ask the LLM (fast, small prompt) which tool fits: rag | calculator | direct
  2. EXECUTE -> run the chosen tool to gather context
  3. ANSWER  -> ask the LLM again, this time with the gathered context, to produce the final reply
  4. Every step yields a "trace" event so the frontend can render a live agent log.
"""

import os
import re
import json
from groq import Groq

MODEL = "llama-3.3-70b-versatile"  # fast + free-tier friendly on Groq


class Tool:
    name = "base"

    def run(self, query: str, rag_engine):
        raise NotImplementedError


class CalculatorTool(Tool):
    name = "calculator"

    SAFE_PATTERN = re.compile(r"^[\d\s\.\+\-\*\/\(\)%]+$")

    def run(self, query: str, rag_engine):
        expr_match = re.search(r"[\d\.\+\-\*\/\(\)%\s]{3,}", query)
        if not expr_match or not self.SAFE_PATTERN.match(expr_match.group()):
            return "Could not find a safe arithmetic expression to evaluate."
        try:
            result = eval(expr_match.group(), {"__builtins__": {}})
            return f"Calculation result: {result}"
        except Exception as e:
            return f"Calculator error: {e}"


class RAGTool(Tool):
    name = "rag"

    def run(self, query: str, rag_engine):
        if not rag_engine.has_documents():
            return "No documents have been uploaded yet, so retrieval is unavailable."
        hits = rag_engine.search(query, top_k=4)
        if not hits:
            return "No relevant passages were found in the uploaded documents."
        formatted = "\n\n".join(
            f"[Source: {h['source']} | relevance {h['score']:.2f}]\n{h['text']}"
            for h in hits
        )
        return formatted


class DirectTool(Tool):
    name = "direct"

    def run(self, query: str, rag_engine):
        return ""  # no extra context needed; the LLM answers from its own knowledge


class Agent:
    def __init__(self, api_key: str):
        self.client = Groq(api_key=api_key)
        self.tools = {
            "rag": RAGTool(),
            "calculator": CalculatorTool(),
            "direct": DirectTool(),
        }

    def _route(self, query: str, has_docs: bool):
        system = (
            "You are a routing controller for an AI agent. Given a user message, "
            "reply with exactly one word: 'rag' if the question likely needs the "
            "user's uploaded documents to answer, 'calculator' if it is an arithmetic "
            "question, or 'direct' if it can be answered from general knowledge. "
            f"Documents currently uploaded: {has_docs}."
        )
        resp = self.client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": query},
            ],
            max_tokens=5,
            temperature=0,
        )
        choice = resp.choices[0].message.content.strip().lower()
        for tool_name in self.tools:
            if tool_name in choice:
                return tool_name
        return "direct"

    def stream_answer(self, query: str, rag_engine, history):
        """
        Generator yielding dict events:
          {"type": "trace", "step": "...", "detail": "..."}
          {"type": "token", "content": "..."}
          {"type": "done"}
        """
        route = self._route(query, rag_engine.has_documents())
        yield {"type": "trace", "step": "route", "detail": f"Selected tool -> {route}"}

        tool = self.tools[route]
        context = tool.run(query, rag_engine)
        preview = (context[:160] + "...") if len(context) > 160 else context
        yield {"type": "trace", "step": "execute", "detail": preview or "(no extra context needed)"}

        system_prompt = (
            "You are NeuroDoc AI, a helpful research assistant. "
            "If context passages are provided below, ground your answer in them "
            "and mention the source filename when relevant. If no context is "
            "provided, answer directly and concisely."
        )
        user_content = query if not context else f"Context:\n{context}\n\nQuestion: {query}"

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-6:])  # short rolling memory
        messages.append({"role": "user", "content": user_content})

        yield {"type": "trace", "step": "generate", "detail": "Generating final answer..."}

        stream = self.client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.4,
            stream=True,
        )
        full_text = ""
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                full_text += delta
                yield {"type": "token", "content": delta}

        yield {"type": "done", "full_text": full_text, "tool_used": route}
