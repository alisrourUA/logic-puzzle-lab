"""Part 1 experiments: LLM as puzzle GENERATOR.

  A. prompting   - 0 vs 1 vs 3 example puzzles in the prompt  (Prompt engineering chapter)
  B. temperature - 0.0 / 0.4 / 0.8 / 1.2                       (Generative configuration chapter)
  C. difficulty  - ask for easy / medium / hard, measure what we get
Every run uses the repair loop, so we also get: validity before vs after repair,
rounds needed, and how often the LLM's own "this is unique" claim was wrong.

Usage
  python run_generation.py                 # real run (needs OPENAI_API_KEY in .env)
  python run_generation.py --n 5           # smaller / cheaper run
  python run_generation.py --backend mock  # offline test, no API calls
Results are appended to results/<backend>/generation.jsonl (re-running resumes).
"""
from __future__ import annotations

import argparse
import json
import zlib
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from puzzlelab import config
from puzzlelab.generator import Spec, run
from puzzlelab.llm import get_client


def plan(n: int) -> list[tuple[str, Spec]]:
    jobs = []
    for shots in (0, 1, 3):
        jobs += [("A_prompting", Spec(size=4, n_cats=3, difficulty="medium", shots=shots, temperature=0.7))] * n
    for t in (0.0, 0.4, 0.8, 1.2):
        jobs += [("B_temperature", Spec(size=4, n_cats=3, difficulty="medium", shots=1, temperature=t))] * n
    for d in ("easy", "medium", "hard"):
        jobs += [("C_difficulty", Spec(size=4, n_cats=3, difficulty=d, shots=1, temperature=0.7))] * n
    # give each job a stable id: experiment + params + repetition
    out, counter = [], {}
    for exp, spec in jobs:
        key = f"{exp}|{json.dumps(spec.to_dict(), sort_keys=True)}"
        counter[key] = counter.get(key, 0) + 1
        out.append((f"{key}|{counter[key]}", exp, spec))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=12, help="repetitions per setting (default 12)")
    ap.add_argument("--backend", default=config.BACKEND, choices=["openai", "mock"])
    ap.add_argument("--model", default=config.MODEL)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    outdir = config.RESULTS / args.backend
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / "generation.jsonl"
    done = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(line)["job_id"])
            except Exception:
                pass
    jobs = [j for j in plan(args.n) if j[0] not in done]
    print(f"backend={args.backend} model={args.model if args.backend == 'openai' else 'mock'} "
          f"| {len(jobs)} runs to do ({len(done)} already done)")
    lock = threading.Lock()

    def work(i, job):
        job_id, exp, spec = job
        client = get_client(args.backend, args.model, seed=zlib.crc32(job_id.encode()))
        gr = run(client, spec)
        rec = {"job_id": job_id, "experiment": exp, "model": getattr(client, "name", "?"), **gr.to_record()}
        with lock:
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec

    finished = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(work, i, j) for i, j in enumerate(jobs)]
        for fu in as_completed(futs):
            finished += 1
            try:
                r = fu.result()
                print(f"[{finished}/{len(jobs)}] {r['experiment']:<14} shots={r['shots']} T={r['temperature']} "
                      f"{r['difficulty']:<6} first={r['first_status']:<18} final={r['final_status']:<18} "
                      f"rounds={r['rounds_used']}")
            except Exception as e:
                print(f"[{finished}/{len(jobs)}] ERROR {type(e).__name__}: {e}")
    print(f"saved -> {path}\nnext: python make_charts.py --backend {args.backend}")


if __name__ == "__main__":
    main()
