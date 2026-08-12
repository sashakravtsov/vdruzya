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
    ok("marketplace listing")

    # friend list
    r = c.post("/friends/lists", {"name": f"QA List {uuid.uuid4().hex[:4]}"}, secure=True)
    assert r.status_code in (301, 302)
    fl = FriendList.objects.filter(social_user=me, name__startswith="QA List").order_by("-id").first()
    assert fl
    ok("friend list create")

    # cleanup
    Post.objects.filter(id__in=[link.id, note.id]).delete()
    item.delete()
    from apps.social.models import FriendListMember
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
