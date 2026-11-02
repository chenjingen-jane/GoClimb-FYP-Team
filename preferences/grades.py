"""One grade scale for the whole site (the team's French-style 4A ... 8B).

Grades are compared by POSITION on the scale, never as text: "5a", " 5A ", "6a+" all work.
"""
import re

GRADES = ["4A", "4B", "4C", "5A", "5B", "5C", "6A", "6B", "6C", "7A", "7B", "7C", "8A", "8B"]
GRADE_CHOICES = [(g, g) for g in GRADES]
_INDEX = {g: i for i, g in enumerate(GRADES)}


def normalize(value):
    """'5a' -> '5A', ' 6b+ ' -> '6B+'. Returns '' for empty/unknown input."""
    if value is None:
        return ""
    g = re.sub(r"\s+", "", str(value)).upper()
    base = g.rstrip("+")
    return g if base in _INDEX else ""


def rank(value):
    """Position on the scale (0 = 4A). '6A+' sits half-way between 6A and 6B. None if unknown."""
    g = normalize(value)
    if not g:
        return None
    return _INDEX[g.rstrip("+")] + (0.5 if g.endswith("+") else 0.0)


def label(r):
    """Inverse of rank for display (rounds down)."""
    if r is None:
        return ""
    i = max(0, min(len(GRADES) - 1, int(r)))
    return GRADES[i] + ("+" if r - int(r) >= 0.5 else "")


def range_overlaps(lo, hi, want_lo, want_hi):
    """Does the climb range lo..hi share any grade with want_lo..want_hi? (all ranks; None = open end)"""
    if lo is None or hi is None:
        return False
    if lo > hi:                                  # stored the wrong way round: still usable
        lo, hi = hi, lo
    if want_lo is not None and hi < want_lo:
        return False
    if want_hi is not None and lo > want_hi:
        return False
    return True
