"""Builds plain rows from the database for the recommenders (only real, approved data)."""
from collections import defaultdict

from climbing.models import Crag, Route


def crag_rows():
    from wallscan.models import APPROVED, WallSubmission
    routes = defaultdict(lambda: {"grades": [], "types": []})
    for r in Route.objects.values("crag_id", "grade", "route_type"):
        routes[r["crag_id"]]["grades"].append(r["grade"])
        routes[r["crag_id"]]["types"].append(r["route_type"])
    ar = defaultdict(int)
    for cid in WallSubmission.objects.filter(status=APPROVED, crag__isnull=False).values_list("crag_id", flat=True):
        ar[cid] += 1
    rows = []
    for c in Crag.objects.all():
        rows.append({
            "id": c.pk, "name": c.name, "slug": c.slug, "lat": float(c.lat), "lng": float(c.lng),
            "rock_type": c.rock_type, "difficulty_min": c.difficulty_min, "difficulty_max": c.difficulty_max,
            "route_grades": routes[c.pk]["grades"], "route_types": routes[c.pk]["types"],
            "route_count": len(routes[c.pk]["grades"]), "ar_walls": ar[c.pk],
            "image": c.image, "rock_label": c.get_rock_type_display(),
        })
    return rows
