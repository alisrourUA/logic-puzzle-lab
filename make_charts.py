"""Turn results/*.jsonl into slide-ready charts (PNG) and a summary table (Markdown).

Usage:  python make_charts.py --backend openai     (or --backend mock)
Output: results/<backend>/charts/*.png and results/<backend>/summary.md
"""
from __future__ import annotations

import argparse
import itertools
import json
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from puzzlelab import config  # noqa: E402

# palette (validated categorical slots + one ordinal blue ramp)
C1, C2, C3, C4 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
ORDINAL = {"easy": "#9ec5f4", "medium": "#3987e5", "hard": "#184f95", "unsolvable": "#bbbbbb", None: "#dddddd"}
INK, MUTED, GRID = "#1f1f1e", "#6b6a64", "#e6e5e0"

plt.rcParams.update({
    "font.size": 12, "axes.titlesize": 15, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.edgecolor": GRID, "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "axes.grid.axis": "y",
    "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True, "legend.frameon": False,
    "figure.dpi": 150, "savefig.bbox": "tight", "text.color": INK,
})


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def pct(xs) -> float:
    xs = list(xs)
    return 100 * sum(xs) / len(xs) if xs else float("nan")


def bar_labels(ax, bars, fmt="{:.0f}%"):
    for b in bars:
        h = b.get_height()
        if h == h:  # not nan
            ax.annotate(fmt.format(h), (b.get_x() + b.get_width() / 2, h), xytext=(0, 3),
                        textcoords="offset points", ha="center", va="bottom", fontsize=10, color=INK)


def grouped(ax, groups, series: dict[str, list[float]], colors, width=0.36):
    n = len(series)
    for k, ((name, vals), col) in enumerate(zip(series.items(), colors)):
        xs = [i + (k - (n - 1) / 2) * (width + 0.02) for i in range(len(groups))]
        bars = ax.bar(xs, vals, width, color=col, label=name)
        bar_labels(ax, bars)
    ax.set_xticks(range(len(groups)), groups)


def valid_within(r, k: int) -> bool:
    return bool(r["valid_final"] and r["rounds_used"] <= k)


def first_solutions(r):
    """number of solutions of the first attempt (None if it did not parse)."""
    a = r["attempts"][0]
    return a.get("n_solutions") if a["status"] in ("valid", "multiple_solutions") else None


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return float("nan")
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2


