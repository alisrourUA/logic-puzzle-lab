"""Puzzle data model for Zebra / Einstein logic puzzles.

A puzzle has `size` houses in a row (positions 1..size) and several categories
(e.g. color, person, pet). Each category has exactly `size` distinct values, and
every value sits in exactly one house. Clues constrain where values can be.

Items are written as "category:value", e.g. "pet:cat".

Clue types (all positions are 1-based, house 1 is the leftmost):
    same         a and b are in the same house
    not_same     a and b are in different houses
    at           a is in house `pos`
    not_at       a is not in house `pos`
    right_of     a is IMMEDIATELY to the right of b   (pos(a) == pos(b) + 1)
    left_of      a is somewhere to the left of b      (pos(a) <  pos(b))
    next_to      a and b are in adjacent houses       (|pos(a) - pos(b)| == 1)
    not_next_to  a and b are not adjacent and not in the same house
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

CLUE_TYPES = {
    "same": ("a", "b"),
    "not_same": ("a", "b"),
    "at": ("a", "pos"),
    "not_at": ("a", "pos"),
    "right_of": ("a", "b"),
    "left_of": ("a", "b"),
    "next_to": ("a", "b"),
    "not_next_to": ("a", "b"),
}


class PuzzleFormatError(ValueError):
    """Raised when a puzzle (usually LLM output) does not follow the schema."""


@dataclass(frozen=True)
class Clue:
    type: str
    a: str
    b: str | None = None
    pos: int | None = None

    def items(self) -> list[str]:
        return [x for x in (self.a, self.b) if x is not None]

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": self.type, "a": self.a}
        if self.b is not None:
            d["b"] = self.b
        if self.pos is not None:
            d["pos"] = self.pos
        return d

    def holds(self, p: dict[str, int]) -> bool:
        """Check the clue against a full or partial position map item -> house."""
        pa = p[self.a]
        if self.type == "at":
            return pa == self.pos
        if self.type == "not_at":
            return pa != self.pos
        pb = p[self.b]
        t = self.type
        if t == "same":
            return pa == pb
        if t == "not_same":
            return pa != pb
        if t == "right_of":
            return pa == pb + 1
        if t == "left_of":
            return pa < pb
        if t == "next_to":
            return abs(pa - pb) == 1
        if t == "not_next_to":
            return abs(pa - pb) > 1
        raise PuzzleFormatError(f"unknown clue type {t}")


@dataclass
class Puzzle:
    size: int
    categories: dict[str, list[str]]
    clues: list[Clue]
    # Optional fields an LLM may provide
    claimed_solution: dict[str, list[str]] | None = None
    claimed_unique: bool | None = None
    title: str | None = None
    story: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    # ---------- helpers ----------
    def all_items(self) -> list[str]:
        return [f"{c}:{v}" for c, vals in self.categories.items() for v in vals]

    def category_of(self, item: str) -> str:
        return item.split(":", 1)[0]

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "size": self.size,
            "categories": self.categories,
            "clues": [c.to_dict() for c in self.clues],
        }
        if self.title:
            d["title"] = self.title
        if self.story:
            d["story"] = self.story
        if self.claimed_solution is not None:
            d["claimed_solution"] = self.claimed_solution
        if self.claimed_unique is not None:
            d["claimed_unique"] = self.claimed_unique
        return d

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def canonical_key(self) -> str:
        """Order-independent fingerprint of the logical content (for novelty / duplicates)."""
        cats = sorted((c, tuple(sorted(v))) for c, v in self.categories.items())
        clues = sorted(json.dumps(c.to_dict(), sort_keys=True) for c in self.clues)
        return json.dumps([self.size, cats, clues])

    # ---------- parsing ----------
    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Puzzle":
        if not isinstance(d, dict):
            raise PuzzleFormatError("puzzle must be a JSON object")
        for k in ("size", "categories", "clues"):
            if k not in d:
                raise PuzzleFormatError(f"missing field '{k}'")
        size = d["size"]
        if not isinstance(size, int) or not 2 <= size <= 6:
            raise PuzzleFormatError("'size' must be an integer between 2 and 6")
        cats = d["categories"]
        if not isinstance(cats, dict) or len(cats) < 2:
            raise PuzzleFormatError("'categories' must be an object with at least 2 categories")
        clean_cats: dict[str, list[str]] = {}
        for cname, vals in cats.items():
            if ":" in str(cname):
                raise PuzzleFormatError(f"category name '{cname}' must not contain ':'")
            if not isinstance(vals, list) or len(vals) != size:
                raise PuzzleFormatError(
                    f"category '{cname}' must list exactly {size} values (got {vals})")
            vals = [str(v) for v in vals]
            if len(set(vals)) != size:
                raise PuzzleFormatError(f"category '{cname}' has duplicate values")
            clean_cats[str(cname)] = vals
        known = {f"{c}:{v}" for c, vs in clean_cats.items() for v in vs}

        raw_clues = d["clues"]
        if not isinstance(raw_clues, list) or not raw_clues:
            raise PuzzleFormatError("'clues' must be a non-empty list")
        clues: list[Clue] = []
        for i, rc in enumerate(raw_clues, 1):
            if not isinstance(rc, dict) or "type" not in rc:
                raise PuzzleFormatError(f"clue {i} must be an object with a 'type'")
            t = rc["type"]
            if t not in CLUE_TYPES:
                raise PuzzleFormatError(
                    f"clue {i} has unknown type '{t}'. Allowed: {', '.join(CLUE_TYPES)}")
            a = rc.get("a")
            if a not in known:
                raise PuzzleFormatError(f"clue {i}: item '{a}' is not a known 'category:value'")
            if CLUE_TYPES[t][1] == "pos":
                pos = rc.get("pos")
                if not isinstance(pos, int) or not 1 <= pos <= size:
                    raise PuzzleFormatError(f"clue {i}: 'pos' must be an integer 1..{size}")
                clues.append(Clue(t, a, pos=pos))
            else:
                b = rc.get("b")
                if b not in known:
                    raise PuzzleFormatError(f"clue {i}: item '{b}' is not a known 'category:value'")
                if a == b:
                    raise PuzzleFormatError(f"clue {i}: 'a' and 'b' are the same item")
                clues.append(Clue(t, a, b=b))

        claimed = d.get("claimed_solution")
        if claimed is not None:
            if not isinstance(claimed, dict):
                claimed = None
            else:
                claimed = {str(k): [str(x) for x in v] for k, v in claimed.items()
                           if isinstance(v, list)}
        cu = d.get("claimed_unique")
        return Puzzle(size=size, categories=clean_cats, clues=clues,
                      claimed_solution=claimed,
                      claimed_unique=cu if isinstance(cu, bool) else None,
                      title=d.get("title"), story=d.get("story"))

    @staticmethod
    def from_json(text: str) -> "Puzzle":
        return Puzzle.from_dict(extract_json(text))


def _strip_comments(text: str) -> str:
    """Remove // and /* */ comments (outside strings) and trailing commas - common LLM JSON slips."""
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1]); i += 2; continue
            if ch == '"':
                in_str = False
            i += 1; continue
        if ch == '"':
            in_str = True; out.append(ch); i += 1; continue
        if text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        out.append(ch); i += 1
    import re
    return re.sub(r",\s*([}\]])", r"\1", "".join(out))


