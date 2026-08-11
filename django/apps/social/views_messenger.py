"""Messenger FBVs — classic Facebook Inbox (HTTP, 1:1)."""
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

FOLDERS = frozenset({"inbox", "sent", "unread", "archive"})


def _me(request):
    return profile_of(request.user)


def _compose_form(friends, data=None, files=None, to=None):
    return ComposeMessageForm(friends, data, files, initial={"to": str(to)} if to else None)


def _int_ids(values):
    out = []
    for x in values:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            pass
    return out


def _page(request):
    try:
        return max(1, int(request.GET.get("page") or 1))
    except (TypeError, ValueError):
        return 1


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
        unread_only=folder == "unread",
        sent_only=folder == "sent",
        archived_only=folder == "archive",
    )

    active = is_archived = None
    members, chat_messages, has_older = [], [], False
    active_id = request.GET.get("c")
    if active_id:
        try:
            active = ch.require_member(me, int(active_id))
        except (Http404, TypeError, ValueError):
            messages.error(request, "Диалог недоступен.")
            return redirect("messenger")

    if active:
        active.display_name = ch.label(active, me)
        active.peer = ch.peer(active, me)
        members = ch.others(active, me)
        chat_messages, has_older = ch.thread(active, q=tq, all_messages=show_all)
        is_archived = ch.is_archived(me, active)
        if not is_archived:
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
        "is_archived": is_archived,
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


@login_required
@never_cache
def messages_older(request, conversation_id):
    """HTTP fallback for «earlier messages» — full thread via ?all=1."""
    return redirect(f"/messenger?c={int(conversation_id)}&all=1")


@ch.member_post
@throttle("msg", 40, 60)
def message_send(request, me, conv):
    form = MessageForm(request.POST, request.FILES)
    go = f"/messenger?c={conv.id}"
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
    return redirect(f"/messenger?c={ch.dm_find_or_create(me, other).id}")


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
        return redirect("/messenger?compose=1")
    try:
        tid = int(form.cleaned_data["to"])
    except (TypeError, ValueError):
        messages.error(request, "Выберите друга и напишите сообщение.")
        return redirect("/messenger?compose=1")
    other = SocialProfile.objects.filter(id=tid).first()
    if not other:
        messages.error(request, "Писать можно только друзьям.")
        return redirect("/messenger?compose=1")
    conv = ch.start_thread(me, [other], subject=(form.cleaned_data.get("subject") or "").strip())
    if not conv:
        messages.error(request, "Писать можно только друзьям.")
        return redirect("/messenger?compose=1")
    try:
        ch.post_message(
            me, conv, form.cleaned_data.get("body") or "",
            upload=form.cleaned_data.get("photo") or request.FILES.get("photo"),
        )
    except ValueError:
        messages.error(request, "Напишите текст или приложите фото.")
        return redirect("/messenger?compose=1")
    return redirect(f"/messenger?c={conv.id}")


@ch.member_post
def messenger_leave(request, me, conv):
    ch.leave(me, conv)
    messages.info(request, "Диалог перенесён в архив.")
    return redirect("messenger")


@login_required
@require_POST
@transaction.atomic
def messenger_bulk(request):
    """Classic inbox bulk: archive / restore / unread."""
    me = _me(request)
    if not me:
        return redirect("messenger")
    ids = _int_ids(request.POST.getlist("ids"))
    action = (request.POST.get("action") or "archive").strip()
    if action == "restore":
        n = ch.restore_many(me, ids)
        if n:
            messages.info(request, f"Возвращено во входящие: {n}.")
        return redirect("/messenger?folder=archive")
    if action == "unread":
        n = ch.mark_unread_many(me, ids)
        if n:
            messages.info(request, f"Непрочитанных: {n}.")
        return redirect("/messenger?folder=unread")
    if action == "read_all":
        ch.mark_all_read(me)
        messages.info(request, "Все диалоги отмечены прочитанными.")
        return redirect("messenger")
    n = ch.leave_many(me, ids)
    if n:
        messages.info(request, f"В архиве: {n}.")
    return redirect("messenger")


# Back-compat alias used by older templates/urls
messenger_archive = messenger_bulk


@ch.member_post
def messenger_restore(request, me, conv):
    ch.restore(me, conv)
    messages.info(request, "Диалог возвращён во входящие.")
    return redirect(f"/messenger?c={conv.id}")


@ch.member_post
def messenger_unread(request, me, conv):
    ch.mark_unread(me, conv)
    return redirect("/messenger?folder=unread")


@ch.member_post
def messenger_title(request, me, conv):
    """FB 2006 Inbox — no group-chat rename UI."""
    return redirect(f"/messenger?c={conv.id}")


@ch.member_post
def messenger_invite(request, me, conv):
    """FB 2006 Inbox — no adding members to a thread."""
    return redirect(f"/messenger?c={conv.id}")


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
    return redirect(request.POST.get("next") or f"/messenger?c={cid}")
