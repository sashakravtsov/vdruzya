"""Global Search (gnav) — people / groups / pages; views_browse.search stays thin."""
from __future__ import annotations

from django.db.models import Q

from apps.social.models import Community, Company


def _people(me, q):
    from apps.social import friendship as fr
    page = fr.find_people(me, q=q, page=1, per=20)
    people = list(page)
    rel = fr.relations_for(me, [p.id for p in people])
    for p in people:
        n = fr.mutual_count(me, p)
        p.rel = rel.get(p.id)
        p.mutual = fr.mutual_label(n) if n else ""
    return people


def _groups(q):
    return list(
        Community.objects.filter(Q(name__icontains=q) | Q(slug__icontains=q)).order_by("name")[:20]
    )


def _pages(q):
    return list(
        Company.objects.filter(
            Q(name__icontains=q) | Q(slug__icontains=q) | Q(city__icontains=q)
        ).order_by("name")[:20]
    )


def search_ctx(me, request):
    q = (request.GET.get("q") or request.GET.get("name") or "").strip()
    tab = (request.GET.get("tab") or "people").strip()
    if tab not in ("people", "groups", "pages"):
        tab = "people"
    people = groups_qs = pages_qs = []
    searched = bool(q)
    if searched and me:
        people, groups_qs, pages_qs = _people(me, q), _groups(q), _pages(q)
    return {
        "q": q, "tab": tab, "searched": searched,
        "people": people, "groups": groups_qs, "pages": pages_qs, "me": me,
    }
