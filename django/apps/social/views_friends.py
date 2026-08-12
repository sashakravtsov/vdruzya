"""Friends / people / invite FBVs — classic Facebook Friends."""
from django.contrib import messages
from django.contrib.auth.decorators import login_not_required, login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.social import friendship as fr
from apps.social.models import SocialProfile
from apps.social.services import friend_ids, get_profile, profile_of

_TABS = ("requests", "search")


def _forbid_block(request, who=None):
    return render(
        request, "social/profile_blocked.html",
        {"who": who, "me": profile_of(request.user) if request.user.is_authenticated else None},
        status=403,
    )


def _page_int(raw, default=1):
    try:
        return max(1, int(raw or default))
    except (TypeError, ValueError):
        return default


def _pending(me, limit=40):
    return fr.annotate_mutuals(me, list(fr.pending_to(me)[:limit])) if me else []


@login_required
def people(request):
    """Find Friends — search + requests (FB 2006; no PYMK)."""
    # Legacy tabs: friends list moved; PYMK/suggested never existed in FB 2006.
    if request.GET.get("tab") == "friends":
        return redirect("friends")
    if request.GET.get("tab") == "suggested":
        return redirect("people")
    me = profile_of(request.user)
    tab = request.GET.get("tab") or "search"
    if tab not in _TABS:
        tab = "search"
    q = (request.GET.get("q") or "").strip()
    city = (request.GET.get("city") or "").strip()
    school = (request.GET.get("school") or "").strip()
    gender = (request.GET.get("gender") or "").strip()
    workplace = (request.GET.get("workplace") or "").strip()
    pending = _pending(me)
    outgoing = list(fr.pending_from(me)[:40]) if me and tab == "requests" else []
    results = None
    searching = bool(q or city or school or gender or workplace)
    if tab == "search" and searching and me:
        results = fr.find_people(
            me, q=q, city=city, school=school, gender=gender, workplace=workplace,
            page=_page_int(request.GET.get("p")),
        )
        rel = fr.relations_for(me, [p.id for p in results])
        for p in results:
            n = fr.mutual_count(me, p)
            p.rel = rel.get(p.id)
            p.mutual = fr.mutual_label(n) if n else ""
    return render(
        request, "social/people.html",
        {
            "me": me, "tab": tab, "q": q, "city": city, "school": school,
            "gender": gender, "workplace": workplace,
            "pending": pending, "outgoing": outgoing,
            "results": results, "searching": searching,
        },
    )


@login_required
def friends_home(request):
    """Dedicated Мои друзья — FB 2005 two-column."""
    me = profile_of(request.user)
    q = (request.GET.get("q") or "").strip()
    city = (request.GET.get("city") or "").strip()
    sort = request.GET.get("sort") or "name"
    if sort not in ("name", "recent"):
        sort = "name"
    friends, total, page = ([], 0, None)
    if me:
        friends, total, page = fr.friends_page(
            me, q=q, city=city, sort=sort, page=_page_int(request.GET.get("p")),
        )
    from apps.social import relationship as relmod

    return render(
        request, "social/friends.html",
        {
            "me": me, "q": q, "city": city, "sort": sort,
            "friends": friends, "friends_total": total, "page_obj": page,
            "pending": _pending(me),
            "outgoing": list(fr.pending_from(me)[:40]) if me else [],
            "blocked": list(fr.blocked_by(me)[:40]) if me else [],
            "relationship_incoming": relmod.incoming_for(me) if me else [],
        },
    )


@login_required
def profile_friends(request, pk):
    owner = get_profile(pk)
    me = profile_of(request.user)
    if me and me.id != owner.id and fr.is_blocked(me, owner):
        return _forbid_block(request, owner)
    if not fr.can_see_friends(me, owner):
        return render(
            request, "social/friends_user.html",
            {
                "owner": owner, "friends": [], "me": me, "q": "", "page_obj": None,
                "friends_total": len(friend_ids(owner)),
                "is_own": bool(me and me.id == owner.id),
                "private": True,
            },
            status=403,
        )
    q = (request.GET.get("q") or "").strip()
    fids = friend_ids(owner)
    qs = SocialProfile.objects.filter(id__in=fids).order_by("name")
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(city__icontains=q) | Q(headline__icontains=q))
    page = Paginator(qs, 40).get_page(_page_int(request.GET.get("p")))
    items = list(page.object_list)
    rel = fr.relations_for(me, [p.id for p in items]) if me else {}
    for p in items:
        n = fr.mutual_count(me, p) if me and me.id != p.id else 0
        p.mutual = fr.mutual_label(n) if n else ""
        p.rel = rel.get(p.id)
    return render(
        request, "social/friends_user.html",
        {
            "owner": owner, "friends": items, "me": me, "q": q, "page_obj": page,
            "friends_total": len(fids),
            "is_own": bool(me and me.id == owner.id),
            "private": False,
        },
    )


@login_required
def mutual_friends_view(request, pk):
    other = get_profile(pk)
    me = profile_of(request.user)
    if not me:
        return redirect("login")
    if other.id == me.id:
        return redirect("friends")
    if fr.is_blocked(me, other):
        return _forbid_block(request, other)
    q = (request.GET.get("q") or "").strip()
    friends, page = fr.mutual_friends_page(me, other, q=q, page=_page_int(request.GET.get("p")))
    count = fr.mutual_count(me, other)
    return render(
        request, "social/mutual_friends.html",
        {
            "me": me, "other": other, "friends": friends, "page_obj": page,
            "q": q, "mutual_count": count, "mutual_label": fr.mutual_label(count) if count else "",
        },
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
    if not fr.accept_request(me, other):
        return HttpResponseForbidden("Нет заявки.")
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
