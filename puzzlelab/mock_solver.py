"""Offline imitation of an LLM solving puzzles (for testing Part 2 without an API key).

Accuracy is made to depend on method and difficulty so the pipeline and charts can be
exercised. These numbers are NOT results - real results come from the OpenAI backend.
"""
from __future__ import annotations

import json

from .difficulty import rate

BASE = {"plain": {"easy": 0.55, "medium": 0.3, "hard": 0.1},
        "cot": {"easy": 0.75, "medium": 0.5, "hard": 0.25}}


def _corrupt(rng, truth):
    t = {k: list(v) for k, v in truth.items()}
    cat = rng.choice(list(t))
    i, j = rng.sample(range(len(t[cat])), 2)
    t[cat][i], t[cat][j] = t[cat][j], t[cat][i]
    return t


def mock_solve_reply(rng, messages, puzzle, truth) -> str:
    system = messages[0]["content"]
    label = rate(puzzle).label
    if "Thought" in system and "Action" in system:  # ReAct
        n_obs = sum(1 for m in messages if m["role"] == "user" and m["content"].startswith("Observation"))
        if n_obs == 0:
            return "Thought: Let me see what pure deduction gives.\nAction: deduce[{}]"
        last = messages[-1]["content"]
        if "All items are determined" in last or "satisfies all clues" in last:
            return f"Thought: Everything is fixed.\nAction: finish[{json.dumps(truth)}]"
        p_ok = {"easy": 0.9, "medium": 0.75, "hard": 0.55}[label]
        guess = truth if rng.random() < p_ok else _corrupt(rng, truth)
        act = "check" if n_obs < 3 and rng.random() < 0.6 else "finish"
        return f"Thought: I will try this arrangement.\nAction: {act}[{json.dumps(guess)}]"
    method = "cot" if "step by step" in system else "plain"
    ok = rng.random() < BASE[method][label]
    ans = truth if ok else _corrupt(rng, truth)
    pre = "Clue 1 tells us ... so ...\n" * 3 + "ANSWER: " if method == "cot" else ""
    return pre + json.dumps(ans)
