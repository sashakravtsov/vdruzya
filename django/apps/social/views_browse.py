"""Browse FBVs: people, groups, search — short only."""
from django.contrib.auth.decorators import login_not_required, login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.views.decorators.http import condition, require_http_methods

from apps.social.models import (
    Community, CommunityJoinRequest, CommunityMember, CommunityPost, SocialProfile,
)
from apps.social.services import profile_of


# Bump when group.html / rail markup changes (avoids stale 304 HTML in browsers).
_GROUP_UI = "g10"


def _group_etag(request, pk):
    row = Community.objects.filter(pk=pk).values("id", "updated_at").first()
    if not row:
        return None
    last = CommunityPost.objects.filter(community_id=row["id"]).order_by("-id").values_list("id", flat=True).first() or 0
    uid = request.user.pk if getattr(request.user, "is_authenticated", False) else 0
    mem = pend = 0
    if uid:
        me = profile_of(request.user)
        if me:
            mem = int(CommunityMember.objects.filter(community_id=row["id"], social_user=me).exists())
            pend = int(
                not mem
                and CommunityJoinRequest.objects.filter(
                    community_id=row["id"], social_user=me, status="pending"
                ).exists()
            )
    return f'{_GROUP_UI}-{row["id"]}-{row["updated_at"]}-{last}-{uid}-{mem}{pend}-{request.GET.urlencode()}'


@login_not_required
@require_http_methods(["GET", "HEAD", "POST"])
def groups(request):
    """FB 2005 groups directory — browse is public; create/mine need login."""
    from apps.social.groups_dir import directory_ctx
    me = profile_of(request.user) if request.user.is_authenticated else None
    if request.method == "POST" and not me:
        return redirect("/login?next=/groups")
    data = directory_ctx(request, me)
    if data["need_login_mine"]:
        return redirect("/login?next=/groups?mine=1")
    if data["created"]:
        messages.success(request, "Группа создана.")
        return redirect(data["created"])
    return render(request, "social/groups.html", {
        "page": data["page"], "communities": data["communities"], "me": me,
        "form": data["form"], "q": data["q"], "mine": data["mine"],
        "category": data["category"], "categories": data["categories"],
        "invites": data["invites"],
    })


@login_not_required
@condition(etag_func=_group_etag)
def group_show(request, pk):
    from apps.social.group_page import page_ctx
    group = get_object_or_404(Community, pk=pk)
    me = profile_of(request.user) if request.user.is_authenticated else None
    return render(request, "social/group.html", page_ctx(request, group, me))


@login_required
def search(request):
    """Global Search (gnav) — people / groups / pages. Find Friends stays on /people."""
    from apps.social import friendship as fr
    from apps.social.models import Company

    q = (request.GET.get("q") or request.GET.get("name") or "").strip()
    tab = (request.GET.get("tab") or "people").strip()
    if tab not in ("people", "groups", "pages"):
        tab = "people"
    me = profile_of(request.user)
    people = groups_qs = pages_qs = []
    searched = bool(q)
    if searched and me:
        page = fr.find_people(me, q=q, page=1, per=20)
        people = list(page)
        rel = fr.relations_for(me, [p.id for p in people])
        for p in people:
            n = fr.mutual_count(me, p)
            p.rel = rel.get(p.id)
            p.mutual = fr.mutual_label(n) if n else ""
        groups_qs = list(
            Community.objects.filter(Q(name__icontains=q) | Q(slug__icontains=q)).order_by("name")[:20]
        )
        pages_qs = list(
            Company.objects.filter(
                Q(name__icontains=q) | Q(slug__icontains=q) | Q(city__icontains=q)
            ).order_by("name")[:20]
        )
    return render(
        request, "social/search.html",
        {
            "q": q, "tab": tab, "searched": searched,
            "people": people, "groups": groups_qs, "pages": pages_qs, "me": me,
        },
    )


@login_not_required
def group_slug_redirect(request, slug):
    g = get_object_or_404(Community.objects.only("id"), slug=slug)
    qs = request.GET.urlencode()
    return redirect(f"{g.get_absolute_url()}{'?' + qs if qs else ''}", permanent=True)


@login_not_required
def profile_slug_redirect(request, slug):
    p = get_object_or_404(SocialProfile.objects.only("id"), slug=slug)
    qs = request.GET.urlencode()
    return redirect(f"{p.get_absolute_url()}{'?' + qs if qs else ''}", permanent=True)
