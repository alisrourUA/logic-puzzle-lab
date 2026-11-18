"""Part 2 experiments: LLM as puzzle SOLVER - plain vs chain-of-thought vs ReAct (tools).

Puzzle set: verified puzzles with a known unique answer, balanced over the measured
difficulty (easy / medium / hard). By default they come from the classic generator
(so the set is controlled); --include-llm adds valid puzzles the LLM made in Part 1.

Usage
  python run_solving.py                  # real run
  python run_solving.py --per-level 5    # smaller / cheaper
  python run_solving.py --backend mock   # offline test
"""
from __future__ import annotations

import argparse
import json
import threading
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed

from puzzlelab import config
from puzzlelab.baseline import generate
from puzzlelab.difficulty import rate
from puzzlelab.llm import get_client
from puzzlelab.puzzle import Puzzle
from puzzlelab.solving import solve_with_llm

METHODS = ["plain", "cot", "react"]


def build_set(per_level: int, include_llm: bool, backend: str) -> list[dict]:
    buckets = {"easy": [], "medium": [], "hard": []}
    if include_llm:
        path = config.RESULTS / backend / "generation.jsonl"
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                r = json.loads(line)
                if r["valid_final"] and r["measured_label"] in buckets:
                    lst = buckets[r["measured_label"]]
                    if len(lst) < per_level // 2:
                        lst.append({"source": "llm", "puzzle": r["final_puzzle"]})
    seed = 1000
    while any(len(v) < per_level for v in buckets.values()):
        seed += 1
        p = generate(4, 3, "easy" if seed % 2 else "hard", seed=seed)
        lab = rate(p).label
        if len(buckets[lab]) < per_level:
            buckets[lab].append({"source": "classic", "puzzle": p.to_dict()})
    out = []
    for lab, lst in buckets.items():
        for i, item in enumerate(lst):
            out.append({"puzzle_id": f"{lab}-{i}", "label": lab, **item})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-level", type=int, default=8)
    ap.add_argument("--include-llm", action="store_true")
    ap.add_argument("--backend", default=config.BACKEND, choices=["openai", "mock"])
    ap.add_argument("--model", default=config.MODEL)
    ap.add_argument("--max-steps", type=int, default=10)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    outdir = config.RESULTS / args.backend
    outdir.mkdir(parents=True, exist_ok=True)
    set_path = outdir / "solve_set.json"
    if set_path.exists():
        pset = json.loads(set_path.read_text(encoding="utf-8"))
    else:
        pset = build_set(args.per_level, args.include_llm, args.backend)
        set_path.write_text(json.dumps(pset, indent=1), encoding="utf-8")
    path = outdir / "solving.jsonl"
    done = set()
    if path.exists():
        done = {json.loads(l)["job_id"] for l in path.read_text(encoding="utf-8").splitlines() if l.strip()}
    jobs = [(f"{it['puzzle_id']}|{m}", it, m) for it in pset for m in METHODS]
    jobs = [j for j in jobs if j[0] not in done]
    print(f"{len(pset)} puzzles x {len(METHODS)} methods | {len(jobs)} runs to do")
    lock = threading.Lock()

    def work(job):
        job_id, it, method = job
        client = get_client(args.backend, args.model, seed=zlib.crc32(job_id.encode()))
        p = Puzzle.from_dict(it["puzzle"])
        r = solve_with_llm(client, p, method, temperature=0.0, max_steps=args.max_steps)
        rec = {"job_id": job_id, "puzzle_id": it["puzzle_id"], "label": it["label"], "source": it["source"],
               "n_clues": len(p.clues), "model": getattr(client, "name", "?"), **r.to_record()}
        with lock:
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(work, j) for j in jobs]
        for k, fu in enumerate(as_completed(futs), 1):
            try:
                r = fu.result()
                print(f"[{k}/{len(jobs)}] {r['puzzle_id']:<9} {r['method']:<6} correct={r['correct']!s:<5} "
                      f"cells={r['cell_accuracy']:.2f} steps={r['steps']}")
            except Exception as e:
                print(f"[{k}/{len(jobs)}] ERROR {type(e).__name__}: {e}")
    print(f"saved -> {path}\nnext: python make_charts.py --backend {args.backend}")


if __name__ == "__main__":
    main()
