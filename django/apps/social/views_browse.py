"""Browse FBVs: people, groups, search — short only."""
from django.contrib.auth.decorators import login_not_required, login_required
from django.contrib.postgres.search import SearchHeadline, SearchQuery, SearchRank
from django.db.models import Count, Exists, OuterRef, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.views.decorators.http import condition, require_http_methods, require_POST

from apps.social.forms import CreateGroupForm
from apps.social.models import (
    Community, CommunityJoinRequest, CommunityMember, CommunityPost, SocialProfile,
)
from apps.social.services import now as _now, profile_of


# Bump when group.html / rail markup changes (avoids stale 304 HTML in browsers).
_GROUP_UI = "g9"


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
    from django.core.paginator import Paginator
    me = profile_of(request.user) if request.user.is_authenticated else None
    form = CreateGroupForm(request.POST or None)
    if request.method == "POST":
        if not me:
            return redirect(f"/login?next=/groups")
        if form.is_valid():
            from apps.social.slugs import unique_slug
            d = form.cleaned_data
            blurb = (d.get("short_description") or "").strip()
            g = Community(
                name=d["name"].strip(), slug=unique_slug(Community, d["name"]),
                category=d["category"], privacy=d["privacy"], short_description=blurb or None,
                description=blurb or d["name"].strip(),
                cover_color="#3B5998",
                join_mode="request" if d["privacy"] == "closed" else "open",
                posting_policy="members",
                messaging_enabled=False, creator=me, created_at=_now(), updated_at=_now(),
            )
            g.save()
            CommunityMember.objects.create(community=g, social_user=me, role="admin", created_at=_now())
            messages.success(request, "Группа создана.")
            return redirect(g)

    q = (request.GET.get("q") or "").strip()
    mine = request.GET.get("mine") == "1"
    category = (request.GET.get("category") or "").strip()
    if mine and not me:
        return redirect("/login?next=/groups?mine=1")

    qs = Community.objects.annotate(n_members=Count("memberships", distinct=True))
    if me:
        qs = qs.annotate(
            joined=Exists(CommunityMember.objects.filter(community_id=OuterRef("pk"), social_user=me)),
            join_pending=Exists(
                CommunityJoinRequest.objects.filter(community_id=OuterRef("pk"), social_user=me, status="pending")
            ),
        )
    if mine and me:
        qs = qs.filter(memberships__social_user=me).distinct()
    if category:
        qs = qs.filter(category=category)
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(slug__icontains=q) | Q(short_description__icontains=q))
    page = Paginator(qs.order_by("name"), 20).get_page(request.GET.get("p"))
    cats = (
        Community.objects.exclude(category="")
        .values_list("category", flat=True).distinct().order_by("category")
    )
    invites = []
    if mine and me:
        from apps.social.models import Notification
        invites = list(
            Notification.objects.filter(social_user=me, type="group_invite", seen=False).order_by("-id")[:20]
        )
        if invites:
            Notification.objects.filter(pk__in=[n.id for n in invites]).update(seen=True)
    return render(
        request, "social/groups.html",
        {
            "page": page, "communities": page, "me": me, "form": form,
            "q": q, "mine": mine, "category": category, "categories": list(cats),
            "invites": invites,
        },
    )


@login_not_required
@condition(etag_func=_group_etag)
def group_show(request, pk):
    from apps.social.group_page import page_ctx
    group = get_object_or_404(Community, pk=pk)
    me = profile_of(request.user) if request.user.is_authenticated else None
    return render(request, "social/group.html", page_ctx(request, group, me))


@login_required
def search(request):
    from apps.social import friendship as fr
    from apps.social.models import Post

    q = (request.GET.get("q") or "").strip()
    name = (request.GET.get("name") or "").strip()
    city = (request.GET.get("city") or "").strip()
    school = (request.GET.get("school") or "").strip()
    me = profile_of(request.user)
    people = groups_qs = posts = []
    searched = bool(q or name or city or school)
    if searched and me:
        page = fr.find_people(me, q=name or q, city=city, school=school, page=1, per=20)
        people = list(page)
        rel = fr.relations_for(me, [p.id for p in people])
        for p in people:
            n = fr.mutual_count(me, p)
            p.rel = rel.get(p.id)
            p.mutual = fr.mutual_label(n) if n else ""
        gq = q or name or school or city
        groups_qs = Community.objects.filter(Q(name__icontains=gq) | Q(slug__icontains=gq))[:20]
        if q or name:
            query = SearchQuery(q or name, config="simple", search_type="websearch")
            posts = (
                Post.objects.annotate(
                    rank=SearchRank("search_vector", query),
                    headline=SearchHeadline("body", query, config="simple", start_sel="<b>", stop_sel="</b>", max_words=32),
                )
                .filter(search_vector=query)
                .select_related("social_user")
                .order_by("-rank")[:20]
            )
    return render(
        request, "social/search.html",
        {
            "q": q, "name": name, "city": city, "school": school,
            "searched": searched, "people": people, "groups": groups_qs, "posts": posts, "me": me,
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
