from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Quick Postgres + Redis health probe"

    def handle(self, *args, **options):
        with connection.cursor() as c:
            c.execute("select 1")
            c.fetchone()
        cache.set("health:ping", 1, 10)
        assert cache.get("health:ping") == 1
        self.stdout.write(self.style.SUCCESS("ok"))
