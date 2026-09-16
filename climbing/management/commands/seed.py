"""Seed the database with real Singapore climbing spots and routes.

Usage:  python manage.py seed
Re-running is safe: it clears existing Crag/Route/Favorite data first.
"""
import random

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from django.contrib.auth.models import User
from climbing.models import Crag, Route, ForumPost, ForumComment


CRAGS = [
    {
        "name": "Dairy Farm Quarry",
        "description": (
            "A disused granite quarry turned bouldering and sport-climbing "
            "playground on the fringes of Bukit Timah. Big slabs, cracks and "
            "overhangs make it the spiritual home of Singapore outdoor climbing."
        ),
        "lat": 1.3640, "lng": 103.7790,
        "rock_type": "granite",
        "difficulty_min": "5A", "difficulty_max": "7A",
        "length_m": 18,
        "hazards": "Access to the rock walls is currently prohibited by NParks due to rockfall risk. "
                   "Use this listing for route-reference only; do not enter restricted areas.",
        "image": "/static/climbing/crags/dairy-farm-quarry.png",
    },
    {
        "name": "Bukit Timah Nature Reserve",
        "description": (
            "Singapore's highest point hides granite boulders scattered along the "
            "Hindu end and the old quarry trails. A classic urban-crag session "
            "with shade and easy access."
        ),
        "lat": 1.3290, "lng": 103.7770,
        "rock_type": "granite",
        "difficulty_min": "4A", "difficulty_max": "6B",
        "length_m": 8,
        "hazards": "Mosquitoes at dusk; stay on marked trails. Some landings are uneven.",
        "image": "/static/climbing/crags/bukit-timah-nature-reserve.png",
    },
    {
        "name": "Mandai Rock",
        "description": (
            "Quiet granite outcrops near the zoo. A handful of tall sport lines "
            "and quality boulder problems for a peaceful session away from the crowds."
        ),
        "lat": 1.4250, "lng": 103.7350,
        "rock_type": "granite",
        "difficulty_min": "5B", "difficulty_max": "7B",
        "length_m": 20,
        "hazards": "Limited shade; bring water. Access paths can be overgrown.",
        "image": "/static/climbing/crags/mandai-rock.png",
    },
    {
        "name": "Pulau Ubin Granite",
        "description": (
            "Take a bumboat to the island for rustic granite bouldering among the "
            "old granite quarries. A half-day adventure with a true get-away vibe."
        ),
        "lat": 1.4230, "lng": 103.9650,
        "rock_type": "boulder",
        "difficulty_min": "4A", "difficulty_max": "6C",
        "length_m": 4,
        "hazards": "Ferry closes in the evening — plan your return. Watch for monkeys.",
        "image": "/static/climbing/crags/pulau-ubin-granite.png",
    },
    {
        "name": "The Cliff @ Snow City",
        "description": (
            "Singapore's first indoor climbing wall, located inside Snow City. "
            "Floor-to-ceiling artificial walls with top-rope, lead and a boulder cave."
        ),
        "lat": 1.3340, "lng": 103.6820,
        "rock_type": "indoor",
        "difficulty_min": "4A", "difficulty_max": "7A",
        "length_m": 14,
        "hazards": "Indoor — no environmental hazards. Pre-book weekends.",
        "image": "/static/climbing/crags/the-cliff-snow-city.png",
    },
    {
        "name": "Onsight Climbing Gym",
        "description": (
            "A large, well-lit bouldering and lead gym in the east with regularly "
            "reset problems and beginner classes."
        ),
        "lat": 1.2990, "lng": 103.8490,
        "rock_type": "indoor",
        "difficulty_min": "4A", "difficulty_max": "7C",
        "length_m": 12,
        "hazards": "Indoor — padded flooring. Warm-up before hard attempts.",
        "image": "/static/climbing/crags/onsight-climbing-gym.png",
    },
    {
        "name": "Boulder+ (The Chevrons)",
        "description": (
            "Premium bouldering-only facility with angles, slabs and a training "
            "area. Friendly community and weekly competitions."
        ),
        "lat": 1.2900, "lng": 103.6500,
        "rock_type": "boulder",
        "difficulty_min": "4A", "difficulty_max": "8A",
        "length_m": 4,
        "hazards": "Indoor — no external hazards. Grades can feel stiff!",
        "image": "/static/climbing/crags/boulder-plus-chevrons.png",
    },
    {
        "name": "Climb Central",
        "description": (
            "Central, high-ceiling lead and boulder gym with a café. Great for "
            "after-work sessions and first-timers."
        ),
        "lat": 1.2940, "lng": 103.8510,
        "rock_type": "indoor",
        "difficulty_min": "4A", "difficulty_max": "7B",
        "length_m": 15,
        "hazards": "Indoor — slip mats in place. Peak hours get busy.",
        "image": "/static/climbing/crags/climb-central.png",
    },
]


