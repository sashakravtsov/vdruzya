"""FB 2011 helpers — Subscribe, Timeline, Open Graph, Ticker (classic chrome)."""
from __future__ import annotations

from datetime import date, datetime

from django.db.models import Q

from apps.social.models import ProfileFollow, TimelineMilestone, OgStory, profile_related
from apps.social.services import bump_news, friend_ids, now

OG_VERBS = frozenset({"listening", "reading", "watching"})
OG_LABELS = {
    "listening": "слушает",
    "reading": "читает",
    "watching": "смотрит",
}
MILESTONE_KINDS = (
    ("life", "Жизнь"),
    ("work", "Работа"),
    ("school", "Учёба"),
    ("travel", "Путешествие"),
    ("relationship", "Отношения"),
    ("custom", "Другое"),
)


def followee_ids(me) -> set[int]:
    if not me:
        return set()
    return set(
        ProfileFollow.objects.filter(follower=me).values_list("followee_id", flat=True)
    )


def follower_ids(profile) -> set[int]:
    if not profile:
        return set()
    return set(
        ProfileFollow.objects.filter(followee=profile).values_list("follower_id", flat=True)
    )


def is_following(me, other) -> bool:
    if not me or not other or me.id == other.id:
        return False
    return ProfileFollow.objects.filter(follower=me, followee=other).exists()


def follow_count(profile) -> int:
    return ProfileFollow.objects.filter(followee=profile).count() if profile else 0


def following_count(profile) -> int:
    return ProfileFollow.objects.filter(follower=profile).count() if profile else 0


def follow(me, other) -> str:
    from apps.social.friendship import is_blocked
    from apps.social.notify import push

    if not me or not other or me.id == other.id:
        return "self"
    if is_blocked(me, other):
        return "blocked"
    _, created = ProfileFollow.objects.get_or_create(
        follower=me, followee=other, defaults={"created_at": now()},
    )
    if created:
        push(
            other.id, title="Подписка",
            body=f"{me.name} подписался(ась) на ваши обновления",
            type="follow", url=f"/profile/{me.id}",
        )
        bump_news()
    return "ok" if created else "pending"


def unfollow(me, other) -> bool:
    if not me or not other:
        return False
    n, _ = ProfileFollow.objects.filter(follower=me, followee=other).delete()
    if n:
        bump_news()
    return bool(n)


def milestones_for(profile, *, year=None, limit=40):
    if not profile:
        return []
    qs = TimelineMilestone.objects.filter(social_user=profile).order_by("-occurred_on", "-id")
    if year:
        qs = qs.filter(occurred_on__year=year)
    return list(qs[:limit])


def milestone_years(profile) -> list[int]:
    if not profile:
        return []
    years = (
        TimelineMilestone.objects.filter(social_user=profile)
        .dates("occurred_on", "year", order="DESC")
    )
    return [d.year for d in years]


def add_milestone(me, *, title, occurred_on, kind="life", body="") -> TimelineMilestone | None:
    title = (title or "").strip()[:255]
    if not me or not title or not occurred_on:
        return None
    kind = kind if kind in {k for k, _ in MILESTONE_KINDS} else "life"
    t = now()
    row = TimelineMilestone.objects.create(
        social_user=me, title=title, body=(body or "")[:500],
        kind=kind, occurred_on=occurred_on, created_at=t, updated_at=t,
    )
    bump_news()
    return row


def delete_milestone(me, milestone_id) -> bool:
    n, _ = TimelineMilestone.objects.filter(pk=milestone_id, social_user=me).delete()
    if n:
        bump_news()
    return bool(n)


def publish_og(me, *, verb, title, url="", app_slug="custom") -> OgStory | None:
    verb = (verb or "").strip().lower()
    title = (title or "").strip()[:255]
    if not me or verb not in OG_VERBS or not title:
        return None
    row = OgStory.objects.create(
        social_user=me, verb=verb, object_title=title,
        object_url=(url or "")[:255], app_slug=(app_slug or "custom")[:40],
        created_at=now(),
    )
    bump_news()
    return row


def og_label(verb: str) -> str:
    return OG_LABELS.get(verb, verb)


def _add_og(items, blocked, fids, limit):
    if not fids:
        return
    qs = (
        OgStory.objects.filter(social_user_id__in=fids)
        .select_related("social_user")
        .defer(*profile_related("social_user__"))
        .order_by("-id")
    )
    if blocked:
        qs = qs.exclude(social_user_id__in=blocked)
    for row in qs[:limit]:
        items.append({
            "kind": "og", "at": row.created_at, "actor": row.social_user,
            "og": row, "verb": row.verb, "verb_label": og_label(row.verb),
        })


def _add_milestones(items, blocked, fids, limit):
    if not fids:
        return
    qs = (
        TimelineMilestone.objects.filter(social_user_id__in=fids)
        .select_related("social_user")
        .defer(*profile_related("social_user__"))
        .order_by("-occurred_on", "-id")
    )
    if blocked:
        qs = qs.exclude(social_user_id__in=blocked)
    for row in qs[:limit]:
        items.append({
            "kind": "milestone",
            "at": row.created_at or datetime.combine(row.occurred_on, datetime.min.time()),
            "actor": row.social_user, "milestone": row,
        })


