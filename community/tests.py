"""Run:  python manage.py test wallscan preferences community"""
import json
import shutil
import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from climbing.models import Crag, ForumPost, Route

from .models import PENDING, PostDetails, PostPhoto, PostPlace

JPEG = b"\xff\xd8\xff\xe0" + b"\x00\x10JFIF" + bytes(range(256)) * 4 + b"\xff\xd9"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


class IsolatedEngine:
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


class PhotoAndGradePostTests(TestCase):
    """Issue 2: post with photos + grade; saved in the database and shown later."""

    def setUp(self):
        self.user = User.objects.create_user("climber", password="pw-12345678")
        self.crag = Crag.objects.create(name="Dairy Farm Quarry", lat=1.36, lng=103.77)
        self.route = Route.objects.create(crag=self.crag, name="Plus One", grade="4A", route_type="boulder")
        self.client.force_login(self.user)

    def post(self, data, photos=()):
        payload = {"data": json.dumps(data)}
        if photos:
            payload["photos"] = list(photos)
        return self.client.post("/api/community/posts/", payload)          # multipart, like the browser

    def test_photo_and_grade_are_saved_and_shown_later(self):
        r = self.post({"title": "Sunday session", "content": "Great day", "grade": "6a",
                       "place": {"kind": "crag", "crag_id": self.crag.pk}},
                      [SimpleUploadedFile("wall.jpg", JPEG, "image/jpeg"), SimpleUploadedFile("me.png", PNG, "image/png")])
        self.assertEqual(r.status_code, 200, r.content)
        post = ForumPost.objects.get(title="Sunday session")
        self.assertEqual(post.photos.count(), 2)
        self.assertEqual(PostDetails.objects.get(post=post).grade, "6A")              # "6a" normalised
        # later, from the feed (a fresh request, not the form preview)
        item = next(p for p in self.client.get("/api/community/feed/").json()["results"] if p["id"] == post.pk)
        self.assertEqual(item["grade"], "6A")
        self.assertEqual(len(item["photos"]), 2)
        img = self.client.get(item["photos"][0])
        self.assertEqual(img.status_code, 200)
        self.assertEqual(img["Content-Type"], "image/jpeg")
        self.assertEqual(b"".join(img.streaming_content) if img.streaming else img.content, JPEG)
        self.assertEqual(self.client.get(item["photos"][1])["Content-Type"], "image/png")

    def test_route_sets_grade_and_must_belong_to_tagged_crag(self):
        r = self.post({"title": "Sent it", "content": "x", "route_id": self.route.pk,
                       "place": {"kind": "crag", "crag_id": self.crag.pk}})
        self.assertEqual(r.status_code, 200, r.content)
        d = PostDetails.objects.get(post__title="Sent it")
        self.assertEqual((d.grade, d.route_id), ("4A", self.route.pk))
        other = Crag.objects.create(name="Elsewhere")
        r = self.post({"title": "Wrong", "content": "x", "route_id": self.route.pk, "place": {"kind": "crag", "crag_id": other.pk}})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(ForumPost.objects.filter(title="Wrong").exists())

    def test_fake_image_is_rejected_and_nothing_is_saved(self):
        r = self.post({"title": "Bad", "content": "x"}, [SimpleUploadedFile("virus.jpg", b"MZ not an image", "image/jpeg")])
        self.assertEqual(r.status_code, 400)
        self.assertFalse(ForumPost.objects.filter(title="Bad").exists())
        self.assertEqual(PostPhoto.objects.count(), 0)

    def test_too_many_photos_and_bad_grade(self):
        five = [SimpleUploadedFile(f"{i}.jpg", JPEG, "image/jpeg") for i in range(5)]
        self.assertEqual(self.post({"title": "Many", "content": "x"}, five).status_code, 400)
        self.assertEqual(self.post({"title": "Grade", "content": "x", "grade": "V5"}).status_code, 400)
        self.assertEqual(ForumPost.objects.count(), 0)

    def test_json_post_without_photos_still_works(self):
        r = self.client.post("/api/community/posts/", json.dumps({"title": "Plain", "content": "text only"}),
                             content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content)
        item = self.client.get("/api/community/feed/").json()["results"][0]
        self.assertEqual((item["title"], item["photos"], item["grade"]), ("Plain", [], ""))

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.post({"title": "x", "content": "y"}).status_code, 401)


