"""FB 2010 Places + Questions + Reviews + classic Polls helpers."""
from __future__ import annotations

from django.db.models import Count

from apps.social.models import (
    ClassicPoll, ClassicPollOption, ClassicPollVote,
    Place, PlaceCheckin, PlaceReview,
    Post, Question, QuestionAnswer, QuestionVote,
)
from apps.social.services import bump_news, friend_ids, now, profile_related


def places_list(q="", city="", limit=40):
    qs = Place.objects.all().order_by("name")
    if q:
        qs = qs.filter(name__icontains=q)
    if city:
        qs = qs.filter(city__icontains=city)
    return list(qs[:limit])


def place_create(me, *, name, city="", address="", photo=None):
    from apps.social.media import try_save_image
    name = (name or "").strip()[:160]
    if not me or not name:
        return None
    t = now()
    return Place.objects.create(
        name=name,
        city=(city or "").strip()[:120],
        address=(address or "").strip()[:255],
        photo_path=try_save_image(photo, "places"),
        created_at=t, updated_at=t,
    )


def place_checkin(me, place, message="", photo=None):
    from apps.social.media import try_save_image
    if not me or not place:
        return None
    t = now()
    msg = (message or "").strip()[:500]
    path = try_save_image(photo, "checkins")
    checkin = PlaceCheckin.objects.create(
        place=place, social_user=me, message=msg, photo_path=path, created_at=t,
    )
    Post.objects.create(
        social_user=me,
        body=msg or f"в «{place.name}»",
        kind="checkin",
        topic=f"place:{place.id}",
        media_label=place.name,
        media_path=path,
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


def place_reviews(place, limit=40):
    return list(
        PlaceReview.objects.filter(place=place)
        .select_related("social_user")
        .defer(*profile_related("social_user__"))
        .order_by("-id")[:limit]
    )


def place_review_upsert(me, place, *, stars: int, body="") -> PlaceReview | None:
    if not me or not place:
        return None
    try:
        stars = int(stars)
    except (TypeError, ValueError):
        return None
    if stars < 1 or stars > 5:
        return None
    body = (body or "").strip()[:500]
    t = now()
    existing = PlaceReview.objects.filter(place=place, social_user=me).first()
    if existing:
        existing.stars = stars
        existing.body = body
        existing.created_at = t
        existing.save(update_fields=["stars", "body", "created_at"])
        bump_news()
        return existing
    row = PlaceReview.objects.create(
        place=place, social_user=me, stars=stars, body=body, created_at=t,
    )
    bump_news()
    return row


def my_place_review(me, place):
    if not me or not place:
        return None
    return PlaceReview.objects.filter(place=place, social_user=me).first()


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


def question_create(me, body: str, photo=None):
    from apps.social.media import try_save_image
    body = (body or "").strip()[:500]
    if not me or not body:
        return None
    t = now()
    q = Question.objects.create(
        social_user=me, body=body,
        photo_path=try_save_image(photo, "questions"),
        created_at=t, updated_at=t,
    )
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


def polls_feed(viewer, *, mine=False, limit=40):
    fids = friend_ids(viewer) | {viewer.id} if viewer else set()
    qs = (
        ClassicPoll.objects.select_related("social_user")
        .defer(*profile_related("social_user__"))
        .annotate(n_votes=Count("votes", distinct=True))
        .order_by("-id")
    )
    if mine and viewer:
        qs = qs.filter(social_user=viewer)
    elif viewer:
        qs = qs.filter(social_user_id__in=fids)
    return list(qs[:limit])


def poll_create(me, question: str, options: list[str]):
    question = (question or "").strip()[:500]
    opts = []
    for raw in options or []:
        body = (raw or "").strip()[:255]
        if body and body not in opts:
            opts.append(body)
    if not me or not question or len(opts) < 2:
        return None
    t = now()
    poll = ClassicPoll.objects.create(
        social_user=me, question=question, created_at=t, updated_at=t,
    )
    for i, body in enumerate(opts[:8]):
        ClassicPollOption.objects.create(poll=poll, body=body, sort_order=i)
    bump_news()
    return poll


def poll_options(poll, viewer=None):
    rows = list(
        ClassicPollOption.objects.filter(poll=poll)
        .annotate(n_votes=Count("votes", distinct=True))
        .order_by("sort_order", "id")
    )
    my_option = None
    if viewer:
        vote = (
            ClassicPollVote.objects.filter(poll=poll, social_user=viewer)
            .values_list("option_id", flat=True)
            .first()
        )
        my_option = vote
    total = sum(getattr(o, "n_votes", 0) or 0 for o in rows) or 0
    for o in rows:
        o.voted_by_me = o.id == my_option
        o.pct = int(round(100 * (o.n_votes or 0) / total)) if total else 0
    return rows, my_option, total


def poll_vote(me, poll, option) -> str:
    if not me or not poll or not option or option.poll_id != poll.id:
        return ""
    existing = ClassicPollVote.objects.filter(poll=poll, social_user=me).first()
    if existing and existing.option_id == option.id:
        existing.delete()
        bump_news()
        return "unvoted"
    if existing:
        existing.option = option
        existing.created_at = now()
        existing.save(update_fields=["option", "created_at"])
        bump_news()
        return "changed"
    ClassicPollVote.objects.create(
        poll=poll, option=option, social_user=me, created_at=now(),
    )
    bump_news()
    return "voted"
