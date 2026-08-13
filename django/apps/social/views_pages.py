"""Pages (Страницы) — classic FB Pages on companies schema."""
from django.contrib import messages
from django.contrib.auth.decorators import login_not_required, login_required
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.social.forms import CommentForm, PageForm, PagePostForm
from apps.social.models import (
    POST_DEFER, Comment, Company, CompanyAdmin, CompanyFollower, Post, profile_related,
)
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
    from apps.social.pages_dir import directory_ctx
    me = profile_of(request.user) if request.user.is_authenticated else None
    if request.method == "POST" and not me:
        return redirect("/login?next=/pages")
    data = directory_ctx(request, me)
    if data["need_login_mine"]:
        return redirect("/login?next=/pages?mine=1")
    if data["created"]:
        messages.success(request, "Страница создана.")
        return redirect(data["created"])
    return render(request, "social/pages.html", {
        "me": me, "form": data["form"], "pages": data["pages"], "page_obj": data["page_obj"],
        "q": data["q"], "mine": data["mine"], "industry": data["industry"],
        "industries": data["industries"],
    })


@login_not_required
@require_http_methods(["GET", "HEAD"])
def page_show(request, pk):
    from apps.social.page_show import build_page_show, page_qs
    page = get_object_or_404(page_qs(), pk=pk)
    me = profile_of(request.user) if request.user.is_authenticated else None
    return render(
        request, "social/page.html",
        build_page_show(
            request, page, me,
            is_admin=_is_admin(me, page), is_fan=_is_fan(me, page),
            page_posts=_page_posts,
        ),
    )


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
    form = EventForm(request.POST, request.FILES)
    if form.is_valid():
        event = ev.create_event(
            me,
            title=form.cleaned_data["title"],
            place=form.cleaned_data.get("place") or "—",
            description=form.cleaned_data.get("description") or "",
            starts_at=form.cleaned_data["starts_at"],
            company=page,
            cover=form.cleaned_data.get("cover"),
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
