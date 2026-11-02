"""Run:  python manage.py test wallscan preferences community"""
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from climbing.models import ClimberProfile, Crag, Route

from .grades import rank, range_overlaps
from .models import ClimberPreference
from .recommend import recommend_crags


class GradeScaleTests(SimpleTestCase):
    def test_grades_compare_by_position_not_text(self):
        self.assertEqual(rank("5a"), rank("5A"))
        self.assertEqual(rank(" 6B "), rank("6B"))
        self.assertTrue(rank("6B") < rank("6b+") < rank("6C"))
        self.assertIsNone(rank("V5"))
        self.assertTrue(range_overlaps(rank("5a"), rank("8a"), rank("6A"), rank("6A")))
        self.assertTrue(range_overlaps(rank("7A"), rank("5A"), rank("6A"), rank("6A")))     # stored reversed
        self.assertFalse(range_overlaps(rank("4A"), rank("5B"), rank("6A"), rank("7A")))


class PreferencesPageTests(TestCase):
    """Issue 6A: climbers can change their level and preferences after sign-up."""

    def setUp(self):
        self.user = User.objects.create_user("climber", password="pw-12345678")
        ClimberProfile.objects.create(user=self.user, experience_level="beginner")
        self.client.force_login(self.user)

    def test_update_everything_and_it_is_saved(self):
        r = self.client.post("/profile/preferences/", {
            "experience_level": "experienced", "max_grade": "6b", "region": "sg-west", "environment": "outdoor",
            "hold_types": ["crimps", "pinches"], "styles": ["sport"]})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Saved.")
        pref = ClimberPreference.objects.get(user=self.user)
        self.assertEqual((pref.max_grade, pref.region, pref.environment), ("6B", "sg-west", "outdoor"))
        self.assertEqual((pref.hold_types, pref.styles), (["crimps", "pinches"], ["sport"]))
        self.assertEqual(ClimberProfile.objects.get(user=self.user).experience_level, "experienced")
        page = self.client.get("/profile/preferences/")
        self.assertContains(page, '<option value="6B" selected>')

    def test_invalid_choices_are_rejected(self):
        r = self.client.post("/profile/preferences/", {"region": "mars", "environment": "indoor", "styles": ["sport"]})
        self.assertContains(r, "Choose your region")
        self.assertFalse(ClimberPreference.objects.filter(user=self.user, region="mars").exists())


class CragRecommendationTests(TestCase):
    """Issue 6C: crags ranked from real crag + route grades and the climber's saved preferences."""

    def setUp(self):
        gym = Crag.objects.create(name="Boulder Gym East", lat=1.35, lng=103.94, rock_type="indoor",
                                  difficulty_min="4A", difficulty_max="6A")
        for i, g in enumerate(["4A", "5A", "5B", "5C"]):
            Route.objects.create(crag=gym, name=f"Gym {i}", grade=g, route_type="boulder")
        quarry = Crag.objects.create(name="Dairy Farm Quarry", lat=1.363, lng=103.776, rock_type="granite",
                                     difficulty_min="6A", difficulty_max="8A")
        for i, g in enumerate(["6A", "6C", "7A", "7B", "8A"]):
            Route.objects.create(crag=quarry, name=f"Quarry {i}", grade=g, route_type="sport")

    def user(self, name, **pref):
        u = User.objects.create_user(name, password="pw-12345678")
        ClimberProfile.objects.create(user=u)
        ClimberPreference.objects.create(user=u, **pref)
        return u

    def picks(self, user):
        self.client.force_login(user)
        r = self.client.get("/api/recommendations/crags/")
        self.assertEqual(r.status_code, 200)
        return r.json()

    def test_different_climbers_get_different_crags(self):
        beginner = self.user("b", max_grade="5B", region="sg-east", environment="indoor", styles=["bouldering"])
        strong = self.user("s", max_grade="7B", region="sg-west", environment="outdoor", styles=["sport"])
        b, s = self.picks(beginner), self.picks(strong)
        self.assertEqual(b["crags"][0]["name"], "Boulder Gym East")
        self.assertNotIn("Dairy Farm Quarry", [c["name"] for c in b["crags"]])        # too hard for them
        self.assertEqual(s["crags"][0]["name"], "Dairy Farm Quarry")
        self.assertTrue(s["crags"][0]["reasons"])

    def test_for_you_page_and_login_required(self):
        self.assertEqual(self.client.get("/api/recommendations/crags/").status_code, 401)
        u = self.user("x", max_grade="5B", region="sg-east", environment="indoor", styles=["bouldering"])
        self.client.force_login(u)
        page = self.client.get("/for-you/")
        self.assertContains(page, "Boulder Gym East")
        self.assertContains(page, "Edit preferences")

    def test_same_profile_rules_as_routes(self):
        """Crag picks never include a crag whose routes are all outside the climber's level."""
        res = recommend_crags([{"name": "Only hard", "rock_type": "granite", "route_grades": ["8A", "8B"],
                                "lat": 1.3, "lng": 103.8}], {"max_grade": "5A"})
        self.assertEqual(res["crags"], [])


class SearchGradeFilterTests(TestCase):
    """Issue 4. Needs apply_fixes.py (steps 1-2) on the team's search API."""

    def setUp(self):
        Crag.objects.create(name="Wide 5a-8a", difficulty_min="5a", difficulty_max="8a")     # messy lowercase data
        Crag.objects.create(name="Easy 4A-5B", difficulty_min="4A", difficulty_max="5B")
        Crag.objects.create(name="Reversed 7A-5A", difficulty_min="7A", difficulty_max="5A")
        Crag.objects.create(name="Hard 7B-8B", difficulty_min="7B", difficulty_max="8B")

    def names(self, query):
        r = self.client.get("/api/crags/" + query)
        self.assertEqual(r.status_code, 200)
        return {c["name"] for c in r.json()["results"]}

    def test_single_grade(self):
        self.assertEqual(self.names("?difficulty=6A"), {"Wide 5a-8a", "Reversed 7A-5A"},
                         "Run 'python apply_fixes.py' to fix the search API.")
        self.assertEqual(self.names("?difficulty=5A"), {"Wide 5a-8a", "Easy 4A-5B", "Reversed 7A-5A"})

    def test_grade_range(self):
        self.assertEqual(self.names("?grade_min=7C&grade_max=8B"), {"Wide 5a-8a", "Hard 7B-8B"},
                         "Run 'python apply_fixes.py' to add grade ranges to the search API.")
        self.assertEqual(self.names("?grade_max=4C"), {"Easy 4A-5B"})
        self.assertEqual(len(self.names("")), 4)
