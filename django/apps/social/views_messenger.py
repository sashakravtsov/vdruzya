"""Messenger FBVs — classic Facebook inbox."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from apps.social import chat as ch
from apps.social.forms import ComposeMessageForm, MessageForm
from apps.social.friendship import friends_of
from apps.social.models import ConversationMember, SocialProfile
from apps.social.services import profile_of
from apps.social.throttle import throttle


def _me(request):
    return profile_of(request.user)


def _compose_form(friends, data=None, files=None, to=None):
    initial = {"to": [str(to)]} if to else None
    return ComposeMessageForm(friends, data, files, initial=initial)


def _int_ids(values):
    out = []
    for x in values:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            pass
    return out


@login_required
@never_cache
def messenger(request):
    me = _me(request)
    if not me:
        return redirect("home")

    q = (request.GET.get("q") or "").strip()
    tq = (request.GET.get("tq") or "").strip()
    folder = (request.GET.get("folder") or "inbox").strip()
    if folder not in ("inbox", "sent", "unread", "archive"):
        folder = "inbox"
    unread_only = folder == "unread"
    sent_only = folder == "sent"
    archived_only = folder == "archive"
    try:
        page = max(1, int(request.GET.get("page") or 1))
    except (TypeError, ValueError):
        page = 1
    compose = request.GET.get("compose") or request.GET.get("new")
    to_id = request.GET.get("to")
    conversations, has_more = ch.inbox(
        me, limit=40, offset=(page - 1) * 40, q=q,
        unread_only=unread_only, sent_only=sent_only, archived_only=archived_only,
    )

    active = None
    active_id = request.GET.get("c")
    if active_id:
        try:
            active = ch.require_member(me, int(active_id))
        except (Http404, TypeError, ValueError):
            messages.error(request, "Диалог недоступен.")
            return redirect("messenger")
    elif conversations and not compose:
        active = conversations[0]

    members, chat_messages, has_older = [], [], False
    is_archived = False
    if active:
        active.display_name = ch.label(active, me)
        active.peer = ch.peer(active, me)
        members = ch.others(active, me)
        chat_messages, has_older = ch.thread(active, q=tq)
        is_archived = ConversationMember.objects.filter(
            conversation=active, social_user=me, archived_at__isnull=False,
        ).exists()
        if not is_archived:
            ch.mark_read(me, active)
        for c in conversations:
            if c.id == active.id:
                c.unread = False

    friends = list(friends_of(me, limit=200))
    member_ids = {p.id for p in members} | ({active.peer.id} if active and active.peer else set())
    invite_friends = [f for f in friends if f.id not in member_ids and (not active or f.id != me.id)]
    preselect = int(to_id) if to_id and str(to_id).isdigit() else None
    reply_to = request.GET.get("reply")
    return render(request, "social/messenger.html", {
        "conversations": conversations,
        "active": active,
        "members": members,
        "chat_messages": chat_messages,
        "has_older": has_older,
        "is_archived": is_archived,
        "me": me,
        "form": MessageForm(initial={"reply_to": reply_to} if reply_to else None),
        "compose_form": _compose_form(friends, to=preselect),
        "compose_mode": bool(compose) or (bool(preselect) and not active_id),
        "friends": friends,
        "invite_friends": invite_friends,
        "q": q,
        "tq": tq,
        "folder": folder,
        "page": page,
        "has_more": has_more,
    })


@login_required
@require_GET
@never_cache
def messages_older(request, conversation_id):
    me = _me(request)
    if not me:
        return JsonResponse({"error": "auth"}, status=401)
    try:
        conv = ch.require_member(me, conversation_id)
        rows, has_older = ch.older(conv, request.GET.get("before"), q=request.GET.get("tq") or "")
    except (Http404, TypeError, ValueError):
        return JsonResponse({"error": "gone"}, status=404)
    return JsonResponse({"has_older": has_older, "messages": [ch.ws_payload(m) for m in rows]})


@ch.member_post
@throttle("msg", 40, 60)
def message_send(request, me, conv):
    form = MessageForm(request.POST, request.FILES)
    if not form.is_valid():
        if ch.wants_json(request):
            return JsonResponse({"error": "empty"}, status=400)
        messages.error(request, "Напишите текст или приложите фото.")
        return redirect(f"/messenger?c={conv.id}")
    try:
        m = ch.post_message(
            me, conv, form.cleaned_data.get("body") or "",
            reply_to_id=form.cleaned_data.get("reply_to"),
            upload=form.cleaned_data.get("photo") or request.FILES.get("photo"),
        )
    except ValueError:
        if ch.wants_json(request):
            return JsonResponse({"error": "empty"}, status=400)
        messages.error(request, "Напишите текст или приложите фото.")
        return redirect(f"/messenger?c={conv.id}")
    ch.after_send(m)
    return ch.json_message(m) if ch.wants_json(request) else redirect(f"/messenger?c={conv.id}")


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
    recipients = list(SocialProfile.objects.filter(id__in=_int_ids(form.cleaned_data["to"])))
    conv = ch.start_thread(me, recipients, subject=(form.cleaned_data.get("subject") or "").strip())
    if not conv:
        messages.error(request, "Писать можно только друзьям.")
        return redirect("/messenger?compose=1")
    try:
        m = ch.post_message(
            me, conv, form.cleaned_data.get("body") or "",
            upload=form.cleaned_data.get("photo") or request.FILES.get("photo"),
        )
        ch.after_send(m)
    except ValueError:
        pass
    return redirect(f"/messenger?c={conv.id}")


@ch.member_post
def messenger_leave(request, me, conv):
    ch.leave(me, conv)
    messages.info(request, "Диалог перенесён в архив.")
    return redirect("messenger")


@login_required
@require_POST
@transaction.atomic
def messenger_archive(request):
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
    n = ch.leave_many(me, ids)
    if n:
        messages.info(request, f"В архиве: {n}.")
    return redirect("messenger")


@ch.member_post
def messenger_restore(request, me, conv):
    ch.restore(me, conv)
    messages.info(request, "Диалог возвращён во входящие.")
    return redirect(f"/messenger?c={conv.id}")


@ch.member_post
def messenger_spam(request, me, conv):
    from apps.social.friendship import block_user
    peer = ch.report_spam(me, conv)
    if peer and request.POST.get("block") == "1":
        block_user(me, peer)
        messages.info(request, f"Помечено как спам, {peer.name} заблокирован.")
    else:
        messages.info(request, "Диалог помечен как спам и убран в архив.")
    return redirect("messenger")


@ch.member_post
def messenger_unread(request, me, conv):
    ch.mark_unread(me, conv)
    return redirect("messenger")


@ch.member_post
def messenger_title(request, me, conv):
    ch.set_title(me, conv, request.POST.get("title") or "")
    messages.success(request, "Тема сохранена.")
    return redirect(f"/messenger?c={conv.id}")


@ch.member_post
@throttle("msg", 20, 60)
def messenger_invite(request, me, conv):
    ids = _int_ids(request.POST.getlist("ids") or request.POST.getlist("to"))
    people = list(SocialProfile.objects.filter(id__in=ids))
    try:
        added = ch.add_members(me, conv, people)
    except PermissionError as e:
        messages.error(request, str(e))
        return redirect(f"/messenger?c={conv.id}")
    if added:
        messages.success(request, f"Добавлено: {', '.join(p.name for p in added)}.")
    else:
        messages.info(request, "Некого добавить.")
    return redirect(f"/messenger?c={conv.id}")


@login_required
@require_POST
@transaction.atomic
@throttle("msg", 20, 60)
def message_forward(request, message_id):
    me = _me(request)
    if not me:
        return redirect("messenger")
    other = get_object_or_404(SocialProfile, pk=request.POST.get("to"))
    try:
        m, conv = ch.forward_message(me, message_id, other)
        ch.after_send(m)
    except Http404:
        messages.error(request, "Сообщение недоступно.")
        return redirect("messenger")
    except PermissionError as e:
        messages.error(request, str(e) or "Нельзя переслать.")
        return redirect(request.POST.get("next") or "messenger")
    messages.success(request, "Сообщение переслано.")
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
    transaction.on_commit(lambda: ch.broadcast_delete(cid, message_id))
    if ch.wants_json(request):
        return JsonResponse({"ok": True, "id": message_id, "event": "delete"})
    return redirect(request.POST.get("next") or f"/messenger?c={cid}")
