# 🧩 Logic Puzzle Lab
**Can an LLM invent logic puzzles — and can it solve them?**
Generative AI course project · built with Claude Code

An LLM **generates** Zebra/Einstein logic puzzles. An exact constraint **solver verifies**
each one (it must have exactly one solution). If a puzzle is broken, the solver's
diagnosis is sent back to the LLM, which **repairs** it (ReAct-style
Thought → Action → Observation loop). In Part 2, LLMs try to **solve** verified puzzles
with plain prompting, chain-of-thought, and a ReAct agent that can call tools.


## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env          # Windows: copy .env.example .env
# open .env and paste your OpenAI key after OPENAI_API_KEY=
python check_key.py           # confirms the key works and the model is available
```

### Run the experiments (real LLM)
```bash
python run_generation.py      # Part 1: ~120 generation runs (A, B, C)
python run_solving.py         # Part 2: 24 puzzles x 3 methods
python make_charts.py --backend openai
```
Charts → `results/openai/charts/*.png`, tables → `results/openai/summary.md`.
Cheaper/faster: `python run_generation.py --n 5` and `python run_solving.py --per-level 4`.
Runs are resumable: if something stops, run the same command again.
Expected cost with gpt-4o-mini: well under $1.

### Demo app
```bash
streamlit run app.py
```
Tab 1 generates and repairs a puzzle live, tab 2 lets an LLM solve it (see the ReAct trace),
tab 3 shows the experiment charts.

### Offline mode (no key)
Add `--backend mock` to any script (or pick "mock" in the app). The mock imitates typical
LLM mistakes so the whole pipeline can be tested — **its numbers are not results.**

### Tests
```bash
python -m pytest -q
```

## How it works

```
spec (size, difficulty, shots, temperature)
   │
   ▼
LLM generator ──JSON──► verifier ──► valid? ──yes──► difficulty rater ──► puzzle ✔
   ▲                        │
   └──── feedback ◄─────────┘ no: "2 solutions, they differ on Sara/Mhmd"
         (Observation)          / "clues 2 and 6 contradict" / "broken JSON"
```

* **Puzzle format** (`puzzlelab/puzzle.py`): JSON with `size`, `categories`, `clues`.
  8 clue types: `same, not_same, at, not_at, right_of, left_of, next_to, not_next_to`.
* **Solver** (`solver.py`): constraint propagation + backtracking; counts solutions
  (stops at 2 for the uniqueness test). Cross-checked against a brute-force solver.
* **Verifier** (`verifier.py`): statuses `valid / multiple_solutions / no_solution /
  format_error`; finds the minimal set of contradicting clues; shows two competing
  solutions; detects redundant clues; checks the LLM's claimed solution.
* **Difficulty rater** (`difficulty.py`): simulates a human solver — deduction rounds and
  number of guesses needed. `easy` = pure deduction in ≤6 rounds, `hard` = needs guessing.
* **Generator** (`generator.py`): system prompt with the schema, few-shot examples from
  the classic generator, repair loop.
* **Classic generator** (`baseline.py`): non-LLM baseline (random solution → add true
  clues until unique → remove unneeded clues).
* **Solvers** (`solving.py`): plain, chain-of-thought, ReAct agent with tools
  `deduce[...]`, `check[...]`, `finish[...]`.

## Metrics
validity on first try · validity after repair · repair rounds · failure types ·
LLM self-verification error rate · theme diversity (1 − mean Jaccard) · duplicates ·
requested vs measured difficulty · solving accuracy (exact and per cell) · steps · tokens.

## Project layout
```
puzzlelab/         core library (puzzle, solver, verifier, difficulty, generator, solving, llm)
run_generation.py  Part 1 experiments
run_solving.py     Part 2 experiments
make_charts.py     charts + summary.md
app.py             Streamlit demo
check_key.py       API key check
tests/             pytest tests
results/           outputs (results/mock = pipeline test data only)
```
