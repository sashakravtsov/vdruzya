#!/usr/bin/env python
"""Smoke: FB 2014 classic modules (Save / Safety Check)."""
import os
import sys
import uuid

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.test import Client

from apps.accounts.models import User
from apps.social import era2014 as e14
from apps.social.models import Post, SafetyCheckin, SafetyEvent, SavedItem
from apps.social.services import bump_news, news_items, now, profile_of


def ok(label):
    print(f"OK   {label}")


def main():
    from django.db import connection
    with connection.cursor() as cur:
        for t in ("saved_items", "safety_events", "safety_checkins"):
            cur.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name=%s", [t]
            )
            assert cur.fetchone(), f"missing {t}"
    ok("schema 2014")

    u = User.objects.filter(email="alexandr@vdruzya.ru").first() or User.objects.first()
    assert u
    me = profile_of(u)
    assert me
    c = Client(HTTP_HOST="vdruzya.ru")
    c.force_login(u)

    for path, needle in (("/saves", "Сохранённое"), ("/safety", "Проверка безопасности")):
        r = c.get(path, secure=True)
        assert r.status_code == 200, f"{path} -> {r.status_code}"
        assert needle.encode() in r.content
        assert b"page-tabs" not in r.content
        assert b"display: flex" not in r.content.lower()
    ok("saves + safety pages")

    t = now()
    post = Post.objects.create(
        social_user=me, body=f"QA save {uuid.uuid4().hex[:6]}",
        visibility="public", kind="status", topic="status",
        created_at=t, updated_at=t,
    )
    r = c.post(f"/posts/{post.id}/save", {"next": "/saves"}, secure=True)
    assert r.status_code in (301, 302)
    assert SavedItem.objects.filter(social_user=me, post=post).exists()
    r = c.get("/saves", secure=True)
    assert r.status_code == 200
    assert post.body.split()[0].encode() in r.content or b"QA save" in r.content
    r = c.post(f"/posts/{post.id}/save", {"next": "/saves"}, secure=True)
    assert r.status_code in (301, 302)
    assert not SavedItem.objects.filter(social_user=me, post=post).exists()
    r = c.post(f"/posts/{post.id}/save", {"next": "/saves"}, secure=True)
    assert r.status_code in (301, 302)
    assert SavedItem.objects.filter(social_user=me, post=post).exists()
    ok("save post toggle")

    event = e14.ensure_demo_event()
    assert event
    r = c.get(f"/safety/{event.id}", secure=True)
    assert r.status_code == 200
    assert event.title.encode() in r.content
    r = c.post(f"/safety/{event.id}", {"status": "safe"}, secure=True)
    assert r.status_code in (301, 302)
    assert SafetyCheckin.objects.filter(event=event, social_user=me, status="safe").exists()
    bump_news()
    feed = news_items(me, limit=80)
    safety_items = [
        i for i in feed
        if i.get("kind") == "safety" and i.get("event") and i["event"].id == event.id
    ]
    assert safety_items, "safety story missing from feed"
    assert safety_items[0].get("story_key", "").startswith("safety:"), safety_items[0].get("story_key")
    ok("safety checkin + feed")

    r = c.get("/apps/saves", secure=True)
    assert r.status_code == 200
    assert "Сохранённое".encode() in r.content
    r = c.get("/apps/safety", secure=True)
    assert r.status_code == 200
    assert "Проверка безопасности".encode() in r.content
    ok("app center entries")

    # cleanup
    SavedItem.objects.filter(social_user=me, post=post).delete()
    post.delete()
    SafetyCheckin.objects.filter(event=event, social_user=me).delete()
    # keep demo event if title is the seed one and no other checkins
    if event.title == "Проверка безопасности" and not SafetyCheckin.objects.filter(event=event).exists():
        SafetyEvent.objects.filter(pk=event.id).delete()
    ok("cleanup")
    print("ALL 2014 classic modules probes passed")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FAIL", e)
        raise
