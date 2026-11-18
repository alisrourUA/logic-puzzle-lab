"""LLM puzzle generator + verifier-guided repair loop.

The repair loop follows the ReAct pattern from the course:
    Thought      - the LLM explains (in a 'thought' field) what it intends
    Action       - it outputs a puzzle (JSON)
    Observation  - the exact solver reports what is wrong
and repeats until the puzzle is valid or we run out of rounds.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from . import config
from .baseline import generate as baseline_generate
from .verifier import VerifyReport, verify

SYSTEM_PROMPT = """You are a creative designer of logic grid puzzles (Zebra / Einstein riddles).

A puzzle has N houses in a row, numbered 1..N from left to right. There are several
categories (e.g. color, person, pet). Each category has exactly N different values and
each value is in exactly one house. The solver must deduce the full arrangement from clues.

You must answer with ONE JSON object and nothing else. Use exactly this field order:
{
  "thought": "<your plan: how the clues will pin down every value, and how you reach the requested difficulty>",
  "title": "<short creative title>",
  "story": "<1-2 sentence story setting>",
  "size": N,
  "categories": {"<category>": ["<value1>", ..., "<valueN>"], ...},
  "claimed_solution": {"<category>": ["<value in house 1>", ..., "<value in house N>"], ...},
  "clues": [ <clue>, ... ],
  "claimed_unique": true or false
}

Items are written "category:value", e.g. "pet:cat". Allowed clue objects:
  {"type": "same",        "a": item, "b": item}   a and b are in the same house
  {"type": "not_same",    "a": item, "b": item}   a and b are in different houses
  {"type": "at",          "a": item, "pos": k}    a is in house k
  {"type": "not_at",      "a": item, "pos": k}    a is not in house k
  {"type": "right_of",    "a": item, "b": item}   a is IMMEDIATELY right of b (pos a = pos b + 1)
  {"type": "left_of",     "a": item, "b": item}   a is somewhere left of b (pos a < pos b)
  {"type": "next_to",     "a": item, "b": item}   a and b are in adjacent houses
  {"type": "not_next_to", "a": item, "b": item}   a and b are not adjacent (and not the same house)

Method:
1. First decide the hidden solution (claimed_solution).
2. Then write clues that are all TRUE for that solution.
3. Add clues until every value of every category is forced. For N houses and C categories
   there are C*N values to place; a 4-house, 3-category puzzle typically needs about 8-12 clues,
   a 5-house, 4-category puzzle about 14-20.
4. Each clue must be checkable against claimed_solution.

