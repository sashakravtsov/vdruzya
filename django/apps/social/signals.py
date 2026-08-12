"""Side effects that still belong in classic FB 2006 — FTS only (no notification center)."""
from django.contrib.postgres.search import SearchVector
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.social.models import Post


@receiver(post_save, sender=Post)
def index_post(sender, instance, created, **kwargs):
    from django.db import transaction
    pk = instance.pk

    def _fts():
        Post.objects.filter(pk=pk).update(search_vector=SearchVector("body", config="simple"))

    transaction.on_commit(_fts)
