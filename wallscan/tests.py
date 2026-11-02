"""End-to-end tests for scanned walls, multiple routes per wall, recommendations and admin tools.

Run:  python manage.py test wallscan preferences community
"""
import json
import shutil
import tempfile
import uuid
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from climbing.models import ClimberProfile, Crag, Route
from preferences.models import ClimberPreference

from .models import APPROVED, PENDING, RouteReview, RouteWallLink, WallSubmission


class IsolatedEngine:
    """Point the route engine at a temporary folder so tests never touch real scanned walls."""

    def setUp(self):
        super().setUp()
        self._tmp = tempfile.mkdtemp()
        self._settings = override_settings(GOCLIMB_AR_DATA=Path(self._tmp) / "data",
                                           GOCLIMB_AR_UNITY_EXPORT=Path(self._tmp) / "unity")
        self._settings.enable()
        import wallscan.engine as engine
        self._saved_engine, engine._engine = engine._engine, None

    def tearDown(self):
        import wallscan.engine as engine
        engine._engine = self._saved_engine
        self._settings.disable()
        shutil.rmtree(self._tmp, ignore_errors=True)
        super().tearDown()


def make_doc(wall_id, route_ids):
    holds = [{"id": f"H{i}", "x": round(0.08 * i, 3), "y": round(1 - 0.08 * i, 3)} for i in range(1, 11)]
    routes = [{"id": rid, "hold_ids": [f"H{(n % 8) + 1}", f"H{(n % 8) + 2}", f"H{(n % 8) + 3}"],
               "color": "#22C55E", "difficulty": "medium", "points": [], "steps": []}
              for n, rid in enumerate(route_ids)]
    return {"schema": 4, "wall_id": wall_id, "name": "Test wall", "holds": holds, "routes": routes}


def make_wall(routes, status=APPROVED, crag=None, uploader=None, mode="indoor"):
    """routes: list of (route_id, review_status, grade, style, hold_types)"""
    wid = str(uuid.uuid4())
    sub = WallSubmission.objects.create(wall_id=wid, name="Cave", venue="Gym", mode=mode, status=status, crag=crag,
                                        uploaded_by=uploader, doc=make_doc(wid, [r[0] for r in routes]),
                                        photo=b"\xff\xd8\xff\xe0fake", photo_type="image/jpeg")
    for rid, st, grade, style, holds in routes:
        RouteReview.objects.create(wall=sub, route_id=rid, status=st, grade=grade, style=style, hold_types=holds,
                                   name=f"Route {rid}")
    return sub


def climber(username, max_grade="", experience="", styles=(), holds=(), environment="indoor", staff=False):
    u = User.objects.create_user(username, password="pw-12345678", is_staff=staff)
    ClimberProfile.objects.create(user=u, experience_level=experience)
    ClimberPreference.objects.create(user=u, region="sg-east", environment=environment, max_grade=max_grade,
                                     styles=list(styles), hold_types=list(holds))
    return u