Rules:
- The clues must have EXACTLY ONE solution, and it must equal claimed_solution.
- Do not include clues that are not needed.
- Output strict JSON: no comments (no // or /* */), no trailing commas, no text outside the JSON.
- Difficulty: easy = mostly direct clues (at, same), solvable by simple deduction;
  medium = mix of clue types; hard = mostly relational / negative clues (next_to,
  left_of, not_same, not_next_to) that require chains of reasoning, few direct 'at' clues.
"""

FEEDBACK_TEMPLATE = """FEEDBACK from the exact solver (Observation):
{feedback}

Fix the puzzle. Keep the same categories and claimed_solution unless they are the problem.
In 'thought', explain what you change, then return the complete corrected JSON object
(same schema, strict JSON, no comments)."""


@dataclass
class Spec:
    size: int = 4
    n_cats: int = 3
    difficulty: str = "medium"   # easy / medium / hard
    shots: int = 0               # number of worked example puzzles in the prompt
    temperature: float = 0.7
    top_p: float = 1.0
    theme: str | None = None

    def to_dict(self):
        return dict(size=self.size, n_cats=self.n_cats, difficulty=self.difficulty, shots=self.shots,
                    temperature=self.temperature, top_p=self.top_p, theme=self.theme)


_EXAMPLE_CACHE: dict[tuple, list[str]] = {}


def few_shot_examples(k: int) -> list[str]:
    """k verified example puzzles (from the classic generator) with mixed difficulty."""
    if k <= 0:
        return []
    key = (k,)
    if key not in _EXAMPLE_CACHE:
        plan = [(3, 3, "easy", 11), (4, 3, "hard", 7), (4, 4, "hard", 3), (5, 3, "easy", 5)]
        out = []
        for size, nc, diff, seed in plan[:k]:
            p = baseline_generate(size, nc, diff, seed=seed)
            rep = verify(p, check_redundancy=False)
            d = {"thought": f"A {rep.difficulty['label']} {size}-house puzzle; every clue is needed.",
                 "title": f"Example {len(out) + 1}", "story": "A quiet street.",
                 "size": p.size, "categories": p.categories, "claimed_solution": p.claimed_solution,
                 "clues": [c.to_dict() for c in p.clues], "claimed_unique": True}
            import json
            out.append(f"EXAMPLE PUZZLE {len(out) + 1} (verified unique, difficulty = "
                       f"{rep.difficulty['label']}):\n{json.dumps(d, ensure_ascii=False)}")
        _EXAMPLE_CACHE[key] = out
    return _EXAMPLE_CACHE[key]


def build_user_prompt(spec: Spec) -> str:
    parts = []
    ex = few_shot_examples(spec.shots)
    if ex:
        parts.append("Here are examples of correct puzzles in the required format:\n\n" + "\n\n".join(ex))
    theme = f" Theme: {spec.theme}." if spec.theme else ""
    parts.append(
        f"### GENERATE\nCreate a NEW, original puzzle. Spec: size={spec.size} houses, "
        f"categories={spec.n_cats} categories, difficulty={spec.difficulty}.{theme} "
        f"Use your own category names and values (do not copy the examples).")
    return "\n\n".join(parts)


@dataclass
class Attempt:
    round: int
    raw: str
    report: VerifyReport
    prompt_tokens: int
    completion_tokens: int
    seconds: float

    def summary(self) -> dict[str, Any]:
        r = self.report
        return {"round": self.round, "status": r.status, "n_solutions": r.n_solutions,
                "claimed_unique": r.claimed_unique, "claim_correct": r.claim_correct,
                "difficulty": r.difficulty, "feedback": r.feedback,
                "prompt_tokens": self.prompt_tokens, "completion_tokens": self.completion_tokens}


@dataclass
class GenerationRun:
    spec: Spec
    attempts: list[Attempt] = field(default_factory=list)

    @property
    def final(self) -> Attempt:
        return self.attempts[-1]

    @property
    def first(self) -> Attempt:
        return self.attempts[0]

    def to_record(self) -> dict[str, Any]:
        f, first = self.final.report, self.first.report
        return {
            **self.spec.to_dict(),
            "first_status": first.status,
            "first_claimed_unique": first.claimed_unique,
            "first_claim_correct": first.claim_correct,
            "final_status": f.status,
            "valid_first_try": first.valid,
            "valid_final": f.valid,
            "rounds_used": len(self.attempts) - 1,
            "measured_label": (f.difficulty or {}).get("label"),
            "measured_score": (f.difficulty or {}).get("score"),
            "guesses": (f.difficulty or {}).get("guesses"),
            "n_clues": len(f.puzzle.clues) if f.puzzle else None,
            "n_redundant": len(f.redundant_clues) if f.valid else None,
            "canonical": f.puzzle.canonical_key() if f.puzzle else None,
            "prompt_tokens": sum(a.prompt_tokens for a in self.attempts),
            "completion_tokens": sum(a.completion_tokens for a in self.attempts),
            "seconds": round(sum(a.seconds for a in self.attempts), 2),
            "attempts": [a.summary() for a in self.attempts],
            "final_puzzle": f.puzzle.to_dict() if f.puzzle else None,
            "final_raw": self.final.raw,
        }


def run(client, spec: Spec, max_repair: int | None = None, on_step=None) -> GenerationRun:
    """Generate one puzzle and repair it with solver feedback up to `max_repair` times."""
    max_repair = config.MAX_REPAIR_ROUNDS if max_repair is None else max_repair
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(spec)}]
    gr = GenerationRun(spec)
    for rnd in range(max_repair + 1):
        t = time.time()
        reply = client.chat(messages, temperature=spec.temperature, top_p=spec.top_p)
        rep = verify(reply.text)
        att = Attempt(rnd, reply.text, rep, reply.prompt_tokens, reply.completion_tokens,
                      reply.seconds or time.time() - t)
        gr.attempts.append(att)
        if on_step:
            on_step(att)
        if rep.valid:
            break
        messages.append({"role": "assistant", "content": reply.text})
        messages.append({"role": "user", "content": FEEDBACK_TEMPLATE.format(feedback=rep.feedback)})
    return gr
