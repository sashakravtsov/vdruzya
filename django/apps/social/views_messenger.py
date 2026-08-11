"""Messenger FBVs — classic Facebook inbox."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.social import chat as ch
from apps.social.forms import ComposeMessageForm, MessageForm
from apps.social.friendship import friends_of
from apps.social.models import SocialProfile, Sticker
from apps.social.services import profile_of
from apps.social.throttle import throttle


def _me(request):
    return profile_of(request.user)


def _conv(me, conversation_id):
    return ch.require_member(me, conversation_id)


@login_required
@never_cache
def messenger(request):
    me = _me(request)
    if not me:
        return redirect("home")

    q = (request.GET.get("q") or "").strip()
    folder = (request.GET.get("folder") or "inbox").strip()
    unread_only = request.GET.get("unread") == "1" or folder == "unread"
    sent_only = folder == "sent"
    compose = request.GET.get("compose") or request.GET.get("new")
    conversations = ch.inbox(me, q=q, unread_only=unread_only, sent_only=sent_only)

    active = None
    active_id = request.GET.get("c")
    if active_id:
        try:
            active = _conv(me, int(active_id))
        except (Http404, TypeError, ValueError):
            messages.error(request, "Диалог недоступен.")
            return redirect("messenger")
    elif conversations and not compose:
        active = conversations[0]

    if active:
        active.display_name = ch.label(active, me)
        active.peer = ch.peer(active, me)
        before = request.GET.get("before")
        try:
            chat_messages, has_older = ch.thread(active, before_id=before)
        except (TypeError, ValueError):
            chat_messages, has_older = ch.thread(active)
        ch.mark_read(me, active)
        for c in conversations:
            if c.id == active.id:
                c.unread = False
    else:
        chat_messages, has_older = [], False

    friends = list(friends_of(me, limit=200))
    return render(
        request,
        "social/messenger.html",
        {
            "conversations": conversations,
            "active": active,
            "chat_messages": chat_messages,
            "has_older": has_older,
            "me": me,
            "form": MessageForm(),
            "compose_form": ComposeMessageForm(friends),
            "compose_mode": bool(compose),
            "friends": friends,
            "q": q,
            "folder": "unread" if unread_only else ("sent" if sent_only else "inbox"),
            "stickers": (
                list(Sticker.objects.filter(is_active=True).order_by("sort_order")[:24])
                if active else []
            ),
        },
    )


@login_required
@require_POST
@transaction.atomic
@throttle("msg", 40, 60)
def message_send(request, conversation_id):
    me = _me(request)
    if not me:
        return redirect("messenger")
    try:
        conv = _conv(me, conversation_id)
    except Http404:
        messages.error(request, "Диалог недоступен.")
        return redirect("messenger")
    form = MessageForm(request.POST)
    if not form.is_valid():
        if ch.wants_json(request):
            return JsonResponse({"error": "empty"}, status=400)
        messages.error(request, "Напишите текст сообщения.")
        return redirect(f"/messenger?c={conversation_id}")
    try:
        m = ch.post_message(me, conv, form.cleaned_data["body"])
    except ValueError:
        if ch.wants_json(request):
            return JsonResponse({"error": "empty"}, status=400)
        messages.error(request, "Напишите текст сообщения.")
        return redirect(f"/messenger?c={conversation_id}")
    ch.after_send(m)
    if ch.wants_json(request):
        return ch.json_message(m)
    return redirect(f"/messenger?c={conversation_id}")


@login_required
@require_POST
@transaction.atomic
@throttle("msg", 40, 60)
def sticker_send(request, conversation_id):
    me = _me(request)
    if not me:
        return redirect("messenger")
    try:
        conv = _conv(me, conversation_id)
    except Http404:
        messages.error(request, "Диалог недоступен.")
        return redirect("messenger")
    sticker = get_object_or_404(Sticker, pk=request.POST.get("sticker_id"), is_active=True)
    m = ch.post_sticker(me, conv, sticker)
    ch.after_send(m)
    if ch.wants_json(request):
        return ch.json_message(m)
    return redirect(f"/messenger?c={conversation_id}")


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
    conv = ch.dm_find_or_create(me, other)
    return redirect(f"/messenger?c={conv.id}")


@login_required
@require_POST
@transaction.atomic
@throttle("msg", 40, 60)
def messenger_compose(request):
    me = _me(request)
    if not me:
        return redirect("messenger")
    friends = list(friends_of(me, limit=200))
    form = ComposeMessageForm(friends, request.POST)
    if not form.is_valid() or not form.cleaned_data.get("to"):
        messages.error(request, "Выберите друга.")
        return redirect("/messenger?compose=1")
    other = get_object_or_404(SocialProfile, pk=int(form.cleaned_data["to"]))
    err = ch.can_dm(me, other)
    if err:
        messages.error(request, err)
        return redirect("/messenger?compose=1")
    conv = ch.dm_find_or_create(me, other)
    body = (form.cleaned_data.get("body") or "").strip()
    if body:
        m = ch.post_message(me, conv, body)
        ch.after_send(m)
    return redirect(f"/messenger?c={conv.id}")


@login_required
@require_POST
@transaction.atomic
def messenger_leave(request, conversation_id):
    me = _me(request)
    if not me:
        return redirect("messenger")
    try:
        conv = _conv(me, conversation_id)
    except Http404:
        return redirect("messenger")
    ch.leave(me, conv)
    messages.info(request, "Диалог убран из входящих.")
    return redirect("messenger")


@login_required
@require_POST
@transaction.atomic
def messenger_unread(request, conversation_id):
    me = _me(request)
    if not me:
        return redirect("messenger")
    try:
        conv = _conv(me, conversation_id)
    except Http404:
        return redirect("messenger")
    ch.mark_unread(me, conv)
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
    transaction.on_commit(lambda: ch.broadcast_delete(cid, message_id))
    if ch.wants_json(request):
        return JsonResponse({"ok": True, "id": message_id, "event": "delete"})
    return redirect(request.POST.get("next") or f"/messenger?c={cid}")
