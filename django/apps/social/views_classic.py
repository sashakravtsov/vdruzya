"""Classic 2006–09 expansion FBVs: networks, links, videos, notes, market, lists, blocked, mobile."""
from django.contrib import messages
from django.contrib.auth.decorators import login_not_required, login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.social import classic_extra as cx
from apps.social import friendship as fr
from apps.social.forms import FriendListForm, MarketForm, NoteForm, PostedItemForm
from apps.social.models import FriendList, MarketplaceListing, SocialProfile
from apps.social.services import bump_news, friend_ids, profile_of


def _posted_home(request, *, kind: str, title: str, template: str, nav: str):
    me = profile_of(request.user)
    form = PostedItemForm(request.POST or None)
    mine = request.GET.get("mine") == "1"
    if request.method == "POST":
        if form.is_valid():
            post = cx.create_posted_item(
                me,
                kind=kind,
                title=form.cleaned_data["title"],
                url=form.cleaned_data["url"],
                blurb=form.cleaned_data.get("blurb") or "",
                visibility=form.cleaned_data.get("visibility") or "friends",
            )
            if post:
                bump_news()
                messages.success(request, "Опубликовано." if kind == "link" else "Видео добавлено.")
                return redirect(request.path + ("?mine=1" if mine else ""))
            messages.error(request, "Проверьте ссылку.")
        else:
            messages.error(request, "Укажите название и адрес.")
    items = cx.list_posted(me, kind, mine=mine, limit=40) if me else []
    return render(request, template, {
        "me": me, "form": form, "items": items, "mine": mine,
        "kind": kind, "page_title": title, "nav": nav,
    })


@login_required
@require_http_methods(["GET", "POST"])
def links_home(request):
    return _posted_home(
        request, kind="link", title="Ссылки", template="social/links.html", nav="links",
    )


@login_required
@require_http_methods(["GET", "POST"])
def videos_home(request):
    return _posted_home(
        request, kind="video", title="Видео", template="social/videos.html", nav="videos",
    )


@login_required
@require_http_methods(["GET", "POST"])
def notes_home(request):
    """Notes directory + create (POST shared with notes.store)."""
    if request.method == "POST":
        from apps.social.views_actions import note_create
        return note_create(request)
    me = profile_of(request.user)
    form = NoteForm()
    mine = request.GET.get("mine") == "1"
    items = cx.notes_feed(me, mine=mine, limit=40) if me else []
    return render(request, "social/notes.html", {
        "me": me, "form": form, "items": items, "mine": mine, "nav": "notes",
    })


@login_not_required
@require_http_methods(["GET", "HEAD"])
def networks_home(request):
    me = profile_of(request.user) if request.user.is_authenticated else None
    return render(request, "social/networks.html", {
        "me": me, "nav": "networks", **cx.network_catalog(48),
    })


@login_required
@require_http_methods(["GET", "POST"])
def marketplace_home(request):
    me = profile_of(request.user)
    form = MarketForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            row = cx.market_create(
                me,
                title=form.cleaned_data["title"],
                price=form.cleaned_data.get("price") or "",
                place=form.cleaned_data.get("place") or "",
                description=form.cleaned_data.get("description") or "",
            )
            if row:
                messages.success(request, "Объявление опубликовано.")
                return redirect(row)
            messages.error(request, "Укажите название.")
        else:
            messages.error(request, "Укажите название.")
    q = (request.GET.get("q") or "").strip()
    place = (request.GET.get("place") or "").strip()
    items = cx.market_list(q=q, place=place, limit=40)
    return render(request, "social/marketplace.html", {
        "me": me, "form": form, "items": items, "q": q, "place": place, "nav": "marketplace",
    })


@login_not_required
@require_http_methods(["GET", "HEAD"])
def marketplace_show(request, pk):
    item = get_object_or_404(MarketplaceListing.objects.select_related("social_user"), pk=pk)
    me = profile_of(request.user) if request.user.is_authenticated else None
    return render(request, "social/marketplace_show.html", {
        "me": me, "item": item, "nav": "marketplace",
        "is_owner": bool(me and item.social_user_id == me.id),
    })


@login_required
@require_POST
def marketplace_delete(request, pk):
    me = profile_of(request.user)
    item = get_object_or_404(MarketplaceListing, pk=pk)
    if item.social_user_id != me.id:
        messages.error(request, "Можно удалить только своё объявление.")
        return redirect(item)
    item.delete()
    messages.info(request, "Объявление удалено.")
    return redirect("marketplace")


@login_required
@require_http_methods(["GET", "POST"])
def lists_home(request):
    me = profile_of(request.user)
    form = FriendListForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            fl = cx.list_create(me, form.cleaned_data["name"])
            if fl:
                messages.success(request, "Список создан.")
                return redirect(fl)
        messages.error(request, "Укажите название списка.")
    return render(request, "social/friend_lists.html", {
        "me": me, "form": form, "lists": cx.lists_for(me), "nav": "lists",
    })


@login_required
@require_http_methods(["GET", "POST"])
def list_show(request, pk):
    me = profile_of(request.user)
    fl = get_object_or_404(FriendList, pk=pk, social_user=me)
    if request.method == "POST":
        action = request.POST.get("action") or "add"
        try:
            fid = int(request.POST.get("friend_id") or 0)
        except (TypeError, ValueError):
            fid = 0
        if action == "remove":
            cx.list_remove(me, fl, fid)
            messages.info(request, "Удалено из списка.")
        else:
            if cx.list_add(me, fl, fid):
                messages.success(request, "Добавлено в список.")
            else:
                messages.error(request, "Можно добавлять только друзей.")
        return redirect(fl)
    members = cx.list_members(fl)
    taken = {p.id for p in members}
    candidates = list(
        SocialProfile.objects.filter(id__in=friend_ids(me)).exclude(id__in=taken).order_by("name")[:60]
    )
    return render(request, "social/friend_list.html", {
        "me": me, "flist": fl, "members": members, "candidates": candidates, "nav": "lists",
    })


@login_required
@require_POST
def list_delete(request, pk):
    me = profile_of(request.user)
    fl = get_object_or_404(FriendList, pk=pk, social_user=me)
    from apps.social.models import FriendListMember
    FriendListMember.objects.filter(friend_list=fl).delete()
    fl.delete()
    messages.info(request, "Список удалён.")
    return redirect("friends.lists")


@login_required
@require_http_methods(["GET", "HEAD"])
def blocked_home(request):
    me = profile_of(request.user)
    return render(request, "social/blocked.html", {
        "me": me, "blocked": list(fr.blocked_by(me)[:80]) if me else [], "nav": "account",
    })


@login_not_required
@require_http_methods(["GET", "HEAD"])
def mobile_home(request):
    me = profile_of(request.user) if request.user.is_authenticated else None
    return render(request, "social/mobile.html", {"me": me, "nav": "mobile"})
