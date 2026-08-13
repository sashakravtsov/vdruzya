"""Pages (Страницы) — classic FB Pages on companies schema."""
from django.contrib import messages
from django.contrib.auth.decorators import login_not_required, login_required
from django.core.paginator import Paginator
from django.db.models import Count, Exists, OuterRef, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.social.forms import CommentForm, PageForm, PagePostForm
from apps.social.models import (
    POST_DEFER, Comment, Company, CompanyAdmin, CompanyFollower, Post, profile_related,
)
from apps.social.page_categories import CATALOG, label as industry_label
from apps.social.services import bump_news, now, profile_of


def _is_admin(me, page) -> bool:
    return bool(me and CompanyAdmin.objects.filter(company=page, social_user=me).exists())


def _is_fan(me, page) -> bool:
    return bool(me and CompanyFollower.objects.filter(company=page, social_user=me).exists())


def _page_posts(page, limit=30, viewer=None):
    posts = list(
        Post.objects.filter(topic=page.topic_key)
        .exclude(kind__in=("status", "picture", "poll", "share", "note"))
        .select_related("social_user")
        .defer(*POST_DEFER, *profile_related("social_user__"))
        .prefetch_related(
            "media",
            Prefetch(
                "comments",
                queryset=Comment.objects.select_related("social_user")
                .defer(*profile_related("social_user__")).order_by("id"),
            ),
        )
        .annotate(n_comments=Count("comments", distinct=True))
        .order_by("-id")[:limit]
    )
    from apps.social.classic_extra import hydrate_posted
    from apps.social.likes import attach_likes
    attach_likes(posts, viewer)
    for p in posts:
        if getattr(p, "kind", None) in ("link", "video"):
            hydrate_posted(p)
    return posts


@login_not_required
@require_http_methods(["GET", "POST"])
def pages_home(request):
    """Directory + create Page."""
    me = profile_of(request.user) if request.user.is_authenticated else None
    form = PageForm(request.POST or None)
    if request.method == "POST":
        if not me:
            return redirect("/login?next=/pages")
        if form.is_valid():
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
            messages.success(request, "Страница создана.")
            return redirect(page)

    q = (request.GET.get("q") or "").strip()
    mine = request.GET.get("mine") == "1"
    industry = (request.GET.get("industry") or "").strip()
    if mine and not me:
        return redirect("/login?next=/pages?mine=1")

    qs = Company.objects.annotate(n_fans=Count("followers", distinct=True))
    if me:
        qs = qs.annotate(
            is_fan=Exists(CompanyFollower.objects.filter(company_id=OuterRef("pk"), social_user=me)),
            is_admin=Exists(CompanyAdmin.objects.filter(company_id=OuterRef("pk"), social_user=me)),
        )
    if mine and me:
        qs = qs.filter(
            Q(admins__social_user=me) | Q(followers__social_user=me)
        ).distinct()
    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(city__icontains=q) | Q(description__icontains=q)
        )
    if industry:
        qs = qs.filter(industry=industry)
    page_obj = Paginator(qs.order_by("name"), 20).get_page(request.GET.get("p"))
    return render(request, "social/pages.html", {
        "me": me, "form": form, "pages": page_obj, "page_obj": page_obj,
        "q": q, "mine": mine, "industry": industry,
        "industries": [c[0] for c in CATALOG],
    })


@login_not_required
@require_http_methods(["GET", "HEAD"])
def page_show(request, pk):
    page = get_object_or_404(
        Company.objects.annotate(n_fans=Count("followers", distinct=True)),
        pk=pk,
    )
    me = profile_of(request.user) if request.user.is_authenticated else None
    is_admin = _is_admin(me, page)
    is_fan = _is_fan(me, page)
    tab = (request.GET.get("tab") or "wall").lower()
    if tab not in ("wall", "timeline", "info"):
        tab = "wall"
    posts = _page_posts(page, limit=80 if tab == "timeline" else 30, viewer=me)
    fans = list(
        CompanyFollower.objects.filter(company=page)
        .select_related("social_user")
        .order_by("-id")[:12]
    )
    admins = list(
        CompanyAdmin.objects.filter(company=page)
        .select_related("social_user")
        .order_by("id")[:8]
    )
    from apps.social import events as ev
    from apps.social import era2012 as e12
    from apps.social.forms import EventForm
    page_events = ev.list_page_events(page, upcoming=True, limit=12)
    timeline = {}
    if tab == "timeline":
        y = None
        if (request.GET.get("y") or "").isdigit():
            y = int(request.GET.get("y"))
        timeline = e12.page_timeline_bundle(page, year=y, posts=posts)
    return render(request, "social/page.html", {
        "page": page, "me": me, "is_admin": is_admin, "is_fan": is_fan,
        "posts": posts if tab == "wall" else [], "fans": fans, "admins": admins,
        "industry_label": industry_label(page.industry),
        "post_form": PagePostForm() if is_admin and tab == "wall" else None,
        "event_form": EventForm() if is_admin and tab == "wall" else None,
        "page_events": page_events if tab == "wall" else [],
        "comment_form": CommentForm() if me and tab == "wall" else None,
        "wall_owner": None,
        "next": request.path,
        "tab": tab,
        **timeline,
    })


