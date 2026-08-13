from django.contrib.postgres.search import SearchVector
from django.core.management.base import BaseCommand

from apps.social.models import Post


class Command(BaseCommand):
    help = "Rebuild Postgres FTS vectors for posts"

    def handle(self, *args, **options):
        n = Post.objects.update(search_vector=SearchVector("body", config="simple"))
        self.stdout.write(self.style.SUCCESS(f"posts={n}"))
