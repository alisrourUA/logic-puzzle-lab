"""Logic Puzzle Lab - story-style demo.   Run:  streamlit run app.py"""
from __future__ import annotations

import json
import os
import random

import streamlit as st

from puzzlelab import config, ui
from puzzlelab.baseline import generate as classic_generate
from puzzlelab.generator import Spec, run
from puzzlelab.llm import get_client
from puzzlelab.puzzle import extract_json, solution_to_table
from puzzlelab.solver import differing_items, solve
from puzzlelab.solving import canon_table, solve_with_llm
from puzzlelab.verifier import _unsat_core, verify

st.set_page_config(page_title="Logic Puzzle Lab", page_icon="🏘️", layout="wide",
                   initial_sidebar_state="collapsed")
st.markdown(ui.CSS, unsafe_allow_html=True)
ss = st.session_state


def html(x: str):
    # st.html inserts raw HTML (no markdown parsing), so long HTML blocks are never mangled
    st.html(x)


# ------------------------------------------------------------------ hero
html(f"""
<div class="hero">
  <div>
    <h1>Can an AI write a riddle it can’t solve?</h1>
    <p>GPT invents logic puzzles about a street of houses. An exact solver checks every one.
    When a riddle is broken, the solver explains why and GPT rewrites it. Then we see whether
    GPT can solve the riddles itself.</p>
    <div class="cast">
      <div class="castcard"><span class="face">🏗️</span><div><b>The Architect</b>
        <span>GPT. Writes the riddle and says it has exactly one answer.</span></div></div>
      <div class="castcard"><span class="face">🔎</span><div><b>The Inspector</b>
        <span>An exact solver. Tries every possible street and never guesses.</span></div></div>
    </div>
  </div>
  <div>{ui.hero_street()}</div>
</div>
""")

act1, act2, act3, act4 = st.tabs(["1. The Architect writes a riddle", "2. Your turn", "3. Can an AI solve it?",
                                  "4. What we found"])


# ------------------------------------------------------------------ helpers
def set_puzzle(p, source: str):
    rep = verify(p, check_redundancy=False)
    ss.puzzle, ss.truth, ss.source = p, rep.solution, source
    ss.pid = str(abs(hash(p.canonical_key())))[:8]
    ss.play_bad, ss.play_result = set(), None


def load_classic():
    set_puzzle(classic_generate(4, 3, "hard", seed=random.randrange(10**6)), "ready-made")


def client_from_settings():
    backend = ss.get("backend", "openai" if os.getenv("OPENAI_API_KEY") else "mock")
    return get_client(backend, ss.get("model", config.MODEL), seed=random.randrange(10**9))


def no_puzzle_state(key: str):
    html('<p class="note">There is no riddle yet. Write one in act 1, or start with a ready-made riddle.</p>')
    st.button("Load a ready-made riddle", key=key, on_click=load_classic)


