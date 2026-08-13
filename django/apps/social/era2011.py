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
    from apps.social.news_stories import _add_og as add
    return add(items, blocked, fids, limit)


def _add_milestones(items, blocked, fids, limit):
    from apps.social.news_stories import _add_milestones as add
    return add(items, blocked, fids, limit)


def _add_follow_public(items, viewer, blocked, follows, limit):
    from apps.social.news_stories import _add_follow_public as add
    return add(items, viewer, blocked, follows, limit)


def ticker_items(viewer, limit=12):
    """Compact friend/follow activity — builders in ticker.ticker_items."""
    from apps.social.ticker import ticker_items as build
    return build(viewer, limit=limit)


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
