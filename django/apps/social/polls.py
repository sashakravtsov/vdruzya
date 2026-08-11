"""Tiny poll helpers — no fat services."""
from django.db import transaction
from django.db.models import F

from apps.social.models import (
    CommunityPollOption, CommunityPollVote, CommunityPostPoll, PollOption, PollVote, PostPoll,
)
from apps.social.services import now


def attach_post_poll(post, labels: list[str], multi=False):
    labels = [x.strip() for x in labels if x and x.strip()][:8]
    if len(labels) < 2:
        return None
    t = now()
    poll = PostPoll.objects.create(post=post, allows_multiple=multi, votes_count=0, created_at=t, updated_at=t)
    PollOption.objects.bulk_create(
        [PollOption(poll=poll, label=lab, sort_order=i, votes_count=0) for i, lab in enumerate(labels)]
    )
    return poll


def attach_group_poll(post, labels: list[str], multi=False):
    labels = [x.strip() for x in labels if x and x.strip()][:8]
    if len(labels) < 2:
        return None
    t = now()
    poll = CommunityPostPoll.objects.create(
        post=post, allows_multiple=multi, votes_count=0, created_at=t, updated_at=t
    )
    CommunityPollOption.objects.bulk_create(
        [CommunityPollOption(poll=poll, label=lab, sort_order=i, votes_count=0) for i, lab in enumerate(labels)]
    )
    return poll


@transaction.atomic
def vote_post_option(me, option: PollOption):
    poll = option.poll
    if not poll.allows_multiple:
        old = PollVote.objects.filter(option__poll=poll, social_user=me).select_related("option").first()
        if old and old.option_id == option.id:
            old.delete()
            PollOption.objects.filter(pk=option.pk).update(votes_count=F("votes_count") - 1)
            PostPoll.objects.filter(pk=poll.pk).update(votes_count=F("votes_count") - 1)
            return
        if old:
            PollOption.objects.filter(pk=old.option_id).update(votes_count=F("votes_count") - 1)
            old.delete()
            PostPoll.objects.filter(pk=poll.pk).update(votes_count=F("votes_count") - 1)
    else:
        row = PollVote.objects.filter(option=option, social_user=me).first()
        if row:
            row.delete()
            PollOption.objects.filter(pk=option.pk).update(votes_count=F("votes_count") - 1)
            PostPoll.objects.filter(pk=poll.pk).update(votes_count=F("votes_count") - 1)
            return
    PollVote.objects.create(option=option, social_user=me, created_at=now())
    PollOption.objects.filter(pk=option.pk).update(votes_count=F("votes_count") + 1)
    PostPoll.objects.filter(pk=poll.pk).update(votes_count=F("votes_count") + 1)


@transaction.atomic
def vote_group_option(me, option: CommunityPollOption):
    poll = option.poll
    if not poll.allows_multiple:
        old = CommunityPollVote.objects.filter(option__poll=poll, social_user=me).select_related("option").first()
        if old and old.option_id == option.id:
            old.delete()
            CommunityPollOption.objects.filter(pk=option.pk).update(votes_count=F("votes_count") - 1)
            CommunityPostPoll.objects.filter(pk=poll.pk).update(votes_count=F("votes_count") - 1)
            return
        if old:
            CommunityPollOption.objects.filter(pk=old.option_id).update(votes_count=F("votes_count") - 1)
            old.delete()
            CommunityPostPoll.objects.filter(pk=poll.pk).update(votes_count=F("votes_count") - 1)
    else:
        row = CommunityPollVote.objects.filter(option=option, social_user=me).first()
        if row:
            row.delete()
            CommunityPollOption.objects.filter(pk=option.pk).update(votes_count=F("votes_count") - 1)
            CommunityPostPoll.objects.filter(pk=poll.pk).update(votes_count=F("votes_count") - 1)
            return
    CommunityPollVote.objects.create(option=option, social_user=me, created_at=now())
    CommunityPollOption.objects.filter(pk=option.pk).update(votes_count=F("votes_count") + 1)
    CommunityPostPoll.objects.filter(pk=poll.pk).update(votes_count=F("votes_count") + 1)
