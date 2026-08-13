#!/usr/bin/env python
"""Smoke: Inbox thread layout + flash partial + birthdays."""
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.db.models import Q
from django.test import Client

from apps.accounts.models import User
from apps.social import chat as ch
from apps.social.models import Friendship, Message
from apps.social.services import profile_of


def ok(label):
    print(f"OK   {label}")


def main():
    root = Path(__file__).resolve().parents[1]
    templates = root / "templates"
    missing = []
    for p in templates.rglob("*.html"):
        if p.name.startswith("_") or "partials" in p.parts:
            continue
        t = p.read_text(encoding="utf-8")
        if "extends" not in t:
            continue
        if p.name == "home.html" or "errors" in p.parts:
            continue
        if "legal/" in p.as_posix() and p.name != "base.html":
            continue
        if "partials/flash.html" in t:
            continue
        if 'id="content"' in t or "pagebody" in t:
            missing.append(str(p.relative_to(templates)))
    assert not missing, f"pages missing flash partial: {missing[:8]}"
    ok("flash partial on pages")

    u = User.objects.filter(email="alexandr@vdruzya.ru").first() or User.objects.first()
    assert u
    me = profile_of(u)
    rel = (
        Friendship.objects.filter(status="accepted")
        .filter(Q(user=me) | Q(friend=me))
        .select_related("user", "friend")
        .first()
    )
    assert rel, "need friend"
    other = rel.friend if rel.user_id == me.id else rel.user

    c = Client(HTTP_HOST="vdruzya.ru")
    c.force_login(u)

    conv = ch.dm_find_or_create(me, other)
    marker = f"QA inbox layout {os.getpid()}"
    ch.post_message(me, conv, marker + "\nвторая строка")
    r = c.get(f"/inbox?c={conv.id}", secure=True)
    assert r.status_code == 200
    html = r.content.decode("utf-8", "replace")
    assert marker in html
    assert 'class="msg-line"' in html
    assert 'class="msg-head"' in html
    assert 'class="msg-av"' in html
    assert 'class="msg-body"' in html
    assert 'id="inbox-thread"' in html
    assert 'data-rt="' in html or "realtime/stream" in html
    assert "<br" in html  # linebreaksbr for multiline
    css = (root / "static/css/classic.css").read_text()
    body_rule = re.search(r"\.inbox-pane \.msg-line \.msg-body\s*\{[^}]+\}", css)
    assert body_rule and "pre-wrap" not in body_rule.group(0)
    assert "overflow: hidden" in re.search(r"\.inbox-pane \.msg-line\s*\{[^}]+\}", css, re.S).group(0)
    ok("inbox thread layout chrome")

    from apps.social import realtime as rt
    snap = rt.snapshot(me, conv_id=conv.id)
    assert "unread_messages" in snap and "last_message_id" in snap
    assert "typing" in snap
    assert 'id="inbox-typing"' in html
    assert 'data-typing-url="' in html
    assert 'id="inbox-voice-btn"' in html
    r = c.post(f"/inbox/{conv.id}/typing", {"state": "typing"}, secure=True)
    assert r.status_code == 200 and r.json().get("ok")
    r = c.post(f"/inbox/{conv.id}/typing", {"state": "voice"}, secure=True)
    assert r.status_code == 200 and r.json().get("state") == "voice"
    # peer view of typing: set as other, read as me
    assert rt.set_typing(other, conv.id, "typing")
    peers = rt.typing_for(me, conv.id)
    assert any(p.get("id") == other.id and p.get("state") == "typing" for p in peers)
    r = c.get(f"/inbox/{conv.id}/since?after=0", secure=True)
    assert r.status_code == 200
    data = r.json()
    assert "html" in data and "last_id" in data and "typing" in data
    r = c.get(f"/realtime/stream?once=1&c={conv.id}", secure=True)
    assert r.status_code == 200
    assert "text/event-stream" in (r.get("Content-Type") or "")
    chunk = b"".join(r.streaming_content)
    assert b"data:" in chunk and b"unread_messages" in chunk and b"typing" in chunk
    js = (root / "static/js/realtime.js").read_text(encoding="utf-8")
    assert "pingTyping" in js and "записывает голосовое" in js
    assert "MediaRecorder" in js and "uploadVoice" in js
    ok("realtime SSE + inbox since + typing")

    # Voice note upload (tiny fake ogg/webm payload)
    from django.core.files.uploadedfile import SimpleUploadedFile
    voice_blob = b"OggS" + b"\x00" * 200
    r = c.post(
        f"/inbox/{conv.id}/message",
        {"body": "", "voice": SimpleUploadedFile("voice.ogg", voice_blob, content_type="audio/ogg")},
        secure=True,
    )
    assert r.status_code in (301, 302)
    vm = Message.objects.filter(conversation=conv, message_type="voice").order_by("-id").first()
    assert vm and vm.attachment_path and vm.attachment_path.startswith("messages/")
    r = c.get(f"/inbox?c={conv.id}", secure=True)
    assert r.status_code == 200 and b"<audio" in r.content
    ok("voice message upload")

    # Archive folder + restore
    r = c.post(f"/inbox/{conv.id}/leave", {}, secure=True)
    assert r.status_code in (301, 302)
    r = c.get("/inbox?folder=archive", secure=True)
    assert r.status_code == 200 and "Архив".encode() in r.content
    assert other.name.encode() in r.content or str(conv.id).encode() in r.content
    r = c.get("/inbox?unread=1", secure=True)
    assert r.status_code == 200 and "Непрочитанные".encode() in r.content
    r = c.post(f"/inbox/{conv.id}/unarchive", {}, secure=True)
    assert r.status_code in (301, 302)
    r = c.get("/inbox", secure=True)
    assert r.status_code == 200
    ok("archive + unread folders")

    # Read receipts + mute + mark-all + subject + compose stickers
    r = c.get(f"/inbox?c={conv.id}", secure=True)
    assert r.status_code == 200
    assert ("отправлено".encode() in r.content) or ("прочитано".encode() in r.content)
    assert b"msg-receipt" in r.content
    assert b"data-peer-read=" in r.content
    assert (b"\xd0\xb1\xd0\xb5\xd0\xb7 \xd1\x83\xd0\xb2\xd0\xb5\xd0\xb4\xd0\xbe\xd0\xbc\xd0\xbb\xd0\xb5\xd0\xbd\xd0\xb8\xd0\xb9" in r.content) or ("вкл. уведомления".encode() in r.content) or (b"без уведомлений" in r.content)
    assert b'name="title"' in r.content
    r = c.post(f"/inbox/{conv.id}/title", {"title": "QA тема"}, secure=True)
    assert r.status_code in (301, 302)
    r = c.get(f"/inbox?c={conv.id}", secure=True)
    assert r.status_code == 200 and "QA тема".encode() in r.content
    r = c.post(f"/inbox/{conv.id}/mute", {}, secure=True)
    assert r.status_code in (301, 302)
    assert ch.is_muted(me, conv)
    r = c.get(f"/inbox?c={conv.id}", secure=True)
    assert r.status_code == 200 and "вкл. уведомления".encode() in r.content
    r = c.post(f"/inbox/{conv.id}/unmute", {}, secure=True)
    assert r.status_code in (301, 302)
    assert not ch.is_muted(me, conv)
    r = c.get("/inbox", secure=True)
    assert r.status_code == 200 and "прочитать всё".encode() in r.content
    r = c.post("/inbox/read-all", {}, secure=True)
    assert r.status_code in (301, 302)
    r = c.get("/inbox?compose=1", secure=True)
    assert r.status_code == 200 and "Стикер".encode() in r.content
    snap = rt.snapshot(me, conv_id=conv.id)
    assert "peer_read_at" in snap
    js = (root / "static/js/realtime.js").read_text(encoding="utf-8")
    assert "applyReadReceipts" in js
    ok("receipts + mute + read-all + subject + compose stickers")
    r = c.post(f"/inbox/{conv.id}/title", {"title": ""}, secure=True)
    assert r.status_code in (301, 302)

    r = c.get("/birthdays", secure=True)
    assert r.status_code == 200 and "Дни рождения".encode() in r.content
    ok("birthdays page")

    r = c.get("/apps", secure=True)
    assert "Дни рождения".encode() in r.content
    ok("apps lists birthdays")

    Message.objects.filter(conversation=conv, body__startswith=marker).delete()
    Message.objects.filter(conversation=conv, message_type="voice").delete()
    ok("cleanup")
    print("ALL inbox/flash/birthdays probes passed")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FAIL", e)
        raise
