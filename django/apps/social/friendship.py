"""Friendship helpers — short only, FB 2005 / Laravel parity."""
from collections import defaultdict

from django.db.models import Count, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404

from apps.social.models import Block, CommunityMember, Friendship, SocialProfile
from apps.social.services import friend_ids, now


def friends_of(me, limit=200):
    ids = list(friend_ids(me))[:limit]
    if not ids:
        return SocialProfile.objects.none()
    return SocialProfile.objects.filter(id__in=ids).order_by("name")


def pending_to(me):
    return (
        Friendship.objects.filter(friend=me, status="pending")
        .select_related("user")
        .order_by("-id")
    )


def pending_from(me):
    """Outgoing friend requests I sent."""
    return (
        Friendship.objects.filter(user=me, status="pending")
        .select_related("friend")
        .order_by("-id")
    )


def blocked_by(me):
    ids = Block.objects.filter(blocker=me).values_list("blocked_id", flat=True)
    return SocialProfile.objects.filter(id__in=ids).order_by("name")


def is_blocked(a, b) -> bool:
    return Block.objects.filter(
        Q(blocker=a, blocked=b) | Q(blocker=b, blocked=a)
    ).exists()


def _exclude_ids(me):
    out = {me.id}
    out |= set(Friendship.objects.filter(user=me).values_list("friend_id", flat=True))
    out |= set(Friendship.objects.filter(friend=me, status="pending").values_list("user_id", flat=True))
    out |= set(Block.objects.filter(blocker=me).values_list("blocked_id", flat=True))
    out |= set(Block.objects.filter(blocked=me).values_list("blocker_id", flat=True))
    return out


def mutual_label(n):
    n = int(n)
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} общий друг"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return f"{n} общих друга"
    return f"{n} общих друзей"


def suggestions(me, limit=20):
    """People You May Know — mutual friends, city, groups (classic FB)."""
    exclude = _exclude_ids(me)
    scores = defaultdict(lambda: {"score": 0, "reasons": []})

    fids = list(friend_ids(me))
    if fids:
        for oid, cnt in (
            Friendship.objects.filter(status="accepted", user_id__in=fids)
            .exclude(friend_id__in=exclude)
            .values("friend_id")
            .annotate(cnt=Count("id"))
            .values_list("friend_id", "cnt")
        ):
            scores[oid]["score"] += 5 * cnt
            scores[oid]["reasons"].append(mutual_label(cnt))

    city = (me.city or "").strip()
    if city and city.lower() != "не указан":
        for oid in SocialProfile.objects.filter(city=city).exclude(id__in=exclude).values_list("id", flat=True)[:50]:
            scores[oid]["score"] += 4
            scores[oid]["reasons"].append("Ваш город")

    gids = list(CommunityMember.objects.filter(social_user=me).values_list("community_id", flat=True))
    if gids:
        for oid, cnt in (
            CommunityMember.objects.filter(community_id__in=gids)
            .exclude(social_user_id__in=exclude)
            .values("social_user_id")
            .annotate(cnt=Count("id"))
            .values_list("social_user_id", "cnt")
        ):
            scores[oid]["score"] += 3 * min(3, cnt)
            scores[oid]["reasons"].append("Общие группы")

    if not scores:
        people = list(SocialProfile.objects.exclude(id__in=exclude).order_by("-id")[:limit])
        return [{"user": p, "score": 0, "reasons": [], "subtitle": p.city or p.headline or "Новый участник"} for p in people]

    top = sorted(scores, key=lambda i: scores[i]["score"], reverse=True)[:limit]
    users = SocialProfile.objects.filter(id__in=top).in_bulk()
    rows = []
    for i in top:
        p = users.get(i)
        if not p:
            continue
        reasons = list(dict.fromkeys(scores[i]["reasons"]))
        rows.append({
            "user": p, "score": scores[i]["score"], "reasons": reasons,
            "subtitle": reasons[0] if reasons else (p.city or p.headline or ""),
        })
    return rows


def send_request(me, other):
    if not me or me.id == other.id:
        return False
    if is_blocked(me, other):
        return "blocked"
    if Friendship.objects.filter(user=me, friend=other).exists():
        return False
    # Incoming pending → accept instead
    if Friendship.objects.filter(user=other, friend=me, status="pending").exists():
        return accept_request(me, other) is True
    Friendship.objects.create(
        user=me, friend=other, status="pending", created_at=now(), updated_at=now(),
    )
    return True


def cancel_request(me, other):
    Friendship.objects.filter(user=me, friend=other, status="pending").delete()


def relation_of(me, other):
    """Return Friendship row between me and other, or None."""
    if not me or not other or me.id == other.id:
        return None
    return Friendship.objects.filter(
        Q(user=me, friend=other) | Q(user=other, friend=me)
    ).first()


def relations_for(me, ids):
    """Map profile_id → {status, outgoing} for batch UI."""
    if not me or not ids:
        return {}
    out = {}
    for row in Friendship.objects.filter(
        Q(user=me, friend_id__in=ids) | Q(user_id__in=ids, friend=me)
    ):
        oid = row.friend_id if row.user_id == me.id else row.user_id
        out[oid] = {"status": row.status, "outgoing": row.user_id == me.id}
    return out


def accept_request(me, other):
    from django.db import transaction
    from apps.social.models import Notification

    pending = Friendship.objects.filter(user=other, friend=me, status="pending").first()
    if not pending:
        return HttpResponseForbidden("Нет заявки.")
    with transaction.atomic():
        pending.status, pending.updated_at = "accepted", now()
        pending.save(update_fields=["status", "updated_at"])
        Friendship.objects.update_or_create(
            user=me, friend=other,
            defaults={"status": "accepted", "created_at": now(), "updated_at": now()},
        )
        Notification.objects.create(
            social_user=other, title="Заявка принята",
            body=f"{me.name} принял(а) вашу заявку в друзья"[:255],
            seen=False, type="friend_accept", url=f"/profile/{me.id}", created_at=now(),
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


def mutual_count(a, b) -> int:
    if not a or not b or a.id == b.id:
        return 0
    return len(friend_ids(a) & friend_ids(b))


def invite_code_from_request(request):
    """POST / GET / cookie — first non-empty invite code."""
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
    if not code:
        return None
    return SocialProfile.objects.filter(invite_code=code).first()


def registration_requires_invite():
    """Invite-only after the first member exists (bootstrap exception)."""
    return SocialProfile.objects.exists()


def apply_invite(request, me, code=None):
    """After register: link inviter, send friend request."""
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


def apply_invite_cookie(request, me):
    """Back-compat alias."""
    return apply_invite(request, me)


def other_or_404(pk):
    return get_object_or_404(SocialProfile, pk=pk)
