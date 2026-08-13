#!/usr/bin/env python
"""Cross-era tech-debt probes: feed hide keys, checkin dedupe, profile Info fields."""
import os
import sys
import uuid
from datetime import date, datetime
from types import SimpleNamespace

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.test import Client

from apps.accounts.models import User
from apps.social import era2010 as e10
from apps.social import feed_hide as fh
from apps.social.models import Place, PlaceCheckin, Post, PROFILE_DEFER
from apps.social.services import _feed_at, bump_news, get_profile, news_items, now, profile_of


def ok(label):
    print(f"OK   {label}")


def main():
    # feed_hide kind-specific keys (must not collapse to post/place/event)
    post = SimpleNamespace(id=11)
    tag = SimpleNamespace(id=22)
    assert fh.story_key_for({"kind": "hashtag", "tag": tag, "post": post}) == "hashtag:22:11"
    checkin = SimpleNamespace(id=33)
    place = SimpleNamespace(id=44)
    assert fh.story_key_for({
        "kind": "checkin", "checkin": checkin, "place": place,
    }) == "checkin:33"
    review = SimpleNamespace(id=55)
    assert fh.story_key_for({
        "kind": "review", "review": review, "place": place,
    }) == "review:55"
    sc = SimpleNamespace(id=66)
    ev = SimpleNamespace(id=77)
    assert fh.story_key_for({
        "kind": "safety", "checkin": sc, "event": ev,
    }) == "safety:66"
    actor = SimpleNamespace(id=1)
    group = SimpleNamespace(id=9)
    assert fh.story_key_for({
        "kind": "joined", "actor": actor, "group": group,
    }) == "joined:9:1"
    assert fh.story_key_for({
        "kind": "fan", "actor": actor, "page": SimpleNamespace(id=8),
    }) == "fan:8:1"
    assert fh.story_key_for({
        "kind": "market", "listing": SimpleNamespace(id=3),
    }) == "market:3"
    assert fh.story_key_for({
        "kind": "anniversary", "actor": actor, "years": 5,
    }) == "anniversary:1:5"
    assert fh.story_key_for({
        "kind": "group_doc", "doc": SimpleNamespace(id=4),
    }) == "group_doc:4"
    ok("feed_hide story keys")

    assert _feed_at(None) == datetime.min
    assert _feed_at(date(2011, 3, 1)) == datetime(2011, 3, 1)
    assert _feed_at(datetime(2012, 4, 5, 6, 7)) == datetime(2012, 4, 5, 6, 7)
    ok("feed at normalize")

    assert "looking_for" in PROFILE_DEFER  # stay deferred on feed joins
    ok("profile JSON still deferred on hot paths")

    u = User.objects.filter(email="alexandr@vdruzya.ru").first() or User.objects.first()
    assert u
    me = profile_of(u)
    assert me
    c = Client(HTTP_HOST="vdruzya.ru")
    c.force_login(u)

    # Graph Search classic chrome: no HTML5 placeholder
    r = c.get("/graph", secure=True)
    assert r.status_code == 200
    assert b"placeholder=" not in r.content
    ok("graph no placeholder")

    # Info tab via get_profile() loads JSON fields without DeferredAttribute
    p = get_profile(me.id)
    _ = p.looking_for
    _ = p.interested_in
    _ = p.languages
    ok("profile Info field access via get_profile")

    # Place checkin must not also appear as generic wall story
    t = now()
    place_row = Place.objects.order_by("id").first()
    if not place_row:
        place_row = Place.objects.create(
            name=f"QA Place {uuid.uuid4().hex[:5]}", city="Москва",
            address="", created_at=t, updated_at=t,
        )
        created_place = True
    else:
        created_place = False
    cin = e10.place_checkin(me, place_row, message=f"QA cin {uuid.uuid4().hex[:5]}")
    assert cin
    bump_news()
    feed = news_items(me, limit=100)
    checkin_stories = [i for i in feed if i.get("kind") == "checkin" and i.get("checkin") and i["checkin"].id == cin.id]
    wall_dupes = [
        i for i in feed
        if i.get("kind") == "wall" and i.get("post") and getattr(i["post"], "kind", "") == "checkin"
        and getattr(i["post"], "topic", "") == f"place:{place_row.id}"
    ]
    assert checkin_stories, "checkin story missing"
    assert not wall_dupes, "checkin still duplicated as wall"
    assert checkin_stories[0].get("story_key") == f"checkin:{cin.id}"
    ok("checkin feed dedupe + key")

    # Shared video permalink + group body_text: no storage: leak
    from apps.social.models import CommunityPost
    gprobe = CommunityPost(topic="wall", kind="video", body="storage:videos/t.mp4\n\nгруппа")
    assert gprobe.body_text == "группа" and "storage:" not in gprobe.body_text
    ok("group wall video body_text")

    r = c.get("/graph", secure=True)
    assert r.status_code == 200
    assert b"_news_post_body" not in r.content
    from apps.social.services import mini_feed, wall_posts_for, feed_rail, news_items as ni
    feed = mini_feed(me, limit=5, viewer=me)
    assert isinstance(feed, list)
    assert callable(wall_posts_for) and callable(feed_rail)
    from apps.social import graph_search as gs
    from apps.social import groups_dir as gd
    from apps.social import inbox_ctx as ic
    from apps.social import pages_dir as pd
    from apps.social import ticker as tk
    from apps.social import note_edit as ne
    from apps.social import search_dir as sd
    from apps.social import people_search as ps
    from apps.social import comment_thread as ct
    from apps.social import page_show as pshow
    assert callable(gs.graph_search) and callable(gd.directory_ctx) and callable(ic.build_inbox_ctx)
    assert callable(pd.directory_ctx) and callable(tk.ticker_items) and callable(ne.save_note)
    assert callable(sd.search_ctx) and callable(ps.find_people) and callable(ct.build_thread)
    assert callable(pshow.build_page_show)
    r = c.get("/search?q=а&tab=groups", secure=True)
    assert r.status_code == 200, "search Q filter"
    ok("mini_feed slim + graph chrome")
    ok("wall/groups/graph/inbox/news slim modules")
    ok("pages/ticker/note_edit slim + search Q")
    ok("search_dir/people_search/comment_thread/page_show slim")

    PlaceCheckin.objects.filter(pk=cin.id).delete()
    Post.objects.filter(social_user=me, kind="checkin", topic=f"place:{place_row.id}").delete()
    if created_place:
        place_row.delete()
    ok("cleanup")
    print("ALL techdebt probes passed")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FAIL", e)
        raise
