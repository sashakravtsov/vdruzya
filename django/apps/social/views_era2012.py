"""FB 2012 FBVs — Page Timeline, Collections, App Center detail."""
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_not_required, login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.social import era2012 as e12
from apps.social.models import Collection, Company
from apps.social.services import profile_of


def _admin_page(me, pk):
    from apps.social.views_pages import _is_admin
    page = get_object_or_404(Company, pk=pk)
    if not _is_admin(me, page):
        return None, page
    return True, page


@login_required
@require_POST
def page_milestone_create(request, pk):
    me = profile_of(request.user)
    ok, page = _admin_page(me, pk)
    if not ok:
        messages.error(request, "Только администраторы.")
        return redirect(page)
    raw = (request.POST.get("occurred_on") or "").strip()
    try:
        occurred = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        messages.error(request, "Укажите дату ГГГГ-ММ-ДД.")
        return redirect(f"/pages/{pk}?tab=timeline")
    row = e12.add_page_milestone(
        page,
        title=request.POST.get("title") or "",
        body=request.POST.get("body") or "",
        kind=request.POST.get("kind") or "life",
        occurred_on=occurred,
    )
    if row:
        messages.success(request, "Этап добавлен на Timeline страницы.")
    else:
        messages.error(request, "Не удалось сохранить этап.")
    return redirect(f"/pages/{pk}?tab=timeline&y={occurred.year}")


@login_required
@require_POST
def page_milestone_delete(request, pk, mid):
    me = profile_of(request.user)
    ok, page = _admin_page(me, pk)
    if ok and e12.delete_page_milestone(page, mid):
        messages.info(request, "Этап удалён.")
    return redirect(request.POST.get("next") or f"/pages/{pk}?tab=timeline")


@login_required
@require_POST
def page_cover_upload(request, pk):
    from apps.social.media import try_save_image
    from apps.social.services import bump_news, now

    me = profile_of(request.user)
    ok, page = _admin_page(me, pk)
    if not ok:
        messages.error(request, "Только администраторы.")
        return redirect(page)
    path = try_save_image(request.FILES.get("cover"), "page-covers")
    if path:
        page.cover_path = path
        page.updated_at = now()
        page.save(update_fields=["cover_path", "updated_at"])
        bump_news()
        messages.success(request, "Обложка страницы обновлена.")
    return redirect(request.POST.get("next") or f"/pages/{pk}/edit")


@login_required
@require_POST
def page_cover_clear(request, pk):
    from apps.social.services import bump_news, now

    me = profile_of(request.user)
    ok, page = _admin_page(me, pk)
    if ok and page.cover_path:
        page.cover_path = None
        page.updated_at = now()
        page.save(update_fields=["cover_path", "updated_at"])
        bump_news()
        messages.info(request, "Обложка удалена.")
    return redirect(request.POST.get("next") or f"/pages/{pk}/edit")


@login_required
@require_http_methods(["GET", "POST"])
def collections_home(request):
    me = profile_of(request.user)
    if request.method == "POST":
        row = e12.create_collection(
            me,
            title=request.POST.get("title") or "",
            description=request.POST.get("description") or "",
            visibility=request.POST.get("visibility") or "friends",
            cover=request.FILES.get("cover"),
        )
        if row:
            messages.success(request, "Коллекция создана.")
            return redirect(row)
        messages.error(request, "Укажите название.")
    mine = e12.collections_for(me)
    browse = e12.visible_collections(me, 40)
    return render(request, "social/collections.html", {
        "me": me, "mine": mine, "browse": browse, "nav": "collections",
    })


@login_not_required
@require_http_methods(["GET", "HEAD"])
def collection_show(request, pk):
    me = profile_of(request.user) if request.user.is_authenticated else None
    col = get_object_or_404(Collection.objects.select_related("social_user"), pk=pk)
    if not e12.can_view_collection(me, col):
        messages.error(request, "Коллекция недоступна.")
        return redirect("collections" if me else "login")
    items = e12.collection_items(col)
    is_own = bool(me and me.id == col.social_user_id)
    return render(request, "social/collection.html", {
        "me": me, "col": col, "items": items, "is_own": is_own, "nav": "collections",
    })


@login_required
@require_POST
def collection_delete(request, pk):
    me = profile_of(request.user)
    if e12.delete_collection(me, pk):
        messages.info(request, "Коллекция удалена.")
    return redirect("collections")


@login_required
@require_POST
def collection_cover_upload(request, pk):
    me = profile_of(request.user)
    col = get_object_or_404(Collection, pk=pk, social_user=me)
    if e12.set_collection_cover(me, col, request.FILES.get("cover")):
        messages.success(request, "Обложка обновлена.")
    else:
        messages.error(request, "Не удалось сохранить обложку.")
    return redirect(col)


@login_required
@require_POST
def collection_cover_clear(request, pk):
    me = profile_of(request.user)
    col = get_object_or_404(Collection, pk=pk, social_user=me)
    if e12.clear_collection_cover(me, col):
        messages.info(request, "Обложка удалена.")
    return redirect(col)


@login_required
@require_POST
def collection_item_add(request, pk):
    me = profile_of(request.user)
    col = get_object_or_404(Collection, pk=pk, social_user=me)
    kind = (request.POST.get("kind") or "link").lower()
    post_id = request.POST.get("post_id")
    company_id = request.POST.get("company_id")
    try:
        post_id = int(post_id) if post_id else None
    except (TypeError, ValueError):
        post_id = None
    try:
        company_id = int(company_id) if company_id else None
    except (TypeError, ValueError):
        company_id = None
    row = e12.add_item(
        me, col, kind=kind, post_id=post_id, company_id=company_id,
        url=request.POST.get("url") or "", title=request.POST.get("title") or "",
    )
    if row:
        messages.success(request, "Добавлено в коллекцию.")
    else:
        messages.error(request, "Не удалось добавить элемент.")
    return redirect(col)


@login_required
@require_POST
def collection_item_delete(request, pk, item_id):
    me = profile_of(request.user)
    col = get_object_or_404(Collection, pk=pk, social_user=me)
    if e12.remove_item(me, col, item_id):
        messages.info(request, "Элемент удалён.")
    return redirect(col)


@login_not_required
@require_GET
def app_show(request, slug):
    app = e12.app_by_slug(slug)
    if not app:
        messages.error(request, "Приложение не найдено.")
        return redirect("apps")
    me = profile_of(request.user) if request.user.is_authenticated else None
    return render(request, "social/app_detail.html", {
        "me": me, "app": app, "nav": "apps",
        "categories": e12.APP_CATEGORIES,
    })
