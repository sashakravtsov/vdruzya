"""Pages directory — create + browse; views_pages.pages_home stays thin."""
from __future__ import annotations

from django.core.paginator import Paginator
from django.db.models import Count, Exists, OuterRef, Q

from apps.social.forms import PageForm
from apps.social.models import Company, CompanyAdmin, CompanyFollower
from apps.social.page_categories import CATALOG
from apps.social.services import bump_news, now


def create_page(me, form: PageForm):
    from apps.social.media import try_save_image
    from apps.social.slugs import unique_slug
    d = form.cleaned_data
    t = now()
    page = Company(
        name=d["name"],
        slug=unique_slug(Company, d["name"], fallback="page"),
        industry=d["industry"] or "other",
        city=d.get("city") or "",
        size="",
        cover_color="#3B5998",
        cover_path=try_save_image(d.get("cover"), "page-covers"),
        description=d.get("description") or "",
        created_at=t, updated_at=t,
    )
    page.save()
    CompanyAdmin.objects.create(
        company=page, social_user=me, role="admin", created_at=t, updated_at=t,
    )
    CompanyFollower.objects.create(
        company=page, social_user=me, created_at=t, updated_at=t,
    )
    bump_news()
    return page


def browse_pages(me, *, q="", mine=False, industry="", page_num=None):
    qs = Company.objects.annotate(n_fans=Count("followers", distinct=True))
    if me:
        qs = qs.annotate(
            is_fan=Exists(CompanyFollower.objects.filter(company_id=OuterRef("pk"), social_user=me)),
            is_admin=Exists(CompanyAdmin.objects.filter(company_id=OuterRef("pk"), social_user=me)),
        )
    if mine and me:
        qs = qs.filter(Q(admins__social_user=me) | Q(followers__social_user=me)).distinct()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(city__icontains=q) | Q(description__icontains=q))
    if industry:
        qs = qs.filter(industry=industry)
    return Paginator(qs.order_by("name"), 20).get_page(page_num)


def directory_ctx(request, me):
    form = PageForm(request.POST or None, request.FILES or None)
    created = None
    if request.method == "POST" and me and form.is_valid():
        created = create_page(me, form)
    q = (request.GET.get("q") or "").strip()
    mine = request.GET.get("mine") == "1"
    industry = (request.GET.get("industry") or "").strip()
    page_obj = browse_pages(me, q=q, mine=mine, industry=industry, page_num=request.GET.get("p"))
    return {
        "created": created,
        "need_login_mine": bool(mine and not me),
        "me": me, "form": form, "pages": page_obj, "page_obj": page_obj,
        "q": q, "mine": mine, "industry": industry,
        "industries": [c[0] for c in CATALOG],
    }
