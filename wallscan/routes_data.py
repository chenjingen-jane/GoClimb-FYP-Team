"""All routes of a scanned wall as plain rows (+ personal recommendations), shared by the website,
the web AR camera and the Unity app's /unity document."""
from preferences.profile_data import profile_for
from preferences.recommend import recommend_routes

from . import records
from .models import APPROVED, RouteWallLink


def wall_route_rows(sub, doc):
    reviews = {r.route_id: r for r in sub.route_reviews.all()}
    links = {l.wall_route_id: l.route for l in RouteWallLink.objects.select_related("route").filter(wall=sub)}
    rows = []
    for rt in (doc or {}).get("routes") or []:
        rid = rt.get("id")
        rv, team = reviews.get(rid), links.get(rid)
        rows.append({
            "id": rid,
            "name": (rv.name if rv and rv.name else (team.name if team else "")) or rid,
            "grade": (rv.grade if rv and rv.grade else (team.grade if team else "")),
            "style": (rv.style if rv and rv.style else (team.route_type if team else "")),
            "hold_types": list(rv.hold_types or []) if rv else [],
            "mode": sub.mode,
            "status": rv.status if rv else "pending",
            "approved": sub.status == APPROVED and rv is not None and rv.status == APPROVED,
            "hold_ids": rt.get("hold_ids") or [],
            "color": rt.get("color") or "",
            "estimated": rt.get("difficulty") or "",
            "crag_route_id": team.pk if team else None,
        })
    return rows


def routes_for_user(user, sub, doc):
    """{routes (approved, best first), recommended [id1, id2], message, pending (only for uploader/admin)}"""
    rows = wall_route_rows(sub, doc)
    result = recommend_routes(rows, profile_for(user))
    result["pending"] = [r for r in rows if not r["approved"]] if records.can_manage(user, sub) else []
    if sub.status != APPROVED:
        result["message"] = ("This wall is waiting for admin review; routes can be recommended once it's approved."
                             if sub.status == "pending" else "This wall was not approved.")
    return result


def annotate_doc(user, sub, doc):
    """Add name / grade / recommendation fields to the route document the Unity app reads."""
    if not isinstance(doc, dict) or sub is None:
        return doc
    result = routes_for_user(user, sub, doc)
    info = {r["id"]: r for r in result["routes"] + result["pending"]}
    for rt in doc.get("routes") or []:
        r = info.get(rt.get("id"))
        if not r:
            continue
        rt["name"] = r["name"]
        rt["grade"] = r["grade"]
        rt["style"] = r["style"]
        rt["rec_rank"] = r.get("rec_rank", 0)
        rt["rec_reason"] = "; ".join(r.get("reasons") or [])
    order = {rid: i for i, rid in enumerate(result["recommended"])}
    doc["routes"] = sorted(doc.get("routes") or [], key=lambda rt: order.get(rt.get("id"), 99))   # best first
    doc["recommendation"] = result["message"]
    return doc
