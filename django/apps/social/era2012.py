"""FB 2012 helpers — Page Timeline, Collections, App Center catalog."""
from __future__ import annotations

from datetime import date

from django.db.models import Q

from apps.social.models import (
    Collection, CollectionItem, Company, PageTimelineMilestone, Post,
    profile_related,
)
from apps.social.services import bump_news, friend_ids, now, post_visible_q

PAGE_MILESTONE_KINDS = (
    ("life", "История"),
    ("founded", "Основание"),
    ("launch", "Запуск"),
    ("award", "Награда"),
    ("product", "Продукт"),
    ("custom", "Другое"),
)

ITEM_KINDS = frozenset({"post", "link", "page"})
VIS = frozenset({"public", "friends", "private"})

APP_CATEGORIES = (
    ("social", "Общение"),
    ("media", "Медиа"),
    ("places", "Места и события"),
    ("tools", "Инструменты"),
)

# Built-in App Center catalog — no third-party platform.
APP_CENTER = (
    {"slug": "photos", "name": "Фото", "category": "media", "featured": True,
     "blurb": "Альбомы и фотографии друзей.", "detail": "Загружайте альбомы, отмечайте друзей и листайте фото в классическом виде.", "url_name": "albums"},
    {"slug": "groups", "name": "Группы", "category": "social", "featured": True,
     "blurb": "Сообщества по интересам.", "detail": "Открытые и закрытые группы, документы и стена обсуждений.", "url_name": "groups"},
    {"slug": "events", "name": "События", "category": "places", "featured": True,
     "blurb": "Встречи и приглашения.", "detail": "Создавайте события, приглашайте друзей и отмечайте «пойду».", "url_name": "events"},
    {"slug": "pages", "name": "Страницы", "category": "social", "featured": True,
     "blurb": "Публичные страницы брендов и личностей.", "detail": "Страницы с Timeline, обложкой и этапами — для брендов и публичных фигур.", "url_name": "pages"},
    {"slug": "collections", "name": "Коллекции", "category": "media", "featured": True,
     "blurb": "Собирайте посты, ссылки и страницы.", "detail": "FB Collections: тематические подборки ссылок, записей и страниц для себя и друзей.", "url_name": "collections"},
    {"slug": "notes", "name": "Заметки", "category": "media", "featured": False,
     "blurb": "Длинные записи.", "detail": "Классические заметки — статьи на стене и в ленте.", "url_name": "notes"},
    {"slug": "links", "name": "Ссылки", "category": "media", "featured": False,
     "blurb": "Поделитесь ссылкой.", "detail": "Каталог ссылок друзей в классическом интерфейсе.", "url_name": "links"},
    {"slug": "videos", "name": "Видео", "category": "media", "featured": False,
     "blurb": "Ссылки на видеоролики.", "detail": "Делитесь роликами через URL — без отдельного CDN.", "url_name": "videos"},
    {"slug": "marketplace", "name": "Барахолка", "category": "tools", "featured": False,
     "blurb": "Купить и продать рядом.", "detail": "Объявления друзей: вещи, услуги, локальный обмен.", "url_name": "marketplace"},
    {"slug": "places", "name": "Места", "category": "places", "featured": True,
     "blurb": "Отмечайтесь в местах.", "detail": "Check-in и отзывы о местах — Places 2010 под chrome 2006.", "url_name": "places"},
    {"slug": "questions", "name": "Вопросы", "category": "social", "featured": False,
     "blurb": "Спросите друзей.", "detail": "Вопросы с ответами и голосами друзей.", "url_name": "questions"},
    {"slug": "polls", "name": "Опросы", "category": "social", "featured": False,
     "blurb": "Классические опросы.", "detail": "Создайте опрос и соберите голоса друзей.", "url_name": "polls"},
    {"slug": "og", "name": "Open Graph", "category": "media", "featured": True,
     "blurb": "Слушаете, читаете, смотрите.", "detail": "Публикуйте OG-истории: музыка, книги, фильмы — в ленте и Ticker.", "url_name": "og"},
    {"slug": "gifts", "name": "Подарки", "category": "social", "featured": False,
     "blurb": "Виртуальные подарки.", "detail": "Каталог стикеров-подарков для друзей.", "url_name": "gifts"},
    {"slug": "messages", "name": "Сообщения", "category": "social", "featured": False,
     "blurb": "Входящие письма.", "detail": "Классический Message Center: ответы и стикеры без live Messenger.", "url_name": "inbox"},
    {"slug": "lists", "name": "Списки друзей", "category": "tools", "featured": False,
     "blurb": "Группируйте друзей.", "detail": "Списки для фильтра ленты и приватности.", "url_name": "friends.lists"},
    {"slug": "networks", "name": "Сети", "category": "tools", "featured": False,
     "blurb": "Города, школы, работа.", "detail": "Найдите людей по сетям и фильтрам.", "url_name": "networks"},
    {"slug": "birthdays", "name": "Дни рождения", "category": "tools", "featured": False,
     "blurb": "Не пропустите ДР друзей.", "detail": "Календарь ближайших дней рождения.", "url_name": "birthdays"},
    {"slug": "anniversaries", "name": "Годовщины", "category": "tools", "featured": False,
     "blurb": "Сколько лет вы дружите.", "detail": "Годовщины дружбы в классическом списке.", "url_name": "anniversaries"},
    {"slug": "pokes", "name": "Подмигивания", "category": "social", "featured": False,
     "blurb": "Лёгкий «привет».", "detail": "Классические подмигивания во входящих.", "url_name": "pokes"},
    {"slug": "mobile", "name": "Мобильная версия", "category": "tools", "featured": False,
     "blurb": "ВДрузья с телефона.", "detail": "Подсказки по мобильному доступу.", "url_name": "mobile"},
    {"slug": "search", "name": "Поиск", "category": "tools", "featured": False,
     "blurb": "Найти людей и группы.", "detail": "Глобальный поиск по людям, группам и страницам.", "url_name": "search"},
)


