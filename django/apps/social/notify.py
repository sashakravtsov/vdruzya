"""Thin notification helpers — classic FB inbox events (poke / DM / invites)."""
from apps.social.models import Notification
from apps.social.services import now

TYPE_LABELS = {
    "poke": "Подмигивание",
    "gift": "Подарок",
    "message": "Сообщение",
    "event_invite": "Событие",
    "group_invite": "Группа",
    "photo_tag": "Отметка",
    "family": "Семья",
    "relationship": "Отношения",
    "follow": "Подписка",
    "safety": "Безопасность",
}


def push(user_id, *, title, body, type, url):
    if not user_id:
        return
    Notification.objects.create(
        social_user_id=user_id,
        title=title[:255],
        body=(body or "")[:255],
        seen=False,
        type=type,
        url=(url or "")[:255],
        created_at=now(),
    )


def type_label(n) -> str:
    return TYPE_LABELS.get(getattr(n, "type", None) or "", getattr(n, "title", None) or "Уведомление")


def unread_count(me) -> int:
    if not me:
        return 0
    return Notification.objects.filter(social_user=me, seen=False).count()


def for_user(me, *, type=None, limit=50):
    if not me:
        return []
    qs = Notification.objects.filter(social_user=me)
    if type:
        qs = qs.filter(type=type)
    return list(qs.order_by("-id")[:limit])


def mark_seen(me, *, type=None):
    if not me:
        return
    qs = Notification.objects.filter(social_user=me, seen=False)
    if type:
        qs = qs.filter(type=type)
    qs.update(seen=True)
    from django.core.cache import cache
    cache.delete(f"nav:{me.id}")


def attach_actors(rows):
    """Parse /profile/<id> URLs once; attach actor profile when present."""
    ids = []
    for n in rows:
        n.actor_id = None
        n.actor = None
        url = (n.url or "").rstrip("/")
        if "/profile/" not in url:
            continue
        try:
            n.actor_id = int(url.rsplit("/", 1)[-1])
            ids.append(n.actor_id)
        except (TypeError, ValueError):
            n.actor_id = None
    if ids:
        from apps.social.models import SocialProfile
        by_id = SocialProfile.objects.in_bulk(ids)
        for n in rows:
            if n.actor_id:
                n.actor = by_id.get(n.actor_id)
    return rows


def attach_poker_ids(rows):
    """Parse /profile/<id> poke URLs once for rail + Pokes inbox; attach poker profile."""
    attach_actors(rows)
    for n in rows:
        n.poker_id = n.actor_id
        n.poker = n.actor
    return rows


def poke(me, other) -> str:
    """Classic poke. Returns ok | blocked | pending | self."""
    from apps.social.friendship import is_blocked

    if not me or not other or me.id == other.id:
        return "self"
    if is_blocked(me, other):
        return "blocked"
    url = f"/profile/{me.id}"
    if Notification.objects.filter(
        social_user=other, type="poke", url=url, seen=False,
    ).exists():
        return "pending"
    push(
        other.id,
        title="Подмигивание",
        body=f"{me.name} подмигнул(а) вам",
        type="poke",
        url=url,
    )
    return "ok"
