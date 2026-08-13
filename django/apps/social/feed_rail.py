"""Home right-rail — short builders; services.feed_rail re-exports."""
from __future__ import annotations

from django.db.models import Count, Q

from apps.social.models import Community, Company, Notification
from apps.social.services import group_updates, page_updates, upcoming_birthdays


def build_feed_rail(viewer):
    """Home right column — requests, pokes, events, groups, pages, birthdays (FB 2006)."""
    from apps.social import events as ev
    from apps.social import friendship as fr
    from apps.social import feed_hide as fh
    from apps.social import era2011 as e11
    from apps.social import era2013 as e13
    from apps.social import era2014 as e14
    from apps.social import photo_tags as ptags

    pending = fr.annotate_mutuals(viewer, list(fr.pending_to(viewer)[:8])) if viewer else []
    popular = list(
        Community.objects.annotate(n=Count("memberships", distinct=True))
        .filter(Q(privacy="public") | Q(privacy=""))
        .order_by("-n", "name")[:6]
    )
    popular_pages = list(
        Company.objects.annotate(n=Count("followers", distinct=True)).order_by("-n", "name")[:6]
    )
    pokes = []
    if viewer:
        from apps.social.notify import attach_poker_ids
        pokes = attach_poker_ids(list(
            Notification.objects.filter(social_user=viewer, type="poke", seen=False).order_by("-id")[:6]
        ))
    return {
        "requests": pending,
        "pokes": pokes,
        "rail_events": list(ev.list_events(viewer, "upcoming")[:5]) if viewer else [],
        "event_invites": (
            Notification.objects.filter(social_user=viewer, type="event_invite", seen=False).count()
            if viewer else 0
        ),
        "popular_groups": popular,
        "popular_pages": popular_pages,
        "group_posts": group_updates(viewer),
        "page_posts": page_updates(viewer),
        "birthdays": upcoming_birthdays(viewer),
        "anniversaries": fr.upcoming_anniversaries(viewer, days=14, limit=6) if viewer else [],
        "pending_photo_tags": ptags.pending_for(viewer, 6) if viewer else [],
        "feed_hidden_people": fh.hidden_people(viewer, 8) if viewer else [],
        "ticker": e11.ticker_items(viewer, 12) if viewer else [],
        "trending": e13.trending_topics(viewer, 8) if viewer else [],
        "nearby_rail": (e13.nearby_friends(viewer, limit=6)[0] if viewer else []),
        "saved_rail": e14.list_saves(viewer, limit=5) if viewer else [],
        "safety_rail": e14.active_safety_events(3) if viewer else [],
    }
