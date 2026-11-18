import json

from puzzlelab.puzzle import Puzzle
from puzzlelab.verifier import verify

rows = [json.loads(l) for l in open("results/openai/solving.jsonl", encoding="utf-8")]
pset = {p["puzzle_id"]: p for p in json.load(open("results/openai/solve_set.json", encoding="utf-8"))}

react = next(r for r in rows if r["method"] == "react")
print("=" * 30, "REACT", react["puzzle_id"])
for m in react["transcript"][:6]:
    print(f"--- {m['role']} ---")
    print(m["content"][:700])

for method in ("plain", "cot"):
    r = next(x for x in rows if x["method"] == method and x["label"] == "easy")
    truth = verify(Puzzle.from_dict(pset[r["puzzle_id"]]["puzzle"]), check_redundancy=False).solution
    print("=" * 30, method.upper(), r["puzzle_id"])
    print("RAW REPLY (end):", r["transcript"][0]["content"][-900:])
    print("PARSED ANSWER:", r["answer"])
    print("TRUE SOLUTION:", truth)