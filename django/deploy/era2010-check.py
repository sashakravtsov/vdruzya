#!/usr/bin/env python
"""Smoke: FB 2009–2010 classic modules (Like / Share / Places / Reviews / Questions / Polls)."""
import os
import sys
import uuid

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from apps.accounts.models import User
from apps.social.models import (
    ClassicPoll, ClassicPollOption, ClassicPollVote,
    Place, PlaceCheckin, PlaceReview,
    Post, Question, QuestionAnswer, QuestionVote,
)
from apps.social.models.legacy import Reaction
from apps.social.services import bump_news, news_items, now, profile_of, wall_posts_for

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)


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
            "photo_comment_reactions", "group_comment_reactions", "group_post_reactions",
            "relationship_requests", "feed_hides", "feed_story_hides", "family_links",
        ):
            cur.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name=%s", [t]
            )
            assert cur.fetchone(), f"missing {t}"
        for table, col in (("places", "photo_path"), ("place_checkins", "photo_path")):
            cur.execute(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name=%s AND column_name=%s",
                [table, col],
            )
            assert cur.fetchone(), f"{table}.{col}"
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

    # Place + checkin + review (+ optional photos on same media disk)
    name = f"QA Cafe {uuid.uuid4().hex[:5]}"
    r = c.post("/places", {
        "name": name, "city": "Москва", "address": "Тверская",
        "photo": SimpleUploadedFile("place.png", PNG, content_type="image/png"),
    }, secure=True)
    assert r.status_code in (301, 302)
    place = Place.objects.filter(name=name).order_by("-id").first()
    assert place and place.photo_path and place.photo_path.startswith("places/"), place
    r = c.get("/places", secure=True)
    assert r.status_code == 200 and b"place-thumb" in r.content
    r = c.post(f"/places/{place.id}", {
        "action": "checkin", "message": "кофе",
        "photo": SimpleUploadedFile("cin.png", PNG, content_type="image/png"),
    }, secure=True)
    assert r.status_code in (301, 302)
    cin = PlaceCheckin.objects.filter(place=place, social_user=me).order_by("-id").first()
    assert cin and cin.photo_path and cin.photo_path.startswith("checkins/"), cin
    cpost = Post.objects.filter(social_user=me, kind="checkin", topic=f"place:{place.id}").order_by("-id").first()
    assert cpost and cpost.media_path == cin.photo_path
    r = c.get(f"/places/{place.id}", secure=True)
    assert r.status_code == 200 and b"<img" in r.content
    ok("place + checkin photos")
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

    # Wall filters
    r = c.get(f"/profile/{me.id}?tab=wall&filter=photos", secure=True)
    assert r.status_code == 200
    assert b"wall-filters" in r.content or "Фото".encode() in r.content
    assert b'filter=mine' in r.content
    ok("wall filters")

    # Relationship confirmation
    from apps.social.models.legacy import RelationshipRequest
    buddy2 = SocialProfile.objects.exclude(pk=me.id).order_by("id").first()
    if buddy2:
        Friendship.objects.update_or_create(
            user=me, friend=buddy2,
            defaults={"status": "accepted", "created_at": now(), "updated_at": now()},
        )
        Friendship.objects.update_or_create(
            user=buddy2, friend=me,
            defaults={"status": "accepted", "created_at": now(), "updated_at": now()},
        )
        old_status, old_partner = me.relationship_status, me.relationship_with_id
        old_b_status, old_b_partner = buddy2.relationship_status, buddy2.relationship_with_id
        # Clear any prior mutual/accepted state from earlier smokes
        RelationshipRequest.objects.filter(
            requester__in=(me, buddy2), partner__in=(me, buddy2),
        ).delete()
        buddy2.relationship_with = None
        buddy2.relationship_status = ""
        buddy2.save(update_fields=["relationship_with", "relationship_status"])
        me.relationship_status = "in_a_relationship"
        me.relationship_with = buddy2
        me.save(update_fields=["relationship_status", "relationship_with"])
        from apps.social import relationship as relmod
        relmod.request_partner(me, buddy2, "in_a_relationship")
        rr = RelationshipRequest.objects.filter(
            requester=me, partner=buddy2, status="pending",
        ).first()
        assert rr, "relationship request missing"
        r = c.get(f"/profile/{me.id}?tab=info", secure=True)
        assert "ожидает подтверждения".encode() in r.content
        # Accept as partner
        u2 = buddy2.user
        c2 = Client(HTTP_HOST="vdruzya.ru")
        c2.force_login(u2)
        r = c2.get("/friends", secure=True)
        assert r.status_code == 200
        assert "Подтверждение отношений".encode() in r.content
        r = c2.post(
            f"/profile/{buddy2.id}/relationship/{rr.id}/accept",
            {"next": "/friends"},
            secure=True,
        )
        assert r.status_code in (301, 302)
        rr.refresh_from_db()
        assert rr.status == "accepted"
        buddy2.refresh_from_db()
        assert buddy2.relationship_with_id == me.id
        ok("relationship confirm")
        RelationshipRequest.objects.filter(
            requester__in=(me, buddy2), partner__in=(me, buddy2),
        ).delete()
        me.relationship_status = old_status or ""
        me.relationship_with_id = old_partner
        me.save(update_fields=["relationship_status", "relationship_with"])
        buddy2.relationship_status = old_b_status or ""
        buddy2.relationship_with_id = old_b_partner
        buddy2.save(update_fields=["relationship_with", "relationship_status"])
    else:
        ok("relationship confirm skipped (no buddy)")

    # Hide from News Feed
    from apps.social import feed_hide as fh
    from apps.social.models.legacy import FeedHide, FeedStoryHide
    buddy3 = SocialProfile.objects.exclude(pk=me.id).order_by("id").first()
    if buddy3:
        assert fh.hide_actor(me, buddy3.id)
        assert FeedHide.objects.filter(social_user=me, actor=buddy3).exists()
        r = c.post(f"/feed/hide/{buddy3.id}", {"next": "/feed"}, secure=True)
        assert r.status_code in (301, 302)
        r = c.get("/feed", secure=True)
        assert r.status_code == 200
        assert "Скрыты из ленты".encode() in r.content or buddy3.name.encode() in r.content
        sk = f"wall:{tpost.id}"
        assert fh.hide_story(me, sk)
        assert FeedStoryHide.objects.filter(social_user=me, story_key=sk).exists()
        feed = news_items(me, limit=80)
        assert all(getattr(i.get("actor"), "id", None) != buddy3.id for i in feed)
        ok("feed hide actor + story")
        FeedHide.objects.filter(social_user=me, actor=buddy3).delete()
        FeedStoryHide.objects.filter(social_user=me, story_key=sk).delete()
        bump_news()
    else:
        ok("feed hide skipped (no buddy)")

    # Family link confirm
    from apps.social import family as fam
    from apps.social.models.legacy import FamilyLink
    buddy4 = SocialProfile.objects.exclude(pk=me.id).order_by("id").first()
    if buddy4:
        Friendship.objects.update_or_create(
            user=me, friend=buddy4,
            defaults={"status": "accepted", "created_at": now(), "updated_at": now()},
        )
        Friendship.objects.update_or_create(
            user=buddy4, friend=me,
            defaults={"status": "accepted", "created_at": now(), "updated_at": now()},
        )
        FamilyLink.objects.filter(from_user__in=(me, buddy4), to_user__in=(me, buddy4)).delete()
        link = fam.request(me, buddy4.id, "sibling")
        assert link and link.status == "pending"
        c4 = Client(HTTP_HOST="vdruzya.ru")
        c4.force_login(buddy4.user)
        r = c4.post(f"/family/{link.id}/accept", {"next": "/friends"}, secure=True)
        assert r.status_code in (301, 302)
        link.refresh_from_db()
        assert link.status == "approved"
        assert FamilyLink.objects.filter(from_user=buddy4, to_user=me, status="approved").exists()
        r = c.get(f"/profile/{me.id}?tab=info", secure=True)
        assert "Семья".encode() in r.content and buddy4.name.encode() in r.content
        ok("family confirm")
        FamilyLink.objects.filter(from_user__in=(me, buddy4), to_user__in=(me, buddy4)).delete()
    else:
        ok("family confirm skipped (no buddy)")

    # Status + picture + friend stories in News Feed
    st = Post.objects.create(
        social_user=me, body=f"QA status {uuid.uuid4().hex[:6]}",
        visibility="public", kind="status", topic="status",
        created_at=now(), updated_at=now(),
    )
    pic = Post.objects.create(
        social_user=me, body="", visibility="friends",
        kind="photo", topic="picture", media_path=me.avatar_path or "avatars/qa.png",
        created_at=now(), updated_at=now(),
    )
    bump_news()
    feed = news_items(me, limit=80)
    assert any(i.get("kind") == "status" and i.get("post") and i["post"].id == st.id for i in feed)
    assert any(i.get("kind") == "picture" and i.get("post") and i["post"].id == pic.id for i in feed)
    ok("status + picture in news feed")
    from django.db.models import Q
    from apps.social.models import Friendship, SocialProfile
    buddy_f = SocialProfile.objects.exclude(pk=me.id).order_by("id").first()
    if buddy_f:
        pair = Friendship.objects.filter(
            Q(user=me, friend=buddy_f) | Q(user=buddy_f, friend=me),
            status="accepted",
        )
        created = False
        if not pair.exists():
            t = now()
            Friendship.objects.create(
                user=me, friend=buddy_f, status="accepted", created_at=t, updated_at=t,
            )
            Friendship.objects.create(
                user=buddy_f, friend=me, status="accepted", created_at=t, updated_at=t,
            )
            created = True
        else:
            Friendship.objects.filter(
                Q(user=me, friend=buddy_f) | Q(user=buddy_f, friend=me),
                status="accepted",
            ).update(updated_at=now())
        bump_news()
        feed = news_items(me, limit=80)
        assert any(
            i.get("kind") == "friend" and i.get("other")
            and {i["actor"].id, i["other"].id} == {me.id, buddy_f.id}
            for i in feed
        ), "friend story missing"
        ok("friend story in news feed")
        if created:
            Friendship.objects.filter(
                Q(user=me, friend=buddy_f) | Q(user=buddy_f, friend=me)
            ).delete()
    else:
        ok("friend story skipped (no buddy)")

    r = c.get("/notifications", secure=True)
    assert r.status_code == 200
    assert "Уведомления".encode() in r.content
    ok("notifications page")

    Post.objects.filter(pk__in=[st.id, pic.id]).delete()

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