class PendingPlaceReviewTests(IsolatedEngine, TestCase):
    """Issue 3: a new place from a post shows as pending, appears in the admin Review page, approve works."""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user("climber", password="pw-12345678")
        self.admin = User.objects.create_user("admin", password="pw-12345678", is_staff=True)

    def test_full_review_flow(self):
        self.client.force_login(self.user)
        r = self.client.post("/api/community/posts/", json.dumps({
            "title": "Found a boulder", "content": "Nice rock",
            "place": {"kind": "new", "name": "Secret Boulder Ubin", "lat": 1.4044, "lng": 103.9625}}),
            content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content)
        place = PostPlace.objects.get(name="Secret Boulder Ubin")
        self.assertEqual(place.status, PENDING)
        feed = self.client.get("/api/community/feed/").json()["results"][0]
        self.assertEqual(feed["place"]["status_label"], "Pending admin review")

        self.client.force_login(self.admin)
        review = self.client.get("/ar/review/")                                    # the main Review page
        self.assertContains(review, "Secret Boulder Ubin")
        self.assertContains(review, "New places from community posts")
        r = self.client.post(f"/api/community/places/{place.pk}/decision/", json.dumps({
            "status": "approved", "note": "Real spot", "add_to_map": True,
            "rock_type": "boulder", "difficulty_min": "5A", "difficulty_max": "6C"}), content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content)
        crag = Crag.objects.get(name="Secret Boulder Ubin")
        self.assertEqual((crag.rock_type, crag.difficulty_min, crag.difficulty_max), ("boulder", "5A", "6C"))
        self.assertEqual(r.json()["edit_url"], f"/ar/review/locations/{crag.pk}/")
        place.refresh_from_db()
        self.assertEqual((place.status, place.crag_id), ("approved", crag.pk))

        self.client.force_login(self.user)
        feed = self.client.get("/api/community/feed/").json()["results"][0]
        self.assertEqual((feed["place"]["status_label"], feed["place"]["note"]), ("Approved by admin", "Real spot"))

    def test_inverted_grades_rejected_and_reject_works(self):
        place_post = ForumPost.objects.create(author=self.user, title="t", content="c")
        place = PostPlace.objects.create(post=place_post, kind="new", name="Odd Place", lat=1.3, lng=103.8, status=PENDING)
        self.client.force_login(self.admin)
        r = self.client.post(f"/api/community/places/{place.pk}/decision/", json.dumps({
            "status": "approved", "add_to_map": True, "difficulty_min": "7A", "difficulty_max": "5A"}),
            content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Crag.objects.filter(name="Odd Place").exists())
        r = self.client.post(f"/api/community/places/{place.pk}/decision/", json.dumps({"status": "rejected", "note": "Not a crag"}),
                             content_type="application/json")
        self.assertEqual(r.json()["status"], "rejected")

    def test_non_admin_cannot_decide(self):
        post = ForumPost.objects.create(author=self.user, title="t", content="c")
        place = PostPlace.objects.create(post=post, kind="new", name="P", status=PENDING)
        self.client.force_login(self.user)
        r = self.client.post(f"/api/community/places/{place.pk}/decision/", json.dumps({"status": "approved"}),
                             content_type="application/json")
        self.assertEqual(r.status_code, 403)


class OldForumLinkTests(TestCase):
    """"Discuss this Crag" (old /forum/ links) must open the new Community page, filtered to that crag."""

    def setUp(self):
        self.user = User.objects.create_user("climber", password="pw-12345678")
        self.crag = Crag.objects.create(name="Boulder+ (The Chevrons)", slug="boulder-the-chevrons")
        other = Crag.objects.create(name="Dairy Farm Quarry")
        ForumPost.objects.create(author=self.user, title="About chevrons", content="x", crag=self.crag)
        ForumPost.objects.create(author=self.user, title="About dairy", content="y", crag=other)

    def test_old_forum_url_redirects_to_new_page(self):
        r = self.client.get("/forum/?crag=boulder-the-chevrons")
        self.assertRedirects(r, "/community/?crag=boulder-the-chevrons", fetch_redirect_response=False)
        self.assertRedirects(self.client.get("/forum/"), "/community/", fetch_redirect_response=False)

    def test_new_page_shows_the_crag_and_feed_is_filtered(self):
        self.client.force_login(self.user)
        page = self.client.get("/community/?crag=boulder-the-chevrons")
        self.assertContains(page, "Discussing")
        self.assertContains(page, "Boulder+ (The Chevrons)")
        titles = [p["title"] for p in self.client.get("/api/community/feed/?crag=boulder-the-chevrons").json()["results"]]
        self.assertEqual(titles, ["About chevrons"])
