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


def _make_other():
    """Temp second profile for probe (prod may have only one user)."""
    email = f"qa.friends.{uuid.uuid4().hex[:8]}@vdruzya.ru"
    u = User(email=email, name="QA Friend")
    u.set_password("TempQaFriends2026!")
    u.save()
    t = now()
    p = SocialProfile.objects.create(
        user=u, name="QA Friend", slug=f"qa-friend-{u.id}",
        city="Москва", avatar_color="#3B5998",
        created_at=t, updated_at=t, onboarding_completed_at=t,
    )
    return u, p


def main():
    u = User.objects.filter(email="alexandr@vdruzya.ru").first() or User.objects.first()
    assert u, "no user"
    me = profile_of(u)
    other_user, other = _make_other()

    Friendship.objects.filter(
        user_id__in=[me.id, other.id], friend_id__in=[me.id, other.id]
    ).delete()
    Block.objects.filter(blocker=me, blocked=other).delete()

    c = Client(HTTP_HOST="vdruzya.ru")
    c.force_login(u)

    try:
        r = c.get("/people", secure=True)
        assert r.status_code == 200 and "Рекомендации".encode() in r.content
        ok("people suggested")

        r = c.get("/friends", secure=True)
        assert r.status_code == 200 and "Мои друзья".encode() in r.content
        assert "Заявки".encode() in r.content and "Рекомендации".encode() in r.content
        assert "Найти друга".encode() in r.content
        assert b"snav-profile" in r.content and "[ред.]".encode() in r.content
        ok("friends home page")

        r = c.get("/friends?q=Анна", secure=True)
        assert r.status_code == 200
        ok("friends search filter")

        r = c.get("/people?tab=friends", secure=True)
        assert r.status_code == 200 and "Мои друзья".encode() in r.content
        ok("friends tab")

        r = c.get("/people?tab=requests", secure=True)
        assert r.status_code == 200
        ok("requests tab")

        r = c.get("/people?tab=search&q=QA", secure=True)
        assert r.status_code == 200 and b"QA Friend" in r.content
        ok("search tab")

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

        r = c.post(f"/friends/{other.id}/remove", {"next": "/people?tab=friends"}, secure=True)
        assert not Friendship.objects.filter(user=me, friend=other).exists()
        ok("friend remove")

        Friendship.objects.create(user=me, friend=other, status="accepted", created_at=now(), updated_at=now())
        Friendship.objects.create(user=other, friend=me, status="accepted", created_at=now(), updated_at=now())
        r = c.post(f"/friends/{other.id}/block", {"next": "/people?tab=friends"}, secure=True)
        assert Block.objects.filter(blocker=me, blocked=other).exists()
        assert not Friendship.objects.filter(user=me, friend=other).exists()
        ok("friend block")

        r = c.post(f"/friends/{other.id}/block/remove", {"next": "/people?tab=friends"}, secure=True)
        assert not Block.objects.filter(blocker=me, blocked=other).exists()
        ok("friend unblock")

        r = c2.post(f"/friends/{me.id}/accept", {}, secure=True)
        assert r.status_code == 403
        ok("accept without pending 403")

        # block prevents request + profile
        from apps.social import friendship as fr
        fr.block_user(me, other)
        r = c2.post(f"/friends/{me.id}/request", {}, secure=True)
        assert r.status_code == 403
        ok("block prevents friend request 403")
        r = c2.get(f"/profile/{me.id}", secure=True)
        assert r.status_code == 403 and "недоступно".encode() in r.content
        ok("block prevents profile view 403")
        fr.unblock_user(me, other)

        # cancel outgoing
        c.post(f"/friends/{other.id}/request", {}, secure=True)
        r = c.post(f"/friends/{other.id}/cancel", {"next": f"/profile/{other.id}"}, secure=True)
        assert r.status_code in (301, 302)
        assert not Friendship.objects.filter(user=me, friend=other, status="pending").exists()
        ok("friend cancel")

        r = c.get(f"/profile/{me.id}/friends", secure=True)
        assert r.status_code == 200
        ok("profile friends")

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
        Friendship.objects.filter(user_id__in=[me.id, other.id], friend_id__in=[me.id, other.id]).delete()
        Block.objects.filter(blocker_id__in=[me.id, other.id], blocked_id__in=[me.id, other.id]).delete()
        SocialProfile.objects.filter(pk=other.id).delete()
        User.objects.filter(pk=other_user.id).delete()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print("FAIL", e, file=sys.stderr)
        raise