def diversity(recs) -> float:
    """1 - mean pairwise Jaccard similarity of the value vocabularies (higher = more varied)."""
    vocab = []
    for r in recs:
        p = r.get("final_puzzle")
        if p:
            vocab.append({f"{c}:{v}".lower() for c, vs in p["categories"].items() for v in vs})
    if len(vocab) < 2:
        return float("nan")
    sims = [len(a & b) / len(a | b) for a, b in itertools.combinations(vocab, 2)]
    return 100 * (1 - sum(sims) / len(sims))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default=config.BACKEND, choices=["openai", "mock"])
    args = ap.parse_args()
    base = config.RESULTS / args.backend
    out = base / "charts"
    out.mkdir(parents=True, exist_ok=True)
    gen = load(base / "generation.jsonl")
    sol = load(base / "solving.jsonl")
    md = [f"# Results ({args.backend})\n"]
    if gen:
        md.append(f"Model: {gen[0].get('model')}  |  generation runs: {len(gen)}\n")
    note = "\n[mock data - pipeline test only]" if args.backend == "mock" else ""

    if gen:
        # ---------- A: prompting ----------
        A = [r for r in gen if r["experiment"] == "A_prompting"]
        shots = sorted({r["shots"] for r in A})
        first = [pct(r["valid_first_try"] for r in A if r["shots"] == s) for s in shots]
        two = [pct(valid_within(r, 2) for r in A if r["shots"] == s) for s in shots]
        final = [pct(r["valid_final"] for r in A if r["shots"] == s) for s in shots]
        fig, ax = plt.subplots(figsize=(8.5, 4.6))
        grouped(ax, [f"{s}-shot" for s in shots],
                {"Valid on first try": first, "Valid within 2 repairs": two, "Valid after all repairs": final},
                [C1, C2, C3], width=0.26)
        ax.set_ylim(0, 110); ax.set_ylabel("% of puzzles with exactly one solution")
        ax.set_title("A. Prompting: effect of example puzzles in the prompt" + note)
        ax.legend(loc="upper center", ncol=3, bbox_to_anchor=(0.5, -0.12))
        fig.savefig(out / "A_prompting.png"); plt.close(fig)
        md.append("## A. Prompting (0 / 1 / 3 examples)\n\n| shots | n | valid first try | valid within 2 repairs | valid after all repairs | median #solutions on first try | avg repair rounds |\n|---|---|---|---|---|---|---|")
        for s, f1, f2, f3 in zip(shots, first, two, final):
            rs = [r for r in A if r["shots"] == s]
            md.append(f"| {s} | {len(rs)} | {f1:.0f}% | {f2:.0f}% | {f3:.0f}% | {median(first_solutions(r) for r in rs)} | {sum(r['rounds_used'] for r in rs)/len(rs):.2f} |")

        # ---------- B: temperature ----------
        B = [r for r in gen if r["experiment"] == "B_temperature"]
        temps = sorted({r["temperature"] for r in B})
        vf = [pct(valid_within(r, 2) for r in B if r["temperature"] == t) for t in temps]
        fe = [pct(r["first_status"] == "format_error" for r in B if r["temperature"] == t) for t in temps]
        dv = [diversity([r for r in B if r["temperature"] == t]) for t in temps]
        dup = []
        for t in temps:
            keys_t = [r["canonical"] for r in B if r["temperature"] == t and r["canonical"]]
            dup.append(100 * (1 - len(set(keys_t)) / len(keys_t)) if keys_t else float("nan"))
        fig, ax = plt.subplots(figsize=(7.5, 4.5))
        ax.plot(temps, vf, "-o", color=C1, lw=2, ms=8, label="Valid within 2 repairs")
        ax.plot(temps, dv, "-o", color=C3, lw=2, ms=8, label="Diversity of themes (1 - Jaccard)")
        ax.plot(temps, fe, "-o", color=C2, lw=2, ms=8, label="Broken JSON / schema")
        for ys, col in ((vf, C1), (dv, C3), (fe, C2)):
            ax.annotate(f"{ys[-1]:.0f}%", (temps[-1], ys[-1]), xytext=(8, 0), textcoords="offset points",
                        va="center", fontsize=10, color=INK)
        ax.set_xticks(temps); ax.set_xlabel("temperature"); ax.set_ylabel("%"); ax.set_ylim(0, 105)
        ax.set_title("B. Temperature: correctness vs creativity" + note)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=2)
        fig.savefig(out / "B_temperature.png"); plt.close(fig)
        md.append("\n## B. Temperature\n\n| T | n | valid first try | valid within 2 repairs | valid after all repairs | median #solutions on first try | first-try format errors | theme diversity | duplicate puzzles |\n|---|---|---|---|---|---|---|---|---|")
        for t, a, b, c, d in zip(temps, vf, fe, dv, dup):
            rs = [r for r in B if r["temperature"] == t]
            md.append(f"| {t} | {len(rs)} | {pct(r['valid_first_try'] for r in rs):.0f}% | {a:.0f}% | {pct(r['valid_final'] for r in rs):.0f}% | {median(first_solutions(r) for r in rs)} | {b:.0f}% | {c:.0f}% | {d:.0f}% |")

        # ---------- C: difficulty control ----------
        C = [r for r in gen if r["experiment"] == "C_difficulty"]
        req = ["easy", "medium", "hard"]
        levels = ["easy", "medium", "hard", None]
        fig, ax = plt.subplots(figsize=(7.5, 4.5))
        bottoms = [0.0] * 3
        for lev in levels:
            vals = []
            for q in req:
                rs = [r for r in C if r["difficulty"] == q]
                vals.append(pct(r["measured_label"] == lev for r in rs) if rs else 0)
            name = f"measured {lev}" if lev else "no valid puzzle"
            ax.bar(req, vals, 0.6, bottom=bottoms, color=ORDINAL[lev], label=name,
                   edgecolor="white", linewidth=2)
            bottoms = [b + v for b, v in zip(bottoms, vals)]
        ax.set_ylim(0, 100); ax.set_ylabel("% of generated puzzles"); ax.set_xlabel("difficulty requested in the prompt")
        ax.set_title("C. Difficulty control: asked vs measured" + note)
        ax.legend(loc="upper left", bbox_to_anchor=(1, 1))
        fig.savefig(out / "C_difficulty.png"); plt.close(fig)
        md.append("\n## C. Difficulty control\n\n| requested | n | valid | measured easy | medium | hard | mean score | mean clues |\n|---|---|---|---|---|---|---|---|")
        for q in req:
            rs = [r for r in C if r["difficulty"] == q]
            v = [r for r in rs if r["valid_final"]]
            cnt = Counter(r["measured_label"] for r in v)
            ms = sum(r["measured_score"] for r in v) / len(v) if v else float("nan")
            mc = sum(r["n_clues"] for r in v) / len(v) if v else float("nan")
            md.append(f"| {q} | {len(rs)} | {len(v)} | {cnt['easy']} | {cnt['medium']} | {cnt['hard']} | {ms:.1f} | {mc:.1f} |")

        # ---------- D: repair loop + self-claims (all runs) ----------
        maxr = max(len(r["attempts"]) for r in gen)
        cum = [pct(r["valid_final"] and r["rounds_used"] <= k for r in gen) for k in range(maxr)]
        status = Counter(r["first_status"] for r in gen)
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.8), gridspec_kw={"width_ratios": [1.1, 1], "wspace": 0.25})
        bars = ax1.bar([f"round {k}" if k else "first try" for k in range(maxr)], cum, 0.6, color=C1)
        bar_labels(ax1, bars)
        ax1.set_ylim(0, 110); ax1.set_ylabel("% valid (cumulative)")
        ax1.set_title("D. Repair loop: cumulative validity" + note)
        names = {"valid": "valid", "multiple_solutions": "several\nsolutions", "no_solution": "contradiction",
                 "format_error": "broken\nformat"}
        keys = ["valid", "multiple_solutions", "no_solution", "format_error"]
        vals = [100 * status[k] / len(gen) for k in keys]
        bars = ax2.bar([names[k] for k in keys], vals, 0.6, color=[C3, C2, C4, "#9a9990"])
        bar_labels(ax2, bars)
        ax2.set_ylim(0, 110); ax2.set_title("First-try outcome" + ("\n " if note else ""))
        fig.savefig(out / "D_repair.png"); plt.close(fig)
        claimed = [r for r in gen if r["first_claimed_unique"] is True and r["first_status"] != "format_error"]
        wrong = sum(1 for r in claimed if r["first_status"] != "valid")
        md.append(f"\n## D. Repair loop & self-verification\n\n- valid on first try: {cum[0]:.0f}%  ->  after repair: {cum[-1]:.0f}%")
        md.append("- first-try outcomes: " + ", ".join(f"{names[k].replace(chr(10), ' ')} {100*status[k]/len(gen):.0f}%" for k in keys))
        if claimed:
            md.append(f"- LLM said **\"my puzzle is unique\"** {len(claimed)} times; it was wrong {wrong} times "
                      f"(**{100*wrong/len(claimed):.0f}%**) - the solver caught every one.")
        tok = sum(r["prompt_tokens"] + r["completion_tokens"] for r in gen)
        nv = sum(r["valid_final"] for r in gen)
        md.append(f"- tokens used: {tok:,} total, {tok/max(nv,1):,.0f} per valid puzzle")

    if sol:
        methods = ["plain", "cot", "react"]
        mname = {"plain": "Plain prompt", "cot": "Chain-of-thought", "react": "ReAct + tools"}
        labs = ["easy", "medium", "hard"]
        fig, ax = plt.subplots(figsize=(8.5, 4.8))
        series = {mname[m]: [pct(r["correct"] for r in sol if r["method"] == m and r["label"] == l) for l in labs]
                  for m in methods}
        grouped(ax, labs, series, [C1, C2, C3], width=0.26)
        ax.set_ylim(0, 115); ax.set_ylabel("% puzzles solved exactly"); ax.set_xlabel("puzzle difficulty (measured)")
        ax.set_title("E. Solving: plain vs chain-of-thought vs ReAct agent" + note)
        ax.legend(loc="upper center", ncol=3, bbox_to_anchor=(0.5, -0.17))
        fig.savefig(out / "E_solving.png"); plt.close(fig)
        md.append("\n## E. Solving (Part 2)\n\n| method | solved (all) | easy | medium | hard | cell accuracy | avg steps | avg tokens |\n|---|---|---|---|---|---|---|---|")
        for m in methods:
            rs = [r for r in sol if r["method"] == m]
            per = [pct(r["correct"] for r in rs if r["label"] == l) for l in labs]
            ca = 100 * sum(r["cell_accuracy"] for r in rs) / len(rs)
            st = sum(r["steps"] for r in rs) / len(rs)
            tk = sum(r["prompt_tokens"] + r["completion_tokens"] for r in rs) / len(rs)
            md.append(f"| {mname[m]} | {pct(r['correct'] for r in rs):.0f}% | " + " | ".join(f"{x:.0f}%" for x in per)
                      + f" | {ca:.0f}% | {st:.1f} | {tk:,.0f} |")

    (base / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    print(f"\ncharts -> {out}")


if __name__ == "__main__":
    main()