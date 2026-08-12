"""FB 2010 Places + Questions helpers."""
from __future__ import annotations

from django.db.models import Count

from apps.social.models import Place, PlaceCheckin, Post, Question, QuestionAnswer, QuestionVote
from apps.social.services import bump_news, friend_ids, now, profile_related


def places_list(q="", city="", limit=40):
    qs = Place.objects.all().order_by("name")
    if q:
        qs = qs.filter(name__icontains=q)
    if city:
        qs = qs.filter(city__icontains=city)
    return list(qs[:limit])


def place_create(me, *, name, city="", address=""):
    name = (name or "").strip()[:160]
    if not me or not name:
        return None
    t = now()
    return Place.objects.create(
        name=name,
        city=(city or "").strip()[:120],
        address=(address or "").strip()[:255],
        created_at=t, updated_at=t,
    )


def place_checkin(me, place, message=""):
    if not me or not place:
        return None
    t = now()
    msg = (message or "").strip()[:500]
    checkin = PlaceCheckin.objects.create(
        place=place, social_user=me, message=msg, created_at=t,
    )
    Post.objects.create(
        social_user=me,
        body=msg or f"в «{place.name}»",
        kind="checkin",
        topic=f"place:{place.id}",
        media_label=place.name,
        visibility="friends",
        created_at=t, updated_at=t,
    )
    bump_news()
    return checkin


def place_checkins(place, limit=40):
    return list(
        PlaceCheckin.objects.filter(place=place)
        .select_related("social_user")
        .defer(*profile_related("social_user__"))
        .order_by("-id")[:limit]
    )


def questions_feed(viewer, *, mine=False, limit=40):
    fids = friend_ids(viewer) | {viewer.id} if viewer else set()
    qs = (
        Question.objects.select_related("social_user")
        .defer(*profile_related("social_user__"))
        .annotate(n_answers=Count("answers", distinct=True))
        .order_by("-id")
    )
    if mine and viewer:
        qs = qs.filter(social_user=viewer)
    elif viewer:
        qs = qs.filter(social_user_id__in=fids)
    return list(qs[:limit])


def question_create(me, body: str):
    body = (body or "").strip()[:500]
    if not me or not body:
        return None
    t = now()
    q = Question.objects.create(social_user=me, body=body, created_at=t, updated_at=t)
    bump_news()
    return q


def question_answer(me, question, body: str):
    body = (body or "").strip()[:500]
    if not me or not question or not body:
        return None
    ans = QuestionAnswer.objects.create(
        question=question, social_user=me, body=body, created_at=now(),
    )
    question.updated_at = now()
    question.save(update_fields=["updated_at"])
    bump_news()
    return ans


def question_answers(question, viewer=None):
    rows = list(
        QuestionAnswer.objects.filter(question=question)
        .select_related("social_user")
        .defer(*profile_related("social_user__"))
        .annotate(n_votes=Count("votes", distinct=True))
        .order_by("-n_votes", "id")
    )
    mine = set()
    if viewer and rows:
        mine = set(
            QuestionVote.objects.filter(
                answer_id__in=[a.id for a in rows], social_user=viewer,
            ).values_list("answer_id", flat=True)
        )
    for a in rows:
        a.voted_by_me = a.id in mine
    return rows


def toggle_vote(me, answer) -> str:
    if not me or not answer:
        return ""
    existing = QuestionVote.objects.filter(answer=answer, social_user=me).first()
    if existing:
        existing.delete()
        bump_news()
        return "unvoted"
    QuestionVote.objects.create(answer=answer, social_user=me, created_at=now())
    bump_news()
    return "voted"
