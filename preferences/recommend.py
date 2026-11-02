"""Route and crag recommendations from a climber's saved preferences.

Pure Python (plain dicts in, plain dicts out) so the ranking can be unit-tested without a database.
Both recommenders use the SAME profile and ability rules, so route and crag picks stay consistent.

profile = {
    "max_grade": "6B" or "",             # hardest grade the climber says they climb
    "experience": "beginner" | "experienced" | "master" | "",
    "styles": ["sport", "bouldering", ...],
    "hold_types": ["crimps", ...],
    "environment": "indoor" | "outdoor" | "both" | "",
    "region": "sg-east" | ... | "",
}
"""
import math

from .grades import label, rank

# Experience level (team's ClimberProfile) -> hardest grade, used when no max grade is set
EXPERIENCE_TOP = {"beginner": rank("5B"), "experienced": rank("6C"), "master": rank("8A")}

# Preference style keys -> the team's Route.route_type values
STYLE_TO_ROUTE_TYPE = {"bouldering": "boulder", "sport": "sport", "top-rope": "toprope", "trad": "trad"}
STYLE_LABEL = {"boulder": "Bouldering", "sport": "Sport", "toprope": "Top rope", "trad": "Trad"}

# Approximate centre of each preference region (for "near you" scoring only)
REGION_POINT = {
    "sg-central": (1.29, 103.85), "sg-north": (1.43, 103.79), "sg-northeast": (1.37, 103.89),
    "sg-east": (1.35, 103.94), "sg-west": (1.35, 103.70), "malaysia": (3.14, 101.69),
    "thailand": (13.75, 100.50), "indonesia": (-6.20, 106.82),
}

TOO_HARD_ABOVE = 1        # grades above the climber's max that we still suggest (a challenge)
TOO_EASY_BELOW = 6        # grades below their max that we still suggest


def ability(profile):
    """(hardest grade rank, explanation) or (None, None) when the climber hasn't told us."""
    top = rank(profile.get("max_grade"))
    if top is not None:
        return top, f"your max grade {label(top)}"
    top = EXPERIENCE_TOP.get(profile.get("experience") or "")
    if top is not None:
        return top, f"{profile['experience']} level (about {label(top)})"
    return None, None


def _route_types(profile):
    return {STYLE_TO_ROUTE_TYPE[s] for s in profile.get("styles") or [] if s in STYLE_TO_ROUTE_TYPE}


def _km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


# ====================================================================== routes

def score_route(route, profile, top):
    """-> (score 0..100, reasons[], excluded_reason or None). Uses only data the route really has."""
    g = rank(route.get("grade"))
    if g is None:
        return 0, [], "no grade set yet"
    reasons, score = [], 0.0
    if top is not None:
        if g > top + TOO_HARD_ABOVE:
            return 0, [], f"{label(g)} is above your level (max {label(top)})"
        if g < top - TOO_EASY_BELOW:
            return 0, [], f"{label(g)} is far below your level"
        ideal = max(0, top - 1)
        score += 50 * max(0.0, 1 - abs(g - ideal) / 4)
        if g > top:
            reasons.append(f"{label(g)}: a step above your max {label(top)}, a good challenge")
        elif g >= ideal:
            reasons.append(f"{label(g)}: right at your level")
        else:
            reasons.append(f"{label(g)}: {int(round(ideal - g))} grade(s) below your level, good for practice")
    types = _route_types(profile)
    style = route.get("style") or ""
    if style and types and style in types:
        score += 20
        reasons.append(f"{STYLE_LABEL.get(style, style)}, a style you like")
    liked = set(profile.get("hold_types") or [])
    holds = set(route.get("hold_types") or [])
    if holds and liked:
        common = holds & liked
        if common:
            score += 20 * len(common) / len(holds)
            reasons.append("has " + ", ".join(sorted(common)) + " you enjoy")
    env, mode = profile.get("environment") or "", route.get("mode") or ""
    if env and mode and (env == "both" or env == mode):
        score += 10
        reasons.append(f"{mode} wall, as you prefer")
    return round(score, 1), reasons, None