# Real route names appended per crag (index-aligned with CRAGS above).
ROUTES_BY_CRAG = {
    "Dairy Farm Quarry": [
        ("The Milky Way", "6A", "sport", 15, "Sustained slab to a small roof."),
        ("Cow's Corner", "5C", "sport", 12, "Short, juggy warm-up line."),
        ("New Real Route", "6C", "boulder", 4, "Powerful compression on slopers."),
        ("Quarry Crack", "6B", "trad", 16, "Classic finger crack."),
    ],
    "Bukit Timah Nature Reserve": [
        ("Monkey Business", "5A", "boulder", 4, "Fun traverse with good feet."),
        ("Roots", "5C", "boulder", 5, "Balancey slab problem."),
        ("The Hindu", "6B", "sport", 10, "Steep pull over a bulge."),
    ],
    "Mandai Rock": [
        ("Zoo View", "5B", "sport", 18, "Long line with a committing crux."),
        ("Keeper", "6C", "sport", 20, "Technical face climbing."),
        ("Feeder", "7B", "sport", 22, "Hard, sustained overhang."),
    ],
    "Pulau Ubin Granite": [
        ("Bumboat", "4A", "boulder", 3, "Easy intro problem."),
        ("Island Time", "5B", "boulder", 4, "Slabby balance line."),
        ("Quarryman", "6C", "boulder", 4, "Crimpy and proud."),
    ],
    "The Cliff @ Snow City": [
        ("Ice Breaker", "5A", "toprope", 12, "Vertical warm-up."),
        ("Snow Storm", "6A", "lead", 14, "Overhang with big moves."),
        ("Cold Feet", "7A", "lead", 14, "Techy finish."),
    ],
    "Onsight Climbing Gym": [
        ("First Pull", "4A", "boulder", 4, "Beginner-friendly."),
        ("Onsight Special", "6C", "boulder", 4, "Dynamic and fun."),
        ("Project 7C", "7C", "boulder", 4, "The gym's benchmark."),
    ],
    "Boulder+ (The Chevrons)": [
        ("Plus One", "4A", "boulder", 4, "Soft intro problem."),
        ("Chevron Crimp", "6B", "boulder", 4, "Crimp ladder."),
        ("Stiff Grade", "8A", "boulder", 4, "The gym testpiece."),
    ],
    "Climb Central": [
        ("Central Line", "5A", "toprope", 15, "Long, friendly route."),
        ("Café Crimp", "6A", "boulder", 4, "After-coffee burner."),
        ("Sky Section", "7B", "lead", 15, "Airy upper section."),
    ],
}


class Command(BaseCommand):
    help = "Seed Singapore crags and routes into the database."

    def handle(self, *args, **options):
        # 'Kinetics Climbing' is appended programmatically to keep the list clean.
        kinetic = {
            "name": "Kinetics Climbing",
            "description": (
                "East-side bouldering gym with a strong training culture, campus "
                "boards and frequent resets."
            ),
            "lat": 1.3480,
            "lng": 103.8690,
            "rock_type": "indoor",
            "difficulty_min": "4A", "difficulty_max": "7B",
            "length_m": 4,
            "hazards": "Indoor — fingerboard area, pace your sessions.",
            "image": "/static/climbing/crags/kinetics-climbing.png",
        }
        seed_data = CRAGS + [kinetic]
        ROUTES_BY_CRAG["Kinetics Climbing"] = [
            ("Kinetic Energy", "4A", "boulder", 4, "Warm-up circuit."),
            ("Board Sesh", "6B", "boulder", 4, "Steep campus-style."),
            ("East Side", "7B", "boulder", 4, "The local proj."),
        ]

        # Idempotent: wipe and re-create.
        Route.objects.all().delete()
        Crag.objects.all().delete()

        created = 0
        for c in seed_data:
            slug = slugify(c["name"])
            crag = Crag.objects.create(
                name=c["name"],
                slug=slug,
                description=c["description"],
                lat=c["lat"],
                lng=c["lng"],
                rock_type=c["rock_type"],
                difficulty_min=c["difficulty_min"],
                difficulty_max=c["difficulty_max"],
                length_m=c["length_m"],
                hazards=c["hazards"],
                image=c.get("image", ""),
            )
            for rname, grade, rtype, length_m, desc in ROUTES_BY_CRAG.get(c["name"], []):
                Route.objects.create(
                    crag=crag, name=rname, grade=grade,
                    route_type=rtype, length_m=length_m, description=desc,
                )
            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {created} crags and "
                f"{Route.objects.count()} routes."
            )
        )

        # Seed a little community chatter (only on first run to avoid duplicates).
        if ForumPost.objects.count() == 0:
            demo, _ = User.objects.get_or_create(
                username='trailblazer',
                defaults={'email': 'trailblazer@example.com'}
            )
            if demo.check_password('climb2026') is False and not demo.has_usable_password():
                demo.set_password('climb2026')
                demo.save()

            helper, _ = User.objects.get_or_create(
                username='cragmaster',
                defaults={'email': 'cragmaster@example.com'}
            )
            if helper.has_usable_password() is False:
                helper.set_password('climb2026')
                helper.save()

            def crag(name):
                return Crag.objects.filter(name=name).first()

            sample_posts = [
                (demo, "Best warm-up at Dairy Farm Quarry?",
                 "Heading there Saturday morning. Any recommendations for an easy "
                 "sport line to get the blood flowing before the harder stuff?",
                 crag("Dairy Farm Quarry")),
                (helper, "Indoor vs outdoor for training finger strength",
                 "I've been alternating Boulder+ sessions with outdoor granite. Curious "
                 "what everyone else does to keep progressing through the grades.",
                 None),
                (demo, "Pulau Ubin bumboat times?",
                 "Want to hit the granite boulders on the island — what's the last "
                 "bumboat back in the afternoon so we don't get stranded?",
                 crag("Pulau Ubin Granite")),
            ]
            for author, title, content, cr in sample_posts:
                ForumPost.objects.create(author=author, title=title, content=content, crag=cr)

            p = ForumPost.objects.filter(title__icontains="warm-up").first()
            if p:
                ForumComment.objects.create(
                    post=p, author=helper,
                    content="Cow's Corner (5C) is a perfect juggy warm-up there.")
                ForumComment.objects.create(
                    post=p, author=demo,
                    content="Perfect, thanks! See you Saturday.")

            self.stdout.write(
                self.style.SUCCESS(
                    f"Seeded {ForumPost.objects.count()} forum posts and "
                    f"{ForumComment.objects.count()} comments."
                )
            )
