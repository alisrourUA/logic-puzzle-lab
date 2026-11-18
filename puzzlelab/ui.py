"""HTML/CSS building blocks for the Streamlit demo: the street of houses, clue cards, chat bubbles."""
from __future__ import annotations

import html

from .puzzle import Puzzle, render_clue

# ---------------------------------------------------------------- palette
INK = "#F4F0E8"        # text on dusk
MUTED = "#A9A6C8"
DUSK = "#1F1C3F"       # page
DUSK_2 = "#2A2654"     # panels
DUSK_3 = "#37326A"     # raised
LIGHT = "#FFC65C"      # window light / success glow
MINT = "#47D6A0"       # valid
CORAL = "#FF7466"      # contradiction / wrong
SKY = "#7FB3FF"        # info

FACADES = {
    "red": "#E0574A", "green": "#4FAF72", "blue": "#3F7FD0", "yellow": "#F0C24B", "white": "#ECE7DC",
    "black": "#3A3946", "purple": "#8D6BD0", "orange": "#F08B3D", "pink": "#E98CB2", "brown": "#8E5F3E",
    "gray": "#8C90A0", "grey": "#8C90A0", "ivory": "#EFE6CF", "beige": "#D9C7A3", "teal": "#2FA3A0",
    "cyan": "#4CC3D9", "navy": "#2C3E78", "gold": "#D9A62E", "silver": "#B9BCC6", "violet": "#9B6FD6",
    "lavender": "#B7A4E3", "maroon": "#8A2E3B", "turquoise": "#38C1B4", "lime": "#9BCB3C", "magenta": "#C9479B",
}
LIGHT_FACADES = {"white", "yellow", "ivory", "beige", "silver", "gold", "lime", "lavender", "cyan", "pink"}

EMOJI = {
    # pets / animals
    "cat": "🐱", "dog": "🐶", "fish": "🐟", "bird": "🐦", "rabbit": "🐰", "turtle": "🐢", "horse": "🐴",
    "hamster": "🐹", "parrot": "🦜", "snake": "🐍", "zebra": "🦓", "lizard": "🦎", "frog": "🐸", "mouse": "🐭",
    # drinks
    "tea": "🍵", "coffee": "☕", "juice": "🧃", "milk": "🥛", "water": "💧", "lemonade": "🍋", "wine": "🍷",
    "beer": "🍺", "soda": "🥤", "smoothie": "🥤",
    # food
    "pizza": "🍕", "sushi": "🍣", "falafel": "🧆", "burger": "🍔", "pasta": "🍝", "salad": "🥗", "cake": "🍰",
    "fries": "🍟", "cookies": "🍪", "chips": "🥔", "candy": "🍬", "fruit": "🍎", "tacos": "🌮", "soup": "🍲",
    "sandwich": "🥪", "chocolate": "🍫", "ice cream": "🍨", "bread": "🍞", "cheese": "🧀", "rice": "🍚",
    # sports / hobbies
    "football": "⚽", "soccer": "⚽", "tennis": "🎾", "chess": "♟️", "swimming": "🏊", "basketball": "🏀",
    "running": "🏃", "cycling": "🚴", "painting": "🎨", "reading": "📚", "gardening": "🌱", "cooking": "🍳",
    "baking": "🧁", "golf": "⛳", "golfing": "⛳", "music": "🎵", "dancing": "💃", "hiking": "🥾",
    "photography": "📷", "gaming": "🎮", "fishing": "🎣", "yoga": "🧘", "singing": "🎤", "writing": "✍️",
    # jobs
    "doctor": "🩺", "teacher": "🧑‍🏫", "engineer": "🛠️", "chef": "👨‍🍳", "pilot": "✈️", "artist": "🎨",
    "nurse": "💉", "lawyer": "⚖️", "farmer": "🌾", "writer": "✍️", "scientist": "🔬", "musician": "🎻",
    # flowers / plants
    "rose": "🌹", "roses": "🌹", "tulip": "🌷", "tulips": "🌷", "daisy": "🌼", "daisies": "🌼", "lily": "🪷",
    "lilies": "🪷", "sunflower": "🌻", "cactus": "🌵", "fern": "🌿",
    # tools / vehicles
    "shovel": "🪏", "rake": "🧹", "hammer": "🔨", "car": "🚗", "bike": "🚲", "bus": "🚌", "truck": "🚚",
    "sedan": "🚗", "convertible": "🏎️", "train": "🚆", "boat": "⛵", "plane": "✈️",
}
CAT_EMOJI = {"person": "🧑", "name": "🧑", "owner": "🧑", "friend": "🧑", "family": "🏠", "nationality": "🌍"}

PERSON_CATS = {"person", "name", "owner", "friend", "people", "resident", "nationality", "family"}
COLOR_CATS = {"color", "colour", "house color", "house_color"}