# ------------------------------------------------------------------ act 1
def render_round(att, idx: int):
    rep = att.report
    p = rep.puzzle
    html(f'<div class="round-head"><div class="dot">{idx + 1}</div>'
         f'<div class="t">{"First draft" if idx == 0 else "Rewrite after feedback"}</div></div>')

    # --- the Architect speaks
    thought, title, story = None, None, None
    try:
        d = extract_json(att.raw)
        thought, title, story = d.get("thought"), d.get("title"), d.get("story")
    except Exception:
        pass
    say = ""
    if title:
        say += f"<b>{ui.esc(title)}</b><br>"
    if story:
        say += f"{ui.esc(story)}<br>"
    if thought:
        say += f"<i>“{ui.esc(thought)}”</i>"
    if p:
        say += f"<br>I wrote {len(p.clues)} clues. {'I am sure it has exactly one answer.' if p.claimed_unique else ''}"
    else:
        say = say or "<i>(the reply could not be read)</i>"
    html(ui.bubble("architect", "The Architect", "🏗️", say))

    bad_clues = set()
    if rep.status == "no_solution" and p:
        bad_clues = set(_unsat_core(p))
    if p:
        html(ui.clues_html(p, bad=bad_clues))

    # --- the Inspector answers
    if rep.status == "valid":
        diff = rep.difficulty
        body = (f'<div class="verdict valid">Exactly one street fits. The riddle is fair.</div>'
                f'Measured difficulty: <b>{diff["label"]}</b>. A solver needs {diff["rounds"]} rounds of deduction'
                f' and {diff["guesses"]} guesses.{ui.meter(diff["label"])}'
                + ui.street_html(p, rep.solution, lit=True, title="<b>The only street that fits</b>"))
        kind = "valid"
    elif rep.status == "multiple_solutions":
        sols = solve(p, limit=2).solutions
        a, b = sols[0], sols[1]
        dif = differing_items(p, a, b)
        ma = {(it.split(":", 1)[0], a[it] - 1): "diff" for it in dif}
        mb = {(it.split(":", 1)[0], b[it] - 1): "diff" for it in dif}
        n = rep.n_solutions
        count = f"At least {n}" if n >= 50 else str(n)
        body = (f'<div class="verdict multiple">{count} different streets fit every clue.</div>'
                f'A fair riddle has exactly one answer. Here are two streets that both satisfy all the clues. '
                f'The glowing cells are where they disagree, so the clues never decide them.'
                f'<div class="streets2">'
                + ui.street_html(p, solution_to_table(p, a), ma, title="<b>Street A</b> fits every clue")
                + ui.street_html(p, solution_to_table(p, b), mb, title="<b>Street B</b> also fits every clue")
                + '</div>')
        kind = "multiple"
    elif rep.status == "no_solution":
        nums = ", ".join(str(i) for i in sorted(bad_clues))
        body = (f'<div class="verdict contra">No street can satisfy these clues.</div>'
                f'Clues {nums} contradict each other (marked in red above). At least one of them has to change.')
        kind = "contra"
    else:
        body = (f'<div class="verdict format">The blueprint could not be read.</div>'
                f'The reply was not valid JSON, so nothing could be checked. Detail: {ui.esc(rep.feedback[:200])}')
        kind = "format"
    if p and p.claimed_unique and rep.status != "valid":
        body += '<div class="claim">The Architect claimed this riddle has exactly one answer. <b>It was wrong.</b></div>'
    html(ui.bubble(f"inspector {kind}", "The Inspector", "🔎", body))
    if rep.status != "valid":
        with st.expander("What the Inspector sent back to the Architect"):
            st.write(rep.feedback)


