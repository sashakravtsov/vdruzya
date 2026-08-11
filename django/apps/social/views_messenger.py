"""Inbox FBVs — classic Facebook Message Center (HTTP, 1:1)."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.social import chat as ch
from apps.social.forms import ComposeMessageForm, MessageForm
from apps.social.friendship import friends_of
from apps.social.models import SocialProfile
from apps.social.services import profile_of
from apps.social.throttle import throttle

FOLDERS = frozenset({"inbox", "sent"})


def _me(request):
    return profile_of(request.user)


def _compose_form(friends, data=None, files=None, to=None):
    return ComposeMessageForm(friends, data, files, initial={"to": str(to)} if to else None)


def _page(request):
    try:
        return max(1, int(request.GET.get("page") or 1))
    except (TypeError, ValueError):
        return 1


def _go(conv_id=None, *, compose=False, folder="inbox"):
    if compose:
        return "/inbox?compose=1"
    if conv_id:
        q = f"/inbox?c={conv_id}"
        return q if folder == "inbox" else f"{q}&folder={folder}"
    return "/inbox" if folder == "inbox" else f"/inbox?folder={folder}"


@login_required
@never_cache
def messenger(request):
    me = _me(request)
    if not me:
        return redirect("home")

    q = (request.GET.get("q") or "").strip()
    tq = (request.GET.get("tq") or "").strip()
    folder = request.GET.get("folder") or "inbox"
    if folder not in FOLDERS:
        folder = "inbox"
    compose = request.GET.get("compose") or request.GET.get("new")
    to_id = request.GET.get("to")
    page = _page(request)
    show_all = request.GET.get("all") == "1"
    conversations, has_more = ch.inbox(
        me, limit=40, offset=(page - 1) * 40, q=q,
        sent_only=folder == "sent",
    )

    active = None
    members, chat_messages, has_older = [], [], False
    active_id = request.GET.get("c")
    if active_id:
        try:
            active = ch.require_member(me, int(active_id))
        except (Http404, TypeError, ValueError):
            messages.error(request, "Сообщение недоступно.")
            return redirect("messenger")

    if active:
        active.display_name = ch.label(active, me)
        active.peer = ch.peer(active, me)
        members = ch.others(active, me)
        chat_messages, has_older = ch.thread(active, q=tq, all_messages=show_all)
        if not ch.is_archived(me, active):
            ch.mark_read(me, active)
        for c in conversations:
            if c.id == active.id:
                c.unread = False

    friends = list(friends_of(me, limit=200))
    preselect = int(to_id) if to_id and str(to_id).isdigit() else None
    return render(request, "social/messenger.html", {
        "conversations": conversations,
        "active": active,
        "members": members,
        "chat_messages": chat_messages,
        "has_older": has_older,
        "show_all": show_all,
        "me": me,
        "form": MessageForm(),
        "compose_form": _compose_form(friends, to=preselect),
        "compose_mode": bool(compose) or (bool(preselect) and not active_id),
        "friends": friends,
        "q": q,
        "tq": tq,
        "folder": folder,
        "page": page,
        "has_more": has_more,
    })


@ch.member_post
@throttle("msg", 40, 60)
def message_send(request, me, conv):
    form = MessageForm(request.POST, request.FILES)
    go = _go(conv.id)
    if not form.is_valid():
        messages.error(request, "Напишите текст или приложите фото.")
        return redirect(go)
    try:
        ch.post_message(
            me, conv, form.cleaned_data.get("body") or "",
            upload=form.cleaned_data.get("photo") or request.FILES.get("photo"),
        )
    except ValueError:
        messages.error(request, "Напишите текст или приложите фото.")
        return redirect(go)
    return redirect(go)


@login_required
@require_POST
@transaction.atomic
def messenger_start(request, pk):
    me = _me(request)
    other = get_object_or_404(SocialProfile, pk=pk)
    err = ch.can_dm(me, other)
    if err:
        messages.error(request, err)
        return redirect(request.POST.get("next") or "messenger")
    return redirect(_go(ch.dm_find_or_create(me, other).id))


@login_required
@require_POST
@transaction.atomic
@throttle("msg", 40, 60)
def messenger_compose(request):
    me = _me(request)
    if not me:
        return redirect("messenger")
    friends = list(friends_of(me, limit=200))
    form = _compose_form(friends, request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Выберите друга и напишите сообщение.")
        return redirect(_go(compose=True))
    try:
        tid = int(form.cleaned_data["to"])
    except (TypeError, ValueError):
        messages.error(request, "Выберите друга и напишите сообщение.")
        return redirect(_go(compose=True))
    other = SocialProfile.objects.filter(id=tid).first()
    conv = ch.start_thread(me, [other], subject=(form.cleaned_data.get("subject") or "").strip()) if other else None
    if not conv:
        messages.error(request, "Писать можно только друзьям.")
        return redirect(_go(compose=True))
    try:
        ch.post_message(
            me, conv, form.cleaned_data.get("body") or "",
            upload=form.cleaned_data.get("photo") or request.FILES.get("photo"),
        )
    except ValueError:
        messages.error(request, "Напишите текст или приложите фото.")
        return redirect(_go(compose=True))
    return redirect(_go(conv.id))


@ch.member_post
def messenger_leave(request, me, conv):
    ch.leave(me, conv)
    messages.info(request, "Сообщение удалено из входящих.")
    return redirect("messenger")


@login_required
@require_POST
@transaction.atomic
def message_delete(request, message_id):
    me = _me(request)
    if not me:
        return redirect("messenger")
    try:
        cid = ch.delete_message(me, message_id)
    except Http404:
        return redirect("messenger")
    except PermissionError:
        messages.error(request, "Можно удалить только своё сообщение.")
        return redirect(request.POST.get("next") or "messenger")
    return redirect(request.POST.get("next") or _go(cid))
