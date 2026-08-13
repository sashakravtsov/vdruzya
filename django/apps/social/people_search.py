"""Find Friends filters — friendship.find_people re-exports."""
from __future__ import annotations

from django.core.paginator import Paginator
from django.db.models import Q

from apps.social.models import Block, Education, Experience, SocialProfile


def _ban_ids(me) -> set[int]:
    ban = set(Block.objects.filter(blocker=me).values_list("blocked_id", flat=True))
    ban |= set(Block.objects.filter(blocked=me).values_list("blocker_id", flat=True))
    return ban


def _apply_filters(qs, *, q, city, school, gender, workplace):
    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(city__icontains=q) | Q(headline__icontains=q)
            | Q(slug__icontains=q) | Q(hometown__icontains=q) | Q(workplace__icontains=q)
        )
    if city:
        qs = qs.filter(Q(city__icontains=city) | Q(hometown__icontains=city))
    if school:
        ids = Education.objects.filter(institution__icontains=school).values_list(
            "social_user_id", flat=True,
        )
        qs = qs.filter(id__in=ids)
    if gender in ("male", "female"):
        qs = qs.filter(gender=gender)
    if workplace:
        exp_ids = Experience.objects.filter(company_name__icontains=workplace).values_list(
            "social_user_id", flat=True,
        )
        qs = qs.filter(Q(workplace__icontains=workplace) | Q(id__in=exp_ids))
    return qs


def find_people(me, *, q="", city="", school="", gender="", workplace="", page=1, per=24):
    """Classic Find Friends search (both-way blocks excluded)."""
    qs = SocialProfile.objects.exclude(id=me.id).exclude(id__in=_ban_ids(me))
    qs = _apply_filters(
        qs,
        q=(q or "").strip(),
        city=(city or "").strip(),
        school=(school or "").strip(),
        gender=(gender or "").strip(),
        workplace=(workplace or "").strip(),
    )
    return Paginator(qs.order_by("name"), per).get_page(page)