with act1:
    c1, c2, c3 = st.columns([2.2, 1.2, 1.6])
    theme = c1.text_input("Theme for the street", placeholder="e.g. a street of Beirut cafés, a space station")
    size = c2.segmented_control("Houses", [3, 4, 5], default=4, key="size")
    diff_req = c3.segmented_control("Difficulty to ask for", ["easy", "medium", "hard"], default="medium",
                                    key="diffreq")
    with st.expander("Lab settings"):
        a, b, c = st.columns(3)
        n_cats = a.slider("Categories per house", 2, 5, 3)
        shots = b.select_slider("Example riddles shown to GPT", [0, 1, 2, 3], value=3)
        temperature = c.slider("Temperature", 0.0, 1.5, 0.7, 0.1)
        a, b, c = st.columns(3)
        max_repair = a.slider("Rewrites allowed", 0, 6, 4)
        top_p = b.slider("Top-p", 0.1, 1.0, 1.0, 0.05)
        c.radio("LLM", ["openai", "mock"], key="backend", horizontal=True,
                index=0 if os.getenv("OPENAI_API_KEY") else 1,
                help="'mock' is an offline imitation used for testing without an API key.")
        st.text_input("Model", config.MODEL, key="model")

    if st.button("Write a riddle", type="primary"):
        spec = Spec(size=size or 4, n_cats=n_cats, difficulty=diff_req or "medium", shots=shots,
                    temperature=temperature, top_p=top_p, theme=theme or None)
        ss.gen = None
        live = st.container()
        counter = {"i": 0}

        def on_step(att):
            with live:
                render_round(att, counter["i"])
            counter["i"] += 1

        with st.status("The Architect is drafting a riddle and the Inspector is checking it…", expanded=False):
            gr = run(client_from_settings(), spec, max_repair=max_repair, on_step=on_step)
        ss.gen = gr
        if gr.final.report.valid:
            set_puzzle(gr.final.report.puzzle, "GPT")
        st.rerun()

    gr = ss.get("gen")
    if gr:
        for i, att in enumerate(gr.attempts):
            render_round(att, i)
        if gr.final.report.valid:
            n = len(gr.attempts) - 1
            took = "Fair on the first try." if n == 0 else f"It took {n} rewrite{'s' if n > 1 else ''} to make it fair."
            html(f'<div class="final win"><h3>The riddle is ready</h3><p>{took} '
                 f'Open “Your turn” to play it, or “Can an AI solve it?” to watch GPT try.</p></div>')
        else:
            html(f'<div class="final lose"><h3>No fair riddle after {len(gr.attempts) - 1} rewrites</h3>'
                 f'<p>The Architect kept producing riddles with several answers or contradictions. '
                 f'This happens in about a quarter of our runs. Try again, or use a ready-made riddle.</p></div>')
            st.button("Use a ready-made riddle", on_click=load_classic, key="fallback1")
    else:
        html('<p class="note">Pick a theme and a difficulty, then ask the Architect to write a riddle. '
             'Every draft goes to the Inspector, and you will see exactly what it finds.</p>')


# ------------------------------------------------------------------ act 2
def hint_cb():
    p, truth = ss.puzzle, ss.truth
    for i in range(p.size):
        for cat in p.categories:
            k = f"play_{ss.pid}_{cat}_{i}"
            if ss.get(k) != truth[cat][i]:
                ss[k] = truth[cat][i]
                ss.hint_msg = f"House {i + 1} has {truth[cat][i]} ({cat}). It is filled in for you."
                return
    ss.hint_msg = "Every slot is already right."


def answer_cb():
    p, truth = ss.puzzle, ss.truth
    for i in range(p.size):
        for cat in p.categories:
            ss[f"play_{ss.pid}_{cat}_{i}"] = truth[cat][i]
    ss.hint_msg = "The answer is filled in."


with act2:
    if "puzzle" not in ss:
        no_puzzle_state("load2")
    else:
        p, truth = ss.puzzle, ss.truth
        html(f'<p class="note">Fill in the street so that every clue is true. '
             f'This riddle was written by {"GPT and checked by the Inspector" if ss.source == "GPT" else "the classic generator"}.</p>')
        html(ui.clues_html(p, bad=ss.get("play_bad", set())))
        st.write("")
        guess = {cat: [ss.get(f"play_{ss.pid}_{cat}_{i}") for i in range(p.size)] for cat in p.categories}
        marks = {}
        if ss.get("play_result") == "checked":
            marks = {(cat, i): ("good" if guess[cat][i] == truth[cat][i] else "bad")
                     for cat in p.categories for i in range(p.size) if guess[cat][i]}
        solved = all(guess[c] == truth[c] for c in p.categories)
        html(ui.street_html(p, guess, marks if not solved else {}, lit=solved,
                            title="<b>Your street</b>" + (" is solved" if solved else "")))
        cols = st.columns(p.size)
        for i, col in enumerate(cols):
            with col:
                for cat, vals in p.categories.items():
                    st.selectbox(f"{cat}, house {i + 1}", [None] + vals, key=f"play_{ss.pid}_{cat}_{i}",
                                 format_func=lambda v: "choose…" if v is None else f"{ui.icon('', v)} {v}")
        b1, b2, b3, _ = st.columns([1.2, 1.2, 1.2, 3])
        if b1.button("Check my street", type="primary"):
            empty = sum(v is None for row in guess.values() for v in row)
            dupes = [f"{v} ({c})" for c, row in guess.items() for v in set(row) if v and row.count(v) > 1]
            ss.hint_msg = None
            if empty:
                st.warning(f"Fill every slot first. {empty} slots are still empty.")
            elif dupes:
                st.warning("Each value can only be used once. Used twice: " + ", ".join(dupes))
            else:
                pos = {f"{c}:{v}": i + 1 for c, row in guess.items() for i, v in enumerate(row)}
                ss.play_bad = {i for i, cl in enumerate(p.clues, 1) if not cl.holds(pos)}
                ss.play_result = "checked"
                if not ss.play_bad:
                    st.balloons()
                st.rerun()
        b2.button("Give me a hint", on_click=hint_cb)
        b3.button("Show the answer", on_click=answer_cb)
        if ss.get("hint_msg"):
            st.info(ss.hint_msg)
        if ss.get("play_result") == "checked":
            if solved:
                st.success("Solved. Every clue checks out.")
            elif ss.play_bad:
                st.error(f"{len(ss.play_bad)} clue(s) are broken: they are marked in red. "
                         f"Cells in red on the street are wrong.")
        st.button("Load a different ready-made riddle", on_click=load_classic, key="load2b")


