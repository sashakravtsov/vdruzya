#!/usr/bin/env python
"""Smoke: classic 2006–09 modules wave (networks/links/notes/videos/market/lists/blocked/mobile)."""
import os
import sys
import uuid

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from apps.accounts.models import User
from apps.social.models import FriendList, MarketplaceListing, Post
from apps.social.services import news_items, profile_of

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)


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
        cur.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='marketplace_listings' AND column_name='photo_path'"
        )
        assert cur.fetchone(), "marketplace_listings.photo_path — run ensure-classic-modules.py"
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

    # notes photo on same media disk
    ntitle = f"QA NotePhoto {uuid.uuid4().hex[:5]}"
    r = c.post("/notes", {
        "title": ntitle,
        "body": "note with photo",
        "visibility": "friends",
        "photo": SimpleUploadedFile("note.png", PNG, content_type="image/png"),
    }, secure=True)
    assert r.status_code in (301, 302), r.status_code
    nphoto = Post.objects.filter(social_user=me, kind="note", media_label=ntitle).first()
    assert nphoto and nphoto.media_path and nphoto.media_path.startswith("notes/"), nphoto
    assert nphoto.media_url
    r = c.get(f"/posts/{nphoto.id}", secure=True)
    assert r.status_code == 200 and b"<img" in r.content
    r = c.get("/notes?mine=1", secure=True)
    assert r.status_code == 200 and b"note-thumb" in r.content
    nphoto.delete()
    ok("notes photo attach")

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

    # marketplace photo on same media disk as wall photos
    mtitle = f"QA MarketPhoto {uuid.uuid4().hex[:5]}"
    r = c.post("/marketplace", {
        "title": mtitle,
        "price": "500",
        "place": "СПб",
        "description": "с фото",
        "photo": SimpleUploadedFile("m.png", PNG, content_type="image/png"),
    }, secure=True)
    assert r.status_code in (301, 302), r.status_code
    mitem = MarketplaceListing.objects.filter(social_user=me, title=mtitle).first()
    assert mitem and mitem.photo_path and mitem.photo_path.startswith("market/"), mitem
    assert mitem.photo_url
    r = c.get(f"/marketplace/{mitem.id}", secure=True)
    assert r.status_code == 200 and b"<img" in r.content
    assert mitem.photo_path.encode() in r.content or mitem.photo_url.encode() in r.content
    r = c.get("/marketplace", secure=True)
    assert r.status_code == 200 and b"market-thumb" in r.content
    mitem.delete()
    ok("marketplace listing photo")

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
        r = c.get(f"/friends?list={fl.id}", secure=True)
        assert r.status_code == 200
        assert buddy.name.encode() in r.content
        assert b"friends-list-tabs" in r.content or fl.name.encode() in r.content
        r = c.get(f"/feed?filter=photos&list={fl.id}", secure=True)
        assert r.status_code == 200
        assert b"feed-filters" in r.content
        r = c.post(f"/friends/lists/{fl.id}", {"action": "remove", "friend_id": str(buddy.id)}, secure=True)
        assert r.status_code in (301, 302)
        assert not FriendListMember.objects.filter(friend_list=fl, social_user=buddy).exists()
        ok("friend list membership + feed/friends filters")
    else:
        ok("friend list membership skipped (no friend)")
    r = c.get("/feed?filter=shares", secure=True)
    assert r.status_code == 200 and b"feed-filters" in r.content
    ok("feed kind filters")

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
