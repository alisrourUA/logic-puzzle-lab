"""Re-score saved Part 2 answers with the current scoring code (no API calls).
Usage:  python rescore.py            (a backup is written to results/openai/solving_backup.jsonl)"""
import json
import shutil

from puzzlelab.puzzle import Puzzle
from puzzlelab.solving import _score
from puzzlelab.verifier import verify

path = "results/openai/solving.jsonl"
shutil.copy(path, "results/openai/solving_backup.jsonl")
pset = {p["puzzle_id"]: p for p in json.load(open("results/openai/solve_set.json", encoding="utf-8"))}
rows = [json.loads(l) for l in open(path, encoding="utf-8")]
changed = 0
for r in rows:
    p = Puzzle.from_dict(pset[r["puzzle_id"]]["puzzle"])
    truth = verify(p, check_redundancy=False).solution
    ok, acc = _score(p, truth, r["answer"])
    if ok != r["correct"] or abs(acc - r["cell_accuracy"]) > 1e-9:
        print(f"{r['puzzle_id']:<10} {r['method']:<6} correct {r['correct']} -> {ok}   cells {r['cell_accuracy']:.2f} -> {acc:.2f}")
        changed += 1
    r["correct"], r["cell_accuracy"] = ok, acc
with open(path, "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"{changed} answers re-scored. Now run: python make_charts.py --backend openai")