# ---------------------------------------------------------------------------------------------------------
class MultipleRoutesTests(IsolatedEngine, TestCase):
    """Issue 5: one wall = many independent routes; API returns all approved; picks are personal."""

    def setUp(self):
        super().setUp()
        self.wall = make_wall([
            ("R1", APPROVED, "4A", "toprope", ["jugs"]),
            ("R2", APPROVED, "6B", "boulder", ["crimps", "edges"]),
            ("R3", APPROVED, "5B", "boulder", ["slopers"]),
            ("R4", APPROVED, "7B", "sport", ["pinches"]),
            ("R5", PENDING, "5A", "boulder", ["jugs"]),          # not approved: must never reach climbers
            ("R6", APPROVED, "", "boulder", []),                 # no grade: listed, never recommended
        ])
        self.beginner = climber("beginner", max_grade="5B", styles=["bouldering"], holds=["slopers", "jugs"])
        self.strong = climber("strong", max_grade="6C", styles=["bouldering"], holds=["crimps"])
        self.sporty = climber("sporty", experience="master", styles=["sport"], holds=["pinches"], environment="both")

    def routes_for(self, user):
        self.client.force_login(user)
        r = self.client.get(f"/ar/walls/{self.wall.wall_id}/routes/")
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()

    def test_api_returns_every_approved_route_and_hides_pending(self):
        data = self.routes_for(self.beginner)
        ids = {r["id"] for r in data["routes"]}
        self.assertEqual(ids, {"R1", "R2", "R3", "R4", "R6"})
        self.assertNotIn("R5", ids)
        self.assertEqual(data["pending"], [])                    # normal climbers don't see pending routes
        for r in data["routes"]:                                 # each route keeps its own data
            self.assertEqual(len(r["hold_ids"]), 3)
            self.assertIn("grade", r)

    def test_recommendations_follow_each_climbers_preferences(self):
        b, s, m = self.routes_for(self.beginner), self.routes_for(self.strong), self.routes_for(self.sporty)
        self.assertEqual(b["recommended"], ["R3", "R1"])
        self.assertEqual(s["recommended"][0], "R2")
        self.assertEqual(m["recommended"][0], "R4")
        self.assertNotEqual(b["recommended"], ["R1", "R2"])      # not database order
        self.assertNotIn("R6", b["recommended"] + s["recommended"] + m["recommended"])
        best = next(r for r in b["routes"] if r["id"] == "R3")
        self.assertEqual(best["rec_rank"], 1)
        self.assertTrue(best["reasons"])                         # explains why

    def test_too_hard_routes_are_not_recommended_to_beginners(self):
        b = self.routes_for(self.beginner)
        hard = {r["id"]: r for r in b["routes"]}
        self.assertFalse({"R2", "R4"} & set(b["recommended"]))
        self.assertIn("above your level", hard["R4"]["unsuitable_reason"])

    def test_nothing_suitable_gives_a_clear_message(self):
        wall = make_wall([("R1", APPROVED, "8A", "sport", [])])
        self.client.force_login(self.beginner)
        data = self.client.get(f"/ar/walls/{wall.wall_id}/routes/").json()
        self.assertEqual(data["recommended"], [])
        self.assertIn("None of the approved routes suit", data["message"])

    def test_unity_document_has_names_grades_and_picks_best_first(self):
        self.client.force_login(self.strong)
        doc = self.client.get(f"/ar/api/walls/{self.wall.wall_id}/unity").json()
        ids = [r["id"] for r in doc["routes"]]
        self.assertNotIn("R5", ids)
        self.assertEqual(ids[0], "R2")                           # best match first
        first = doc["routes"][0]
        self.assertEqual((first["grade"], first["rec_rank"], first["name"]), ("6B", 1, "Route R2"))
        self.assertTrue(first["rec_reason"])
        self.assertIn("recommendation", doc)

    def test_uploader_sees_pending_routes_separately(self):
        owner = climber("owner", max_grade="6A")
        wall = make_wall([("R1", APPROVED, "5A", "boulder", []), ("R2", PENDING, "5B", "boulder", [])],
                         status=PENDING, uploader=owner)
        self.client.force_login(owner)
        data = self.client.get(f"/ar/walls/{wall.wall_id}/routes/").json()
        self.assertEqual(data["recommended"], [])                # wall itself not approved yet
        self.assertIn("waiting for admin review", data["message"])
        self.assertEqual({r["id"] for r in data["pending"]}, {"R1", "R2"})

    def test_strangers_cannot_open_a_pending_wall(self):
        wall = make_wall([("R1", APPROVED, "5A", "boulder", [])], status=PENDING, uploader=self.strong)
        self.client.force_login(self.beginner)
        self.assertEqual(self.client.get(f"/ar/walls/{wall.wall_id}/routes/").status_code, 404)

    def test_wall_and_crag_pages_render(self):
        crag = Crag.objects.create(name="Gym East", difficulty_min="4A", difficulty_max="7B")
        self.wall.crag = crag
        self.wall.save()
        self.client.force_login(self.beginner)
        self.assertContains(self.client.get(f"/ar/wall/{self.wall.wall_id}/"), "Routes on this wall")
        page = self.client.get(f"/ar/crag/{crag.slug}/")
        self.assertContains(page, "Best match")
        self.assertContains(page, "Route R3")


