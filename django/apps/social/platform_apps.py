"""First-party Facebook Platform–style apps under 2006 chrome.

Soft ban: no third-party hosted canvas / external app platform.
These apps live in Django and mimic 2007–08 Applications + 2012 App Center UX.
"""
from __future__ import annotations

from django.db.models import Count

from apps.social.models import SocialProfile
from apps.social.services import friend_ids, now, profile_related

# App Center categories (Platform-era)
APP_CATEGORIES = (
    ("games", "Игры"),
    ("lifestyle", "Образ жизни"),
    ("utilities", "Утилиты"),
)

PLATFORM_APPS = (
    {
        "slug": "causes",
        "name": "Дела",
        "category": "lifestyle",
        "featured": True,
        "blurb": "Поддержите дело вместе с друзьями.",
        "detail": (
            "Классическое приложение в духе Causes: выберите дело, "
            "присоединитесь и расскажите друзьям на стене."
        ),
        "developer": "ВДрузья",
    },
    {
        "slug": "quiz",
        "name": "Викторины",
        "category": "games",
        "featured": True,
        "blurb": "Короткие тесты про вас и друзей.",
        "detail": (
            "Викторина в canvas-приложении: ответьте на вопросы и "
            "при желании опубликуйте результат на стене."
        ),
        "developer": "ВДрузья",
    },
    {
        "slug": "superpoke",
        "name": "Супер-подмигивание",
        "category": "games",
        "featured": True,
        "blurb": "Подмигните друзьям необычным способом.",
        "detail": (
            "В духе SuperPoke: выберите друга и тип подмигивания — "
            "он получит уведомление во входящих."
        ),
        "developer": "ВДрузья",
    },
    {
        "slug": "compare",
        "name": "Сравнение друзей",
        "category": "utilities",
        "featured": False,
        "blurb": "Кто из двоих ближе по интересам.",
        "detail": (
            "Простое сравнение двух друзей по городу и интересам — "
            "classic utility app без стороннего кода."
        ),
        "developer": "ВДрузья",
    },
    {
        "slug": "truth",
        "name": "Правда или вопрос",
        "category": "games",
        "featured": False,
        "blurb": "Задайте другу вопрос на стене приложения.",
        "detail": (
            "Лёгкая canvas-игра: отправьте другу вопрос; ответ можно "
            "оставить на стене приложения."
        ),
        "developer": "ВДрузья",
    },
)

# Old App Center entries that were just site modules — redirect for bookmarks/smoke.
LEGACY_MODULE_REDIRECTS = {
    "photos": "albums",
    "groups": "groups",
    "events": "events",
    "pages": "pages",
    "collections": "collections",
    "notes": "notes",
    "links": "links",
    "videos": "videos",
    "marketplace": "marketplace",
    "places": "places",
    "questions": "questions",
    "polls": "polls",
    "og": "og",
    "gifts": "gifts",
    "messages": "inbox",
    "lists": "friends.lists",
    "networks": "networks",
    "birthdays": "birthdays",
    "anniversaries": "anniversaries",
    "pokes": "pokes",
    "mobile": "mobile",
    "search": "search",
    "graph": "graph",
    "trending": "trending",
    "nearby": "nearby",
    "hashtags": "trending",
    "saves": "saves",
    "safety": "safety",
}

CAUSES = (
    {"slug": "ecology", "title": "Экология", "blurb": "Чистота дворов и парков."},
    {"slug": "books", "title": "Книги в школы", "blurb": "Сбор книг для библиотек."},
    {"slug": "blood", "title": "Донорство", "blurb": "Напоминание о донорских днях."},
    {"slug": "pets", "title": "Помощь животным", "blurb": "Приюты и передержки."},
)

SUPERPOKE_TYPES = (
    ("poke", "обычное подмигивание"),
    ("wave", "помахать"),
    ("hug", "обнять"),
    ("highfive", "дать пять"),
    ("coffee", "пригласить на кофе"),
)

QUIZ_QUESTIONS = (
    {
        "id": "q1",
        "text": "Субботний вечер — это…",
        "options": (
            ("a", "встреча с друзьями"),
            ("b", "книга или фильм дома"),
            ("c", "прогулка без плана"),
        ),
    },
    {
        "id": "q2",
        "text": "В ленте вас больше тянет к…",
        "options": (
            ("a", "фотографиям друзей"),
            ("b", "длинным заметкам"),
            ("c", "событиям и встречам"),
        ),
    },
    {
        "id": "q3",
        "text": "Новый знакомый — сначала…",
        "options": (
            ("a", "добавить в друзья"),
            ("b", "написать на стену"),
            ("c", "найти общих друзей"),
        ),
    },
)

