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
    assert "<br" in html  # linebreaksbr for multiline
    css = (root / "static/css/classic.css").read_text()
    body_rule = re.search(r"\.inbox-pane \.msg-line \.msg-body\s*\{[^}]+\}", css)
    assert body_rule and "pre-wrap" not in body_rule.group(0)
    assert "overflow: hidden" in re.search(r"\.inbox-pane \.msg-line\s*\{[^}]+\}", css, re.S).group(0)
    ok("inbox thread layout chrome")

    r = c.get("/birthdays", secure=True)
    assert r.status_code == 200 and "Дни рождения".encode() in r.content
    ok("birthdays page")

    r = c.get("/apps", secure=True)
    assert "Дни рождения".encode() in r.content
    ok("apps lists birthdays")

    Message.objects.filter(conversation=conv, body__startswith=marker).delete()
    ok("cleanup")
    print("ALL inbox/flash/birthdays probes passed")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FAIL", e)
        raise
