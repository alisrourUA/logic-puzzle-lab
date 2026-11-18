import json

from puzzlelab.puzzle import Puzzle
from puzzlelab.solving import canon_table, tool_check

rows = [json.loads(l) for l in open("results/openai/solving.jsonl", encoding="utf-8")]
pset = {p["puzzle_id"]: p for p in json.load(open("results/openai/solve_set.json", encoding="utf-8"))}

for method in ("plain", "cot"):
    print("=" * 20, method.upper())
    for r in sorted((x for x in rows if x["method"] == method), key=lambda x: x["puzzle_id"]):
        p = Puzzle.from_dict(pset[r["puzzle_id"]]["puzzle"])
        ans = canon_table(p, r["answer"])
        if not ans:
            print(f"{r['puzzle_id']:<10} could not read the answer")
            continue
        dupes = [c for c, row in ans.items() if len(set(row)) != len(row)]
        res = tool_check(p, json.dumps(ans))
        broken = 0 if "satisfies" in res else res.count(";") + 1
        print(f"{r['puzzle_id']:<10} correct={r['correct']!s:<5} cells={r['cell_accuracy']:.2f} "
              f"clues broken={broken:<2} same value twice in: {dupes or '-'}")