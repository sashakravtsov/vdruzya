from django.core.management.base import BaseCommand

from apps.social.chess.service import ensure_week_championship


class Command(BaseCommand):
    help = "Create or refresh the current weekly chess championship row."

    def handle(self, *args, **options):
        week = ensure_week_championship()
        self.stdout.write(
            self.style.SUCCESS(
                f"Week championship ready: {week.title} "
                f"({week.starts_on} — {week.ends_on})"
            )
        )
