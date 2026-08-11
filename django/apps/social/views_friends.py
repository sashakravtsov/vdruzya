"""Friends / people / invite FBVs — short only, FB 2005."""
from django.contrib import messages
from django.contrib.auth.decorators import login_not_required, login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.social import friendship as fr
from apps.social.models import Block, SocialProfile
from apps.social.services import accepted_friends, get_profile, profile_of

_TABS = ("suggested", "friends", "requests", "search")


def _forbid_block(request, who=None):
    return render(
        request, "social/profile_blocked.html",
        {"who": who, "me": profile_of(request.user) if request.user.is_authenticated else None},
        status=403,
    )


@login_required
def people(request):
    me = profile_of(request.user)
    tab = request.GET.get("tab") or "suggested"
    if tab not in _TABS:
        tab = "suggested"
    q = (request.GET.get("q") or "").strip()
    pending = list(fr.pending_to(me)[:40]) if me else []
    outgoing = list(fr.pending_from(me)[:40]) if me and tab == "requests" else []
    friends = list(fr.friends_of(me)[:200]) if me and tab == "friends" else []
    if tab == "friends" and q and friends:
        ql = q.lower()
        friends = [f for f in friends if ql in (f.name or "").lower() or ql in (f.city or "").lower()]
    blocked = list(fr.blocked_by(me)[:40]) if me and tab == "friends" else []
    sugg = fr.suggestions(me, 20) if me and tab == "suggested" else []
    results = None
    if tab == "search" and q and me:
        ban = Block.objects.filter(blocker=me).values_list("blocked_id", flat=True)
        qs = (
            SocialProfile.objects.exclude(id=me.id).exclude(id__in=ban)
            .filter(Q(name__icontains=q) | Q(city__icontains=q) | Q(headline__icontains=q) | Q(slug__icontains=q))
            .order_by("name")
        )
        results = Paginator(qs, 24).get_page(request.GET.get("p"))
        rel = fr.relations_for(me, [p.id for p in results])
        for p in results:
            p.rel = rel.get(p.id)
    return render(
        request, "social/people.html",
        {
            "me": me, "tab": tab, "q": q, "friends": friends, "pending": pending,
            "outgoing": outgoing, "blocked": blocked, "suggestions": sugg, "results": results,
            "invite_url": fr.invite_url(me, request) if me else "",
        },
    )


@login_required
def friends_home(request):
    """Dedicated Мои друзья — FB 2005 two-column."""
    me = profile_of(request.user)
    q = (request.GET.get("q") or "").strip()
    friends = list(fr.friends_of(me)[:200]) if me else []
    total = len(friends)
    if q and friends:
        ql = q.lower()
        friends = [f for f in friends if ql in (f.name or "").lower() or ql in (f.city or "").lower()]
    return render(
        request, "social/friends.html",
        {
            "me": me,
            "q": q,
            "friends": friends,
            "friends_total": total,
            "pending": list(fr.pending_to(me)[:40]) if me else [],
            "outgoing": list(fr.pending_from(me)[:40]) if me else [],
            "suggestions": fr.suggestions(me, 12) if me else [],
            "blocked": list(fr.blocked_by(me)[:40]) if me else [],
            "invite_url": fr.invite_url(me, request) if me else "",
        },
    )


@login_not_required
def profile_friends(request, pk):
    owner = get_profile(pk)
    me = profile_of(request.user) if request.user.is_authenticated else None
    if me and me.id != owner.id and fr.is_blocked(me, owner):
        return _forbid_block(request, owner)
    items = list(accepted_friends(owner, 120))
    rel = fr.relations_for(me, [p.id for p in items]) if me else {}
    for p in items:
        n = fr.mutual_count(me, p) if me and me.id != p.id else 0
        p.mutual = fr.mutual_label(n) if n else ""
        p.rel = rel.get(p.id)
    return render(
        request, "social/friends_user.html",
        {"owner": owner, "friends": items, "me": me, "is_own": bool(me and me.id == owner.id)},
    )


@login_required
def invite_mine(request):
    me = profile_of(request.user)
    return render(
        request, "social/invite_mine.html",
        {"me": me, "invite_url": fr.invite_url(me, request)},
    )


@login_not_required
def invite_show(request, code):
    inviter = get_object_or_404(SocialProfile, invite_code=code)
    me = profile_of(request.user) if request.user.is_authenticated else None
    if me:
        if me.id != inviter.id:
            out = fr.send_request(me, inviter)
            if out == "blocked":
                return _forbid_block(request, inviter)
            if out:
                messages.info(request, f"Заявка в друзья отправлена {inviter.name}.")
            return redirect("profile", pk=inviter.id)
        return redirect("feed")
    resp = render(request, "social/invite_show.html", {"inviter": inviter})
    resp.set_cookie("vdruzya_invite", code, max_age=60 * 60 * 24 * 14)
    return resp


def _back(request, default="people"):
    return redirect(request.POST.get("next") or request.META.get("HTTP_REFERER") or default)


@login_required
@require_POST
def friend_request(request, pk):
    me, other = profile_of(request.user), fr.other_or_404(pk)
    out = fr.send_request(me, other)
    if out == "blocked":
        return HttpResponseForbidden("Взаимодействие с этим пользователем недоступно.")
    if out:
        messages.info(request, "Заявка в друзья отправлена.")
    return _back(request, f"/profile/{pk}")


@login_required
@require_POST
def friend_accept(request, pk):
    me, other = profile_of(request.user), fr.other_or_404(pk)
    if fr.is_blocked(me, other):
        return HttpResponseForbidden("Взаимодействие с этим пользователем недоступно.")
    out = fr.accept_request(me, other)
    if out is not True:
        return out
    messages.success(request, "Заявка принята.")
    return _back(request, "/friends")


@login_required
@require_POST
def friend_reject(request, pk):
    me, other = profile_of(request.user), fr.other_or_404(pk)
    fr.reject_request(me, other)
    messages.info(request, "Заявка отклонена.")
    return _back(request, "/friends")


@login_required
@require_POST
def friend_cancel(request, pk):
    me, other = profile_of(request.user), fr.other_or_404(pk)
    fr.cancel_request(me, other)
    messages.info(request, "Заявка отменена.")
    return _back(request, "/friends")


@login_required
@require_POST
def friend_remove(request, pk):
    me, other = profile_of(request.user), fr.other_or_404(pk)
    fr.remove_friend(me, other)
    messages.info(request, "Пользователь удалён из друзей.")
    return _back(request, "/friends")


@login_required
@require_POST
def friend_block(request, pk):
    me, other = profile_of(request.user), fr.other_or_404(pk)
    fr.block_user(me, other)
    messages.info(request, "Пользователь заблокирован.")
    return _back(request, "/friends")


@login_required
@require_POST
def friend_unblock(request, pk):
    me, other = profile_of(request.user), fr.other_or_404(pk)
    fr.unblock_user(me, other)
    messages.info(request, "Пользователь разблокирован.")
    return _back(request, "/friends")