# ---------------------------------------------------------------------------------------------------------
class AdminRouteInfoTests(IsolatedEngine, TestCase):
    def setUp(self):
        super().setUp()
        self.admin = climber("admin", staff=True)
        self.user = climber("user")
        self.wall = make_wall([("R1", PENDING, "", "", []), ("R2", PENDING, "", "", [])], status=PENDING)

    def post(self, url, body):
        return self.client.post(url, json.dumps(body), content_type="application/json")

    def test_admin_sets_each_routes_own_grade_and_approves_several(self):
        self.client.force_login(self.admin)
        for rid, grade in (("R1", "5a"), ("R2", "6C")):
            r = self.post(f"/ar/review/{self.wall.wall_id}/routes/{rid}/info/",
                          {"name": f"Line {rid}", "grade": grade, "style": "boulder", "hold_types": ["crimps", "bogus"]})
            self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self.post(f"/ar/review/{self.wall.wall_id}/decision/",
                                   {"status": "approved", "approve_pending_routes": True}).status_code, 200)
        rows = {rv.route_id: rv for rv in RouteReview.objects.filter(wall=self.wall)}
        self.assertEqual((rows["R1"].grade, rows["R2"].grade), ("5A", "6C"))     # "5a" normalised
        self.assertEqual(rows["R1"].hold_types, ["crimps"])                      # unknown hold type dropped
        self.assertTrue(all(rv.status == APPROVED for rv in rows.values()))
        self.client.force_login(self.user)
        data = self.client.get(f"/ar/walls/{self.wall.wall_id}/routes/").json()
        self.assertEqual({r["id"] for r in data["routes"]}, {"R1", "R2"})

    def test_bad_grade_and_non_admin_are_rejected(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.post(f"/ar/review/{self.wall.wall_id}/routes/R1/info/", {"grade": "V5"}).status_code, 400)
        self.client.force_login(self.user)
        self.assertEqual(self.post(f"/ar/review/{self.wall.wall_id}/routes/R1/info/", {"grade": "5A"}).status_code, 403)

    def test_linking_a_crag_route_fills_in_its_info(self):
        crag = Crag.objects.create(name="Linked Crag")
        route = Route.objects.create(crag=crag, name="Plus One", grade="4A", route_type="boulder")
        self.wall.crag = crag
        self.wall.save()
        RouteReview.objects.filter(wall=self.wall, route_id="R2").update(name="", grade="", style="")   # no info yet
        RouteReview.objects.filter(wall=self.wall, route_id="R1").update(name="Admin Name", grade="6A")  # admin already set
        self.client.force_login(self.admin)
        r = self.post(f"/ar/review/{self.wall.wall_id}/routes/R2/link/", {"route_pk": route.pk})
        self.assertEqual(r.status_code, 200, r.content)
        rv = RouteReview.objects.get(wall=self.wall, route_id="R2")
        self.assertEqual((rv.name, rv.grade, rv.style), ("Plus One", "4A", "boulder"))       # empty fields filled in
        self.assertTrue(RouteWallLink.objects.filter(route=route, wall=self.wall, wall_route_id="R2").exists())
        # linking never overwrites information an admin already entered
        other = Route.objects.create(crag=crag, name="Other", grade="4B", route_type="sport")
        self.assertEqual(self.post(f"/ar/review/{self.wall.wall_id}/routes/R1/link/", {"route_pk": other.pk}).status_code, 200)
        rv1 = RouteReview.objects.get(wall=self.wall, route_id="R1")
        self.assertEqual((rv1.name, rv1.grade, rv1.style), ("Admin Name", "6A", "sport"))


