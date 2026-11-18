"""Verifier: turns raw LLM output into a verdict + human-readable feedback.

Statuses
    format_error        reply is not valid JSON / breaks the schema
    no_solution         clues contradict each other
    multiple_solutions  more than one arrangement fits all clues
    valid               exactly one solution
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .difficulty import rate
from .puzzle import Puzzle, PuzzleFormatError, extract_json, render_clue, solution_to_table, table_to_solution
from .solver import count_solutions, differing_items, solve


@dataclass
class VerifyReport:
    status: str
    feedback: str
    puzzle: Puzzle | None = None
    n_solutions: int | None = None          # capped at `max_count`
    solution: dict[str, list[str]] | None = None
    difficulty: dict[str, Any] | None = None
    redundant_clues: list[int] = field(default_factory=list)   # 1-based indices
    claimed_unique: bool | None = None      # what the LLM said about its own puzzle
    claim_correct: bool | None = None       # was the LLM's claimed solution/uniqueness right?
    solver_nodes: int = 0

    @property
    def valid(self) -> bool:
        return self.status == "valid"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "feedback": self.feedback,
            "n_solutions": self.n_solutions,
            "solution": self.solution,
            "difficulty": self.difficulty,
            "redundant_clues": self.redundant_clues,
            "claimed_unique": self.claimed_unique,
            "claim_correct": self.claim_correct,
            "solver_nodes": self.solver_nodes,
            "puzzle": self.puzzle.to_dict() if self.puzzle else None,
        }


def _unsat_core(p: Puzzle) -> list[int]:
    """Greedy minimal set of clues that already contradict each other (1-based)."""
    keep = list(range(len(p.clues)))
    for i in list(keep):
        trial = [j for j in keep if j != i]
        if count_solutions(p, limit=1, clues=[p.clues[j] for j in trial]) == 0:
            keep = trial
    return [j + 1 for j in keep]


def _redundant(p: Puzzle) -> list[int]:
    """Clues that can be removed one at a time while keeping a unique solution."""
    out = []
    for i in range(len(p.clues)):
        rest = p.clues[:i] + p.clues[i + 1:]
        if count_solutions(p, limit=2, clues=rest) == 1:
            out.append(i + 1)
    return out


def _describe(p: Puzzle, item: str, house: int) -> str:
    cat, val = item.split(":", 1)
    return f"{cat}={val} in house {house}"


def verify(raw: str | dict | Puzzle, max_count: int = 50, check_redundancy: bool = True) -> VerifyReport:
    # 1) parse
    try:
        if isinstance(raw, Puzzle):
            p = raw
        elif isinstance(raw, dict):
            p = Puzzle.from_dict(raw)
        else:
            p = Puzzle.from_dict(extract_json(raw))
    except PuzzleFormatError as e:
        return VerifyReport("format_error", f"FORMAT ERROR: {e}. Return only valid JSON in the required schema.")

    # 2) count solutions
    res = solve(p, limit=max_count)
    n = res.count
    claimed_unique = p.claimed_unique
    rep = VerifyReport(status="", feedback="", puzzle=p, n_solutions=n,
                       claimed_unique=claimed_unique, solver_nodes=res.nodes)

    if n == 0:
        core = _unsat_core(p)
        lines = "; ".join(f"clue {i} ({render_clue(p.clues[i-1])})" for i in core)
        rep.status = "no_solution"
        rep.feedback = (f"NO SOLUTION: the clues contradict each other. These clues cannot all be "
                        f"true at the same time: {lines}. Change or remove one of them, "
                        f"keeping the puzzle uniquely solvable.")
        rep.claim_correct = False if claimed_unique is not None or p.claimed_solution else None
        return rep

    if n > 1:
        s1, s2 = res.solutions[0], res.solutions[1]
        diff = differing_items(p, s1, s2)
        ex1 = ", ".join(_describe(p, it, s1[it]) for it in diff[:4])
        ex2 = ", ".join(_describe(p, it, s2[it]) for it in diff[:4])
        more = "at least " if not res.complete else ""
        rep.status = "multiple_solutions"
        if n >= 20:
            hint = ("The clues are far too weak: many values are not constrained at all. "
                    "Add several clues (3 or more) so that every value is pinned down. ")
        elif n >= 3:
            hint = "Add about 2 more clues that are true for your claimed_solution. "
        else:
            hint = "One more well-chosen clue that separates these two arrangements should be enough. "
        rep.feedback = (f"NOT UNIQUE: {more}{n} different solutions satisfy all clues. {hint}"
                        f"For example, solution A has {ex1}, while solution B has {ex2}. "
                        f"Add or change clue(s) so that only one arrangement is possible "
                        f"(the items that are still ambiguous: {', '.join(diff)}).")
        rep.claim_correct = False if claimed_unique is not None or p.claimed_solution else None
        return rep

    # 3) unique: rate difficulty, check claims, redundancy
    sol = res.solutions[0]
    rep.status = "valid"
    rep.solution = solution_to_table(p, sol)
    rep.difficulty = rate(p).to_dict()
    if p.claimed_solution:
        claimed = table_to_solution(p, p.claimed_solution)
        rep.claim_correct = claimed == sol
    elif claimed_unique is not None:
        rep.claim_correct = claimed_unique is True
    if check_redundancy:
        rep.redundant_clues = _redundant(p)
    rep.feedback = f"VALID: exactly one solution. Difficulty: {rep.difficulty['label']}."
    return rep
