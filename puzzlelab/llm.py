"""LLM clients: the real OpenAI client and an offline mock.

Both expose:  chat(messages, temperature, top_p, max_tokens) -> LLMReply

The mock lets us test the whole pipeline without an API key. It imitates typical
LLM mistakes (missing clues -> several solutions, contradicting clues, broken JSON)
more often at high temperature. It is ONLY for testing - real results come from
the OpenAI backend.
"""
from __future__ import annotations

import json
import random
import re
import time
from dataclasses import dataclass

from . import config


@dataclass
class LLMReply:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0


class OpenAIClient:
    def __init__(self, model: str | None = None):
        import os

        from openai import OpenAI  # imported lazily so the mock works without the package
        # OPENAI_BASE_URL lets you use any OpenAI-compatible provider (Groq, Gemini, OpenRouter...)
        self.client = OpenAI(base_url=os.getenv("OPENAI_BASE_URL") or None)
        self.model = model or config.MODEL
        self.name = self.model

    def chat(self, messages, temperature=0.7, top_p=1.0, max_tokens=1500, json_mode=False) -> LLMReply:
        kwargs = dict(model=self.model, messages=messages, temperature=temperature,
                      top_p=top_p, max_tokens=max_tokens)
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        t = time.time()
        for attempt in range(8):
            try:
                r = self.client.chat.completions.create(**kwargs)
                break
            except Exception as e:  # rate limits / transient errors
                msg = str(e)
                if "insufficient_quota" in msg or "no credits" in msg.lower() or "billing" in msg.lower():
                    raise SystemExit("\n[API] The account behind this key has no credit left. Add credit, or use "
                                     "another provider (see README: 'Free alternative').") from None
                if getattr(e, "status_code", None) in (400, 401, 403, 404):
                    raise
                if attempt == 7:
                    raise
                wait = min(60, 3 * 2 ** attempt)
                print(f"  [api] {type(e).__name__}: waiting {wait}s and retrying (free tiers have per-minute limits)")
                time.sleep(wait)
        u = r.usage
        return LLMReply(text=r.choices[0].message.content or "",
                        prompt_tokens=getattr(u, "prompt_tokens", 0),
                        completion_tokens=getattr(u, "completion_tokens", 0),
                        seconds=time.time() - t)


class MockClient:
    """Offline stand-in for an LLM, used for tests and demos without a key."""

    name = "mock"

    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)

    def chat(self, messages, temperature=0.7, top_p=1.0, max_tokens=1500, json_mode=False) -> LLMReply:
        last = messages[-1]["content"]
        if "### SOLVE" in messages[0]["content"] or "### SOLVE" in last:
            text = self._solve(messages, temperature)
        elif last.startswith("FEEDBACK"):
            text = self._repair(messages, temperature)
        else:
            text = self._generate(last, temperature)
        n_in = sum(len(m["content"]) for m in messages) // 4
        return LLMReply(text=text, prompt_tokens=n_in, completion_tokens=len(text) // 4)

    # ----- generation -----
    def _generate(self, prompt: str, temperature: float) -> str:
        from .baseline import generate
        m = re.search(r"size=(\d+).*?categories=(\d+).*?difficulty=(\w+)", prompt, re.S)

    

def get_client(backend: str | None = None, model: str | None = None, seed: int = 0):
    backend = backend or config.BACKEND
    if backend == "openai":
        return OpenAIClient(model)
    return MockClient(seed)