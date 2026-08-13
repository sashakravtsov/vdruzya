"""Inbox home context — short builders; views_inbox.inbox_home stays thin."""
from __future__ import annotations

from django.http import Http404

from apps.social import chat as ch
from apps.social.forms import MessageForm
from apps.social.models import Message
from apps.social.services import accepted_friends as friends_of

FOLDERS = frozenset({"inbox", "sent", "archive"})


def _page(request) -> int:
    try:
        return max(1, int(request.GET.get("page") or 1))
    except (TypeError, ValueError):
        return 1


def _folder(request) -> str:
    folder = request.GET.get("folder") or "inbox"
    return folder if folder in FOLDERS else "inbox"


def _load_active(me, active_id, conversations, show_all, *, tq=""):
    """Return (active, members, thread_messages, has_older, err_redirect)."""
    if not active_id:
        return None, [], [], False, None
    try:
        active = ch.require_member(me, int(active_id))
    except (Http404, TypeError, ValueError):
        return None, [], [], False, "inbox"
    active.display_name = ch.label(active, me)
    active.peer = ch.peer(active, me)
    active.is_archived = ch.is_archived(me, active)
    active.is_muted = ch.is_muted(me, active)
    active.peer_read_at = ch.peer_read_at(me, active)
    members = ch.others(active, me)
    thread_messages, has_older = ch.thread(active, q=tq, all_messages=show_all)
    if not active.is_archived:
        ch.mark_read(me, active)
    for c in conversations:
        if c.id == active.id:
            c.unread = False
    return active, members, thread_messages, has_older, None


def build_inbox_ctx(request, me, *, compose_form):
    q = (request.GET.get("q") or "").strip()
    tq = (request.GET.get("tq") or "").strip()
    folder = _folder(request)
    unread_only = request.GET.get("unread") == "1" and folder == "inbox"
    compose = request.GET.get("compose") or request.GET.get("new")
    to_id = request.GET.get("to")
    page = _page(request)
    show_all = request.GET.get("all") == "1"
    conversations, has_more = ch.inbox(
        me, limit=40, offset=(page - 1) * 40, q=q,
        sent_only=folder == "sent",
        archived=folder == "archive",
        unread_only=unread_only,
    )
    active_id = request.GET.get("c")
    active, members, thread_messages, has_older, err_redirect = _load_active(
        me, active_id, conversations, show_all, tq=tq,
    )
    friends = list(friends_of(me, limit=200))
    preselect = int(to_id) if to_id and str(to_id).isdigit() else None
    from apps.social.gifts import catalog
    stickers = catalog()[:40]
    reply_id = request.GET.get("reply")
    reply_preview = None
    if reply_id and str(reply_id).isdigit() and active:
        reply_preview = (
            Message.objects.filter(pk=int(reply_id), conversation=active)
            .select_related("social_user")
            .first()
        )
    form = MessageForm(
        stickers=stickers,
        initial={"reply_to": reply_preview.id} if reply_preview else None,
    )
    return err_redirect, {
        "conversations": conversations,
        "active": active,
        "members": members,
        "thread_messages": thread_messages,
        "has_older": has_older,
        "show_all": show_all,
        "me": me,
        "form": form,
        "compose_form": compose_form(friends, to=preselect, stickers=stickers),
        "compose_mode": bool(compose) or (bool(preselect) and not active_id),
        "friends": friends,
        "q": q,
        "tq": tq,
        "folder": folder,
        "unread_only": unread_only,
        "page": page,
        "has_more": has_more,
        "nav": "inbox",
        "stickers": stickers,
        "reply_preview": reply_preview,
    }
