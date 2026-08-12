#!/usr/bin/env python
"""Smoke probe: classic Events."""
import os
import sys
from datetime import timedelta

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.test import Client

from apps.accounts.models import User
from apps.social import events as ev
from apps.social.models import Event, EventAttendee, SocialProfile
from apps.social.services import now, profile_of


def ok(label):
    print(f"OK   {label}")


def main():
    u = User.objects.filter(email="alexandr@vdruzya.ru").first() or User.objects.first()
    assert u, "no user"
    me = profile_of(u)
    friend = SocialProfile.objects.exclude(id=me.id).order_by("id").first()

    c = Client(HTTP_HOST="vdruzya.ru")
    c.force_login(u)
    created = []

    try:
        r = c.get("/events", secure=True)
        assert r.status_code == 200 and "События".encode() in r.content
        assert "Ближайшие".encode() in r.content
        assert b"datetime-local" not in r.content
        assert "ДД.ММ.ГГГГ".encode() in r.content
        assert b'id="tabs"' in r.content and b"page-tabs" not in r.content
        assert b'name="title"' in r.content  # EventForm
        assert b"event-list-row" in r.content or "Нет событий".encode() in r.content
        ok("events home")

        starts = (now() + timedelta(days=2)).strftime("%d.%m.%Y %H:%M")
        r = c.post("/events", {
            "title": "QA Event Night",
            "place": "Москва",
            "description": "Тест classic events",
            "starts_at": starts,
        }, secure=True)
        assert r.status_code in (301, 302)
        event = Event.objects.filter(title="QA Event Night", host=me).order_by("-id").first()
        assert event and event.description
        created.append(event.id)
        ok("create event with host")

        r = c.get(f"/events/{event.id}", secure=True)
        assert r.status_code == 200 and b"QA Event Night" in r.content
        assert "Иду".encode() in r.content and "Возможно".encode() in r.content
        assert b"friends-main" not in r.content and b"event-main" in r.content
        assert "✓".encode() not in r.content
        ok("event detail")

        r = c.post(f"/events/{event.id}/rsvp", {"status": "maybe"}, secure=True)
        assert r.status_code in (301, 302)
        assert EventAttendee.objects.filter(event=event, social_user=me, status="maybe").exists()
        ok("rsvp maybe")

        r = c.post(f"/events/{event.id}/rsvp", {"status": "going"}, secure=True)
        assert EventAttendee.objects.filter(event=event, social_user=me, status="going").exists()
        ok("rsvp going")

        r = c.get("/events?tab=going", secure=True)
        assert r.status_code == 200 and b"QA Event Night" in r.content
        ok("tab going")

        r = c.get("/events?tab=hosting", secure=True)
        assert r.status_code == 200 and b"QA Event Night" in r.content
        ok("tab hosting")

        if friend:
            from apps.social.models import Friendship
            if me.id not in __import__("apps.social.services", fromlist=["friend_ids"]).friend_ids(friend):
                Friendship.objects.filter(
                    user_id__in=[me.id, friend.id], friend_id__in=[me.id, friend.id]
                ).delete()
                t = now()
                Friendship.objects.create(user=me, friend=friend, status="accepted", created_at=t, updated_at=t)
                Friendship.objects.create(user=friend, friend=me, status="accepted", created_at=t, updated_at=t)
            r = c.post(f"/events/{event.id}/invite", {"friends": [str(friend.id)]}, secure=True)
            assert r.status_code in (301, 302)
            assert EventAttendee.objects.filter(event=event, social_user=friend, status="maybe").exists()
            ok("invite friend")
        else:
            ok("invite friend skipped (no other profile)")

        # Event wall + photos
        r = c.get(f"/events/{event.id}?tab=wall", secure=True)
        assert r.status_code == 200
        assert b"?tab=wall" in r.content and b"?tab=photos" in r.content
        assert "Стена".encode() in r.content
        r = c.post(f"/events/{event.id}/posts", {
            "body": "__event_wall_probe__",
            "next": f"/events/{event.id}?tab=wall",
        }, secure=True)
        assert r.status_code in (301, 302)
        from apps.social.models import Post
        ep = Post.objects.filter(topic=f"event:{event.id}", body="__event_wall_probe__").first()
        assert ep
        r = c.get(f"/events/{event.id}?tab=wall", secure=True)
        assert b"__event_wall_probe__" in r.content
        ok("event wall post")
        Post.objects.filter(pk=ep.id).delete()

        # Host edit
        r = c.get(f"/events/{event.id}/edit", secure=True)
        assert r.status_code == 200 and b'name="title"' in r.content
        starts = (now() + timedelta(days=3)).strftime("%d.%m.%Y %H:%M")
        r = c.post(f"/events/{event.id}/edit", {
            "title": "QA Event Night Edited",
            "place": "СПб",
            "description": "edited",
            "starts_at": starts,
        }, secure=True)
        assert r.status_code in (301, 302)
        event.refresh_from_db()
        assert event.title == "QA Event Night Edited" and event.place == "СПб"
        ok("event host edit")

        from apps.social.services import bump_news, news_items
        bump_news()
        feed = news_items(me, limit=80)
        assert any(i.get("kind") == "event_created" and i.get("event") and i["event"].id == event.id for i in feed)
        ok("event created in news feed")

        if friend:
            # friend going → feed story for me
            from apps.social.models import EventAttendee
            t = now()
            EventAttendee.objects.update_or_create(
                event=event, social_user=friend,
                defaults={"status": "going", "created_at": t, "updated_at": t},
            )
            bump_news()
            feed = news_items(me, limit=80)
            assert any(
                i.get("kind") == "event_going" and i.get("event") and i["event"].id == event.id
                and i.get("actor") and i["actor"].id == friend.id
                for i in feed
            )
            ok("event going in news feed")
        else:
            ok("event going in news feed skipped")

        print("ALL events probes passed")
        return 0
    finally:
        if created:
            from apps.social.models import Post
            Post.objects.filter(topic__in=[f"event:{i}" for i in created]).delete()
            EventAttendee.objects.filter(event_id__in=created).delete()
            Event.objects.filter(id__in=created).delete()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print("FAIL", e, file=sys.stderr)
        raise
