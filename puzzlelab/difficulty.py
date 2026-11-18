"""Difficulty rater.

Simulates a human-style solver: it applies simple deduction rules
(constraint propagation) over a grid of "which houses can this item still be in?".
- If pure deduction solves the puzzle, it is easy or medium depending on how many
  deduction rounds were needed.
- If deduction gets stuck, the solver has to guess (try a value, see if it breaks).
  Every guess makes the puzzle harder.

score = rounds + 8 * guesses   (easy: no guessing and <=6 rounds; medium: score<=20; hard: above)
"""
from __future__ import annotations

from dataclasses import dataclass

from .puzzle import Puzzle

Domains = dict[str, set[int]]


class Contradiction(Exception):
    pass


@dataclass
class DifficultyReport:
    rounds: int          # deduction rounds before solved / stuck (main line)
    guesses: int         # branching points needed (0 = pure deduction)
    score: float
    label: str           # easy / medium / hard

    def to_dict(self):
        return {"rounds": self.rounds, "guesses": self.guesses,
                "score": round(self.score, 2), "label": self.label}


def _initial(p: Puzzle) -> Domains:
    full = set(range(1, p.size + 1))
    return {it: set(full) for it in p.all_items()}


def _restrict(dom: Domains, item: str, allowed: set[int]) -> bool:
    new = dom[item] & allowed
    if not new:
        raise Contradiction(item)
    if new != dom[item]:
        dom[item] = new
        return True
    return False


def _single(d: set[int]) -> int | None:
    return next(iter(d)) if len(d) == 1 else None


def _apply_clue(p: Puzzle, dom: Domains, c) -> bool:
    n = p.size
    ch = False
    if c.type == "at":
        return _restrict(dom, c.a, {c.pos})
    if c.type == "not_at":
        return _restrict(dom, c.a, set(range(1, n + 1)) - {c.pos})
    A, B = dom[c.a], dom[c.b]
    t = c.type
    if t == "same":
        inter = A & B
        ch |= _restrict(dom, c.a, inter)
        ch |= _restrict(dom, c.b, inter)
    elif t == "not_same":
        sa, sb = _single(A), _single(B)
        if sa is not None:
            ch |= _restrict(dom, c.b, set(dom[c.b]) - {sa})
        if sb is not None:
            ch |= _restrict(dom, c.a, set(dom[c.a]) - {sb})
    elif t == "right_of":
        ch |= _restrict(dom, c.a, {x + 1 for x in B})
        ch |= _restrict(dom, c.b, {x - 1 for x in dom[c.a]})
    elif t == "left_of":
        ch |= _restrict(dom, c.a, {x for x in A if x < max(B)})
        ch |= _restrict(dom, c.b, {x for x in dom[c.b] if x > min(dom[c.a])})
    elif t == "next_to":
        ch |= _restrict(dom, c.a, {x + d for x in B for d in (-1, 1)})
        ch |= _restrict(dom, c.b, {x + d for x in dom[c.a] for d in (-1, 1)})
    elif t == "not_next_to":
        sa, sb = _single(A), _single(B)
        if sb is not None:
            ch |= _restrict(dom, c.a, set(dom[c.a]) - {sb - 1, sb, sb + 1})
        if sa is not None:
            ch |= _restrict(dom, c.b, set(dom[c.b]) - {sa - 1, sa, sa + 1})
    return ch


def _all_different(p: Puzzle, dom: Domains) -> bool:
    ch = False
    for cat, vals in p.categories.items():
        items = [f"{cat}:{v}" for v in vals]
        # naked singles: a fixed item removes its house from the others
        for it in items:
            s = _single(dom[it])
            if s is not None:
                for other in items:
                    if other != it and s in dom[other]:
                        ch |= _restrict(dom, other, dom[other] - {s})
        # hidden singles: a house that only one item can still take
        for h in range(1, p.size + 1):
            cands = [it for it in items if h in dom[it]]
            if not cands:
                raise Contradiction(f"{cat} house {h}")
            if len(cands) == 1 and len(dom[cands[0]]) > 1:
                ch |= _restrict(dom, cands[0], {h})
    return ch


def propagate(p: Puzzle, dom: Domains) -> int:
    """Run deduction to a fixpoint. Returns number of rounds that changed something."""
    rounds = 0
    while True:
        changed = False
        for c in p.clues:
            changed |= _apply_clue(p, dom, c)
        changed |= _all_different(p, dom)
        if not changed:
            return rounds
        rounds += 1


def _solved(dom: Domains) -> bool:
    return all(len(d) == 1 for d in dom.values())


def _search(p: Puzzle, dom: Domains, counter: list[int]) -> bool:
    """Guess-and-check with propagation; counter[0] counts guesses."""
    propagate(p, dom)
    if _solved(dom):
        return True
    item = min((it for it in dom if len(dom[it]) > 1), key=lambda it: len(dom[it]))
    for h in sorted(dom[item]):
        counter[0] += 1
        trial = {k: set(v) for k, v in dom.items()}
        trial[item] = {h}
        try:
            if _search(p, trial, counter):
                dom.update(trial)
                return True
        except Contradiction:
            continue
    raise Contradiction("dead end")


def rate(p: Puzzle) -> DifficultyReport:
    dom = _initial(p)
    try:
        rounds = propagate(p, dom)
        guesses = 0
        if not _solved(dom):
            counter = [0]
            _search(p, dom, counter)
            guesses = counter[0]
    except Contradiction:
        return DifficultyReport(rounds=0, guesses=0, score=float("nan"), label="unsolvable")
    score = rounds + 8 * guesses
    if guesses == 0 and rounds <= 6:
        label = "easy"
    elif score <= 20:
        label = "medium"
    else:
        label = "hard"
    return DifficultyReport(rounds=rounds, guesses=guesses, score=score, label=label)
