#!/usr/bin/env python
"""Smoke: FB 2011 classic modules (Subscribe / Timeline / OG / Ticker / Messenger extras)."""
import os
import sys
import uuid
from datetime import date

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.db.models import Q
from django.test import Client

from apps.accounts.models import User
from apps.social import era2011 as e11
from apps.social.models import Message, OgStory, ProfileFollow, SocialProfile, TimelineMilestone
from apps.social.services import bump_news, news_items, now, profile_of


def ok(label):
    print(f"OK   {label}")


def main():
    from django.db import connection
    with connection.cursor() as cur:
        for t in ("profile_follows", "timeline_milestones", "og_stories"):
            cur.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name=%s", [t]
            )
            assert cur.fetchone(), f"missing {t}"
    ok("schema 2011")

    u = User.objects.filter(email="alexandr@vdruzya.ru").first() or User.objects.first()
    assert u
    me = profile_of(u)
    c = Client(HTTP_HOST="vdruzya.ru")
    c.force_login(u)

    r = c.get("/og", secure=True)
    assert r.status_code == 200
    assert "Активность".encode() in r.content
    assert b"display: flex" not in r.content.lower()
    ok("og page")

    r = c.post("/og/publish", {
        "verb": "listening",
        "title": f"QA Song {uuid.uuid4().hex[:6]}",
        "url": "https://example.com/song",
        "next": "/og",
    }, secure=True)
    assert r.status_code in (301, 302)
    og = OgStory.objects.filter(social_user=me, verb="listening").order_by("-id").first()
    assert og
    bump_news()
    feed = news_items(me, limit=80)
    assert any(i.get("kind") == "og" and i.get("og") and i["og"].id == og.id for i in feed)
    ok("og story in feed")

    buddy = SocialProfile.objects.exclude(pk=me.id).order_by("id").first()
    assert buddy
    ProfileFollow.objects.filter(follower=me, followee=buddy).delete()
    r = c.post(f"/profile/{buddy.id}/follow", {
        "action": "follow", "next": f"/profile/{buddy.id}",
    }, secure=True)
    assert r.status_code in (301, 302)
    assert ProfileFollow.objects.filter(follower=me, followee=buddy).exists()
    r = c.get(f"/profile/{buddy.id}", secure=True)
    assert r.status_code == 200
    assert "Отписаться".encode() in r.content or "Подписаться".encode() in r.content
    ok("subscribe follow")

    r = c.post(f"/profile/{me.id}/milestones", {
        "title": f"QA Milestone {uuid.uuid4().hex[:5]}",
        "occurred_on": f"{date.today().year}-06-15",
        "kind": "life",
        "body": "probe",
    }, secure=True)
    assert r.status_code in (301, 302)
    ms = TimelineMilestone.objects.filter(social_user=me, title__startswith="QA Milestone").order_by("-id").first()
    assert ms
    r = c.get(f"/profile/{me.id}?tab=timeline&y={ms.occurred_on.year}", secure=True)
    assert r.status_code == 200
    assert "Лента жизни".encode() in r.content
    assert ms.title.encode() in r.content
    assert b"page-tabs" not in r.content
    feed = news_items(me, limit=80)
    assert any(i.get("kind") == "milestone" and i.get("milestone") and i["milestone"].id == ms.id for i in feed)
    ok("timeline milestone + feed")

    # Profile cover on same media disk (classic picture section)
    from django.core.files.uploadedfile import SimpleUploadedFile
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
    )
    prev = me.cover_path
    r = c.post("/profile/cover", {
        "cover": SimpleUploadedFile("cover.png", png, content_type="image/png"),
        "next": "/profile/edit?section=picture",
    }, secure=True)
    assert r.status_code in (301, 302), r.status_code
    me.refresh_from_db()
    assert me.cover_path and me.cover_path.startswith("covers/"), me.cover_path
    r = c.get(f"/profile/{me.id}?tab=timeline", secure=True)
    assert r.status_code == 200 and b"<img" in r.content
    r = c.post("/profile/cover/clear", {"next": "/profile/edit?section=picture"}, secure=True)
    assert r.status_code in (301, 302)
    me.refresh_from_db()
    assert not me.cover_path
    if prev:
        me.cover_path = prev
        me.save(update_fields=["cover_path"])
    ok("profile cover upload + clear")

    r = c.get("/feed", secure=True)
    assert r.status_code == 200
    assert "Лента событий".encode("utf-8") in r.content
    ticker = e11.ticker_items(me, 12)
    assert isinstance(ticker, list)
    ok("ticker rail")

    # Messenger-era inbox: reply + sticker columns usable
    from apps.social import chat as ch
    from apps.social.gifts import catalog
    peer = buddy
    if ch.can_dm(me, peer) is None:
        conv = ch.dm_find_or_create(me, peer)
        m1 = ch.post_message(me, conv, f"QA reply root {uuid.uuid4().hex[:4]}")
        stickers = catalog()
        sid = stickers[0].id if stickers else None
        m2 = ch.post_message(me, conv, "QA reply child", reply_to_id=m1.id, sticker_id=sid)
        assert m2.reply_to_id == m1.id
        if sid:
            assert m2.sticker_id == sid
        rows, _ = ch.thread(conv, limit=20)
        assert any(getattr(x, "reply_to_id", None) == m1.id for x in rows)
        Message.objects.filter(pk__in=[m1.id, m2.id]).delete()
        ok("inbox reply + sticker")
    else:
        ok("inbox reply skipped (not friends)")

    # cleanup
    OgStory.objects.filter(pk=og.id).delete()
    TimelineMilestone.objects.filter(pk=ms.id).delete()
    ProfileFollow.objects.filter(follower=me, followee=buddy).delete()
    ok("cleanup")
    print("ALL 2011 classic modules probes passed")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FAIL", e)
        raise