# ------------------------------------------------------------------ act 3
METHODS = [
    ("plain", "Just answer", "GPT reads the riddle and gives the answer straight away, with no working."),
    ("cot", "Think step by step", "GPT writes out its reasoning first, then gives the answer."),
    ("react", "Agent with tools", "GPT can call a deduction tool and a checker, read the results, and try again."),
]


def react_steps(transcript) -> str:
    rows = []
    for m in transcript:
        c = m["content"]
        if m["role"] == "tool":
            rows.append(("🔧 Observation", c.replace("Observation:", "").strip()[:500]))
            continue
        th = c.split("Action:")[0].replace("Thought:", "").strip()
        ac = c.split("Action:", 1)[1].strip() if "Action:" in c else ""
        if th:
            rows.append(("💭 Thought", th[:400]))
        if ac:
            rows.append(("▶ Action", ac[:300]))
    return "".join(f'<div class="step"><div class="k">{k}</div><div class="v">{ui.esc(v)}</div></div>' for k, v in rows)


with act3:
    if "puzzle" not in ss:
        no_puzzle_state("load3")
    else:
        p, truth = ss.puzzle, ss.truth
        html('<p class="note">The same riddle, asked three different ways. The Inspector already knows the '
             'answer, so every cell can be marked right or wrong.</p>')
        with st.expander("Read the riddle"):
            html(ui.clues_html(p))
        if st.button("Let all three try", type="primary"):
            res = {}
            with st.status("Asking GPT…", expanded=True) as status:
                for key, name, _ in METHODS:
                    status.write(f"{name}…")
                    res[key] = solve_with_llm(client_from_settings(), p, key, temperature=0.0)
                status.update(label="Done", state="complete")
            ss.race = {"pid": ss.pid, "res": res}
            st.rerun()
        race = ss.get("race")
        if race and race["pid"] == ss.pid:
            for key, name, how in METHODS:
                r = race["res"][key]
                ans = canon_table(p, r.answer) or {}
                table = {c: (ans.get(c) + [None] * p.size)[:p.size] if isinstance(ans.get(c), list) else [None] * p.size
                         for c in p.categories}
                marks = {(c, i): ("good" if table[c][i] == truth[c][i] else "bad")
                         for c in p.categories for i in range(p.size) if table[c][i]}
                total = sum(len(v) for v in p.categories.values())
                right = round(r.cell_accuracy * total)
                win = "win" if r.correct else "lose"
                res_txt = "Solved it" if r.correct else (f"Wrong: {right} of {total} cells right" if r.answer
                                                         else "Gave no usable answer")
                html(f'<div class="racecard {win}"><div><h4>{name}</h4><div class="how">{how}</div>'
                     f'<div class="res {win}">{res_txt}</div>'
                     f'<div class="meta">{r.steps} call{"s" if r.steps > 1 else ""} to GPT, '
                     f'{r.prompt_tokens + r.completion_tokens:,} tokens</div></div>'
                     + ui.street_html(p, table, marks, lit=r.correct) + '</div>')
                if key == "react":
                    with st.expander("Watch the agent's reasoning, step by step"):
                        html(react_steps(r.transcript))
                else:
                    with st.expander("Read GPT's reply"):
                        st.text(r.transcript[0]["content"][-2500:] if r.transcript else "")
        else:
            html('<p class="note">Each try costs a fraction of a cent with gpt-4o-mini.</p>')


