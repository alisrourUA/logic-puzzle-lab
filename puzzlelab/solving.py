"""Part 2: LLM as puzzle SOLVER - plain vs chain-of-thought vs ReAct agent.

ReAct agent tools (the 'Action' space, like Search/Lookup/Finish on the ReAct slides):
    deduce[{"item": house, ...}]  run logical deduction from the clues plus optional
                                  assumptions; returns, for every item, the houses still
                                  possible - or says the assumptions lead to a contradiction.
    check[{"category": [...], ...}]  check a full proposed solution; returns which clues
                                  it violates (it does NOT reveal the answer).
    finish[{"category": [...], ...}] submit the final answer.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

from .difficulty import Contradiction, _initial, propagate
from .puzzle import Puzzle, extract_json, render_clue, render_puzzle, solution_to_table, table_to_solution
from .solver import solve

ANSWER_FORMAT = ('{"<category>": ["<value in house 1>", "<value in house 2>", ...], ...} '
                 'with one list per category')

PLAIN_SYSTEM = f"""### SOLVE
You solve logic grid puzzles. Reply with ONLY the final answer as JSON: {ANSWER_FORMAT}. No explanation."""

COT_SYSTEM = f"""### SOLVE
You solve logic grid puzzles. Think step by step: go through the clues, write down what each one
implies, and eliminate possibilities until everything is determined. When you are done, write a line
"ANSWER:" followed by the final answer as JSON: {ANSWER_FORMAT}."""

REACT_SYSTEM = f"""### SOLVE
You solve logic grid puzzles by interleaving Thought, Action and Observation steps.
Each reply must contain exactly one Thought line and one Action line, and then stop:
Thought: <your reasoning about the current situation>
Action: <one action>

Available actions (write them exactly like the examples, with square brackets):
(1) deduce[<assumptions>] - applies the clues with logical deduction (plus your assumptions) and returns,
    for every item, the houses it can still be in, or reports that the assumptions lead to a contradiction.
    Assumptions map "category:value" to a house number. Examples:
    Action: deduce[{{}}]
    Action: deduce[{{"person:Rita": 2, "pet:cat": 3}}]
