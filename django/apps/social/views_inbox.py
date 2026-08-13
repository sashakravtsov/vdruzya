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
from apps.social.models import SocialProfile
from apps.social.services import accepted_friends as friends_of, profile_of
from apps.social.throttle import throttle

FOLDERS = frozenset({"inbox", "sent", "archive"})


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


@ch.member_post
@throttle("msg", 40, 60)
def message_send(request, me, conv):
    from apps.social.gifts import catalog
    form = MessageForm(request.POST, request.FILES, stickers=catalog()[:40])
    go = _go(conv.id)
    if not form.is_valid():
        messages.error(request, "Напишите текст, приложите фото / видео / голосовое или выберите стикер.")
        return redirect(go)
    voice = form.cleaned_data.get("voice") or request.FILES.get("voice")
    photo = form.cleaned_data.get("photo") or request.FILES.get("photo")
    try:
        ch.post_message(
            me, conv, form.cleaned_data.get("body") or "",
            upload=voice or photo,
            voice=bool(voice),
            reply_to_id=form.cleaned_data.get("reply_to"),
            sticker_id=form.cleaned_data.get("sticker") or None,
        )
    except ValueError:
        messages.error(request, "Напишите текст, приложите фото / видео / голосовое или выберите стикер.")
        return redirect(go)
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
def inbox_leave(request, me, conv):
    ch.leave(me, conv)
    messages.info(request, "Переписка перенесена в архив.")
    return redirect("inbox")


@ch.member_post
def inbox_unarchive(request, me, conv):
    if ch.unarchive(me, conv):
        messages.success(request, "Переписка возвращена во входящие.")
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