# ------------------------------------------------------------------ act 4
def load_rows(path):
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


with act4:
    backend = "openai" if (config.RESULTS / "openai" / "generation.jsonl").exists() else "mock"
    base = config.RESULTS / backend
    gen, sol = load_rows(base / "generation.jsonl"), load_rows(base / "solving.jsonl")
    if not gen:
        html('<p class="note">No experiment results yet. Run <b>python run_generation.py</b>, '
             '<b>python run_solving.py</b> and <b>python make_charts.py --backend openai</b>.</p>')
    else:
        if backend == "mock":
            st.warning("These are mock results from the offline test, not real GPT results.")
        claimed = [r for r in gen if r["first_claimed_unique"] is True and r["first_status"] != "format_error"]
        wrong = sum(r["first_status"] != "valid" for r in claimed)
        first = 100 * sum(r["valid_first_try"] for r in gen) / len(gen)
        final = 100 * sum(r["valid_final"] for r in gen) / len(gen)

        def acc(m):
            rs = [r for r in sol if r["method"] == m]
            return (100 * sum(r["correct"] for r in rs) / len(rs)) if rs else float("nan")

        hard = [r for r in gen if r["experiment"] == "C_difficulty" and r["difficulty"] == "hard" and r["valid_final"]]
        hard_hit = sum(r["measured_label"] == "hard" for r in hard)
        findings = [
            (f"{100 * wrong / max(len(claimed), 1):.0f}%",
             "of the time, GPT's “exactly one answer” claim was false",
             f"It made that claim {len(claimed)} times. The Inspector caught every false one."),
            (f"{first:.0f}% → {final:.0f}%", "fair riddles: first draft vs after the Inspector's feedback",
             "Most first drafts had too few clues, so several streets fit. Feedback fixed most of them."),
        ]
        if sol:
            findings.append((f"{acc('plain'):.0f}% / {acc('cot'):.0f}% / {acc('react'):.0f}%",
                             "riddles solved: just answer / step by step / agent with tools",
                             "Reasoning in text alone almost never works. With tools, GPT solves most riddles."))
        if hard:
            findings.append((f"{hard_hit} of {len(hard)}", "riddles requested as “hard” actually came out hard",
                             "Asking for a difficulty barely changes what GPT writes."))
        html("".join(f'<div class="finding"><div class="num">{n}</div><div class="txt"><b>{t}</b><span>{s}</span></div></div>'
                     for n, t, s in findings))
        model = gen[0].get("model", "?")
        html(f'<p class="note">{len(gen)} riddles generated and {len(sol)} solving attempts with {model}.</p>')
        charts = base / "charts"
        names = [("A_prompting.png", "Example riddles in the prompt"), ("B_temperature.png", "Temperature"),
                 ("C_difficulty.png", "Difficulty control"), ("D_repair.png", "The repair loop"),
                 ("E_solving.png", "Solving")]
        avail = [(f, t) for f, t in names if (charts / f).exists()]
        if avail:
            tabs = st.tabs([t for _, t in avail])
            for tab, (f, _) in zip(tabs, avail):
                tab.image(str(charts / f))