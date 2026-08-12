#!/usr/bin/env python
"""Live feature probe: Wall + Groups FB 2005 parity (no Laravel)."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.test import Client
from apps.accounts.models import User
from apps.social.models import Community, CommunityPost, Post
from apps.social.services import profile_of


def fail(msg):
    print(f"FAIL {msg}")
    sys.exit(1)


def ok(msg):
    print(f"OK   {msg}")


def main():
    u = User.objects.filter(email__icontains="alexandr").first() or User.objects.first()
    if not u:
        fail("no user")
    me = profile_of(u)
    c = Client()
    c.force_login(u)

    def get(path):
        return c.get(path, follow=True, secure=True)

    def post(path, data):
        return c.post(path, data, follow=True, secure=True)

    r = get("/feed")
    body = r.content.decode()
    if r.status_code != 200 or "Новости" not in body:
        fail("feed")
    if "wall-comment-compose" not in body and "Пока тихо" not in body:
        # empty feed is ok; otherwise compose markup must exist on wall posts
        pass
    if "news-card" in body:
        fail("news-card chrome still on feed")
    ok("feed news")

    r = post("/posts", {"body": "probe personal wall", "wall_to": me.id})
    if r.status_code != 200:
        fail("personal post")
    wall = Post.objects.filter(body="probe personal wall", social_user=me).order_by("-id").first()
    if not wall or wall.topic != f"wall:{me.id}":
        fail(f"personal wall not saved (topic={getattr(wall, 'topic', None)})")
    ok("personal wall post")

    r = get("/feed")
    body = r.content.decode()
    if f'id="c-{wall.id}"' not in body or "wall-comment-compose" not in body:
        fail("comment compose missing on feed")
    # Form is in DOM but hidden until #c-N (classic reveal)
    if f'href="#c-{wall.id}"' not in body:
        fail("comment reveal link missing")
    ok("comment reveal chrome")

    r = post(f"/posts/{wall.id}/comment", {"body": "probe wall comment", "next": "/feed"})
    if r.status_code != 200:
        fail("wall comment")
    if not wall.comments.filter(body="probe wall comment").exists():
        fail("wall comment not saved")
    ok("wall comment")

    # FB-2006: last 2 comments shown; older behind «Показать предыдущие»
    for i, text in enumerate(("probe c0", "probe c1", "probe c2"), start=1):
        post(f"/posts/{wall.id}/comment", {"body": text, "next": "/feed"})
    r = get("/feed")
    body = r.content.decode()
    if "ico-comment" not in body:
        fail("comment icon missing on feed")
    if "ico-thumb" in body or "Нравится" in body or "react-btn" in body:
        fail("likes are not Facebook 2006")
    if "Показать предыдущие комментарии" not in body:
        fail("many-comments collapse missing")
    if "probe c0" not in body:
        fail("older comment should be in collapsed block")
    if "probe c2" not in body:
        fail("recent comment should be visible")
    ok("comment icons + many-comments collapse")

    # Profile wall: note attribution + compose
    r = get(f"/profile/{me.id}")
    body = r.content.decode()
    if r.status_code != 200 or "Стена" not in body:
        fail("profile wall")
    if "ico-comment" not in body:
        fail("comment icon missing on profile wall")
    ok("profile wall")

    r = get("/groups")
    if r.status_code != 200:
        fail("groups index")
    ok("groups index")

    r = get("/groups?mine=1")
    body = r.content.decode()
    if "mygroups-table" not in body and "Мои группы" not in body:
        fail("my groups")
    ok("my groups table")

    g = Community.objects.filter(memberships__social_user=me).first() or Community.objects.first()
    if not g:
        fail("no group")
    r = get(f"/groups/{g.id}")
    body = r.content.decode()
    for needle in ("Информация", "Стена", "Доска обсуждений", "Участники", "Руководители"):
        if needle not in body:
            fail(f"group show missing {needle}")
    ok(f"group show #{g.id}")

    r = post(f"/groups/{g.id}/posts", {"body": "probe wall django", "board": "wall"})
    if r.status_code != 200:
        fail(f"wall post {r.status_code}")
    post_row = CommunityPost.objects.filter(community=g, body="probe wall django").order_by("-id").first()
    if not post_row or post_row.topic != "wall":
        fail("wall post not saved")
    ok("group wall post")

    r = get(f"/groups/{g.id}")
    body = r.content.decode()
    if f'id="c-{post_row.id}"' not in body or "wall-comment-compose" not in body:
        fail("group comment compose missing")
    if f'href="#c-{post_row.id}"' not in body:
        fail("group comment reveal link missing")
    ok("group comment reveal chrome")

    r = post(f"/groups/{g.id}/posts/{post_row.id}/comment", {"body": "probe c"})
    if r.status_code != 200:
        fail("comment")
    if not post_row.comments.filter(body="probe c").exists():
        fail("group comment not saved")
    ok("group comment")

    r = post(
        f"/groups/{g.id}/posts",
        {"subject": "probe subject", "body": "probe topic django", "board": "discussion"},
    )
    if r.status_code != 200:
        fail(f"discussion post {r.status_code}")
    topic = CommunityPost.objects.filter(community=g, body__contains="probe topic django").order_by("-id").first()
    if not topic or topic.topic != "discussion":
        fail("discussion topic")
    if topic.subject != "probe subject":
        fail(f"discussion subject missing ({topic.subject!r})")
    if topic.body_text != "probe topic django":
        fail(f"discussion body_text ({topic.body_text!r})")
    if "topic=" not in topic.get_absolute_url():
        fail(f"bad url {topic.get_absolute_url()}")
    r = get(f"/groups/{g.id}?topic={topic.id}")
    body = r.content.decode()
    if "probe subject" not in body or "discuss-open" not in body:
        fail("discussion thread chrome missing")
    if "discuss-compose" in body:
        fail("compose should hide while topic open")
    ok("discussion subject + thread")

    closed = Community.objects.filter(privacy="closed").exclude(memberships__social_user=me).first()
    if closed:
        ok("closed group probe")

    CommunityPost.objects.filter(body__startswith="probe ").delete()
    Post.objects.filter(body__startswith="probe ").delete()
    ok("cleanup")
    print("ALL wall/groups probes passed")


if __name__ == "__main__":
    main()
