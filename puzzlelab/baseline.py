"""Classic (non-LLM) puzzle generator.

Used as (a) a baseline to compare the LLM against, (b) the source of few-shot
examples, (c) the offline mock LLM, and (d) a fallback puzzle set for Part 2.

Algorithm: pick a random hidden solution -> add random TRUE clues until the solver
says the solution is unique -> remove clues that are not needed (minimal puzzle).
"""
from __future__ import annotations

import random

from .puzzle import Clue, Puzzle, solution_to_table
from .solver import count_solutions

THEMES = {
    "color": ["red", "green", "blue", "yellow", "white", "black"],
    "person": ["Ali", "Mhmd", "Sara", "Lina", "Omar", "Rita"],
    "pet": ["cat", "dog", "fish", "bird", "rabbit", "turtle"],
    "drink": ["tea", "coffee", "juice", "milk", "water", "lemonade"],
    "sport": ["football", "tennis", "chess", "swimming", "basketball", "running"],
    "food": ["pizza", "sushi", "falafel", "burger", "pasta", "salad"],
    "job": ["doctor", "teacher", "engineer", "chef", "pilot", "artist"],
}

EASY_TYPES = {"at": 4, "same": 5, "right_of": 2, "next_to": 1, "not_at": 1, "not_same": 1,
              "left_of": 1, "not_next_to": 1}
HARD_TYPES = {"at": 0.3, "same": 3, "right_of": 2, "next_to": 3, "not_at": 2, "not_same": 3,
              "left_of": 3, "not_next_to": 2}


def _random_true_clue(rng: random.Random, p: Puzzle, sol: dict[str, int], weights: dict[str, float]) -> Clue:
    items = p.all_items()
    types, w = zip(*weights.items())
    for _ in range(200):
        t = rng.choices(types, w)[0]
        a = rng.choice(items)
        if t == "at":
            return Clue("at", a, pos=sol[a])
        if t == "not_at":
            choices = [h for h in range(1, p.size + 1) if h != sol[a]]
            return Clue("not_at", a, pos=rng.choice(choices))
        b = rng.choice([x for x in items if x.split(":")[0] != a.split(":")[0]] if t in ("same", "not_same")
                       else [x for x in items if x != a])
        c = Clue(t, a, b=b)
        if c.holds(sol):
            return c
    return Clue("at", a, pos=sol[a])


def generate(size: int = 4, n_cats: int = 3, difficulty: str = "medium", seed: int | None = None,
             cats: list[str] | None = None) -> Puzzle:
    rng = random.Random(seed)
    cats = cats or (["person", "color"] + rng.sample([c for c in THEMES if c not in ("person", "color")],
                                                     n_cats - 2))[:n_cats]
    categories = {c: rng.sample(THEMES[c], size) for c in cats}
    p = Puzzle(size=size, categories=categories, clues=[])
    sol = {}
    for c, vals in categories.items():
        perm = rng.sample(range(1, size + 1), size)
        for v, h in zip(vals, perm):
            sol[f"{c}:{v}"] = h
    weights = EASY_TYPES if difficulty == "easy" else HARD_TYPES
    clues: list[Clue] = []
    seen = set()
    while True:
        c = _random_true_clue(rng, p, sol, weights)
        key = (c.type, c.a, c.b, c.pos)
        if key in seen:
            continue
        seen.add(key)
        clues.append(c)
        if count_solutions(p, limit=2, clues=clues) == 1:
            break
    # prune: remove clues that are not needed (keeps puzzle minimal)
    if True:
        candidates = list(clues)
        rng.shuffle(candidates)
        for cand in candidates:
            trial = [c for c in clues if c is not cand]
            if count_solutions(p, limit=2, clues=trial) == 1:
                clues = trial
    rng.shuffle(clues)
    p.clues = clues
    p.claimed_solution = solution_to_table(p, sol)
    p.claimed_unique = True
    return p