def _loads(candidate: str) -> Any:
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return json.loads(_strip_comments(candidate))


def extract_json(text: str) -> Any:
    """Pull the first JSON object out of an LLM reply (handles ```json fences, chatter, comments)."""
    text = text.strip()
    if "```" in text:
        for p in text.split("```")[1::2]:
            p = p.strip()
            if p.lower().startswith("json"):
                p = p[4:]
            try:
                return _loads(p)
            except json.JSONDecodeError:
                continue
    try:
        return _loads(text)
    except json.JSONDecodeError:
        pass
    cleaned = _strip_comments(text)
    start = cleaned.find("{")
    if start == -1:
        raise PuzzleFormatError("no JSON object found in the reply")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(cleaned)):
        ch = cleaned[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(cleaned[start:i + 1])
                except json.JSONDecodeError as e:
                    raise PuzzleFormatError(f"invalid JSON: {e}") from e
    raise PuzzleFormatError("unterminated JSON object in the reply")


# ---------- natural-language rendering ----------
def _name(item: str) -> str:
    cat, val = item.split(":", 1)
    c = cat.lower()
    if c in ("person", "name", "owner", "people", "nationality"):
        return val
    if c in ("color", "colour"):
        return f"the {val} house"
    return f"the {val} ({cat})"


def render_clue(c: Clue) -> str:
    a = _name(c.a)
    b = _name(c.b) if c.b else None
    t = c.type
    if t == "same":
        s = f"{a} is in the same house as {b}"
    elif t == "not_same":
        s = f"{a} is not in the same house as {b}"
    elif t == "at":
        s = f"{a} is in house {c.pos}"
    elif t == "not_at":
        s = f"{a} is not in house {c.pos}"
    elif t == "right_of":
        s = f"{a} is directly to the right of {b}"
    elif t == "left_of":
        s = f"{a} is somewhere to the left of {b}"
    elif t == "next_to":
        s = f"{a} is next to {b}"
    else:
        s = f"{a} is not next to {b}"
    return s[0].upper() + s[1:] + "."


def render_puzzle(p: Puzzle) -> str:
    lines = []
    if p.title:
        lines.append(p.title)
    if p.story:
        lines.append(p.story)
    lines.append(f"There are {p.size} houses in a row, numbered 1 to {p.size} from left to right.")
    for cat, vals in p.categories.items():
        lines.append(f"- {cat}: {', '.join(vals)}")
    lines.append("Each value appears in exactly one house.")
    lines.append("Clues:")
    for i, c in enumerate(p.clues, 1):
        lines.append(f"{i}. {render_clue(c)}")
    return "\n".join(lines)


def solution_to_table(p: Puzzle, sol: dict[str, int]) -> dict[str, list[str]]:
    """item->house map  ->  {category: [value in house 1, value in house 2, ...]}"""
    out: dict[str, list[str]] = {}
    for cat, vals in p.categories.items():
        row = [""] * p.size
        for v in vals:
            row[sol[f"{cat}:{v}"] - 1] = v
        out[cat] = row
    return out


def table_to_solution(p: Puzzle, table: dict[str, list[str]]) -> dict[str, int] | None:
    """Inverse of solution_to_table; returns None if the table is malformed."""
    sol: dict[str, int] = {}
    try:
        for cat, vals in p.categories.items():
            row = table[cat]
            if sorted(row) != sorted(vals):
                return None
            for i, v in enumerate(row, 1):
                sol[f"{cat}:{v}"] = i
    except (KeyError, TypeError):
        return None
    return sol
