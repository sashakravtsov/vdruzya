"""Inbox FBVs — classic Facebook Message Center (HTTP, 1:1)."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.social import chat as ch
from apps.social.forms import ComposeMessageForm, MessageForm
from apps.social.friendship import block_user
from apps.social.markdown_msg import render_message_md
from apps.social.models import SocialProfile
from apps.social.services import accepted_friends as friends_of, profile_of
from apps.social.throttle import throttle


def _int_ids(raw) -> list[int]:
    out = []
    for x in raw or []:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            continue
    return out

FOLDERS = frozenset({"inbox", "sent", "archive"})


def _me(request):
    return profile_of(request.user)


def _compose_form(friends, data=None, files=None, to=None, stickers=None):
    return ComposeMessageForm(
        friends, data, files,
        stickers=stickers,
        initial={"to": str(to)} if to else None,
    )


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
def inbox_home(request):
    from apps.social.inbox_ctx import build_inbox_ctx
    me = _me(request)
    if not me:
        return redirect("home")
    err, ctx = build_inbox_ctx(request, me, compose_form=_compose_form)
    if err:
        messages.error(request, "Сообщение недоступно.")
        return redirect(err)
    return render(request, "social/inbox.html", ctx)


@login_required
@require_POST
@throttle("msg", 60, 60)
def inbox_preview(request):
    """Server-side Markdown preview for the classic compose editor."""
    me = _me(request)
    if not me:
        return JsonResponse({"error": "auth"}, status=403)
    body = (request.POST.get("body") or "")[:4000]
    html = render_message_md(body)
    return JsonResponse({
        "ok": True,
        "html": html or "<p class=\"muted\">Пусто — напишите текст.</p>",
        "empty": not bool(body.strip()),
    })


@ch.member_post
@throttle("msg", 40, 60)
def message_send(request, me, conv):
    from apps.social.gifts import catalog
    form = MessageForm(request.POST, request.FILES, stickers=catalog()[:40])
    go = _go(conv.id)
    wants_json = "application/json" in (request.headers.get("Accept") or "")

    def fail(msg):
        if wants_json:
            return JsonResponse({"ok": False, "error": msg}, status=400)
        messages.error(request, msg)
        return redirect(go)

    if not form.is_valid():
        return fail("Напишите текст, приложите фото / видео / голосовое или выберите стикер.")
    voice = form.cleaned_data.get("voice") or request.FILES.get("voice")
    photo = form.cleaned_data.get("photo") or request.FILES.get("photo")
    try:
        m = ch.post_message(
            me, conv, form.cleaned_data.get("body") or "",
            upload=voice or photo,
            voice=bool(voice),
            reply_to_id=form.cleaned_data.get("reply_to"),
            sticker_id=form.cleaned_data.get("sticker") or None,
            waveform=form.cleaned_data.get("waveform") or request.POST.get("waveform"),
            duration_ms=form.cleaned_data.get("duration_ms") or request.POST.get("duration_ms"),
        )
    except ValueError as exc:
        detail = str(exc).strip()
        if detail in ("", "empty"):
            detail = "Напишите текст, приложите фото / видео / голосовое или выберите стикер."
        return fail(detail)
    if wants_json:
        return JsonResponse({"ok": True, "last_id": m.id})
    return redirect(go)


@login_required
@require_POST
@transaction.atomic
def inbox_start(request, pk):
    me = _me(request)
    other = get_object_or_404(SocialProfile, pk=pk)
    err = ch.can_dm(me, other)
    if err:
        messages.error(request, err)
        return redirect(request.POST.get("next") or "inbox")
    return redirect(_go(ch.dm_find_or_create(me, other).id))


@login_required
@require_POST
@transaction.atomic
@throttle("msg", 40, 60)
def inbox_compose(request):
    me = _me(request)
    if not me:
        return redirect("inbox")
    from apps.social.gifts import catalog
    friends = list(friends_of(me, limit=200))
    stickers = catalog()[:40]
    form = _compose_form(friends, request.POST, request.FILES, stickers=stickers)
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
            sticker_id=form.cleaned_data.get("sticker") or None,
        )
    except ValueError:
        messages.error(request, "Напишите текст, приложите фото или выберите стикер.")
        return redirect(_go(compose=True))
    return redirect(_go(conv.id))


@ch.member_post
def inbox_leave(request, me, conv):
    ch.leave(me, conv)
    messages.info(request, "Переписка перенесена в архив.")
    return redirect("inbox")


@ch.member_post
def inbox_unarchive(request, me, conv):
    if ch.unarchive(me, conv):
        messages.success(request, "Переписка возвращена во входящие.")
    return redirect(_go(conv.id))


@ch.member_post
def inbox_mute(request, me, conv):
    if ch.mute(me, conv):
        messages.info(request, "Уведомления по этой переписке выключены.")
    return redirect(_go(conv.id))


@ch.member_post
def inbox_unmute(request, me, conv):
    if ch.unmute(me, conv):
        messages.success(request, "Уведомления по переписке снова включены.")
    return redirect(_go(conv.id))


@ch.member_post
def inbox_title(request, me, conv):
    title = (request.POST.get("title") or "").strip()
    ch.set_title(me, conv, title)
    messages.success(request, "Тема обновлена." if title else "Тема снята.")
    return redirect(_go(conv.id))


@ch.member_post
def inbox_unread(request, me, conv):
    ch.mark_unread(me, conv)
    messages.info(request, "Переписка отмечена как непрочитанная.")
    return redirect("inbox")


@ch.member_post
def inbox_spam(request, me, conv):
    peer = ch.report_spam(me, conv)
    if peer and request.POST.get("block") == "1":
        block_user(me, peer)
        messages.info(request, f"Спам: {peer.name} заблокирован, переписка в архиве.")
    else:
        messages.info(request, "Переписка помечена как спам и перенесена в архив.")
    return redirect("inbox")


@ch.member_post
def inbox_purge(request, me, conv):
    ch.purge_many(me, [conv.id])
    messages.info(request, "Переписка удалена из вашего ящика.")
    return redirect("inbox")


@login_required
@require_POST
@transaction.atomic
def inbox_read_all(request):
    me = _me(request)
    if not me:
        return redirect("inbox")
    ch.mark_all_read(me)
    messages.info(request, "Все входящие отмечены как прочитанные.")
    return redirect("inbox")


@login_required
@require_POST
@transaction.atomic
def inbox_bulk(request):
    """List bulk: archive / restore / unread / purge."""
    me = _me(request)
    if not me:
        return redirect("inbox")
    ids = _int_ids(request.POST.getlist("ids"))
    action = (request.POST.get("action") or "archive").strip()
    if action == "restore":
        n = ch.restore_many(me, ids)
        if n:
            messages.info(request, f"Возвращено во входящие: {n}.")
        return redirect("/inbox?folder=archive")
    if action == "unread":
        n = 0
        for cid in ids:
            try:
                ch.mark_unread(me, ch.require_member(me, cid))
                n += 1
            except Http404:
                pass
        if n:
            messages.info(request, f"Непрочитанных: {n}.")
        return redirect("inbox")
    if action == "purge":
        n = ch.purge_many(me, ids)
        if n:
            messages.info(request, f"Удалено из ящика: {n}.")
        return redirect("/inbox?folder=archive")
    n = ch.leave_many(me, ids)
    if n:
        messages.info(request, f"В архиве: {n}.")
    return redirect("inbox")


@login_required
@require_POST
@transaction.atomic
@throttle("msg", 20, 60)
def message_forward(request, message_id):
    me = _me(request)
    if not me:
        return redirect("inbox")
    try:
        tid = int(request.POST.get("to") or 0)
    except (TypeError, ValueError):
        tid = 0
    other = SocialProfile.objects.filter(pk=tid).first()
    if not other:
        messages.error(request, "Выберите друга для пересылки.")
        return redirect(request.POST.get("next") or "inbox")
    try:
        _m, conv = ch.forward_message(me, message_id, other)
    except Http404:
        messages.error(request, "Сообщение недоступно.")
        return redirect("inbox")
    except PermissionError as e:
        messages.error(request, str(e) or "Нельзя переслать.")
        return redirect(request.POST.get("next") or "inbox")
    messages.success(request, "Сообщение переслано.")
    return redirect(_go(conv.id))


@login_required
@require_POST
@transaction.atomic
def message_delete(request, message_id):
    me = _me(request)
    if not me:
        return redirect("inbox")
    try:
        cid = ch.delete_message(me, message_id)
    except Http404:
        return redirect("inbox")
    except PermissionError:
        messages.error(request, "Можно удалить только своё сообщение.")
        return redirect(request.POST.get("next") or "inbox")
    return redirect(request.POST.get("next") or _go(cid))