# ---------------------------------------------------------------------------------------------------------
class AdminLocationTests(IsolatedEngine, TestCase):
    """Issue 1: admins create and edit crags with grades, and manage the crag's routes."""

    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user("admin", password="pw-12345678", is_staff=True)
        self.client.force_login(self.admin)

    def form(self, **kw):
        data = {"action": "save", "name": "New Crag", "slug": "", "description": "", "lat": "1.350000", "lng": "103.900000",
                "rock_type": "granite", "difficulty_min": "5A", "difficulty_max": "7A", "length_m": "20", "hazards": "", "image": ""}
        data.update(kw)
        return data

    def test_create_crag_with_grades(self):
        r = self.client.post("/ar/review/locations/new/", self.form())
        crag = Crag.objects.get(name="New Crag")
        self.assertRedirects(r, f"/ar/review/locations/{crag.pk}/?msg=Saved", fetch_redirect_response=False)
        self.assertEqual((crag.difficulty_min, crag.difficulty_max), ("5A", "7A"))
        self.assertContains(self.client.get(f"/ar/review/locations/{crag.pk}/"), "Routes at New Crag")

    def test_inverted_grade_range_is_rejected(self):
        r = self.client.post("/ar/review/locations/new/", self.form(difficulty_min="7A", difficulty_max="5A"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "hardest grade can")
        self.assertFalse(Crag.objects.filter(name="New Crag").exists())

    def test_edit_grades_and_manage_routes(self):
        crag = Crag.objects.create(name="Edit Me", difficulty_min="4A", difficulty_max="6B")
        self.client.post(f"/ar/review/locations/{crag.pk}/", self.form(name="Edit Me", difficulty_min="5B", difficulty_max="6C"))
        crag.refresh_from_db()
        self.assertEqual((crag.difficulty_min, crag.difficulty_max), ("5B", "6C"))
        url = f"/ar/review/locations/{crag.pk}/"
        for name, grade in (("Easy One", "4B"), ("Hard One", "7B")):
            self.client.post(url, {"action": "add_route", "name": name, "grade": grade, "route_type": "sport", "length_m": "12"})
        self.assertEqual(crag.routes.count(), 2)
        self.client.post(url, {"action": "range_from_routes"})
        crag.refresh_from_db()
        self.assertEqual((crag.difficulty_min, crag.difficulty_max), ("4B", "7B"))
        hard = crag.routes.get(name="Hard One")
        self.client.post(url, {"action": "update_route", "route_id": hard.pk, "name": "Hard One", "grade": "7C",
                               "route_type": "boulder", "length_m": "5"})
        hard.refresh_from_db()
        self.assertEqual((hard.grade, hard.route_type), ("7C", "boulder"))
        self.client.post(url, {"action": "delete_route", "route_id": hard.pk})
        self.assertEqual(crag.routes.count(), 1)

    def test_team_manage_page_also_rejects_inverted_range(self):
        """Needs apply_fixes.py (step 3). Uses the team's own /manage/ page."""
        r = self.client.post("/manage/crags/new/", {k: v for k, v in self.form(difficulty_min="7A", difficulty_max="5A").items() if k != "action"})
        self.assertFalse(Crag.objects.filter(name="New Crag").exists(),
                         "Run 'python apply_fixes.py': the team's crag form still accepts an inverted grade range.")
        r = self.client.post("/manage/crags/new/", {k: v for k, v in self.form().items() if k != "action"})
        self.assertEqual(Crag.objects.get(name="New Crag").difficulty_max, "7A")

    def test_non_admin_cannot_manage_locations(self):
        self.client.force_login(User.objects.create_user("normal", password="pw-12345678"))
        self.assertEqual(self.client.get("/ar/review/locations/").status_code, 403)
        self.client.post("/ar/review/locations/new/", self.form())
        self.assertFalse(Crag.objects.filter(name="New Crag").exists())
