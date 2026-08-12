#!/usr/bin/env python
"""Smoke: classic media pipeline — Pillow photos + video file upload."""
import os
import sys
import uuid

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.utils.datastructures import MultiValueDict

from apps.accounts.models import User
from apps.social.media import process_image_bytes
from apps.social.models import Album, Photo, Post
from apps.social.services import bump_news, news_items, now, profile_of

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)


def ok(label):
    print(f"OK   {label}")


def _tiny_mp4() -> bytes:
    return b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 64


def main():
    data, ext = process_image_bytes(PNG, filename="x.png")
    assert data and ext in (".png", ".jpg", ".gif")
    ok("pillow process")

    u = User.objects.filter(email="alexandr@vdruzya.ru").first() or User.objects.first()
    assert u
    me = profile_of(u)
    c = Client(HTTP_HOST="vdruzya.ru")
    c.force_login(u)

    t = now()
    album = Album.objects.create(
        social_user=me, title=f"QA Media {uuid.uuid4().hex[:5]}",
        description="", visibility="public", created_at=t, updated_at=t,
    )
    # Django test Client has no files= kwarg — put uploads in data (MultiValueDict).
    data = MultiValueDict({
        "title": ["Batch"],
        "photo": [
            SimpleUploadedFile("a.png", PNG, content_type="image/png"),
            SimpleUploadedFile("b.png", PNG, content_type="image/png"),
        ],
    })
    r = c.post(
        f"/albums/{album.id}/photos", data, secure=True, follow=True,
    )
    assert r.status_code == 200
    n = Photo.objects.filter(album=album, title="Batch").count()
    assert n >= 2, n
    ok("multi photo album upload")

    r = c.get("/videos", secure=True)
    assert r.status_code == 200
    assert "Видео".encode() in r.content
    assert b'type="file"' in r.content
    assert b"page-tabs" not in r.content
    ok("videos page has file input")

    title = f"QA Upload {uuid.uuid4().hex[:5]}"
    vid = SimpleUploadedFile("qa.mp4", _tiny_mp4(), content_type="video/mp4")
    r = c.post("/videos", {
        "title": title,
        "url": "",
        "blurb": "file probe",
        "visibility": "friends",
        "video": vid,
    }, secure=True)
    assert r.status_code in (301, 302), r.status_code
    post = (
        Post.objects.filter(social_user=me, kind="video", media_label=title)
        .order_by("-id").first()
    )
    assert post and (post.body or "").startswith("storage:"), post
    bump_news()
    feed = news_items(me, limit=80)
    assert any(i.get("kind") == "video" and i.get("post") and i["post"].id == post.id for i in feed)
    r = c.get(f"/posts/{post.id}", secure=True)
    assert r.status_code == 200
    assert b"<video" in r.content
    ok("video file upload + player")

    Photo.objects.filter(album=album).delete()
    album.delete()
    post.delete()
    ok("cleanup")
    print("ALL media pipeline probes passed")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FAIL", e)
        raise
