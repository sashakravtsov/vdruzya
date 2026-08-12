#!/usr/bin/env python
"""Smoke: classic 2006–09 modules wave (networks/links/notes/videos/market/lists/blocked/mobile)."""
import os
import sys
import uuid

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.test import Client

from apps.accounts.models import User
from apps.social.models import FriendList, MarketplaceListing, Post
from apps.social.services import news_items, profile_of


def ok(label):
    print(f"OK   {label}")


def main():
    from django.db import connection
    with connection.cursor() as cur:
        for t in ("friend_lists", "friend_list_members", "marketplace_listings", "photo_tags"):
            cur.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name=%s", [t]
            )
            assert cur.fetchone(), f"missing {t} — run ensure-classic-modules.py"
    ok("schema lists+market+tags")

    u = User.objects.filter(email="alexandr@vdruzya.ru").first() or User.objects.first()
    assert u
    me = profile_of(u)
    c = Client(HTTP_HOST="vdruzya.ru")
    c.force_login(u)

    for path, needle in (
        ("/networks", "Сети"),
        ("/notes", "Заметки"),
        ("/links", "Ссылки"),
        ("/videos", "Видео"),
        ("/marketplace", "Барахолка"),
        ("/friends/lists", "Списки"),
        ("/blocked", "Чёрный список"),
        ("/mobile", "Мобильная"),
        ("/apps", "Барахолка"),
    ):
        r = c.get(path, secure=True)
        assert r.status_code == 200, path
        assert needle.encode() in r.content, path
        assert b' required' not in r.content and b'required="' not in r.content
        assert b"placeholder=" not in r.content, path
    ok("module pages render")

    # link post
    r = c.post("/links", {
        "title": "QA Link",
        "url": "https://example.com/qa",
        "blurb": "probe",
        "visibility": "friends",
    }, secure=True)
    assert r.status_code in (301, 302)
    link = Post.objects.filter(social_user=me, kind="link", media_label="QA Link").order_by("-id").first()
    assert link
    feed = news_items(me, limit=80)
    assert any(i.get("kind") == "link" and i.get("post") and i["post"].id == link.id for i in feed)
    ok("link in news feed")

    # notes browse create
    r = c.post("/notes", {
        "title": "QA Note Dir",
        "body": "note body probe",
        "visibility": "friends",
    }, secure=True)
    assert r.status_code in (301, 302)
    note = Post.objects.filter(social_user=me, kind="note", media_label="QA Note Dir").first()
    assert note
    ok("notes directory create")

    # marketplace
    r = c.post("/marketplace", {
        "title": f"QA Bike {uuid.uuid4().hex[:5]}",
        "price": "1000",
        "place": "Москва",
        "description": "велосипед",
    }, secure=True)
    assert r.status_code in (301, 302)
    item = MarketplaceListing.objects.filter(social_user=me, title__startswith="QA Bike").order_by("-id").first()
    assert item
    r = c.get(f"/marketplace/{item.id}", secure=True)
    assert r.status_code == 200 and "велосипед".encode() in r.content
    feed = news_items(me, limit=80)
    assert any(i.get("kind") == "market" and i.get("listing") and i["listing"].id == item.id for i in feed)
    r = c.get("/marketplace?mine=1", secure=True)
    assert r.status_code == 200 and item.title.encode() in r.content
    r = c.post(f"/marketplace/{item.id}/edit", {
        "title": item.title, "price": "1200", "place": "Москва", "description": "велосипед edited",
    }, secure=True)
    assert r.status_code in (301, 302)
    item.refresh_from_db()
    assert item.price == "1200" and "edited" in item.description
    ok("marketplace listing + edit + feed + mine")

    # video post
    r = c.post("/videos", {
        "title": "QA Video",
        "url": "https://example.com/qa.mp4",
        "blurb": "clip",
        "visibility": "friends",
    }, secure=True)
    assert r.status_code in (301, 302)
    video = Post.objects.filter(social_user=me, kind="video", media_label="QA Video").order_by("-id").first()
    assert video
    feed = news_items(me, limit=80)
    assert any(i.get("kind") == "video" and i.get("post") and i["post"].id == video.id for i in feed)
    ok("video in news feed")

    # friend list
    r = c.post("/friends/lists", {"name": f"QA List {uuid.uuid4().hex[:4]}"}, secure=True)
    assert r.status_code in (301, 302)
    fl = FriendList.objects.filter(social_user=me, name__startswith="QA List").order_by("-id").first()
    assert fl
    from apps.social.models import FriendListMember, SocialProfile
    from apps.social.services import friend_ids
    buddy = SocialProfile.objects.filter(id__in=friend_ids(me)).exclude(id=me.id).first()
    if buddy:
        r = c.post(f"/friends/lists/{fl.id}", {"action": "add", "friend_id": str(buddy.id)}, secure=True)
        assert r.status_code in (301, 302)
        assert FriendListMember.objects.filter(friend_list=fl, social_user=buddy).exists()
        r = c.post(f"/friends/lists/{fl.id}", {"action": "remove", "friend_id": str(buddy.id)}, secure=True)
        assert r.status_code in (301, 302)
        assert not FriendListMember.objects.filter(friend_list=fl, social_user=buddy).exists()
        ok("friend list membership")
    else:
        ok("friend list membership skipped (no friend)")

    # cleanup
    Post.objects.filter(id__in=[x.id for x in (link, note, video) if x]).delete()
    item.delete()
    FriendListMember.objects.filter(friend_list=fl).delete()
    fl.delete()
    ok("cleanup")
    print("ALL classic modules probes passed")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FAIL", e)
        raise