@login_required
@require_http_methods(["GET", "POST"])
def page_edit(request, pk):
    me = profile_of(request.user)
    page = get_object_or_404(Company, pk=pk)
    if not _is_admin(me, page):
        messages.error(request, "Редактировать могут только администраторы.")
        return redirect(page)
    initial = {
        "name": page.name, "industry": page.industry or "other",
        "city": page.city or "", "description": page.description or "",
    }
    form = PageForm(request.POST or None, initial=None if request.method == "POST" else initial)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        page.name = d["name"]
        page.industry = d["industry"] or "other"
        page.city = d.get("city") or ""
        page.description = d.get("description") or ""
        page.updated_at = now()
        page.save(update_fields=["name", "industry", "city", "description", "updated_at"])
        messages.success(request, "Страница сохранена.")
        return redirect(page)
    return render(request, "social/page_edit.html", {"page": page, "form": form, "me": me})


@login_required
@require_POST
def page_fan(request, pk):
    me = profile_of(request.user)
    page = get_object_or_404(Company, pk=pk)
    if not CompanyFollower.objects.filter(company=page, social_user=me).exists():
        t = now()
        CompanyFollower.objects.create(company=page, social_user=me, created_at=t, updated_at=t)
        bump_news()
        messages.success(request, "Вы стали поклонником страницы.")
    return redirect(page)


@login_required
@require_POST
def page_unfan(request, pk):
    me = profile_of(request.user)
    page = get_object_or_404(Company, pk=pk)
    if _is_admin(me, page):
        messages.error(request, "Администратор не может покинуть страницу.")
        return redirect(page)
    CompanyFollower.objects.filter(company=page, social_user=me).delete()
    bump_news()
    messages.success(request, "Вы больше не поклонник.")
    return redirect(page)


@login_required
@require_POST
def page_post(request, pk):
    me = profile_of(request.user)
    page = get_object_or_404(Company, pk=pk)
    if not _is_admin(me, page):
        messages.error(request, "Писать на стене страницы могут администраторы.")
        return redirect(page)
    form = PagePostForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Проверьте текст или фото.")
        return redirect(page)
    from apps.social.attach import apply_wall_uploads
    t = now()
    body = (form.cleaned_data.get("body") or "").strip()
    post = Post(
        social_user=me, body=body, visibility="public",
        kind="text", topic=page.topic_key,
        created_at=t, updated_at=t,
    )
    post.save()
    apply_wall_uploads(
        post, list(request.FILES.getlist("photo")), me, max_photos=5, blurb=body,
    )
    bump_news()
    messages.success(request, "Запись опубликована.")
    return redirect(page)


@login_required
@require_POST
def page_event_create(request, pk):
    me = profile_of(request.user)
    page = get_object_or_404(Company, pk=pk)
    if not _is_admin(me, page):
        messages.error(request, "Создавать события могут администраторы.")
        return redirect(page)
    from apps.social import events as ev
    from apps.social.forms import EventForm
    form = EventForm(request.POST)
    if form.is_valid():
        event = ev.create_event(
            me,
            title=form.cleaned_data["title"],
            place=form.cleaned_data.get("place") or "—",
            description=form.cleaned_data.get("description") or "",
            starts_at=form.cleaned_data["starts_at"],
            company=page,
        )
        if event:
            ev.set_rsvp(me, event, "going")
            messages.success(request, "Событие страницы создано.")
            return redirect(event)
        messages.error(request, "Не удалось создать событие.")
    else:
        messages.error(request, "Укажите название и дату.")
    return redirect(page)


@login_not_required
@require_http_methods(["GET", "HEAD"])
def page_slug_redirect(request, slug):
    page = get_object_or_404(Company, slug=slug)
    return redirect(page, permanent=True)