QUIZ_RESULTS = {
    "a": ("Душа компании", "Вы держите круг друзей вместе."),
    "b": ("Наблюдатель", "Вам важны смыслы и спокойный темп."),
    "c": ("Искатель", "Вы открыты новому и случайным встречам."),
}


def app_by_slug(slug: str) -> dict | None:
    slug = (slug or "").strip().lower()
    for a in PLATFORM_APPS:
        if a["slug"] == slug:
            return a
    return None


def apps_grouped(*, category=None, featured_only=False):
    rows = list(PLATFORM_APPS)
    if featured_only:
        rows = [a for a in rows if a.get("featured")]
    if category:
        rows = [a for a in rows if a.get("category") == category]
    return rows


def legacy_redirect_name(slug: str) -> str | None:
    return LEGACY_MODULE_REDIRECTS.get((slug or "").strip().lower())


def is_installed(me, slug: str) -> bool:
    if not me or not slug:
        return False
    from apps.social.models import AppInstall
    return AppInstall.objects.filter(social_user=me, app_slug=slug).exists()


def installed_slugs(me) -> set[str]:
    if not me:
        return set()
    from apps.social.models import AppInstall
    return set(
        AppInstall.objects.filter(social_user=me).values_list("app_slug", flat=True)
    )


def install(me, slug: str):
    if not me or not app_by_slug(slug):
        return None
    from apps.social.models import AppInstall
    row, _ = AppInstall.objects.get_or_create(
        social_user=me, app_slug=slug,
        defaults={"created_at": now()},
    )
    return row


def uninstall(me, slug: str) -> bool:
    if not me or not slug:
        return False
    from apps.social.models import AppInstall
    n, _ = AppInstall.objects.filter(social_user=me, app_slug=slug).delete()
    return bool(n)


def my_apps(me):
    slugs = installed_slugs(me)
    return [a for a in PLATFORM_APPS if a["slug"] in slugs]


def cause_join_counts() -> dict[str, int]:
    from apps.social.models import AppCauseJoin
    rows = (
        AppCauseJoin.objects.values("cause_slug")
        .annotate(n=Count("id"))
    )
    return {r["cause_slug"]: r["n"] for r in rows}


def join_cause(me, cause_slug: str):
    cause_slug = (cause_slug or "").strip().lower()
    if not me or cause_slug not in {c["slug"] for c in CAUSES}:
        return None
    from apps.social.models import AppCauseJoin
    row, created = AppCauseJoin.objects.get_or_create(
        social_user=me, cause_slug=cause_slug,
        defaults={"created_at": now()},
    )
    return row, created


def my_causes(me) -> set[str]:
    if not me:
        return set()
    from apps.social.models import AppCauseJoin
    return set(
        AppCauseJoin.objects.filter(social_user=me).values_list("cause_slug", flat=True)
    )


def friends_for_app(me, limit=40):
    if not me:
        return []
    fids = friend_ids(me)
    if not fids:
        return []
    return list(
        SocialProfile.objects.filter(id__in=fids)
        .defer(*profile_related())
        .order_by("name")[:limit]
    )


def score_quiz(answers: dict) -> tuple[str, str, str]:
    """Return (key, title, blurb) from answer letters."""
    tallies = {"a": 0, "b": 0, "c": 0}
    for q in QUIZ_QUESTIONS:
        val = (answers.get(q["id"]) or "").strip().lower()
        if val in tallies:
            tallies[val] += 1
    key = max(tallies, key=tallies.get)
    title, blurb = QUIZ_RESULTS[key]
    return key, title, blurb


def compare_profiles(a: SocialProfile, b: SocialProfile) -> list[dict]:
    def bits(p):
        interests = (p.interests or "").lower().replace(";", ",")
        return {
            "city": (p.city or "").strip(),
            "hometown": (p.hometown or "").strip(),
            "tags": {x.strip() for x in interests.split(",") if x.strip()},
        }
    aa, bb = bits(a), bits(b)
    shared = sorted(aa["tags"] & bb["tags"])
    return [
        {"label": "Город", "a": aa["city"] or "—", "b": bb["city"] or "—",
         "same": bool(aa["city"] and aa["city"].lower() == bb["city"].lower())},
        {"label": "Родной город", "a": aa["hometown"] or "—", "b": bb["hometown"] or "—",
         "same": bool(aa["hometown"] and aa["hometown"].lower() == bb["hometown"].lower())},
        {"label": "Общие интересы", "a": ", ".join(shared) or "—", "b": "", "same": bool(shared)},
    ]
