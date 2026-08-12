"""Side effects — FTS + hashtag sync (classic FB)."""
from django.contrib.postgres.search import SearchVector
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.social.models import Post


@receiver(post_save, sender=Post)
def index_post(sender, instance, created, **kwargs):
    from django.db import transaction
    pk = instance.pk

    def _after():
        Post.objects.filter(pk=pk).update(search_vector=SearchVector("body", config="simple"))
        try:
            from apps.social import era2013 as e13
            e13.sync_hashtags(Post.objects.filter(pk=pk).first())
        except Exception:
            pass

    transaction.on_commit(_after)