def app_by_slug(slug: str) -> dict | None:
    slug = (slug or "").strip().lower()
    for a in APP_CENTER:
        if a["slug"] == slug:
            return a
    return None


def apps_grouped(*, category=None, featured_only=False):
    rows = list(APP_CENTER)
    if featured_only:
        rows = [a for a in rows if a.get("featured")]
    if category:
        rows = [a for a in rows if a.get("category") == category]
    return rows


def page_milestones_for(page, *, year=None, limit=40):
    if not page:
        return []
    qs = PageTimelineMilestone.objects.filter(company=page).order_by("-occurred_on", "-id")
    if year:
        qs = qs.filter(occurred_on__year=year)
    return list(qs[:limit])


def page_milestone_years(page) -> list[int]:
    if not page:
        return []
    return [d.year for d in PageTimelineMilestone.objects.filter(company=page).dates("occurred_on", "year", order="DESC")]


def add_page_milestone(page, *, title, occurred_on, kind="life", body="") -> PageTimelineMilestone | None:
    title = (title or "").strip()[:255]
    if not page or not title or not occurred_on:
        return None
    kinds = {k for k, _ in PAGE_MILESTONE_KINDS}
    kind = kind if kind in kinds else "life"
    t = now()
    row = PageTimelineMilestone.objects.create(
        company=page, title=title, body=(body or "")[:500],
        kind=kind, occurred_on=occurred_on, created_at=t, updated_at=t,
    )
    bump_news()
    return row


def delete_page_milestone(page, milestone_id) -> bool:
    n, _ = PageTimelineMilestone.objects.filter(pk=milestone_id, company=page).delete()
    if n:
        bump_news()
    return bool(n)


def page_timeline_bundle(page, *, year=None, posts=None):
    years = page_milestone_years(page)
    y = year
    if y is None and years:
        y = years[0]
    elif y is None:
        y = date.today().year
    ms = page_milestones_for(page, year=y, limit=40)
    activity = []
    for p in posts or []:
        at = getattr(p, "created_at", None)
        if at and getattr(at, "year", None) == y:
            activity.append(p)
    return {
        "timeline_year": y,
        "timeline_years": years or [y],
        "milestones": ms,
        "timeline_posts": activity,
        "milestone_kinds": PAGE_MILESTONE_KINDS,
    }


