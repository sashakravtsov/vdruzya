#!/usr/bin/env python
"""Smoke: FB 2009–2010 classic modules (Like / Share / Places / Reviews / Questions / Polls)."""
import os
import sys
import uuid

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.test import Client

from apps.accounts.models import User
from apps.social.models import (
    ClassicPoll, ClassicPollOption, ClassicPollVote,
    Place, PlaceCheckin, PlaceReview,
    Post, Question, QuestionAnswer, QuestionVote,
)
from apps.social.models.legacy import Reaction
from apps.social.services import news_items, now, profile_of, wall_posts_for


def ok(label):
    print(f"OK   {label}")


def main():
    from django.db import connection
    with connection.cursor() as cur:
        for t in (
            "reactions", "places", "place_checkins", "place_reviews",
            "questions", "question_answers", "question_votes",
            "classic_polls", "classic_poll_options", "classic_poll_votes",
            "photo_reactions", "comment_reactions", "post_tags", "classic_group_docs",
        ):
            cur.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name=%s", [t]
            )
            assert cur.fetchone(), f"missing {t}"
    ok("schema 2010")

    u = User.objects.filter(email="alexandr@vdruzya.ru").first() or User.objects.first()
    assert u
    me = profile_of(u)
    c = Client(HTTP_HOST="vdruzya.ru")
    c.force_login(u)

    for path, needle in (
        ("/places", "Места"),
        ("/questions", "Вопросы"),
        ("/polls", "Опросы"),
        ("/apps", "Опросы"),
    ):
        r = c.get(path, secure=True)
        assert r.status_code == 200, path
        assert needle.encode() in r.content, path
        assert b"placeholder=" not in r.content
    ok("places/questions/polls pages")

    # Place + checkin + review
    name = f"QA Cafe {uuid.uuid4().hex[:5]}"
    r = c.post("/places", {"name": name, "city": "Москва", "address": "Тверская"}, secure=True)
    assert r.status_code in (301, 302)
    place = Place.objects.filter(name=name).order_by("-id").first()
    assert place
    r = c.post(f"/places/{place.id}", {"action": "checkin", "message": "кофе"}, secure=True)
    assert r.status_code in (301, 302)
    assert PlaceCheckin.objects.filter(place=place, social_user=me).exists()
    assert Post.objects.filter(social_user=me, kind="checkin", topic=f"place:{place.id}").exists()
    r = c.post(
        f"/places/{place.id}",
        {"action": "review", "stars": "4", "body": "неплохо"},
        secure=True,
    )
    assert r.status_code in (301, 302)
    assert PlaceReview.objects.filter(place=place, social_user=me, stars=4).exists()
    feed = news_items(me, limit=80)
    assert any(i.get("kind") == "checkin" and i.get("place") and i["place"].id == place.id for i in feed)
    assert any(i.get("kind") == "review" and i.get("place") and i["place"].id == place.id for i in feed)
    ok("place checkin + review + feed")

    # Question + answer + vote
    r = c.post("/questions", {"body": "QA: любимый фильм 2010?"}, secure=True)
    assert r.status_code in (301, 302)
    q = Question.objects.filter(social_user=me, body__startswith="QA:").order_by("-id").first()
    assert q
    r = c.post(f"/questions/{q.id}", {"body": "Начало"}, secure=True)
    assert r.status_code in (301, 302)
    ans = QuestionAnswer.objects.filter(question=q, social_user=me).first()
    assert ans
    r = c.post(f"/questions/{q.id}/answers/{ans.id}/vote", {"next": f"/questions/{q.id}"}, secure=True)
    assert r.status_code in (301, 302)
    assert QuestionVote.objects.filter(answer=ans, social_user=me).exists()
    feed = news_items(me, limit=80)
    assert any(i.get("kind") == "question" and i.get("question") and i["question"].id == q.id for i in feed)
    ok("question answer vote + feed")

    # Classic poll
    r = c.post(
        "/polls",
        {"question": "QA: чай или кофе?", "options": "чай\nкофе\nсок"},
        secure=True,
    )
    assert r.status_code in (301, 302)
    poll = ClassicPoll.objects.filter(social_user=me, question__startswith="QA:").order_by("-id").first()
    assert poll
    opt = ClassicPollOption.objects.filter(poll=poll).order_by("sort_order").first()
    assert opt
    r = c.post(f"/polls/{poll.id}/options/{opt.id}/vote", {"next": f"/polls/{poll.id}"}, secure=True)
    assert r.status_code in (301, 302)
    assert ClassicPollVote.objects.filter(poll=poll, social_user=me, option=opt).exists()
    feed = news_items(me, limit=80)
    assert any(i.get("kind") == "poll" and i.get("poll") and i["poll"].id == poll.id for i in feed)
    ok("classic poll vote + feed")

    # Like + Share (need a second profile's post, or share of self fails — create friend post on wall)
    t = now()
    other = (
        Post.objects.exclude(social_user=me)
        .filter(kind__in=("text", "photo", "note"))
        .order_by("-id")
        .first()
    )
    if not other:
        # Fallback: create a temporary "other" wall note authored by me then share is blocked —
        # use a synthetic second author if available via any other SocialProfile.
        from apps.social.models import SocialProfile
        buddy = SocialProfile.objects.exclude(pk=me.id).order_by("id").first()
        assert buddy, "need second profile for share probe"
        other = Post.objects.create(
            social_user=buddy, body="__share_src__", topic=f"wall:{buddy.id}",
            visibility="friends", kind="text", created_at=t, updated_at=t,
        )
        owned_other = True
    else:
        owned_other = False

    tpost = Post.objects.create(
        social_user=me, body="__like_probe__", topic=f"wall:{me.id}",
        visibility="friends", kind="text", created_at=t, updated_at=t,
    )
    r = c.post(f"/posts/{tpost.id}/like", {"next": f"/profile/{me.id}"}, secure=True)
    assert r.status_code in (301, 302)
    assert Reaction.objects.filter(post=tpost, social_user=me, type="like").exists()
    feed = news_items(me, limit=80)
    assert any(i.get("kind") == "like" and i.get("post") and i["post"].id == tpost.id for i in feed)
    ok("like + feed")

    r = c.post(f"/posts/{other.id}/share", {"next": f"/profile/{me.id}"}, secure=True)
    assert r.status_code in (301, 302), r.status_code
    shared = Post.objects.filter(social_user=me, kind="share", shared_post=other).order_by("-id").first()
    assert shared, "share post not created"
    wall_ids = {p.id for p in wall_posts_for(me, 40, viewer=me)}
    assert shared.id in wall_ids
    feed = news_items(me, limit=80)
    assert any(i.get("kind") == "share" and i.get("post") and i["post"].id == shared.id for i in feed)
    ok("share to wall + feed")

    # Status + Place
    r = c.post(
        "/profile/status",
        {"headline": "QA status place", "place": str(place.id), "next": f"/profile/{me.id}"},
        secure=True,
    )
    assert r.status_code in (301, 302)
    me.refresh_from_db()
    assert place.name in (me.headline or "")
    assert PlaceCheckin.objects.filter(place=place, social_user=me, message="QA status place").exists()
    ok("status with place")

    # Comment like + wall post tag
    from apps.social.models.legacy import CommentReaction, PostTag
    from apps.social.models import Comment, Friendship, SocialProfile
    tpost2 = Post.objects.create(
        social_user=me, body="__tag_probe__", topic=f"wall:{me.id}",
        visibility="friends", kind="text", created_at=now(), updated_at=now(),
    )
    cmt = Comment.objects.create(post=tpost2, social_user=me, body="__cmt_like__", created_at=now())
    r = c.post(f"/comments/{cmt.id}/like", {"next": f"/profile/{me.id}"}, secure=True)
    assert r.status_code in (301, 302)
    assert CommentReaction.objects.filter(comment=cmt, social_user=me, type="like").exists()
    ok("comment like")

    buddy = SocialProfile.objects.exclude(pk=me.id).order_by("id").first()
    if buddy:
        Friendship.objects.update_or_create(
            user=me, friend=buddy,
            defaults={"status": "accepted", "created_at": now(), "updated_at": now()},
        )
        Friendship.objects.update_or_create(
            user=buddy, friend=me,
            defaults={"status": "accepted", "created_at": now(), "updated_at": now()},
        )
        r = c.post(f"/posts/{tpost2.id}/tag", {"person": str(buddy.id), "next": f"/profile/{me.id}"}, secure=True)
        assert r.status_code in (301, 302)
        assert PostTag.objects.filter(post=tpost2, social_user=buddy).exists()
        ok("wall post tag")
        PostTag.objects.filter(post=tpost2).delete()
    else:
        ok("wall post tag skipped (no buddy)")

    CommentReaction.objects.filter(comment=cmt).delete()
    Comment.objects.filter(pk=cmt.id).delete()
    Post.objects.filter(pk=tpost2.id).delete()

    # cleanup
    Reaction.objects.filter(post=tpost).delete()
    Post.objects.filter(pk__in=[tpost.id, shared.id]).delete()
    if owned_other:
        Post.objects.filter(pk=other.id).delete()
    ClassicPollVote.objects.filter(poll=poll).delete()
    ClassicPollOption.objects.filter(poll=poll).delete()
    ClassicPoll.objects.filter(pk=poll.id).delete()
    QuestionVote.objects.filter(answer=ans).delete()
    QuestionAnswer.objects.filter(question=q).delete()
    Question.objects.filter(pk=q.id).delete()
    Post.objects.filter(topic=f"place:{place.id}").delete()
    PlaceReview.objects.filter(place=place).delete()
    PlaceCheckin.objects.filter(place=place).delete()
    place.delete()
    ok("cleanup")
    print("ALL 2010 classic modules probes passed")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FAIL", e)
        raise
