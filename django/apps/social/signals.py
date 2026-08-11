from django.contrib.postgres.search import SearchVector
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.social.models import Comment, Friendship, Notification, Post
from apps.social.services import now


def _notify(**kwargs):
    Notification.objects.create(**kwargs)


@receiver(post_save, sender=Friendship)
def friendship_notify(sender, instance, created, **kwargs):
    if not created or instance.status != "pending":
        return
    payload = dict(
        social_user_id=instance.friend_id,
        title="Заявка в друзья",
        body=f"{instance.user.name} хочет добавить вас в друзья"[:255],
        seen=False,
        type="friend_request",
        url=f"/profile/{instance.user_id}",
        created_at=now(),
    )
    transaction.on_commit(lambda p=payload: _notify(**p))


@receiver(post_save, sender=Comment)
def comment_notify(sender, instance, created, **kwargs):
    if not created or instance.post.social_user_id == instance.social_user_id:
        return
    payload = dict(
        social_user_id=instance.post.social_user_id,
        title="Новый комментарий",
        body=f"{instance.social_user.name}: {instance.body}"[:255],
        seen=False,
        type="comment",
        url=f"/posts/{instance.post_id}",
        created_at=now(),
    )
    transaction.on_commit(lambda p=payload: _notify(**p))


@receiver(post_save, sender=Post)
def index_post(sender, instance, created, **kwargs):
    pk = instance.pk

    def _fts():
        Post.objects.filter(pk=pk).update(search_vector=SearchVector("body", config="simple"))

    transaction.on_commit(_fts)

    # Wall note on someone else's wall
    if not created:
        return
    topic = instance.topic or ""
    if not topic.startswith("wall:"):
        return
    try:
        owner_id = int(topic.split(":", 1)[1])
    except (TypeError, ValueError):
        return
    if owner_id == instance.social_user_id:
        return
    payload = dict(
        social_user_id=owner_id,
        title="Запись на стене",
        body=f"{instance.social_user.name} написал(а) на вашей стене"[:255],
        seen=False,
        type="wall",
        url=f"/profile/{owner_id}",
        created_at=now(),
    )
    transaction.on_commit(lambda p=payload: _notify(**p))