def _add_follow_public(items, viewer, blocked, follows, limit):
    """Public posts from people you Subscribe to (not already in friend circle)."""
    if not viewer or not follows:
        return
    from apps.social.models import Post, POST_DEFER
    from apps.social.services import attach_wall_notes

    qs = (
        Post.objects.filter(social_user_id__in=follows)
        .filter(Q(visibility="public") | Q(visibility=""))
        .exclude(kind__in=("gift", "poll"))
        .exclude(topic__startswith="gift:")
        .exclude(topic__startswith="page:")
        .exclude(topic__startswith="event:")
        .select_related("social_user")
        .defer(*POST_DEFER, *profile_related("social_user__"))
        .order_by("-id")
    )
    if blocked:
        qs = qs.exclude(social_user_id__in=blocked)
    posts = list(qs[:limit])
    attach_wall_notes(posts)
    for p in posts:
        topic = p.topic or ""
        if p.kind == "status" or topic == "status":
            kind = "status"
        elif topic == "picture":
            kind = "picture"
        elif p.kind == "note":
            kind = "note"
        elif p.kind in ("link", "video", "share"):
            kind = p.kind
        else:
            kind = "wall"
        items.append({"kind": kind, "at": p.created_at, "post": p, "actor": p.social_user})
    # OG from followees
    oqs = (
        OgStory.objects.filter(social_user_id__in=follows)
        .select_related("social_user")
        .defer(*profile_related("social_user__"))
        .order_by("-id")
    )
    if blocked:
        oqs = oqs.exclude(social_user_id__in=blocked)
    for row in oqs[:limit]:
        items.append({
            "kind": "og", "at": row.created_at, "actor": row.social_user,
            "og": row, "verb": row.verb, "verb_label": og_label(row.verb),
        })


def ticker_items(viewer, limit=12):
    """Compact friend/follow activity for News Feed right rail (classic Ticker)."""
    if not viewer:
        return []
    from apps.social.models import Block, Post

    fids = friend_ids(viewer) | {viewer.id}
    follows = followee_ids(viewer)
    actors = fids | follows
    blocked = set(
        Block.objects.filter(blocker=viewer).values_list("blocked_id", flat=True)
    )
    actors -= blocked
    actors.discard(viewer.id)
    if not actors:
        return []
    out = []
    for p in (
        Post.objects.filter(social_user_id__in=actors)
        .filter(Q(visibility="public") | Q(visibility="") | Q(social_user_id__in=fids))
        .exclude(kind="gift")
        .select_related("social_user")
        .defer(*profile_related("social_user__"))
        .order_by("-id")[:limit]
    ):
        topic = p.topic or ""
        if p.kind == "status" or topic == "status":
            text = "обновил(а) статус"
        elif topic == "picture":
            text = "сменил(а) фото"
        elif p.kind == "note":
            text = "написал(а) заметку"
        else:
            text = "написал(а) на стене"
        out.append({"at": p.created_at, "actor": p.social_user, "text": text, "url": p.get_absolute_url()})
    for row in (
        OgStory.objects.filter(social_user_id__in=actors)
        .select_related("social_user")
        .defer(*profile_related("social_user__"))
        .order_by("-id")[:limit]
    ):
        out.append({
            "at": row.created_at, "actor": row.social_user,
            "text": f"{og_label(row.verb)} «{row.object_title}»",
            "url": row.object_url or f"/profile/{row.social_user_id}",
        })
    for row in (
        ProfileFollow.objects.filter(follower_id__in=fids)
        .exclude(followee_id=viewer.id)
        .select_related("follower", "followee")
        .defer(*profile_related("follower__"), *profile_related("followee__"))
        .order_by("-id")[:limit]
    ):
        if row.followee_id in blocked or row.follower_id in blocked:
            continue
        out.append({
            "at": row.created_at, "actor": row.follower,
            "text": f"подписался(ась) на {row.followee.name}",
            "url": f"/profile/{row.followee_id}",
        })
    out.sort(key=lambda x: x["at"] or datetime.min, reverse=True)
    return out[:limit]


def timeline_bundle(profile, viewer, *, year=None):
    """Classic Timeline tab: milestones + year filter + activity slice."""
    years = milestone_years(profile)
    y = year
    if y is None and years:
        y = years[0]
    elif y is None:
        y = date.today().year
    ms = milestones_for(profile, year=y, limit=40)
    from apps.social.services import mini_feed
    mini = mini_feed(profile, limit=30, viewer=viewer)
    if y:
        filtered = []
        for it in mini:
            at = it.get("at")
            if at and getattr(at, "year", None) == y:
                filtered.append(it)
        mini = filtered
    return {
        "timeline_year": y,
        "timeline_years": years or [y],
        "milestones": ms,
        "timeline_mini": mini,
    }
