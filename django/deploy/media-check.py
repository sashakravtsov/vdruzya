#!/usr/bin/env python
"""Smoke: classic media pipeline — Pillow photos + video file upload."""
import os
import sys
import uuid

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

import shutil
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Q
from django.test import Client

from apps.accounts.models import User
from apps.social import chat as ch
from apps.social.media import process_image_bytes, save_video
from apps.social.models import (
    Album, Community, CommunityMember, CommunityPost, Company, CompanyAdmin,
    Friendship, Message, Photo, Post,
)
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
    # Django test Client: no files= kwarg; multi-file = list under one key in data.
    data = {
        "title": "Batch",
        "photo": [
            SimpleUploadedFile("a.png", PNG, content_type="image/png"),
            SimpleUploadedFile("b.png", PNG, content_type="image/png"),
        ],
    }
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

    # Wall compose: one video via the same photo field (FileField).
    wall_title = f"wallvid-{uuid.uuid4().hex[:5]}"
    vid2 = SimpleUploadedFile("wall.mp4", _tiny_mp4(), content_type="video/mp4")
    r = c.post("/posts", {
        "body": wall_title,
        "wall_to": str(me.id),
        "photo": vid2,
    }, secure=True)
    assert r.status_code in (301, 302), r.status_code
    wpost = (
        Post.objects.filter(social_user=me, kind="video", topic=f"wall:{me.id}")
        .order_by("-id").first()
    )
    assert wpost and (wpost.body or "").startswith("storage:"), wpost
    assert wall_title in (wpost.body or "")
    r = c.get(f"/posts/{wpost.id}", secure=True)
    assert r.status_code == 200
    assert b"<video" in r.content
    ok("wall compose video + player")

    # Group wall video (discussion topics stay photo-only).
    gpost = None
    membership = (
        CommunityMember.objects.filter(social_user=me)
        .select_related("community").order_by("-id").first()
    )
    if membership:
        group = membership.community
        gbody = f"gvid-{uuid.uuid4().hex[:5]}"
        vid3 = SimpleUploadedFile("gwall.mp4", _tiny_mp4(), content_type="video/mp4")
        r = c.post(f"/groups/{group.id}/posts", {
            "body": gbody,
            "board": "wall",
            "photo": vid3,
        }, secure=True)
        assert r.status_code in (301, 302), r.status_code
        gpost = (
            CommunityPost.objects.filter(
                community=group, social_user=me, kind="video", topic="wall",
            ).order_by("-id").first()
        )
        assert gpost and (gpost.body or "").startswith("storage:"), gpost
        r = c.get(f"/groups/{group.id}?tab=wall", secure=True)
        assert r.status_code == 200
        assert b"<video" in r.content
        ok("group wall video + player")
    else:
        ok("group wall video skipped (no membership)")

    # Page wall video (admin compose) + hydrate on page show.
    ppage = None
    pp_post = None
    admin_row = (
        CompanyAdmin.objects.filter(social_user=me)
        .select_related("company").order_by("-id").first()
    )
    if admin_row:
        ppage = admin_row.company
        pbody = f"pvid-{uuid.uuid4().hex[:5]}"
        vidp = SimpleUploadedFile("page.mp4", _tiny_mp4(), content_type="video/mp4")
        r = c.post(f"/pages/{ppage.id}/posts", {
            "body": pbody,
            "photo": vidp,
        }, secure=True)
        assert r.status_code in (301, 302), r.status_code
        pp_post = (
            Post.objects.filter(
                social_user=me, kind="video", topic=ppage.topic_key,
            ).order_by("-id").first()
        )
        assert pp_post and (pp_post.body or "").startswith("storage:"), pp_post
        r = c.get(f"/pages/{ppage.id}", secure=True)
        assert r.status_code == 200
        assert b"<video" in r.content
        assert b"page-tabs" not in r.content
        ok("page wall video + player")
    else:
        ok("page wall video skipped (no admin page)")

    # Classic Inbox — video attachment (not live Messenger).
    inbox_msg = None
    rel = (
        Friendship.objects.filter(status="accepted")
        .filter(Q(user=me) | Q(friend=me))
        .select_related("user", "friend")
        .first()
    )
    if rel:
        other = rel.friend if rel.user_id == me.id else rel.user
        conv = ch.dm_find_or_create(me, other)
        vid4 = SimpleUploadedFile("inbox.mp4", _tiny_mp4(), content_type="video/mp4")
        r = c.post(f"/inbox/{conv.id}/message", {
            "body": f"QA inbox vid {uuid.uuid4().hex[:5]}",
            "photo": vid4,
        }, secure=True)
        assert r.status_code in (301, 302), r.status_code
        inbox_msg = (
            Message.objects.filter(conversation=conv, social_user=me, message_type="video")
            .order_by("-id").first()
        )
        assert inbox_msg and inbox_msg.attachment_path, inbox_msg
        r = c.get(f"/inbox?c={conv.id}", secure=True)
        assert r.status_code == 200
        assert b"<video" in r.content
        ok("inbox video attachment + player")
    else:
        ok("inbox video skipped (no friend)")

    # Optional ffmpeg poster (same media disk — not a video CDN).
    ffmpeg = getattr(settings, "FFMPEG_BIN", "ffmpeg") or "ffmpeg"
    if shutil.which(ffmpeg):
        with tempfile.TemporaryDirectory(prefix="vdposter_") as tmp:
            src = Path(tmp) / "clip.mp4"
            subprocess.run(
                [
                    ffmpeg, "-y", "-loglevel", "error",
                    "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=1",
                    "-pix_fmt", "yuv420p", str(src),
                ],
                check=True, timeout=60, capture_output=True,
            )
            upload = SimpleUploadedFile("clip.mp4", src.read_bytes(), content_type="video/mp4")
            _path, poster = save_video(upload, "videos")
            assert poster, poster
        ok("ffmpeg video poster")
    else:
        ok("ffmpeg video poster skipped (no ffmpeg)")

    Photo.objects.filter(album=album).delete()
    album.delete()
    post.delete()
    wpost.delete()
    if gpost:
        gpost.delete()
    if pp_post:
        pp_post.delete()
    if inbox_msg:
        inbox_msg.delete()
    ok("cleanup")
    print("ALL media pipeline probes passed")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FAIL", e)
        raise
