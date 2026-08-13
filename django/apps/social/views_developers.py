"""Developer Apps cabinet — OAuth-lite keys, callback, docs (no foreign iframe)."""
from __future__ import annotations

import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.social import platform_apps as pa
from apps.social import platform_oauth as oauth
from apps.social.models import DevApp
from apps.social.services import now, profile_of

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,38}[a-z0-9]$")


def _normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url[:255]


def _valid_slug(slug: str) -> bool:
    slug = (slug or "").strip().lower()
    if not slug or not _SLUG_RE.match(slug):
        return False
    if slug in pa.RESERVED_SLUGS:
        return False
    return True


def _enrich(rows):
    out = []
    for a in rows:
        oauth.ensure_app_credentials(a)
        a.n_installs = oauth.install_count(a.slug)
        out.append(a)
    return out


@login_required
@require_http_methods(["GET", "HEAD"])
def developer_home(request):
    me = profile_of(request.user)
    rows = _enrich(list(DevApp.objects.filter(owner=me).order_by("-id")[:40]))
    return render(request, "social/developers.html", {
        "me": me, "apps": rows, "nav": "developers",
        "categories": pa.APP_CATEGORIES,
    })


@login_required
@require_http_methods(["GET", "HEAD"])
def developer_docs(request):
    me = profile_of(request.user)
    return render(request, "social/developer_docs.html", {
        "me": me, "nav": "developers",
    })


@login_required
@require_http_methods(["GET", "POST"])
def developer_new(request):
    me = profile_of(request.user)
    errors = {}
    data = {
        "slug": "", "name": "", "category": "utilities",
        "blurb": "", "detail": "", "website_url": "", "callback_url": "",
        "published": True,
    }
    if request.method == "POST":
        data = {
            "slug": (request.POST.get("slug") or "").strip().lower(),
            "name": (request.POST.get("name") or "").strip()[:80],
            "category": (request.POST.get("category") or "utilities").strip().lower()[:20],
            "blurb": (request.POST.get("blurb") or "").strip()[:200],
            "detail": (request.POST.get("detail") or "").strip()[:500],
            "website_url": _normalize_url(request.POST.get("website_url") or ""),
            "callback_url": _normalize_url(request.POST.get("callback_url") or ""),
            "published": request.POST.get("published") == "1",
        }
        if data["category"] not in {c[0] for c in pa.APP_CATEGORIES}:
            data["category"] = "utilities"
        if not data["name"]:
            errors["name"] = "Укажите название."
        if not _valid_slug(data["slug"]):
            errors["slug"] = "Slug: 2–40 символов (a-z, 0-9, -), не занят системой."
        elif DevApp.objects.filter(slug=data["slug"]).exists():
            errors["slug"] = "Этот slug уже занят."
        if not data["website_url"]:
            errors["website_url"] = "Укажите сайт приложения (например https://somneniya.ru)."
        if data["callback_url"] and not oauth.same_origin_or_path(
            data["callback_url"], data["website_url"]
        ):
            # allow callback on same host as website, or empty
            if not data["website_url"]:
                errors["callback_url"] = "Сначала укажите сайт."
            else:
                errors["callback_url"] = "Callback должен быть на том же домене, что и сайт."
        if not errors:
            t = now()
            app = DevApp.objects.create(
                owner=me, slug=data["slug"], name=data["name"],
                category=data["category"], blurb=data["blurb"] or data["name"],
                detail=data["detail"] or data["blurb"] or data["name"],
                website_url=data["website_url"],
                callback_url=data["callback_url"] or data["website_url"],
                api_key=oauth.new_api_key(),
                api_secret=oauth.new_api_secret(),
                published=data["published"],
                featured=False, created_at=t, updated_at=t,
            )
            messages.success(request, f"Приложение «{app.name}» создано. Ключи — на странице редактирования.")
            return redirect("developers.edit", slug=app.slug)
    return render(request, "social/developer_edit.html", {
        "me": me, "nav": "developers", "categories": pa.APP_CATEGORIES,
        "data": data, "errors": errors, "is_new": True, "app": None,
        "n_installs": 0,
    })


@login_required
@require_http_methods(["GET", "POST"])
def developer_edit(request, slug):
    me = profile_of(request.user)
    app = get_object_or_404(DevApp, slug=slug, owner=me)
    oauth.ensure_app_credentials(app)
    errors = {}
    data = {
        "slug": app.slug, "name": app.name, "category": app.category,
        "blurb": app.blurb, "detail": app.detail,
        "website_url": app.website_url, "callback_url": app.callback_url,
        "published": app.published,
    }
    if request.method == "POST":
        data = {
            "slug": app.slug,
            "name": (request.POST.get("name") or "").strip()[:80],
            "category": (request.POST.get("category") or "utilities").strip().lower()[:20],
            "blurb": (request.POST.get("blurb") or "").strip()[:200],
            "detail": (request.POST.get("detail") or "").strip()[:500],
            "website_url": _normalize_url(request.POST.get("website_url") or ""),
            "callback_url": _normalize_url(request.POST.get("callback_url") or ""),
            "published": request.POST.get("published") == "1",
        }
        if data["category"] not in {c[0] for c in pa.APP_CATEGORIES}:
            data["category"] = "utilities"
        if not data["name"]:
            errors["name"] = "Укажите название."
        if not data["website_url"]:
            errors["website_url"] = "Укажите сайт приложения."
        if data["callback_url"] and not oauth.same_origin_or_path(
            data["callback_url"], data["website_url"]
        ):
            errors["callback_url"] = "Callback должен быть на том же домене, что и сайт."
        if not errors:
            app.name = data["name"]
            app.category = data["category"]
            app.blurb = data["blurb"] or data["name"]
            app.detail = data["detail"] or app.blurb
            app.website_url = data["website_url"]
            app.callback_url = data["callback_url"] or data["website_url"]
            app.published = data["published"]
            app.updated_at = now()
            app.save()
            messages.success(request, "Сохранено.")
            return redirect("developers.edit", slug=app.slug)
    return render(request, "social/developer_edit.html", {
        "me": me, "nav": "developers", "categories": pa.APP_CATEGORIES,
        "data": data, "errors": errors, "is_new": False, "app": app,
        "n_installs": oauth.install_count(app.slug),
    })


@login_required
@require_POST
def developer_rotate(request, slug):
    me = profile_of(request.user)
    app = get_object_or_404(DevApp, slug=slug, owner=me)
    app.api_key = oauth.new_api_key()
    app.api_secret = oauth.new_api_secret()
    app.updated_at = now()
    app.save(update_fields=["api_key", "api_secret", "updated_at"])
    messages.info(request, "Ключи API перевыпущены. Обновите их на своём сайте.")
    return redirect("developers.edit", slug=app.slug)


@login_required
@require_POST
def developer_delete(request, slug):
    me = profile_of(request.user)
    app = get_object_or_404(DevApp, slug=slug, owner=me)
    name = app.name
    from apps.social.models import AppAccessToken, AppInstall, AppOAuthCode
    AppInstall.objects.filter(app_slug=app.slug).delete()
    AppOAuthCode.objects.filter(app_slug=app.slug).delete()
    AppAccessToken.objects.filter(app_slug=app.slug).delete()
    app.delete()
    messages.info(request, f"Приложение «{name}» удалено.")
    return redirect("developers")
