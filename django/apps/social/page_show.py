"""Page show context — views_pages.page_show stays thin."""
from __future__ import annotations

from django.db.models import Count

from apps.social.forms import CommentForm, EventForm, PagePostForm
from apps.social.models import Company, CompanyAdmin, CompanyFollower
from apps.social.page_categories import label as industry_label


def build_page_show(request, page, me, *, is_admin, is_fan, page_posts):
    from apps.social import events as ev
    from apps.social import era2012 as e12

    tab = (request.GET.get("tab") or "wall").lower()
    if tab not in ("wall", "timeline", "info"):
        tab = "wall"
    posts = page_posts(page, limit=80 if tab == "timeline" else 30, viewer=me)
    fans = list(
        CompanyFollower.objects.filter(company=page)
        .select_related("social_user").order_by("-id")[:12]
    )
    admins = list(
        CompanyAdmin.objects.filter(company=page)
        .select_related("social_user").order_by("id")[:8]
    )
    timeline = {}
    if tab == "timeline":
        y = int(request.GET.get("y")) if (request.GET.get("y") or "").isdigit() else None
        timeline = e12.page_timeline_bundle(page, year=y, posts=posts)
    return {
        "page": page, "me": me, "is_admin": is_admin, "is_fan": is_fan,
        "posts": posts if tab == "wall" else [], "fans": fans, "admins": admins,
        "industry_label": industry_label(page.industry),
        "post_form": PagePostForm() if is_admin and tab == "wall" else None,
        "event_form": EventForm() if is_admin and tab == "wall" else None,
        "page_events": ev.list_page_events(page, upcoming=True, limit=12) if tab == "wall" else [],
        "comment_form": CommentForm() if me and tab == "wall" else None,
        "wall_owner": None,
        "next": request.path,
        "tab": tab,
        **timeline,
    }


def page_qs():
    return Company.objects.annotate(n_fans=Count("followers", distinct=True))