def esc(x) -> str:
    return html.escape(str(x))


def _color_cat(p: Puzzle) -> str | None:
    for c in p.categories:
        if c.lower() in COLOR_CATS:
            return c
    return None


def icon(cat: str, val: str) -> str:
    v = str(val).lower()
    if v in EMOJI:
        return EMOJI[v]
    if v.endswith("s") and v[:-1] in EMOJI:
        return EMOJI[v[:-1]]
    return CAT_EMOJI.get(cat.lower(), "")


CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700;12..96,800&family=Atkinson+Hyperlegible:wght@400;700&display=swap');

.stApp, .stApp *:not([class*="material"]):not([data-testid*="Icon"]):not(code) {{
  font-family: 'Atkinson Hyperlegible', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
}}
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp .display, .stApp .castcard b, .stApp .round-head .t,
.stApp .round-head .dot, .stApp .bubble .who, .stApp .verdict, .stApp .racecard h4, .stApp .racecard .res,
.stApp .finding .num, .stApp .finding .txt b, .stApp div[data-testid="stTabs"] button p {{
  font-family: 'Bricolage Grotesque', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif !important;
  letter-spacing: -0.01em;
}}
.block-container {{ padding-top: 2.2rem; max-width: 1180px; }}
[data-testid="stHeader"] {{ background: transparent; }}

/* ---------- hero ---------- */
.hero {{ display:grid; grid-template-columns: 1.25fr 1fr; gap: 2.5rem; align-items:center; margin-bottom: 1.6rem; }}
.hero h1 {{ font-size: clamp(2.2rem, 4.2vw, 3.6rem); line-height: 1.02; font-weight: 800; margin: 0 0 .8rem 0; color: {INK}; }}
.hero p {{ color: {MUTED}; font-size: 1.12rem; line-height: 1.55; max-width: 34rem; margin:0; }}
.hero .cast {{ display:flex; gap: 1rem; margin-top: 1.2rem; flex-wrap: wrap; }}
.castcard {{ background:{DUSK_2}; border-radius: 14px; padding:.7rem .9rem; display:flex; gap:.7rem; align-items:center; flex: 1 1 14rem; }}
.castcard .face {{ font-size: 1.8rem; }}
.castcard b {{ color:{INK}; font-size:1.05rem; }}
.castcard span {{ color:{MUTED}; font-size:.9rem; display:block; line-height:1.3; }}
@media (max-width: 900px) {{ .hero {{ grid-template-columns: 1fr; }} }}

