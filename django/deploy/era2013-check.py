#!/usr/bin/env python
"""Smoke: FB 2013 classic modules (Graph Search / Hashtags / Nearby / Trending)."""
import os
import sys
import uuid

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.test import Client

from apps.accounts.models import User
from apps.social import era2013 as e13
from apps.social.models import Hashtag, Post, PostHashtag
from apps.social.services import bump_news, news_items, now, profile_of


def ok(label):
    print(f"OK   {label}")


def main():
    from django.db import connection
    with connection.cursor() as cur:
        for t in ("hashtags", "post_hashtags"):
            cur.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name=%s", [t]
            )
            assert cur.fetchone(), f"missing {t}"
    ok("schema 2013")

    u = User.objects.filter(email="alexandr@vdruzya.ru").first() or User.objects.first()
    assert u
    me = profile_of(u)
    assert me
    c = Client(HTTP_HOST="vdruzya.ru")
    c.force_login(u)

    for path, needle in (
        ("/graph", "Поиск по графу"),
        ("/trending", "В тренде"),
        ("/nearby", "Друзья рядом"),
    ):
        r = c.get(path, secure=True)
        assert r.status_code == 200, f"{path} -> {r.status_code}"
        assert needle.encode() in r.content, f"{path} missing {needle!r}"
        assert b"page-tabs" not in r.content
        assert b"display: flex" not in r.content.lower()
    ok("graph/trending/nearby pages")

    tag = f"qa{uuid.uuid4().hex[:8]}"
    body = f"Проверка хэштега #{tag} из smoke"
    t = now()
    post = Post.objects.create(
        social_user=me,
        body=body,
        kind="status",
        topic="status",
        visibility="public",
        created_at=t,
        updated_at=t,
    )
    synced = e13.sync_hashtags(post)
    assert synced and synced[0].name == tag
    assert PostHashtag.objects.filter(post=post, hashtag__name=tag).exists()
    ok("hashtag sync")

    r = c.get(f"/hashtag/{tag}", secure=True)
    assert r.status_code == 200
    assert f"#{tag}".encode() in r.content
    assert body.split()[0].encode() in r.content or tag.encode() in r.content
    ok("hashtag page")

    r = c.get("/graph", {"q": f"кто любит #{tag}"}, secure=True)
    assert r.status_code == 200
    assert me.name.encode() in r.content or "Результаты".encode() in r.content
    assert b"placeholder=" not in r.content
    ok("graph search by hashtag")

    city = (me.city or "").strip() or "Москва"
    r = c.get("/graph", {"q": f"друзья в {city}"}, secure=True)
    assert r.status_code == 200
    assert "Поиск по графу".encode() in r.content
    ok("graph search by city")

    topics = e13.trending_topics(me, 30, hours=24 * 30)
    assert any(x.get("name") == tag for x in topics), "tag missing from trending"
    r = c.get("/trending", secure=True)
    assert r.status_code == 200
    assert f"#{tag}".encode() in r.content
    ok("trending")

    city = (me.city or "").strip() or "Москва"
    old_city = me.city
    if not (me.city or "").strip():
        me.city = city
        me.save(update_fields=["city"])
    r = c.get("/nearby", secure=True)
    assert r.status_code == 200
    assert "рядом".encode() in r.content or city.encode() in r.content
    ok("nearby")

    bump_news()
    feed = news_items(me, limit=80)
    assert any(
        i.get("kind") == "hashtag" and i.get("tag") and i["tag"].name == tag
        for i in feed
    ), "hashtag story missing from feed"
    ok("hashtag feed story")

    r = c.get("/apps/graph", secure=True)
    assert r.status_code == 200
    assert "Поиск по графу".encode() in r.content
    ok("app center graph")

    # cleanup
    PostHashtag.objects.filter(post=post).delete()
    Hashtag.objects.filter(name=tag).delete()
    post.delete()
    if old_city != me.city:
        me.city = old_city
        me.save(update_fields=["city"])
    ok("cleanup")
    print("ALL 2013 classic modules probes passed")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FAIL", e)
        raise
