#!/usr/bin/env python
"""Smoke: FB 2009–2010 classic modules (Like / Places / Questions)."""
import os
import sys
import uuid

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

django.setup()

from django.test import Client

from apps.accounts.models import User
from apps.social.models import Place, PlaceCheckin, Post, Question, QuestionAnswer, QuestionVote
from apps.social.models.legacy import Reaction
from apps.social.services import news_items, profile_of


def ok(label):
    print(f"OK   {label}")


def main():
    from django.db import connection
    with connection.cursor() as cur:
        for t in ("reactions", "places", "place_checkins", "questions", "question_answers", "question_votes"):
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
        ("/apps", "Места"),
    ):
        r = c.get(path, secure=True)
        assert r.status_code == 200, path
        assert needle.encode() in r.content, path
        assert b"placeholder=" not in r.content
    ok("places/questions pages")

    # Place + checkin
    name = f"QA Cafe {uuid.uuid4().hex[:5]}"
    r = c.post("/places", {"name": name, "city": "Москва", "address": "Тверская"}, secure=True)
    assert r.status_code in (301, 302)
    place = Place.objects.filter(name=name).order_by("-id").first()
    assert place
    r = c.post(f"/places/{place.id}", {"message": "кофе"}, secure=True)
    assert r.status_code in (301, 302)
    assert PlaceCheckin.objects.filter(place=place, social_user=me).exists()
    assert Post.objects.filter(social_user=me, kind="checkin", topic=f"place:{place.id}").exists()
    feed = news_items(me, limit=80)
    assert any(i.get("kind") == "checkin" and i.get("place") and i["place"].id == place.id for i in feed)
    ok("place checkin + feed")

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

    # Like
    tpost = Post.objects.create(
        social_user=me, body="__like_probe__", topic=f"wall:{me.id}",
        visibility="friends", kind="text",
        created_at=__import__("apps.social.services", fromlist=["now"]).now(),
        updated_at=__import__("apps.social.services", fromlist=["now"]).now(),
    )
    r = c.post(f"/posts/{tpost.id}/like", {"next": f"/profile/{me.id}"}, secure=True)
    assert r.status_code in (301, 302)
    assert Reaction.objects.filter(post=tpost, social_user=me, type="like").exists()
    feed = news_items(me, limit=80)
    assert any(i.get("kind") == "like" and i.get("post") and i["post"].id == tpost.id for i in feed)
    ok("like + feed")

    # cleanup
    Reaction.objects.filter(post=tpost).delete()
    Post.objects.filter(pk=tpost.id).delete()
    QuestionVote.objects.filter(answer=ans).delete()
    QuestionAnswer.objects.filter(question=q).delete()
    Question.objects.filter(pk=q.id).delete()
    Post.objects.filter(topic=f"place:{place.id}").delete()
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
