#!/usr/bin/env python
"""Smoke probe: Gifts + Page Events."""
import os
import sys
import uuid
from datetime import datetime, timedelta

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.db.models import Q
from django.test import Client

from apps.accounts.models import User
from apps.social.models import (
    Company, CompanyAdmin, CompanyFollower, Event, EventAttendee,
    Friendship, Notification, Post, Sticker,
)
from apps.social.services import news_items, profile_of, wall_posts_for


def ok(label):
    print(f"OK   {label}")


def main():
    from django.db import connection
    with connection.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='events' AND column_name='company_id'"
        )
        assert cur.fetchone(), "events.company_id missing — run ensure-page-events.py"
    ok("schema company_id")

    u = User.objects.filter(email="alexandr@vdruzya.ru").first() or User.objects.first()
    assert u, "no user"
    me = profile_of(u)
    rel = (
        Friendship.objects.filter(status="accepted")
        .filter(Q(user=me) | Q(friend=me))
        .select_related("user", "friend")
        .first()
    )
    assert rel, "need an accepted friendship for gift probe"
    other = rel.friend if rel.user_id == me.id else rel.user

    c = Client(HTTP_HOST="vdruzya.ru")
    c.force_login(u)

    r = c.get("/gifts", secure=True)
    assert r.status_code == 200 and "Подарки".encode() in r.content
    assert b'id="tabs"' in r.content
    ok("gifts shop")

    sticker = Sticker.objects.filter(is_active=True).first()
    assert sticker, "no stickers in catalog"

    r = c.get(f"/gifts/send?to={other.id}&gift={sticker.slug}", secure=True)
    assert r.status_code == 200 and "Отправить подарок".encode() in r.content
    assert b' required' not in r.content and b'required="' not in r.content
    ok("gift send form")

    r = c.post("/gifts/send", {
        "to": str(other.id),
        "gift": sticker.slug,
        "message": "QA gift hello",
    }, secure=True)
    assert r.status_code in (301, 302)
    gift = Post.objects.filter(
        social_user=me, kind="gift", topic=f"gift:{other.id}", sticker=sticker.slug,
    ).order_by("-id").first()
    assert gift
    assert Notification.objects.filter(social_user=other, type="gift").exists()
    wall_ids = {p.id for p in wall_posts_for(me, limit=50, viewer=me)}
    assert gift.id not in wall_ids
    wall_other = {p.id for p in wall_posts_for(other, limit=50, viewer=other)}
    assert gift.id not in wall_other
    ok("send gift + isolated from walls")

    feed = news_items(me, limit=60)
    gift_stories = [
        i for i in feed
        if i.get("kind") == "gift" and i.get("post") and i["post"].id == gift.id
    ]
    assert gift_stories, "gift should appear in sender news feed"
    r = c.get("/feed", secure=True)
    assert r.status_code == 200 and sticker.title.encode() in r.content
    ok("gift in news feed")

    r = c.get(f"/profile/{other.id}?tab=wall", secure=True)
    assert r.status_code == 200 and "Подарки".encode() in r.content
    ok("profile shows gifts box")

    r = c.post("/gifts/send", {
        "to": str(other.id),
        "gift": sticker.slug,
        "message": "QA gift flash",
    }, secure=True, follow=True)
    assert r.status_code == 200
    assert "отправлен".encode() in r.content and b'class="flash"' in r.content
    ok("gift success flash on profile redirect")
    Post.objects.filter(social_user=me, kind="gift", body="QA gift flash").delete()

    r = c.get("/apps", secure=True)
    assert "Подарки".encode() in r.content
    ok("apps lists gifts")

    name = f"QA PageEvt {uuid.uuid4().hex[:6]}"
    r = c.post("/pages", {
        "name": name, "industry": "brand", "city": "Москва", "description": "evt",
    }, secure=True)
    page = Company.objects.filter(name=name).first()
    assert page
    starts = (datetime.now() + timedelta(days=14)).strftime("%d.%m.%Y 19:00")
    r = c.post(f"/pages/{page.id}/events", {
        "title": "QA Page Concert",
        "place": "Клуб",
        "starts_at": starts,
        "description": "концерт",
    }, secure=True)
    assert r.status_code in (301, 302), r.status_code
    event = Event.objects.filter(company=page, title="QA Page Concert").first()
    assert event and event.company_id == page.id
    ok("page event created")

    r = c.get(f"/pages/{page.id}", secure=True)
    assert r.status_code == 200 and "QA Page Concert".encode() in r.content
    ok("page lists event")

    r = c.get(f"/events/{event.id}", secure=True)
    assert r.status_code == 200 and name.encode() in r.content
    ok("event shows page link")

    EventAttendee.objects.filter(event=event).delete()
    event.delete()
    Post.objects.filter(topic=f"page:{page.id}").delete()
    Post.objects.filter(id=gift.id).delete()
    Notification.objects.filter(
        social_user=other, type="gift", body__icontains=sticker.title,
    ).delete()
    CompanyFollower.objects.filter(company=page).delete()
    CompanyAdmin.objects.filter(company=page).delete()
    page.delete()
    ok("cleanup")
    print("ALL gifts/page-events probes passed")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FAIL", e)
        raise
