"""Thin notification helpers — classic FB inbox events (poke / DM / invites)."""
from apps.social.models import Notification
from apps.social.services import now


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


def attach_poker_ids(rows):
    """Parse /profile/<id> poke URLs once for rail + Pokes inbox."""
    for n in rows:
        try:
            n.poker_id = int((n.url or "").rstrip("/").rsplit("/", 1)[-1])
        except (TypeError, ValueError):
            n.poker_id = None
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
