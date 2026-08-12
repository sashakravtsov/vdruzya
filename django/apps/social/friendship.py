"""Friendship helpers — classic Facebook Friends."""
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404

from apps.social.models import Block, Education, Experience, Friendship, SocialProfile
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


def ensure_invite_code(me):
    if me.invite_code:
        return me.invite_code
    import secrets
    code = secrets.token_urlsafe(8)[:12]
    while SocialProfile.objects.filter(invite_code=code).exists():
        code = secrets.token_urlsafe(8)[:12]
    me.invite_code = code
    me.updated_at = now()
    me.save(update_fields=["invite_code", "updated_at"])
    return code


def invite_url(me, request=None):
    code = ensure_invite_code(me)
    if request:
        return request.build_absolute_uri(f"/i/{code}")
    return f"https://vdruzya.ru/i/{code}"


def invite_code_from_request(request):
    for src in (
        (request.POST.get("invite") if hasattr(request, "POST") else None),
        request.GET.get("invite"),
        request.COOKIES.get("vdruzya_invite"),
    ):
        code = (src or "").strip()
        if code:
            return code
    return ""


def find_inviter(code):
    code = (code or "").strip()
    return SocialProfile.objects.filter(invite_code=code).first() if code else None


def registration_requires_invite():
    return SocialProfile.objects.exists()


def apply_invite(request, me, code=None):
    if not me:
        return None
    code = (code or invite_code_from_request(request) or "").strip()
    inviter = find_inviter(code)
    if not inviter or inviter.id == me.id:
        return None
    if not me.invited_by_id:
        me.invited_by = inviter
        me.updated_at = now()
        me.save(update_fields=["invited_by", "updated_at"])
    send_request(me, inviter)
    return inviter


def friends_since(a, b):
    """When friendship became accepted (max created_at of accepted pair)."""
    if not a or not b or a.id == b.id:
        return None
    dates = [
        d for d in Friendship.objects.filter(
            Q(user=a, friend=b) | Q(user=b, friend=a),
            status="accepted",
        ).values_list("created_at", flat=True)
        if d
    ]
    return max(dates) if dates else None


def shared_groups(a, b, limit=12):
    if not a or not b:
        return []
    from apps.social.models import Community, CommunityMember
    ids_a = set(
        CommunityMember.objects.filter(social_user=a).values_list("community_id", flat=True)
    )
    ids_b = set(
        CommunityMember.objects.filter(social_user=b).values_list("community_id", flat=True)
    )
    shared = ids_a & ids_b
    if not shared:
        return []
    return list(Community.objects.filter(id__in=shared).order_by("name")[:limit])


def shared_photos(a, b, limit=12):
    """Photos where both people are tagged."""
    if not a or not b:
        return []
    from apps.social.models import Photo, PhotoTag
    ids = (
        PhotoTag.objects.filter(social_user=a, status="approved")
        .filter(photo_id__in=PhotoTag.objects.filter(social_user=b, status="approved").values("photo_id"))
        .values_list("photo_id", flat=True)
        .distinct()[:limit]
    )
    photos = list(
        Photo.objects.filter(id__in=ids)
        .select_related("album", "album__social_user")
        .order_by("-id")[:limit]
    )
    return photos


def friendship_page(me, other):
    """Bundle for classic «Смотреть дружбу» page."""
    since = friends_since(me, other)
    mutual = mutual_friends(me, other, limit=24)
    rel = relation_of(me, other)
    return {
        "since": since,
        "mutual": mutual,
        "mutual_count": mutual_count(me, other),
        "groups": shared_groups(me, other),
        "photos": shared_photos(me, other),
        "are_friends": bool(rel and rel.status == "accepted"),
    }


def upcoming_anniversaries(viewer=None, days=30, limit=20):
    """Friends whose friendship anniversary falls in the next `days`."""
    from datetime import datetime, timedelta
    from django.utils import timezone

    if not viewer:
        return []
    today = timezone.localdate()
    end = today + timedelta(days=days)
    rows = list(
        Friendship.objects.filter(user=viewer, status="accepted")
        .exclude(friend=viewer)
        .select_related("friend")
        .order_by("id")
    )
    out = []
    for row in rows:
        since = friends_since(viewer, row.friend)
        if not since:
            continue
        if isinstance(since, datetime):
            if timezone.is_aware(since):
                d = timezone.localtime(since).date()
            else:
                d = since.date()
        else:
            d = since
        if d.year >= today.year:
            continue  # not yet a year
        try:
            ann = d.replace(year=today.year)
        except ValueError:
            ann = d.replace(year=today.year, day=28)  # Feb 29
        if ann < today:
            try:
                ann = d.replace(year=today.year + 1)
            except ValueError:
                ann = d.replace(year=today.year + 1, day=28)
        if today <= ann <= end:
            years = ann.year - d.year
            if years >= 1:
                out.append((ann, years, row.friend, d))
    out.sort(key=lambda x: x[0])
    return out[:limit]


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
    """Classic Find Friends search (both-way blocks excluded)."""
    ban = set(Block.objects.filter(blocker=me).values_list("blocked_id", flat=True))
    ban |= set(Block.objects.filter(blocked=me).values_list("blocker_id", flat=True))
    qs = SocialProfile.objects.exclude(id=me.id).exclude(id__in=ban)
    q = (q or "").strip()
    city = (city or "").strip()
    school = (school or "").strip()
    gender = (gender or "").strip()
    workplace = (workplace or "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(city__icontains=q) | Q(headline__icontains=q)
            | Q(slug__icontains=q) | Q(hometown__icontains=q) | Q(workplace__icontains=q)
        )
    if city:
        qs = qs.filter(Q(city__icontains=city) | Q(hometown__icontains=city))
    if school:
        ids = Education.objects.filter(institution__icontains=school).values_list(
            "social_user_id", flat=True
        )
        qs = qs.filter(id__in=ids)
    if gender in ("male", "female"):
        qs = qs.filter(gender=gender)
    if workplace:
        exp_ids = Experience.objects.filter(company_name__icontains=workplace).values_list(
            "social_user_id", flat=True
        )
        qs = qs.filter(Q(workplace__icontains=workplace) | Q(id__in=exp_ids))
    return Paginator(qs.order_by("name"), per).get_page(page)