def _add_page_milestones(items, viewer, page_ids, blocked, limit):
    if not page_ids:
        return
    qs = (
        PageTimelineMilestone.objects.filter(company_id__in=page_ids)
        .select_related("company")
        .order_by("-created_at", "-id")
    )
    for row in qs[:limit]:
        items.append({
            "kind": "page_milestone", "at": row.created_at or row.occurred_on,
            "page": row.company, "milestone": row,
            "actor": None,
        })


def can_view_collection(viewer, col) -> bool:
    if not col:
        return False
    if viewer and viewer.id == col.social_user_id:
        return True
    vis = col.visibility or "friends"
    if vis == "public":
        return True
    if vis == "private":
        return False
    return bool(viewer and col.social_user_id in friend_ids(viewer))


def collections_for(me, limit=40):
    if not me:
        return []
    return list(Collection.objects.filter(social_user=me).order_by("-id")[:limit])


def visible_collections(viewer, limit=40):
    if not viewer:
        return list(Collection.objects.filter(visibility="public").order_by("-id")[:limit])
    fids = friend_ids(viewer) | {viewer.id}
    return list(
        Collection.objects.filter(
            Q(social_user=viewer)
            | Q(visibility="public")
            | Q(visibility="friends", social_user_id__in=fids)
        ).select_related("social_user").order_by("-id")[:limit]
    )


def create_collection(me, *, title, description="", visibility="friends") -> Collection | None:
    title = (title or "").strip()[:160]
    if not me or not title:
        return None
    vis = visibility if visibility in VIS else "friends"
    t = now()
    row = Collection.objects.create(
        social_user=me, title=title, description=(description or "")[:500],
        visibility=vis, created_at=t, updated_at=t,
    )
    bump_news()
    return row


def delete_collection(me, collection_id) -> bool:
    col = Collection.objects.filter(pk=collection_id, social_user=me).first()
    if not col:
        return False
    CollectionItem.objects.filter(collection=col).delete()
    col.delete()
    bump_news()
    return True


def collection_items(col, limit=60):
    rows = list(
        CollectionItem.objects.filter(collection=col)
        .select_related("post", "post__social_user", "company")
        .order_by("position", "id")[:limit]
    )
    return rows


def add_item(me, col, *, kind, post_id=None, company_id=None, url="", title="") -> CollectionItem | None:
    if not me or not col or col.social_user_id != me.id:
        return None
    kind = (kind or "").lower()
    if kind not in ITEM_KINDS:
        return None
    pos = (CollectionItem.objects.filter(collection=col).count())
    t = now()
    kwargs = {
        "collection": col, "kind": kind, "position": pos, "created_at": t,
        "url": "", "title": (title or "")[:255],
    }
    if kind == "post":
        post = Post.objects.filter(pk=post_id).filter(post_visible_q(me)).first()
        if not post:
            return None
        kwargs["post"] = post
        kwargs["title"] = kwargs["title"] or (post.body or "")[:80] or f"Запись #{post.id}"
    elif kind == "page":
        page = Company.objects.filter(pk=company_id).first()
        if not page:
            return None
        kwargs["company"] = page
        kwargs["title"] = kwargs["title"] or page.name
    else:
        from apps.social.classic_extra import normalize_url
        u = normalize_url(url)
        if not u:
            return None
        kwargs["url"] = u[:500]
        kwargs["title"] = kwargs["title"] or u[:80]
    row = CollectionItem.objects.create(**kwargs)
    col.updated_at = t
    col.save(update_fields=["updated_at"])
    bump_news()
    return row


def remove_item(me, col, item_id) -> bool:
    if not me or not col or col.social_user_id != me.id:
        return False
    n, _ = CollectionItem.objects.filter(pk=item_id, collection=col).delete()
    if n:
        bump_news()
    return bool(n)


def _add_collections(items, blocked, fids, limit):
    if not fids:
        return
    qs = (
        Collection.objects.filter(social_user_id__in=fids)
        .exclude(visibility="private")
        .select_related("social_user")
        .defer(*profile_related("social_user__"))
        .order_by("-id")
    )
    if blocked:
        qs = qs.exclude(social_user_id__in=blocked)
    for row in qs[:limit]:
        items.append({
            "kind": "collection", "at": row.created_at or row.updated_at,
            "actor": row.social_user, "collection": row,
        })