/* ---------- street ---------- */
.street {{ display:flex; gap: 14px; align-items:flex-start; padding: 18px 16px 0 16px; position:relative; }}
.street-wrap {{ background: linear-gradient(180deg, #2B2760 0%, #24204F 70%, #1A1838 100%); border-radius: 18px; padding-bottom: 14px; overflow:hidden; }}
.street-wrap .ground {{ height: 8px; background: #141230; margin: 0 0 10px 0; }}
.street-title {{ color:{MUTED}; font-size:.92rem; padding: 12px 18px 0 18px; }}
.street-title b {{ color:{INK}; }}
.house {{ flex:1 1 0; min-width: 0; display:flex; flex-direction:column; align-items:stretch; }}
.roof {{ height: 30px; clip-path: polygon(50% 0, 100% 100%, 0 100%); background: #4A4380; }}
.facade {{ height: 74px; position:relative; display:flex; justify-content:center; align-items:center; gap:10px; }}
.pane {{ width: 18px; height: 22px; border-radius: 3px; background:#1B1838; box-shadow: inset 0 0 0 2px rgba(0,0,0,.25); }}
.lit .pane {{ background:{LIGHT}; box-shadow: 0 0 14px 2px rgba(255,198,92,.55); }}
.door {{ position:absolute; bottom:0; left: 50%; transform:translateX(-50%); width: 18px; height: 30px; border-radius: 9px 9px 0 0; background: rgba(0,0,0,.35); }}
.housenum {{ text-align:center; color:{MUTED}; font-size:.8rem; margin: 6px 0 4px; }}
.cell {{ background:{DUSK_3}; color:{INK}; border-radius: 8px; padding: 5px 6px; margin-top: 5px; font-size:.92rem; text-align:center; border: 2px solid transparent; line-height:1.2; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.cell small {{ display:block; color:{MUTED}; font-size:.68rem; }}
.cell.hidden {{ color:{MUTED}; }}
.cell.good {{ border-color:{MINT}; }}
.cell.bad {{ border-color:{CORAL}; background: rgba(255,116,102,.12); }}
.cell.diff {{ border-color:{LIGHT}; background: rgba(255,198,92,.16); box-shadow: 0 0 12px rgba(255,198,92,.35); }}
.streets2 {{ display:grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
@media (max-width: 900px) {{ .streets2 {{ grid-template-columns: 1fr; }} }}

/* hero animation: windows light up one by one (once) */
.hero-street .facade {{ height: 110px; }}
.hero-street .roof {{ height: 44px; }}
.hero-street .pane {{ width: 24px; height: 30px; }}
.hero-street .door {{ width: 24px; height: 42px; }}
.hero-street .lit .pane {{ animation: lighton .5s ease-out both; }}
.hero-street .house:nth-child(1) .pane {{ animation-delay: .2s; }}
.hero-street .house:nth-child(2) .pane {{ animation-delay: .55s; }}
.hero-street .house:nth-child(3) .pane {{ animation-delay: .9s; }}
.hero-street .house:nth-child(4) .pane {{ animation-delay: 1.25s; }}
@keyframes lighton {{ from {{ background:#1B1838; box-shadow:none; }} to {{ background:{LIGHT}; }} }}
@media (prefers-reduced-motion: reduce) {{ .hero-street .lit .pane {{ animation: none; }} }}

/* ---------- clues ---------- */
.clues {{ display:grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 8px; }}
.clue {{ background:{DUSK_2}; border-radius: 10px; padding: 8px 11px; color:{INK}; font-size: .96rem; border-left: 4px solid #4A4380; display:flex; gap:.6rem; }}
.clue .n {{ color:{MUTED}; font-weight:700; min-width: 1.4rem; }}
.clue.bad {{ border-left-color:{CORAL}; background: rgba(255,116,102,.14); }}
.clue.ok {{ border-left-color:{MINT}; }}

/* ---------- conversation ---------- */
.round-head {{ display:flex; align-items:center; gap:.7rem; margin: 1.6rem 0 .6rem; }}
.round-head .dot {{ width: 30px; height: 30px; border-radius: 50%; background:{DUSK_3}; color:{INK}; display:flex; align-items:center; justify-content:center; font-weight:700; }}
.round-head .t {{ color:{INK}; font-size:1.2rem; font-weight:700; }}
.bubble {{ border-radius: 16px; padding: 14px 16px; margin: 8px 0; }}
.bubble .who {{ font-weight:700; color:{INK}; font-size:1.02rem; margin-bottom: 6px; display:flex; gap:.5rem; align-items:center; }}
.bubble .say {{ color:{INK}; font-size:1.02rem; line-height:1.5; }}
.bubble .say i {{ color:{MUTED}; }}
.architect {{ background:{DUSK_2}; margin-right: 10%; }}
.inspector {{ background:#262350; margin-left: 10%; border: 2px solid {DUSK_3}; }}
.inspector.valid {{ border-color:{MINT}; }}
.inspector.multiple {{ border-color:{LIGHT}; }}
.inspector.contra, .inspector.format {{ border-color:{CORAL}; }}
.verdict {{ font-size:1.35rem; font-weight:800; margin: 2px 0 6px; }}
.verdict.valid {{ color:{MINT}; }} .verdict.multiple {{ color:{LIGHT}; }} .verdict.contra, .verdict.format {{ color:{CORAL}; }}
.claim {{ margin-top:10px; color:{MUTED}; font-size:.95rem; }}
.claim b {{ color:{CORAL}; }}

.final {{ border-radius: 18px; padding: 18px 20px; margin: 1.4rem 0 .6rem; }}
.final.win {{ background: rgba(71,214,160,.12); border: 2px solid {MINT}; }}
.final.lose {{ background: rgba(255,116,102,.10); border: 2px solid {CORAL}; }}
.final h3 {{ margin: 0 0 4px; color:{INK}; }}
.final p {{ margin:0; color:{MUTED}; }}
.meter {{ display:flex; gap:6px; margin-top:10px; }}
.meter span {{ flex:1; height: 10px; border-radius: 5px; background:{DUSK_3}; }}
.meter span.on {{ background:{LIGHT}; }}

/* ---------- AI race cards ---------- */
.racecard {{ background:{DUSK_2}; border-radius: 16px; padding: 16px 18px 12px; border: 2px solid transparent; display:grid; grid-template-columns: 17rem 1fr; gap: 1.4rem; align-items:center; margin-top: 12px; }}
@media (max-width: 900px) {{ .racecard {{ grid-template-columns: 1fr; }} }}
.racecard.win {{ border-color:{MINT}; }} .racecard.lose {{ border-color:{CORAL}; }}
.racecard h4 {{ color:{INK}; margin:0; font-size:1.2rem; }}
.racecard .how {{ color:{MUTED}; font-size:.95rem; margin: 4px 0 10px; line-height:1.4; }}
.racecard .res {{ font-size:1.3rem; font-weight:800; margin: 4px 0; }}
.racecard .res.win {{ color:{MINT}; }} .racecard .res.lose {{ color:{CORAL}; }}
.racecard .meta {{ color:{MUTED}; font-size:.85rem; margin-bottom:8px; }}
.step {{ display:grid; grid-template-columns: 7.5rem 1fr; gap:.6rem; padding: 8px 0; border-top: 1px solid {DUSK_3}; }}
.step .k {{ color:{MUTED}; font-weight:700; }}
.step .v {{ color:{INK}; white-space: pre-wrap; font-size:.93rem; }}

/* ---------- findings ---------- */
.finding {{ display:grid; grid-template-columns: 17rem 1fr; gap: 1.2rem; align-items:center; padding: 18px 0; border-top: 1px solid {DUSK_3}; }}
.finding .num {{ font-weight:800; font-size: 2.2rem; color:{LIGHT}; line-height:1.1; }}
.finding .txt b {{ color:{INK}; font-size:1.15rem; display:block; margin-bottom:3px; }}
.finding .txt span {{ color:{MUTED}; line-height:1.5; }}

.note {{ color:{MUTED}; font-size:.95rem; }}
div[data-testid="stTabs"] button p {{ font-size: 1.05rem; }}
</style>
"""


# ---------------------------------------------------------------- builders
def street_html(p: Puzzle, table: dict[str, list[str]] | None, marks: dict | None = None,
                title: str | None = None, lit: bool = False, extra_class: str = "") -> str:
    """Draw the street. table: {category: [value per house]} (None or missing = unknown '?').
    marks: {(category, house_index): 'good'|'bad'|'diff'}."""
    marks = marks or {}
    ccat = _color_cat(p)
    houses = []
    for i in range(p.size):
        facade = "#5A548F"
        fg_dark = False
        if ccat and table and table.get(ccat) and i < len(table[ccat]) and table[ccat][i]:
            cv = str(table[ccat][i]).lower()
            facade = FACADES.get(cv, facade)
            fg_dark = cv in LIGHT_FACADES
        cells = []
        for cat in p.categories:
            if cat == ccat:
                continue
            val = table.get(cat, [None] * p.size)[i] if table else None
            cls = marks.get((cat, i), "")
            if val in (None, ""):
                cells.append(f'<div class="cell hidden {cls}"><small>{esc(cat)}</small>?</div>')
            else:
                ic = icon(cat, val)
                cells.append(f'<div class="cell {cls}"><small>{esc(cat)}</small>{ic} {esc(val)}</div>')
        if ccat:
            cval = table.get(ccat, [None] * p.size)[i] if table else None
            ccls = marks.get((ccat, i), "")
            label = esc(cval) if cval else "?"
            cells.insert(0, f'<div class="cell {ccls} {"hidden" if not cval else ""}"><small>{esc(ccat)}</small>{label}</div>')
        houses.append(
            f'<div class="house {"lit" if lit else ""}">'
            f'<div class="roof"></div>'
            f'<div class="facade" style="background:{facade}"><div class="pane"></div><div class="pane"></div><div class="door"></div></div>'
            f'<div class="housenum">house {i + 1}</div>{"".join(cells)}</div>')
    t = f'<div class="street-title">{title}</div>' if title else ""
    return f'<div class="street-wrap {extra_class}">{t}<div class="street">{"".join(houses)}</div></div>'


def hero_street() -> str:
    houses = []
    for col in ("#E0574A", "#F0C24B", "#3F7FD0", "#4FAF72"):
        houses.append(f'<div class="house lit"><div class="roof"></div><div class="facade" style="background:{col}">'
                      f'<div class="pane"></div><div class="pane"></div><div class="door"></div></div></div>')
    return f'<div class="street-wrap hero-street"><div class="street" style="padding-top:26px">{"".join(houses)}</div><div class="ground" style="margin-top:0"></div></div>'


def clues_html(p: Puzzle, bad: set[int] | None = None, ok: set[int] | None = None) -> str:
    bad, ok = bad or set(), ok or set()
    items = []
    for i, c in enumerate(p.clues, 1):
        cls = "bad" if i in bad else ("ok" if i in ok else "")
        items.append(f'<div class="clue {cls}"><span class="n">{i}</span><span>{esc(render_clue(c))}</span></div>')
    return f'<div class="clues">{"".join(items)}</div>'


def bubble(kind: str, who: str, face: str, body: str, extra: str = "") -> str:
    return f'<div class="bubble {kind} {extra}"><div class="who"><span>{face}</span>{esc(who)}</div><div class="say">{body}</div></div>'


def meter(level: str) -> str:
    n = {"easy": 1, "medium": 2, "hard": 3}.get(level, 0)
    return '<div class="meter">' + "".join(f'<span class="{"on" if i < n else ""}"></span>' for i in range(3)) + "</div>"