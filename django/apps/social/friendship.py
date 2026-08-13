"""Friendship helpers — classic Facebook Friends."""
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404

from apps.social.models import Block, Friendship, SocialProfile
from apps.social.services import friend_ids, now


def friends_page(me, *, q="", city="", sort="name", page=1, per=40, only_ids=None):
    """Paginated My Friends with name/city filter and sort."""
    ids = friend_ids(me)
    if only_ids is not None:
        ids = ids & set(only_ids)
    total = len(ids)
    empty = Paginator([], per).get_page(1)
    if not ids:
        return [], total, empty
    qs = SocialProfile.objects.filter(id__in=ids)
    q, city = (q or "").strip(), (city or "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(city__icontains=q) | Q(headline__icontains=q))
    if city:
        qs = qs.filter(city__icontains=city)
    if sort == "recent":
        order, seen = [], set()
        for u, f in (
            Friendship.objects.filter(status="accepted")
            .filter(Q(user=me) | Q(friend=me))
            .order_by("-updated_at", "-id")
            .values_list("user_id", "friend_id")
        ):
            oid = f if u == me.id else u
            if oid in ids and oid not in seen:
                seen.add(oid)
                order.append(oid)
        filtered = set(qs.values_list("id", flat=True))
        order = [i for i in order if i in filtered]
        p = Paginator(order, per).get_page(page)
        users = SocialProfile.objects.in_bulk(p.object_list)
        return [users[i] for i in p.object_list if i in users], total, p
    p = Paginator(qs.order_by("name"), per).get_page(page)
    return list(p.object_list), total, p


def pending_to(me):
    return (
        Friendship.objects.filter(friend=me, status="pending")
        .select_related("user")
        .order_by("-id")
    )


def pending_from(me):
    return (
        Friendship.objects.filter(user=me, status="pending")
        .select_related("friend")
        .order_by("-id")
    )


def annotate_mutuals(me, rows, *, who="user"):
    """Attach mutual / mutual_n on Friendship rows for Confirm Friends UI."""
    for row in rows:
        other = getattr(row, who)
        n = mutual_count(me, other)
        row.mutual_n = n
        row.mutual = mutual_label(n) if n else ""
    return rows


def blocked_by(me):
    ids = Block.objects.filter(blocker=me).values_list("blocked_id", flat=True)
    return SocialProfile.objects.filter(id__in=ids).order_by("name")


def is_blocked(a, b) -> bool:
    return Block.objects.filter(
        Q(blocker=a, blocked=b) | Q(blocker=b, blocked=a)
    ).exists()


def mutual_label(n):
    n = int(n)
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} общий друг"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return f"{n} общих друга"
    return f"{n} общих друзей"


def mutual_count(a, b) -> int:
    if not a or not b or a.id == b.id:
        return 0
    return len(friend_ids(a) & friend_ids(b))


def mutual_friends_qs(a, b):
    ids = friend_ids(a) & friend_ids(b)
    if not ids:
        return SocialProfile.objects.none()
    return SocialProfile.objects.filter(id__in=ids).order_by("name")


def mutual_friends(a, b, limit=200):
    return mutual_friends_qs(a, b)[:limit]


def mutual_friends_page(a, b, *, q="", page=1, per=40):
    qs = mutual_friends_qs(a, b)
    q = (q or "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(city__icontains=q) | Q(headline__icontains=q))
    p = Paginator(qs, per).get_page(page)
    return list(p.object_list), p


def send_request(me, other):
    if not me or me.id == other.id:
        return False
    if is_blocked(me, other):
        return "blocked"
    if Friendship.objects.filter(user=me, friend=other).exists():
        return False
    if Friendship.objects.filter(user=other, friend=me, status="pending").exists():
        return accept_request(me, other) is True
    Friendship.objects.create(
        user=me, friend=other, status="pending", created_at=now(), updated_at=now(),
    )
    return True


def cancel_request(me, other):
    Friendship.objects.filter(user=me, friend=other, status="pending").delete()


def relation_of(me, other):
    if not me or not other or me.id == other.id:
        return None
    return Friendship.objects.filter(
        Q(user=me, friend=other) | Q(user=other, friend=me)
    ).first()


def relations_for(me, ids):
    if not me or not ids:
        return {}
    out = {}
    for row in Friendship.objects.filter(
        Q(user=me, friend_id__in=ids) | Q(user_id__in=ids, friend=me)
    ):
        oid = row.friend_id if row.user_id == me.id else row.user_id
        out[oid] = {"status": row.status, "outgoing": row.user_id == me.id}
    return out


def accept_request(me, other) -> bool:
    from django.db import transaction

    from apps.social.services import bump_news

    pending = Friendship.objects.filter(user=other, friend=me, status="pending").first()
    if not pending:
        return False
    with transaction.atomic():
        pending.status, pending.updated_at = "accepted", now()
        pending.save(update_fields=["status", "updated_at"])
        Friendship.objects.update_or_create(
            user=me, friend=other,
            defaults={"status": "accepted", "created_at": now(), "updated_at": now()},
        )
    bump_news()
    return True


def reject_request(me, other):
    Friendship.objects.filter(user=other, friend=me, status="pending").delete()


def remove_friend(me, other):
    Friendship.objects.filter(
        Q(user=me, friend=other) | Q(user=other, friend=me)
    ).delete()


def block_user(me, other):
    if not me or me.id == other.id:
        return
    remove_friend(me, other)
    Block.objects.get_or_create(blocker=me, blocked=other, defaults={"created_at": now()})


def unblock_user(me, other):
    Block.objects.filter(blocker=me, blocked=other).delete()


from apps.social.friendship_invite import (  # noqa: E402
    apply_invite, ensure_invite_code, find_inviter, invite_code_from_request,
    invite_url, registration_requires_invite,
)
from apps.social.friendship_extra import (  # noqa: E402
    friends_since, friendship_page, shared_groups, shared_photos, upcoming_anniversaries,
)


def other_or_404(pk):
    return get_object_or_404(SocialProfile, pk=pk)


def can_see_friends(viewer, owner) -> bool:
    """Early FB: own list always; others only if friends (or self)."""
    if not owner:
        return False
    if not viewer:
        return False
    if viewer.id == owner.id:
        return True
    return owner.id in friend_ids(viewer)


def find_people(me, *, q="", city="", school="", gender="", workplace="", page=1, per=24):
    """Classic Find Friends search — builders in people_search.find_people."""
    from apps.social.people_search import find_people as build
    return build(
        me, q=q, city=city, school=school, gender=gender, workplace=workplace,
        page=page, per=per,
    )
