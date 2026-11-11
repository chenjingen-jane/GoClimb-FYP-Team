from django.core.management.base import BaseCommand

from wallscan.records import restore_missing_walls
from wallscan.views import _engine


class Command(BaseCommand):
    help = "Rebuild the route engine's wall files from the database backup (after a wiped disk)."

    def handle(self, *args, **options):
        engine = _engine()                       # restores automatically on first use
        restored, failed = restore_missing_walls(engine)
        total = len(engine.store.search_walls(limit=100000))
        self.stdout.write(self.style.SUCCESS(f"Engine has {total} wall(s). Restored now: {restored}, failed: {failed}."))