(2) check[<full answer JSON>] - tells you which clues a complete proposed answer violates.
(3) finish[<full answer JSON>] - submits your final answer and ends the task.
Good strategy: start with deduce[{{}}]; if items are still open, assume one value and deduce again
(a contradiction means that assumption is wrong); when everything is determined, finish.
Answer JSON format: {ANSWER_FORMAT}.
You will then receive an Observation. You have at most {{max_steps}} actions."""


@dataclass
class SolveRun:
    method: str
    correct: bool
    cell_accuracy: float
    steps: int
    prompt_tokens: int
    completion_tokens: int
    seconds: float
    answer: dict | None
    error: str | None = None
    transcript: list[dict] = field(default_factory=list)

    def to_record(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in ("method", "correct", "cell_accuracy", "steps", "prompt_tokens",
                                              "completion_tokens", "seconds", "answer", "error")} | \
            {"transcript": self.transcript}


def _norm(x) -> str:
    return str(x).strip().lower()


def canon_table(p: Puzzle, table) -> dict | None:
    """Map an LLM answer onto the puzzle's exact category/value spelling (case-insensitive)."""
    if not isinstance(table, dict):
        return None
    keys = {_norm(k): k for k in table}
    used = set()
    out = {}
    for cat, vals in p.categories.items():
        k = keys.get(_norm(cat))
        if k is None:
            # misnamed category (e.g. "house" instead of "person"): pick the unused key
            # whose values overlap most with this category's values
            want = {_norm(v) for v in vals}
            best, best_hits = None, 0
            for cand, row in table.items():
                if cand in used or _norm(cand) in {_norm(c) for c in p.categories} or not isinstance(row, list):
                    continue
                hits = len(want & {_norm(x) for x in row})
                if hits > best_hits:
                    best, best_hits = cand, hits
            k = best if best_hits >= max(1, len(vals) // 2) else None
        row = table.get(k) if k is not None else None
        if not isinstance(row, list):
            continue
        used.add(k)
        lookup = {_norm(v): v for v in vals}
        out[cat] = [lookup.get(_norm(x), str(x)) for x in row]
    return out or None


def _score(p: Puzzle, truth: dict[str, list[str]], ans: dict | None) -> tuple[bool, float]:
    ans = canon_table(p, ans)
    if not ans:
        return False, 0.0
    total = right = 0
    for cat, row in truth.items():
        got = ans.get(cat, [])
        for i, v in enumerate(row):
            total += 1
            right += int(isinstance(got, list) and i < len(got) and got[i] == v)
    return right == total, right / total


def _parse_answer(text: str) -> dict | None:
    if "ANSWER:" in text:
        text = text.split("ANSWER:")[-1]
    try:
        a = extract_json(text)
        return a if isinstance(a, dict) else None
    except Exception:
        return None


def _user_prompt(p: Puzzle) -> str:
    q = Puzzle(size=p.size, categories=p.categories, clues=p.clues)  # strip title/story/solution
    return render_puzzle(q) + "\n\nFind the full arrangement."


# ---------------- tools ----------------
def _flatten_assumptions(p: Puzzle, raw: dict) -> tuple[dict[str, int], list[str]]:
    """Accept {"person:Rita": 2} and also nested {"person": {"Rita": 2}}; ignore what is not a house number."""
    items = {_norm(it): it for it in p.all_items()}
    out, ignored = {}, []
    for k, v in raw.items():
        if isinstance(v, dict):
            for vk, vv in v.items():
                key = items.get(_norm(f"{k}:{vk}"))
                try:
                    if key is None:
                        raise ValueError
                    out[key] = int(vv)
                except (TypeError, ValueError):
                    ignored.append(f"{k}:{vk}={vv}")
        else:
            key = items.get(_norm(k))
            try:
                if key is None:
                    raise ValueError
                out[key] = int(v)
            except (TypeError, ValueError):
                ignored.append(f"{k}={v}")
    return out, ignored


def tool_deduce(p: Puzzle, arg: str) -> str:
    try:
        raw = json.loads(arg) if arg.strip() else {}
        if not isinstance(raw, dict):
            raise ValueError
    except Exception:
        return 'Invalid input: deduce expects a JSON object like {"pet:cat": 2} or {}.'
    assume, ignored = _flatten_assumptions(p, raw)
    note = (f"(Ignored, not 'category:value': house-number pairs: {', '.join(ignored)})\n" if ignored else "")
    dom = _initial(p)
    for it, h in assume.items():
        dom[it] &= {h}
    try:
        if any(not d for d in dom.values()):
            raise Contradiction("")
        propagate(p, dom)
    except Contradiction:
        return note + "Contradiction: these assumptions cannot all be true."
    return note + _format_domains(p, dom)


def _format_domains(p: Puzzle, dom) -> str:
    lines = []
    for cat, vals in p.categories.items():
        parts = []
        for v in vals:
            d = sorted(dom[f"{cat}:{v}"])
            parts.append(f"{v}={d[0]}" if len(d) == 1 else f"{v}∈{{{','.join(map(str, d))}}}")
        lines.append(f"{cat}: " + ", ".join(parts))
    solved = all(len(d) == 1 for d in dom.values())
    return ("All items are determined.\n" if solved else "Possible houses:\n") + "\n".join(lines)


def tool_check(p: Puzzle, arg: str) -> str:
    try:
        table = json.loads(arg)
    except Exception:
        return "Invalid input: check expects the full answer JSON."
    sol = table_to_solution(p, canon_table(p, table) or {})
    if sol is None:
        return "Malformed answer: each category must list every one of its values exactly once."
    bad = [i for i, c in enumerate(p.clues, 1) if not c.holds(sol)]
    if not bad:
        return "This answer satisfies all clues."
    return "Violated clues: " + "; ".join(f"{i}. {render_clue(p.clues[i-1])}" for i in bad)


ACTION_RE = re.compile(
    r"Action:\s*(?:\(\d\)\s*)?[`*]*\s*(deduce|check|finish)\s*[\[(]?\s*(\{.*\})?\s*[\])]?", re.S | re.I)


def _run_single(client, p: Puzzle, truth, method: str, temperature: float) -> SolveRun:
    system = PLAIN_SYSTEM if method == "plain" else COT_SYSTEM
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": _user_prompt(p)}]
    r = client.chat(msgs, temperature=temperature, max_tokens=2500)
    ans = _parse_answer(r.text)
    ok, acc = _score(p, truth, ans)
    return SolveRun(method, ok, acc, 1, r.prompt_tokens, r.completion_tokens, r.seconds, ans,
                    None if ans else "unparseable answer", [{"role": "assistant", "content": r.text}])


def _run_react(client, p: Puzzle, truth, temperature: float, max_steps: int) -> SolveRun:
    msgs = [{"role": "system", "content": REACT_SYSTEM.replace("{max_steps}", str(max_steps))},
            {"role": "user", "content": _user_prompt(p)}]
    pt = ct = 0
    secs = 0.0
    transcript = []
    ans = None
    err = "no finish action"
    steps = 0
    last_proposed = None
    for steps in range(1, max_steps + 1):
        r = client.chat(msgs, temperature=temperature, max_tokens=800)
        pt += r.prompt_tokens
        ct += r.completion_tokens
        secs += r.seconds
        text = r.text.strip()
        m = ACTION_RE.search(text)
        if m:  # keep only up to the action (models sometimes hallucinate observations)
            text = text[: m.end()]
        transcript.append({"role": "assistant", "content": text})
        msgs.append({"role": "assistant", "content": text})
        if not m:
            obs = "Invalid format. Reply with 'Thought: ...' and 'Action: deduce[...]', 'check[...]' or 'finish[...]'."
        else:
            act, arg = m.group(1).lower(), m.group(2) or "{}"
            if act == "finish":
                try:
                    ans = json.loads(arg)
                    err = None
                except Exception:
                    ans, err = _parse_answer(arg), None
                break
            if act == "check":
                try:
                    last_proposed = json.loads(arg)
                except Exception:
                    pass
            obs = tool_deduce(p, arg) if act == "deduce" else tool_check(p, arg)
        obs = f"Observation: {obs}"
        transcript.append({"role": "tool", "content": obs})
        msgs.append({"role": "user", "content": obs})
    if ans is None and last_proposed is not None:
        ans = last_proposed  # ran out of steps: score the last answer it checked
    ok, acc = _score(p, truth, ans)
    return SolveRun("react", ok, acc, steps, pt, ct, secs, ans, err, transcript)


def solve_with_llm(client, p: Puzzle, method: str, temperature: float = 0.0, max_steps: int = 10) -> SolveRun:
    truth = solution_to_table(p, solve(p, limit=1).solutions[0])
    if hasattr(client, "set_puzzle"):
        client.set_puzzle(p, truth)  # mock only
    t = time.time()
    run = (_run_react(client, p, truth, temperature, max_steps) if method == "react"
           else _run_single(client, p, truth, method, temperature))
    run.seconds = run.seconds or time.time() - t
    return run