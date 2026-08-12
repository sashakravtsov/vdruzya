"""Classic Facebook Gifts — stickers catalog + wall posts topic=gift:{recipient}."""
from django.shortcuts import get_object_or_404

from apps.social.friendship import is_blocked
from apps.social.models import Notification, Post, SocialProfile, Sticker
from apps.social.notify import push
from apps.social.services import friend_ids, now

TOPIC_PREFIX = "gift:"


def topic_for(recipient) -> str:
    return f"{TOPIC_PREFIX}{recipient.id}"


def recipient_id_from_topic(topic) -> int | None:
    topic = topic or ""
    if not topic.startswith(TOPIC_PREFIX):
        return None
    try:
        return int(topic.split(":", 1)[1])
    except (TypeError, ValueError):
        return None


def catalog():
    return list(
        Sticker.objects.filter(is_active=True, sticker_pack__is_active=True)
        .select_related("sticker_pack")
        .order_by("sort_order", "id")
    )


def get_sticker(slug_or_id):
    qs = Sticker.objects.filter(is_active=True)
    if str(slug_or_id).isdigit():
        return get_object_or_404(qs, pk=int(slug_or_id))
    return get_object_or_404(qs, slug=slug_or_id)


def gifts_for(profile, limit=24):
    """Gifts received on this profile."""
    if not profile:
        return []
    return list(
        Post.objects.filter(topic=topic_for(profile), kind="gift")
        .select_related("social_user")
        .order_by("-id")[:limit]
    )


def attach_stickers(posts):
    """Attach Sticker objects from post.sticker slug for templates."""
    slugs = {getattr(p, "sticker", None) for p in posts if getattr(p, "sticker", None)}
    by_slug = {
        s.slug: s for s in Sticker.objects.filter(slug__in=slugs)
    } if slugs else {}
    for p in posts:
        p.gift_sticker = by_slug.get(getattr(p, "sticker", None))
    return posts


def can_send(me, other) -> str:
    """ok | self | blocked | not_friend."""
    if not me or not other:
        return "self"
    if me.id == other.id:
        return "self"
    if is_blocked(me, other):
        return "blocked"
    if other.id not in friend_ids(me):
        return "not_friend"
    return "ok"


def send_gift(me, other, sticker, message="") -> Post | None:
    if can_send(me, other) != "ok" or not sticker:
        return None
    t = now()
    body = (message or "").strip()[:500]
    if not body:
        body = (sticker.phrase or sticker.title or "Подарок")[:255]
    post = Post.objects.create(
        social_user=me,
        visibility="friends",
        kind="gift",
        body=body,
        topic=topic_for(other),
        sticker=sticker.slug,
        created_at=t,
        updated_at=t,
    )
    push(
        other.id,
        title="Подарок",
        body=f"{me.name} отправил(а) вам подарок «{sticker.title}»"[:255],
        type="gift",
        url=f"/profile/{other.id}?tab=wall",
    )
    return post


def friends_for_send(me, limit=40):
    if not me:
        return []
    return list(
        SocialProfile.objects.filter(id__in=friend_ids(me)).order_by("name")[:limit]
    )


def mark_gift_notices_seen(me):
    if me:
        Notification.objects.filter(social_user=me, type="gift", seen=False).update(seen=True)
