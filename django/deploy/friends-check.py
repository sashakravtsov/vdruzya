#!/usr/bin/env python
"""Smoke probe: friends / people FB 2005 parity."""
import os
import sys
import uuid

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.test import Client

from apps.accounts.models import User
from apps.social.models import Block, Friendship, SocialProfile
from apps.social.services import friend_ids, now, profile_of


def ok(label):
    print(f"OK   {label}")


def _make(name, city="Москва"):
    email = f"qa.friends.{uuid.uuid4().hex[:8]}@vdruzya.ru"
    u = User(email=email, name=name)
    u.set_password("TempQaFriends2026!")
    u.save()
    t = now()
    p = SocialProfile.objects.create(
        user=u, name=name, slug=f"qa-friend-{u.id}",
        city=city, avatar_color="#3B5998",
        created_at=t, updated_at=t, onboarding_completed_at=t,
    )
    return u, p


def _link(a, b):
    t = now()
    Friendship.objects.update_or_create(
        user=a, friend=b, defaults={"status": "accepted", "created_at": t, "updated_at": t},
    )
    Friendship.objects.update_or_create(
        user=b, friend=a, defaults={"status": "accepted", "created_at": t, "updated_at": t},
    )


def main():
    u = User.objects.filter(email="alexandr@vdruzya.ru").first() or User.objects.first()
    assert u, "no user"
    me = profile_of(u)
    other_user, other = _make("QA Friend")
    mid_user, mid = _make("QA Mutual")

    Friendship.objects.filter(
        user_id__in=[me.id, other.id, mid.id], friend_id__in=[me.id, other.id, mid.id]
    ).delete()
    Block.objects.filter(blocker_id__in=[me.id, other.id], blocked_id__in=[me.id, other.id]).delete()

    c = Client(HTTP_HOST="vdruzya.ru")
    c.force_login(u)

    try:
        r = c.get("/people", secure=True)
        assert r.status_code == 200 and "Поиск людей".encode() in r.content
        assert "Люди, которых вы можете знать".encode() not in r.content
        assert b'id="tabs"' in r.content and b"page-tabs" not in r.content
        assert b'placeholder=' not in r.content
        ok("people find friends search")

        r = c.get("/friends", secure=True)
        assert r.status_code == 200 and "Мои друзья".encode() in r.content
        assert "Заявки".encode() in r.content
        assert "Люди, которых вы можете знать".encode() not in r.content
        assert "Найти друга".encode() in r.content
        ok("friends home page")

        r = c.get("/friends?q=Анна&sort=recent", secure=True)
        assert r.status_code == 200
        ok("friends search+sort")

        r = c.get("/people?tab=friends", secure=True)
        assert r.status_code in (301, 302)
        assert "/friends" in (r.url or r["Location"])
        ok("people tab=friends redirects")

        r = c.get("/people?tab=requests", secure=True)
        assert r.status_code == 200
        ok("requests tab")

        r = c.get("/people?tab=search&q=QA&city=Москва", secure=True)
        assert r.status_code == 200 and b"QA Friend" in r.content
        ok("search tab filters")

        r = c.get("/search?q=QA", secure=True)
        assert r.status_code == 200 and b'id="tabs"' in r.content
        assert "Люди".encode() in r.content and "Группы".encode() in r.content
        assert b"placeholder=" not in r.content
        ok("global search tabs")

        r = c.get("/invite", secure=True)
        assert r.status_code == 200 and b"/i/" in r.content
        me.refresh_from_db()
        assert me.invite_code
        ok("invite mine")

        r = c.post(f"/friends/{other.id}/request", {"next": "/people"}, secure=True)
        assert r.status_code in (301, 302)
        assert Friendship.objects.filter(user=me, friend=other, status="pending").exists()
        ok("friend request")

        c2 = Client(HTTP_HOST="vdruzya.ru")
        c2.force_login(other_user)
        r = c2.post(f"/friends/{me.id}/accept", {"next": "/people?tab=requests"}, secure=True)
        assert r.status_code in (301, 302)
        assert Friendship.objects.filter(user=other, friend=me, status="accepted").exists()
        assert Friendship.objects.filter(user=me, friend=other, status="accepted").exists()
        assert other.id in friend_ids(me)
        ok("friend accept reciprocal")

        _link(me, mid)
        _link(other, mid)
        r = c.get(f"/profile/{other.id}/mutual", secure=True)
        assert r.status_code == 200 and b"QA Mutual" in r.content
        assert "общий".encode() in r.content or "общих".encode() in r.content
        ok("mutual friends page")

        r = c.get(f"/profile/{other.id}", secure=True)
        assert r.status_code == 200 and f"/profile/{other.id}/mutual".encode() in r.content
        ok("profile mutual link")

        # Confirm Friends shows mutuals on pending
        Friendship.objects.filter(user_id__in=[me.id, mid.id], friend_id__in=[me.id, mid.id]).delete()
        Friendship.objects.create(user=mid, friend=me, status="pending", created_at=now(), updated_at=now())
        _link(mid, other)  # mid+other still linked; me+other friends → mutual for pending mid
        r = c.get("/friends", secure=True)
        assert r.status_code == 200 and b"QA Mutual" in r.content
        assert "общий".encode() in r.content or "общих".encode() in r.content
        ok("pending shows mutuals")
        Friendship.objects.filter(user=mid, friend=me, status="pending").delete()

        # Friends list privacy: stranger cannot browse
        Friendship.objects.filter(
            user_id__in=[me.id, other.id], friend_id__in=[me.id, other.id]
        ).delete()
        r = c.get(f"/profile/{other.id}/friends", secure=True)
        assert r.status_code == 403 and "только друзьям".encode() in r.content
        ok("friends list private to non-friends")
        _link(me, other)
        r = c.get(f"/profile/{other.id}/friends", secure=True)
        assert r.status_code == 200
        ok("friends list visible to friends")

        # School Find Friends filter
        from apps.social.models import Education
        Education.objects.filter(social_user=other).delete()
        Education.objects.create(social_user=other, institution="МГУ QA School")
        r = c.get("/people?tab=search&school=МГУ", secure=True)
        assert r.status_code == 200 and b"QA Friend" in r.content
        ok("school search filter")
        Education.objects.filter(social_user=other).delete()

        r = c.post(f"/friends/{other.id}/remove", {"next": "/friends"}, secure=True)
        assert not Friendship.objects.filter(user=me, friend=other).exists()
        ok("friend remove")

        _link(me, other)
        r = c.post(f"/friends/{other.id}/block", {"next": "/friends"}, secure=True)
        assert Block.objects.filter(blocker=me, blocked=other).exists()
        assert not Friendship.objects.filter(user=me, friend=other).exists()
        ok("friend block")

        r = c.post(f"/friends/{other.id}/block/remove", {"next": "/friends"}, secure=True)
        assert not Block.objects.filter(blocker=me, blocked=other).exists()
        ok("friend unblock")

        r = c2.post(f"/friends/{me.id}/accept", {}, secure=True)
        assert r.status_code == 403
        ok("accept without pending 403")

        from apps.social import friendship as fr
        fr.block_user(me, other)
        r = c2.post(f"/friends/{me.id}/request", {}, secure=True)
        assert r.status_code == 403
        ok("block prevents friend request 403")
        r = c2.get(f"/profile/{me.id}", secure=True)
        assert r.status_code == 403 and "недоступно".encode() in r.content
        ok("block prevents profile view 403")
        fr.unblock_user(me, other)

        c.post(f"/friends/{other.id}/request", {}, secure=True)
        r = c.post(f"/friends/{other.id}/cancel", {"next": f"/profile/{other.id}"}, secure=True)
        assert r.status_code in (301, 302)
        assert not Friendship.objects.filter(user=me, friend=other, status="pending").exists()
        ok("friend cancel")

        r = c.get(f"/profile/{me.id}/friends", secure=True)
        assert r.status_code == 200
        ok("profile friends")

        # classic poke
        _link(me, other)
        r = c.post(f"/profile/{other.id}/poke", {}, secure=True)
        assert r.status_code in (301, 302)
        from apps.social.models import Notification
        assert Notification.objects.filter(social_user=other, type="poke", url=f"/profile/{me.id}").exists()
        ok("poke")

        guest = Client(HTTP_HOST="vdruzya.ru")
        from apps.social.friendship import ensure_invite_code
        code = ensure_invite_code(me)
        r = guest.get(f"/i/{code}", secure=True)
        assert r.status_code == 200 and me.name.encode() in r.content
        assert r.cookies.get("vdruzya_invite").value == code
        ok("invite show guest + cookie")

        print("ALL friends probes passed")
        return 0
    finally:
        ids = [me.id, other.id, mid.id]
        Friendship.objects.filter(user_id__in=ids, friend_id__in=ids).delete()
        Block.objects.filter(blocker_id__in=ids, blocked_id__in=ids).delete()
        from apps.social.models import Notification
        Notification.objects.filter(social_user_id__in=ids, type="poke").delete()
        SocialProfile.objects.filter(pk__in=[other.id, mid.id]).delete()
        User.objects.filter(pk__in=[other_user.id, mid_user.id]).delete()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print("FAIL", e, file=sys.stderr)
        raise
