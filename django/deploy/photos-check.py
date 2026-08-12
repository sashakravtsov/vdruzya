#!/usr/bin/env python
"""Smoke probe: albums / photos FB 2006 parity."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from apps.accounts.models import User
from apps.social.albums import albums_for, can_view, visible_q
from apps.social.models import Album, Photo, SocialProfile
from apps.social.services import friend_ids, now, profile_of

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)


def ok(label):
    print(f"OK   {label}")


def main():
    u = User.objects.filter(email="alexandr@vdruzya.ru").first() or User.objects.first()
    assert u, "no user"
    me = profile_of(u)
    c = Client(HTTP_HOST="vdruzya.ru")
    c.force_login(u)

    r = c.get("/albums", secure=True)
    assert r.status_code == 200 and "Мои альбомы".encode() in r.content
    assert b"album-index" in r.content
    assert b"album-card" not in r.content
    assert b"album-fb" not in r.content
    assert b"albums_user" not in r.content  # single albums template
    ok("albums index")

    r = c.get("/compose/album-photos", secure=True)
    assert r.status_code == 404
    ok("compose album-photos gone")

    t = now()
    a = Album.objects.create(
        social_user=me, title="QA Photos", description="probe", visibility="public",
        created_at=t, updated_at=t,
    )
    r = c.get(f"/albums/{a.id}", secure=True)
    assert r.status_code == 200 and b"QA Photos" in r.content and "Добавить фото".encode() in r.content
    ok("album show owner")

    guest = Client(HTTP_HOST="vdruzya.ru")
    r = guest.get(f"/albums/{a.id}", secure=True)
    assert r.status_code == 200 and b"QA Photos" in r.content
    ok("public album guest")

    a.visibility = "friends"
    a.save(update_fields=["visibility"])
    r = guest.get(f"/albums/{a.id}", secure=True)
    assert r.status_code == 403 and "Альбом недоступен".encode() in r.content
    ok("friends album guest 403 page")

    # empty visibility ≡ friends (classic default)
    a.visibility = ""
    a.save(update_fields=["visibility"])
    assert not can_view(a, None)
    assert can_view(a, me)
    assert not Album.objects.filter(pk=a.id).filter(visible_q(None)).exists()
    ok("empty visibility ≡ friends")

    friend = SocialProfile.objects.filter(id__in=friend_ids(me)).exclude(id=me.id).first()
    if friend:
        assert can_view(a, friend)
        listed = {x.id for x in albums_for(me, friend, 40)}
        assert a.id in listed
        ok("friends album visible to friend via albums_for")
    else:
        ok("friends album friend check skipped (no friend)")

    a.visibility = "friends"
    a.save(update_fields=["visibility"])

    f = SimpleUploadedFile("p.png", PNG, content_type="image/png")
    r = c.post(f"/albums/{a.id}/photos", {"title": "Красиво", "photo": f}, secure=True, follow=True)
    assert r.status_code == 200
    ph = Photo.objects.filter(album=a, title="Красиво").first()
    assert ph and ph.path
    ok("photo upload")

    r = c.get(f"/albums/{a.id}/photos/{ph.id}", secure=True)
    assert r.status_code == 200 and "Красиво".encode() in r.content
    assert "Комментарии".encode() in r.content
    assert "полный размер".encode() in r.content
    assert b"max-height: 520px" not in r.content
    ok("photo show (full size chrome)")

    r = c.post(f"/albums/{a.id}/photos/{ph.id}/comment", {"body": "Классное фото"}, secure=True, follow=True)
    assert r.status_code == 200
    from apps.social.models import PhotoComment
    cm = PhotoComment.objects.filter(photo=ph, body="Классное фото").first()
    assert cm
    ok("photo comment")

    r = c.post(
        f"/albums/{a.id}/photos/{ph.id}/comments/{cm.id}/delete", {}, secure=True, follow=True,
    )
    assert r.status_code == 200 and not PhotoComment.objects.filter(pk=cm.id).exists()
    ok("photo comment delete")

    r = c.post(f"/albums/{a.id}/photos/{ph.id}/caption", {"title": "Новая"}, secure=True, follow=True)
    assert Photo.objects.get(pk=ph.id).title == "Новая"
    ok("photo caption")

    r = c.post(f"/albums/{a.id}/photos/{ph.id}/cover", {}, secure=True, follow=True)
    a.refresh_from_db()
    assert a.cover_path == ph.path
    ok("photo set cover")

    r = c.get(f"/albums/{a.id}/edit", secure=True)
    assert r.status_code == 200 and "Настройки".encode() in r.content
    ok("album edit")

    r = c.get(f"/profile/{me.id}/albums", secure=True)
    assert r.status_code == 200 and b"QA Photos" in r.content
    assert "Друзьям".encode() in r.content
    ok("profile albums")

    r = c.post(f"/albums/{a.id}/photos/{ph.id}/delete", {}, secure=True, follow=True)
    assert r.status_code == 200 and not Photo.objects.filter(pk=ph.id).exists()
    ok("photo delete")

    r = c.post(f"/albums/{a.id}/delete", {}, secure=True, follow=True)
    assert r.status_code == 200 and not Album.objects.filter(pk=a.id).exists()
    ok("album delete")

    print("ALL photos probes passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print("FAIL", e, file=sys.stderr)
        raise
