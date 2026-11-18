"""Core tests:  python -m pytest -q"""
import random

from puzzlelab.baseline import generate
from puzzlelab.generator import Spec, run
from puzzlelab.llm import MockClient
from puzzlelab.puzzle import Clue, Puzzle
from puzzlelab.solver import solve, solve_bruteforce
from puzzlelab.solving import solve_with_llm, tool_check, tool_deduce
from puzzlelab.verifier import verify

EXAMPLE = {"size": 3,
           "categories": {"color": ["red", "green", "blue"], "person": ["Ali", "Mhmd", "Sara"],
                          "pet": ["cat", "dog", "fish"]},
           "clues": [{"type": "same", "a": "person:Ali", "b": "color:red"},
                     {"type": "right_of", "a": "color:green", "b": "color:red"},
                     {"type": "at", "a": "pet:dog", "pos": 3},
                     {"type": "same", "a": "pet:cat", "b": "color:blue"},
                     {"type": "not_next_to", "a": "person:Mhmd", "b": "person:Sara"}]}


def test_example_has_two_solutions_then_fix():
    r = verify(EXAMPLE)
    assert r.status == "multiple_solutions" and r.n_solutions == 2
    assert "person:Mhmd" in r.feedback and "person:Sara" in r.feedback
    fixed = {**EXAMPLE, "clues": EXAMPLE["clues"][:4] + [{"type": "same", "a": "person:Sara", "b": "pet:cat"}]}
    assert verify(fixed).status == "valid"


def test_contradiction_is_located():
    bad = {**EXAMPLE, "clues": EXAMPLE["clues"] + [{"type": "at", "a": "color:red", "pos": 3}]}
    r = verify(bad)
    assert r.status == "no_solution" and "clue 2" in r.feedback and "clue 6" in r.feedback


def test_format_errors():
    assert verify("no json here").status == "format_error"
    assert verify('{"size": 3, "categories": {"a": [1, 2, 3]}, "clues": []}').status == "format_error"
    bad = {**EXAMPLE, "clues": [{"type": "teleport", "a": "pet:cat", "b": "pet:dog"}]}
    assert "unknown type" in verify(bad).feedback


def test_fast_solver_matches_bruteforce():
    rng = random.Random(1)
    types = ["same", "next_to", "left_of", "not_next_to", "right_of", "not_same"]
    for s in range(25):
        p = generate(rng.choice([3, 4]), 3, rng.choice(["easy", "hard"]), seed=s)
        sub = rng.sample(p.clues, rng.randint(1, len(p.clues)))
        a, b = rng.sample(p.all_items(), 2)
        sub.append(Clue(rng.choice(types), a, b=b))
        assert solve(p, 500, sub).count == solve_bruteforce(p, 500, sub).count


def test_classic_generator_is_valid_and_minimal():
    for s in range(10):
        r = verify(generate(4, 3, "hard", seed=s))
        assert r.valid and r.claim_correct and r.redundant_clues == []


def test_tools():
    p = Puzzle.from_dict(EXAMPLE)
    assert "Contradiction" in tool_deduce(p, '{"color:red": 3}')
    assert "Violated clues" in tool_check(p, '{"color": ["red","green","blue"], "person": ["Ali","Mhmd","Sara"], '
                                             '"pet": ["cat","fish","dog"]}')


def test_pipeline_with_mock():
    c = MockClient(0)
    g = run(c, Spec(temperature=0.0, shots=1))
    assert g.attempts and g.final.report.status in ("valid", "multiple_solutions", "no_solution", "format_error")
    p = generate(4, 3, "easy", seed=3)
    assert solve_with_llm(c, p, "react").steps >= 1
