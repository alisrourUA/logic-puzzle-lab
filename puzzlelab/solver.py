"""Exact constraint solver: finds / counts all solutions of a Zebra puzzle.

This is the 'strict verifier' of the project. It never guesses: it searches the
space of assignments with backtracking and returns every solution (up to a limit).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import permutations

from .puzzle import Puzzle


@dataclass
class SolveResult:
    solutions: list[dict[str, int]] = field(default_factory=list)  # item -> house
    nodes: int = 0          # how many partial assignments were tried (search effort)
    complete: bool = True   # False if we stopped early because of the limit

    @property
    def count(self) -> int:
        return len(self.solutions)


def solve(p: Puzzle, limit: int = 2, clues=None) -> SolveResult:
    """Return up to `limit` solutions. limit=2 is enough to test uniqueness.

    Uses constraint propagation + branching (fast). `solve_bruteforce` is the
    simple reference implementation used to cross-check it in the tests.
    """
    from .difficulty import Contradiction, _initial, propagate

    q = p if clues is None else Puzzle(size=p.size, categories=p.categories, clues=list(clues))
    res = SolveResult()

    def rec(dom) -> bool:
        res.nodes += 1
        try:
            propagate(q, dom)
        except Contradiction:
            return False
        # full check when every item is fixed (propagation rules are sound but
        # not complete, so we always confirm with the clues themselves)
        if all(len(d) == 1 for d in dom.values()):
            sol = {it: next(iter(d)) for it, d in dom.items()}
            if all(c.holds(sol) for c in q.clues) and _alldiff_ok(q, sol):
                res.solutions.append(sol)
            return len(res.solutions) >= limit
        item = min((it for it in dom if len(dom[it]) > 1), key=lambda it: len(dom[it]))
        for h in sorted(dom[item]):
            trial = {k: set(v) for k, v in dom.items()}
            trial[item] = {h}
            if rec(trial):
                return True
        return False

    stopped = rec(_initial(q))
    res.complete = not stopped
    return res


def _alldiff_ok(p: Puzzle, sol: dict[str, int]) -> bool:
    for cat, vals in p.categories.items():
        if len({sol[f"{cat}:{v}"] for v in vals}) != len(vals):
            return False
    return True


def solve_bruteforce(p: Puzzle, limit: int = 2, clues=None) -> SolveResult:
    """Reference solver: tries category permutations with backtracking."""
    clues = p.clues if clues is None else clues
    cats = list(p.categories)
    # order categories: most-constrained first (more clues mention it)
    mention = {c: 0 for c in cats}
    for cl in clues:
        for it in cl.items():
            mention[it.split(":", 1)[0]] += 1
    cats.sort(key=lambda c: -mention[c])

    # for each depth, the clues that become checkable once categories[:depth+1] are fixed
    assigned: set[str] = set()
    checks: list[list] = []
    for c in cats:
        assigned.add(c)
        now = []
        for cl in clues:
            needed = {it.split(":", 1)[0] for it in cl.items()}
            if c in needed and needed <= assigned:
                now.append(cl)
        checks.append(now)

    houses = list(range(1, p.size + 1))
    res = SolveResult()
    pos: dict[str, int] = {}

    def rec(depth: int) -> bool:
        if depth == len(cats):
            res.solutions.append(dict(pos))
            return len(res.solutions) >= limit
        cat = cats[depth]
        vals = p.categories[cat]
        for perm in permutations(houses):
            res.nodes += 1
            for v, h in zip(vals, perm):
                pos[f"{cat}:{v}"] = h
            if all(cl.holds(pos) for cl in checks[depth]):
                if rec(depth + 1):
                    return True
        for v in vals:
            pos.pop(f"{cat}:{v}", None)
        return False

    stopped = rec(0)
    res.complete = not stopped
    return res


def count_solutions(p: Puzzle, limit: int = 2, clues=None) -> int:
    return solve(p, limit=limit, clues=clues).count


def differing_items(p: Puzzle, s1: dict[str, int], s2: dict[str, int]) -> list[str]:
    return [it for it in p.all_items() if s1[it] != s2[it]]
