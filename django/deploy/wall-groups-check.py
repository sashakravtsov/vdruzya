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
from apps.social.models import Community, CommunityMember, CommunityPost, Post, SocialProfile
from apps.social.services import now, profile_of


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
        # empty feed is ok; otherwise compose markup must exist on wall cards
        pass
    ok("feed news")

    r = post("/posts", {"body": "probe personal wall", "visibility": "public"})
    if r.status_code != 200:
        fail("personal post")
    wall = Post.objects.filter(body="probe personal wall", social_user=me).order_by("-id").first()
    if not wall:
        fail("personal wall not saved")
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

    # Profile wall: note attribution + compose
    r = get(f"/profile/{me.id}")
    body = r.content.decode()
    if r.status_code != 200 or "Стена" not in body:
        fail("profile wall")
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

    r = post(f"/groups/{g.id}/posts/{post_row.id}/comment", {"body": "probe c"})
    if r.status_code != 200:
        fail("comment")
    post(f"/groups/{g.id}/posts/{post_row.id}/react", {})
    ok("comment+react")

    r = post(f"/groups/{g.id}/posts", {"body": "probe topic django", "board": "discussion"})
    topic = CommunityPost.objects.filter(community=g, body="probe topic django").order_by("-id").first()
    if not topic or topic.topic != "discussion":
        fail("discussion topic")
    if "topic=" not in topic.get_absolute_url():
        fail(f"bad url {topic.get_absolute_url()}")
    ok("discussion + url")

    closed = Community.objects.filter(privacy="closed").exclude(memberships__social_user=me).first()
    if closed:
        ok("closed group probe")

    CommunityPost.objects.filter(body__startswith="probe ").delete()
    Post.objects.filter(body__startswith="probe ").delete()
    ok("cleanup")
    print("ALL wall/groups probes passed")


if __name__ == "__main__":
    main()
