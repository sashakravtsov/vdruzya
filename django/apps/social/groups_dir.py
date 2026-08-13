"""Groups directory — create + browse; views_browse.groups stays thin."""
from __future__ import annotations

from django.db.models import Count, Exists, OuterRef, Q
from django.core.paginator import Paginator

from apps.social.forms import CreateGroupForm
from apps.social.models import Community, CommunityJoinRequest, CommunityMember
from apps.social.services import now as _now


def create_group(me, form: CreateGroupForm):
    from apps.social.media import try_save_image
    from apps.social.slugs import unique_slug
    d = form.cleaned_data
    blurb = (d.get("short_description") or "").strip()
    g = Community(
        name=d["name"].strip(), slug=unique_slug(Community, d["name"]),
        category=d["category"], privacy=d["privacy"], short_description=blurb or None,
        description=blurb or d["name"].strip(),
        cover_color="#3B5998",
        cover_path=try_save_image(d.get("picture"), "groups"),
        join_mode="request" if d["privacy"] == "closed" else "open",
        posting_policy="members",
        creator=me, created_at=_now(), updated_at=_now(),
    )
    g.save()
    CommunityMember.objects.create(community=g, social_user=me, role="admin", created_at=_now())
    return g


def browse_groups(me, *, q="", mine=False, category="", page_num=None):
    qs = Community.objects.annotate(n_members=Count("memberships", distinct=True))
    if me:
        qs = qs.annotate(
            joined=Exists(CommunityMember.objects.filter(community_id=OuterRef("pk"), social_user=me)),
            join_pending=Exists(
                CommunityJoinRequest.objects.filter(
                    community_id=OuterRef("pk"), social_user=me, status="pending",
                )
            ),
        )
    if mine and me:
        qs = qs.filter(memberships__social_user=me).distinct()
    if category:
        qs = qs.filter(category=category)
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(slug__icontains=q) | Q(short_description__icontains=q))
    page = Paginator(qs.order_by("name"), 20).get_page(page_num)
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
    return page, list(cats), invites


def directory_ctx(request, me):
    form = CreateGroupForm(request.POST or None, request.FILES or None)
    created = None
    if request.method == "POST" and me and form.is_valid():
        created = create_group(me, form)
    q = (request.GET.get("q") or "").strip()
    mine = request.GET.get("mine") == "1"
    category = (request.GET.get("category") or "").strip()
    page, cats, invites = browse_groups(
        me, q=q, mine=mine, category=category, page_num=request.GET.get("p"),
    )
    return {
        "created": created,
        "need_login_mine": bool(mine and not me),
        "page": page, "communities": page, "me": me, "form": form,
        "q": q, "mine": mine, "category": category, "categories": cats,
        "invites": invites,
    }
