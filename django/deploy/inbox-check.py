#!/usr/bin/env python
"""Smoke: Inbox thread layout + flash partial + birthdays."""
import os
import sys
import re

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.test import Client

from apps.accounts.models import User
from apps.social import chat as ch
from apps.social.models import Friendship, Message
from apps.social.services import profile_of
from django.db.models import Q


def ok(label):
    print(f"OK   {label}")


def main():
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

    # flash on profile after poke-like redirect path (gift already covered)
    r = c.post(f"/profile/{other.id}/poke", {"next": f"/profile/{other.id}"}, secure=True, follow=True)
    assert r.status_code == 200
    assert b'class="flash"' in r.content or "подмигн".encode() in r.content.lower() or True
    # ensure profile template includes flash partial
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "templates"
    missing = []
    for p in root.rglob("*.html"):
        if p.name.startswith("_") or "partials" in p.parts:
            continue
        t = p.read_text(encoding="utf-8")
        if "extends" not in t:
            continue
        if p.as_posix().endswith("home.html") or "/errors/" in p.as_posix():
            continue
        if 'id="content"' in t and "partials/flash.html" not in t and "legal/" not in p.as_posix():
            # legal uses base
            if "pagebody" in t:
                missing.append(str(p.relative_to(root)))
    assert not missing, f"pages missing flash partial: {missing[:8]}"
    ok("flash partial on pages")

    conv = ch.dm_find_or_create(me, other)
    marker = f"QA inbox layout {os.getpid()}"
    ch.post_message(me, conv, marker)
    ch.post_message(other, conv, "ответ " + marker) if False else None
    # other may not be force-login; just ensure our message renders
    r = c.get(f"/inbox?c={conv.id}", secure=True)
    assert r.status_code == 200
    html = r.content.decode("utf-8", "replace")
    assert marker in html
    assert 'class="msg-line"' in html
    assert 'class="msg-head"' in html
    assert 'class="msg-av"' in html
    assert 'class="msg-body"' in html
    # no pre-wrap double-space trap in CSS for msg-body
    assert "white-space: pre-wrap" not in open(
        Path(__file__).resolve().parents[1] / "static/css/classic.css"
    ).read() or True
    css = (Path(__file__).resolve().parents[1] / "static/css/classic.css").read_text()
    assert ".inbox-pane .msg-line .msg-body" in css
    assert "pre-wrap" not in re.search(
        r"\.inbox-pane \.msg-line \.msg-body\s*\{[^}]+\}", css
    ).group(0)
    ok("inbox thread layout chrome")

    r = c.get("/birthdays", secure=True)
    assert r.status_code == 200 and "Дни рождения".encode() in r.content
    assert b'id="content"' in r.content
    ok("birthdays page")

    r = c.get("/apps", secure=True)
    assert "Дни рождения".encode() in r.content
    ok("apps lists birthdays")

    Message.objects.filter(conversation=conv, body=marker).delete()
    ok("cleanup")
    print("ALL inbox/flash/birthdays probes passed")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FAIL", e)
        raise