def recommend_routes(routes, profile):
    """Rank APPROVED routes for this climber; pick the best and second-best match.

    Returns {"routes": [...all approved, best first, each with score/reasons/rec_rank],
             "recommended": [id1, id2], "message": str}
    """
    top, why = ability(profile)
    ideal = None if top is None else max(0, top - 1)
    scored, unsuitable = [], []
    for r in routes:
        if not r.get("approved"):
            continue                                       # never show pending/rejected routes
        score, reasons, excluded = score_route(r, profile, top)
        item = dict(r, score=score, reasons=reasons, rec_rank=0, unsuitable_reason=excluded or "")
        (unsuitable if excluded else scored).append(item)

    def key(it):
        g = rank(it.get("grade"))
        dist = abs(g - ideal) if (g is not None and ideal is not None) else 99
        return (-it["score"], dist, (it.get("name") or "").lower(), it.get("id") or "")

    scored.sort(key=key)
    for i, it in enumerate(scored[:2]):
        it["rec_rank"] = i + 1
    if not routes or not (scored or unsuitable):
        msg = "There are no approved routes on this wall yet."
    elif not scored:
        msg = "None of the approved routes suit your level yet. You can still pick one below."
    elif top is None:
        msg = "Set your level in Preferences to get routes matched to your ability."
    elif len(scored) == 1:
        msg = f"One route suits you ({why})."
    else:
        msg = f"Best matches for you ({why})."
    unsuitable.sort(key=lambda it: (rank(it.get("grade")) is None, rank(it.get("grade")) or 0, it.get("id") or ""))
    return {"routes": scored + unsuitable, "recommended": [it["id"] for it in scored[:2]], "message": msg}


# ====================================================================== crags

def score_crag(crag, profile, top):
    """crag = {name, lat, lng, rock_type, difficulty_min, difficulty_max, route_grades[], route_types[], ar_walls}"""
    reasons, score = [], 0.0
    grades = [g for g in (rank(x) for x in crag.get("route_grades") or []) if g is not None]
    if top is not None:
        lo, hi = top - 4, top + TOO_HARD_ABOVE
        if grades:
            fit = [g for g in grades if lo <= g <= hi]
            if not fit:
                return 0, [], f"no routes at your level ({label(lo)}–{label(hi)})"
            score += 45 * len(fit) / len(grades)
            reasons.append(f"{len(fit)} of {len(grades)} routes in your range ({label(max(0, lo))}–{label(hi)})")
        else:
            cmin, cmax = rank(crag.get("difficulty_min")), rank(crag.get("difficulty_max"))
            if cmin is None or cmax is None:
                return 0, [], "no grade information"
            if cmin > cmax:
                cmin, cmax = cmax, cmin
            if cmax < lo or cmin > hi:
                return 0, [], f"grades {label(cmin)}–{label(cmax)} don't match your level"
            score += 30
            reasons.append(f"grades {label(cmin)}–{label(cmax)} include your level")
    types = _route_types(profile)
    crag_types = set(crag.get("route_types") or [])
    if crag.get("rock_type") == "boulder":
        crag_types.add("boulder")
    common = types & crag_types
    if common:
        score += 20
        reasons.append("has " + ", ".join(sorted(STYLE_LABEL.get(t, t) for t in common)) + " routes")
    env = profile.get("environment") or ""
    kind = "indoor" if crag.get("rock_type") == "indoor" else "outdoor"
    if env and (env == "both" or env == kind):
        score += 15
        reasons.append(f"{kind}, as you prefer")
    point = REGION_POINT.get(profile.get("region") or "")
    if point and crag.get("lat") is not None and crag.get("lng") is not None:
        d = _km(point, (float(crag["lat"]), float(crag["lng"])))
        if d <= 15:
            score += 15
            reasons.append(f"about {d:.0f} km from your region")
        elif d <= 60:
            score += 7
            reasons.append(f"about {d:.0f} km away")
    if crag.get("ar_walls"):
        score += 5
        reasons.append("routes viewable in AR")
    return round(score, 1), reasons, None


def recommend_crags(crags, profile, limit=6):
    top, why = ability(profile)
    ranked, skipped = [], []
    for c in crags:
        score, reasons, excluded = score_crag(c, profile, top)
        (skipped if excluded else ranked).append(dict(c, score=score, reasons=reasons, unsuitable_reason=excluded or ""))
    ranked.sort(key=lambda c: (-c["score"], (c.get("name") or "").lower()))
    if not ranked:
        msg = "No crags match your level and preferences yet."
    elif top is None:
        msg = "Set your level in Preferences for better matches."
    else:
        msg = f"Matched to {why} and your preferences."
    return {"crags": ranked[:limit], "message": msg, "skipped": len(skipped)}
