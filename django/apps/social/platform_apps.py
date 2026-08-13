"""First-party Facebook Platform–style apps under 2006 chrome.

Soft ban: no third-party hosted canvas / external app platform.
These apps live in Django and mimic 2007–08 Applications + 2012 App Center UX.
"""
from __future__ import annotations

import hashlib
import random

from django.db.models import Count

from apps.social.models import SocialProfile
from apps.social.services import friend_ids, now, profile_related

# App Center categories (Platform-era)
APP_CATEGORIES = (
    ("games", "Игры"),
    ("lifestyle", "Образ жизни"),
    ("utilities", "Утилиты"),
)

DEFAULT_PERMISSIONS = (
    "Основная информация профиля",
    "Список друзей",
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
        "permissions": (
            "Основная информация профиля",
            "Список друзей",
            "Публикация на стене",
        ),
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
        "permissions": (
            "Основная информация профиля",
            "Список друзей",
            "Публикация на стене",
        ),
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
        "permissions": (
            "Основная информация профиля",
            "Список друзей",
            "Отправка уведомлений",
        ),
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
        "permissions": DEFAULT_PERMISSIONS,
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
        "permissions": (
            "Основная информация профиля",
            "Список друзей",
            "Отправка уведомлений",
        ),
    },
    # Sample first-party App Center demos (developer chrome: ВДрузья)
    {
        "slug": "calculator",
        "name": "Калькуляторы",
        "category": "utilities",
        "featured": True,
        "blurb": "Отпускные, кредит, НДС, зарплата, ремонт — десятки удобных расчётов.",
        "detail": (
            "Удобные калькуляторы для работы и быта: зарплата и отпуска, "
            "кредиты и вклады, налоги 2026 года, строительство и здоровье. "
            "Выберите расчёт, введите свои числа и получите понятный ответ."
        ),
        "developer": "ВДрузья",
        "permissions": ("Основная информация профиля",),
        "icon": "img/calc/ico-calc.gif",
    },
    {
        "slug": "weather",
        "name": "Погода",
        "category": "lifestyle",
        "featured": True,
        "blurb": "Погода по городу — демо-прогноз для друзей.",
        "detail": (
            "Приложение ВДрузья: укажите город и получите демо-прогноз "
            "(без внешнего API — как учебный canvas-пример)."
        ),
        "developer": "ВДрузья",
        "permissions": DEFAULT_PERMISSIONS,
    },
    {
        "slug": "horoscope",
        "name": "Гороскопы",
        "category": "lifestyle",
        "featured": False,
        "blurb": "Ежедневный гороскоп по знаку зодиака.",
        "detail": (
            "Гороскопы ВДрузья: выберите знак и прочитайте короткий "
            "прогноз дня — classic lifestyle app."
        ),
        "developer": "ВДрузья",
        "permissions": ("Основная информация профиля",),
    },
    {
        "slug": "dating",
        "name": "Знакомства",
        "category": "lifestyle",
        "featured": True,
        "blurb": "Совместимость с друзьями — лёгкий демо-матч.",
        "detail": (
            "Знакомства ВДрузья: покажет совпадения среди друзей "
            "с процентом совместимости (демо, без стороннего хостинга)."
        ),
        "developer": "ВДрузья",
        "permissions": (
            "Основная информация профиля",
            "Список друзей",
            "Город и интересы",
        ),
    },
    {
        "slug": "farm",
        "name": "Ферма",
        "category": "games",
        "featured": True,
        "blurb": "Поле, хлев, соседи и фишки — соцферма с банкротством и агрошколой.",
        "detail": (
            "Ферма ВДрузья: грядки с таймерами, полив и удобрения, животные, "
            "визиты к друзьям (помощь/доля урожая), лавка, цели дня, обучение "
            "и банкротство на 1 день с сбросом на 1 000 000 фишек — без стороннего iframe."
        ),
        "developer": "ВДрузья",
        "permissions": (
            "Основная информация профиля",
            "Список друзей",
            "Публикация на стене",
        ),
    },
    {
        "slug": "billiards",
        "name": "Бильярд",
        "category": "games",
        "featured": False,
        "blurb": "Партия бильярда — бросок и счёт.",
        "detail": "Простая canvas-игра: удар по шару и подсчёт очков.",
        "developer": "ВДрузья",
        "permissions": DEFAULT_PERMISSIONS,
    },
    {
        "slug": "chess",
        "name": "Шахматы",
        "category": "games",
        "featured": True,
        "blurb": "Партии с друзьями, рейтинг и чемпионат каждой недели.",
        "detail": (
            "Играйте в шахматы с друзьями на ВДрузья: живая доска, рейтинг, "
            "статистика и еженедельный чемпионат. Есть раздел обучения — "
            "от правил до первых тактических идей."
        ),
        "developer": "ВДрузья",
        "permissions": DEFAULT_PERMISSIONS,
        "icon": "img/calc/ico-chess.gif",
    },
    {
        "slug": "tetris",
        "name": "Тетрис",
        "category": "games",
        "featured": False,
        "blurb": "Классические линии — наберите очки.",
        "detail": "Короткий тетрис-раунд: соберите линии и сохраните счёт.",
        "developer": "ВДрузья",
        "permissions": ("Основная информация профиля",),
    },
    {
        "slug": "poker",
        "name": "Покер",
        "category": "games",
        "featured": False,
        "blurb": "Раздача карт — кто ближе к флешу.",
        "detail": "Демо-покер: получите пять карт и сравните комбинацию.",
        "developer": "ВДрузья",
        "permissions": DEFAULT_PERMISSIONS,
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


RESERVED_SLUGS = frozenset(
    {a["slug"] for a in PLATFORM_APPS}
    | set(LEGACY_MODULE_REDIRECTS)
    | {
        "developer", "developers", "new", "edit", "install", "uninstall",
        "canvas", "authorize", "launch", "docs", "rotate",
    }
)


def _dev_app_dict(row) -> dict:
    owner = getattr(row, "owner", None)
    from apps.social import platform_oauth as oauth
    oauth.ensure_app_credentials(row)
    return {
        "slug": row.slug,
        "name": row.name,
        "category": row.category or "utilities",
        "featured": bool(row.featured),
        "blurb": row.blurb or "",
        "detail": row.detail or row.blurb or "",
        "developer": (owner.name if owner else None) or "Разработчик",
        "permissions": DEFAULT_PERMISSIONS + ("Ссылка на сайт приложения", "OAuth / API-доступ"),
        "website_url": (row.website_url or "").strip(),
        "callback_url": (row.callback_url or "").strip(),
        "api_key": (row.api_key or "").strip(),
        "dev_owned": True,
        "owner_id": row.owner_id,
        "published": bool(row.published),
    }


def published_dev_apps():
    from apps.social.models import DevApp
    try:
        rows = list(
            DevApp.objects.filter(published=True)
            .select_related("owner")
            .order_by("name")[:80]
        )
    except Exception:
        return []
    return [_dev_app_dict(r) for r in rows]


def app_by_slug(slug: str, viewer=None) -> dict | None:
    slug = (slug or "").strip().lower()
    for a in PLATFORM_APPS:
        if a["slug"] == slug:
            return dict(a)
    from apps.social.models import DevApp
    try:
        row = DevApp.objects.select_related("owner").filter(slug=slug).first()
    except Exception:
        row = None
    if not row:
        return None
    if row.published or (viewer and getattr(viewer, "id", None) == row.owner_id):
        return _dev_app_dict(row)
    return None


def apps_grouped(*, category=None, featured_only=False):
    rows = [dict(a) for a in PLATFORM_APPS] + published_dev_apps()
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
    """Add app bookmark. Returns (row, created) or (None, False)."""
    if not me or not app_by_slug(slug, viewer=me):
        return None, False
    from apps.social.models import AppInstall
    row, created = AppInstall.objects.get_or_create(
        social_user=me, app_slug=slug,
        defaults={"created_at": now()},
    )
    return row, created


def uninstall(me, slug: str) -> bool:
    if not me or not slug:
        return False
    from apps.social.models import AppInstall
    n, _ = AppInstall.objects.filter(social_user=me, app_slug=slug).delete()
    return bool(n)


def my_apps(me):
    """Installed apps (= bookmarks), newest first."""
    if not me:
        return []
    from apps.social.models import AppInstall

    catalog = {a["slug"]: a for a in PLATFORM_APPS}
    for a in published_dev_apps():
        catalog[a["slug"]] = a
    ordered = list(
        AppInstall.objects.filter(social_user=me)
        .order_by("-id")
        .values_list("app_slug", flat=True)
    )
    out = []
    seen = set()
    for slug in ordered:
        if slug in seen or slug not in catalog:
            continue
        seen.add(slug)
        out.append(catalog[slug])
    return out


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


def permissions_for(app: dict | None) -> tuple:
    if not app:
        return DEFAULT_PERMISSIONS
    return tuple(app.get("permissions") or DEFAULT_PERMISSIONS)


def install_dialog_html(app: dict) -> str:
    """HTML body for 2006 install permissions dialog."""
    name = app.get("name") or "приложение"
    perms = permissions_for(app)
    items = "".join(f"<li>{p}</li>" for p in perms)
    return (
        f"<p>Разрешить «{name}» доступ к вашим данным?</p>"
        f"<p class=\"muted\">Приложение запрашивает:</p>"
        f"<ul class=\"fb-dialog-perms\">{items}</ul>"
        f"<p class=\"muted\">Разработчик: {app.get('developer') or 'ВДрузья'}</p>"
    )


def install_dialog_message(app: dict) -> str:
    """Plain-text fallback for install confirm (data-fb-dialog-message)."""
    name = app.get("name") or "приложение"
    perms = "; ".join(permissions_for(app))
    dev = app.get("developer") or "ВДрузья"
    return (
        f"Добавить «{name}» в закладки? "
        f"Приложение появится слева в «Мои приложения» и запросит: {perms}. "
        f"Разработчик: {dev}."
    )


def bookmark_remove_message(app: dict) -> str:
    name = app.get("name") or "приложение"
    return (
        f"Убрать «{name}» из закладок? "
        "Ссылка исчезнет из блока «Мои приложения» слева."
    )


ZODIAC = (
    ("aries", "Овен"),
    ("taurus", "Телец"),
    ("gemini", "Близнецы"),
    ("cancer", "Рак"),
    ("leo", "Лев"),
    ("virgo", "Дева"),
    ("libra", "Весы"),
    ("scorpio", "Скорпион"),
    ("sagittarius", "Стрелец"),
    ("capricorn", "Козерог"),
    ("aquarius", "Водолей"),
    ("pisces", "Рыбы"),
)

HOROSCOPE_LINES = (
    "Хороший день для короткого сообщения другу.",
    "Не торопитесь с решениями — сначала посмотрите стену.",
    "Вечер подойдёт для фото и тёплого комментария.",
    "Общие друзья подскажут неожиданную встречу.",
    "Спокойный темп: заметка важнее ленты.",
)


def weather_for_city(city: str) -> dict:
    city = (city or "").strip() or "Москва"
    seed = int(hashlib.md5(city.lower().encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed)
    temps = list(range(-12, 32))
    temp = temps[seed % len(temps)]
    skies = ("ясно", "облачно", "небольшой дождь", "пасмурно", "снег")
    return {
        "city": city,
        "temp": temp,
        "sky": skies[seed % len(skies)],
        "wind": 1 + rng.randint(0, 8),
        "hint": "Демо-прогноз (без внешнего API).",
    }


def horoscope_for(sign: str) -> dict:
    labels = dict(ZODIAC)
    sign = (sign or "").strip().lower()
    if sign not in labels:
        sign = "aries"
    seed = int(hashlib.md5(sign.encode()).hexdigest()[:8], 16)
    return {
        "sign": sign,
        "label": labels[sign],
        "line": HOROSCOPE_LINES[seed % len(HOROSCOPE_LINES)],
        "mood": ("удача", "спокойствие", "общение", "дело")[seed % 4],
    }


def dating_matches(me, limit=8) -> list[dict]:
    friends = friends_for_app(me, limit=40)
    out = []
    for p in friends[:limit]:
        seed = int(hashlib.md5(f"{me.id}:{p.id}".encode()).hexdigest()[:8], 16)
        score = 55 + (seed % 41)
        shared_city = bool(
            (me.city or "").strip()
            and (me.city or "").strip().lower() == (p.city or "").strip().lower()
        )
        out.append({
            "profile": p,
            "score": score,
            "note": "один город" if shared_city else "по интересам и кругу друзей",
        })
    out.sort(key=lambda x: -x["score"])
    return out


def calc_eval(a: str, op: str, b: str) -> str:
    try:
        x = float((a or "0").replace(",", "."))
        y = float((b or "0").replace(",", "."))
    except ValueError:
        return "ошибка"
    if op == "+":
        r = x + y
    elif op == "-":
        r = x - y
    elif op == "*":
        r = x * y
    elif op == "/":
        if y == 0:
            return "деление на ноль"
        r = x / y
    else:
        return "ошибка"
    if abs(r - int(r)) < 1e-9:
        return str(int(r))
    return f"{r:.4g}"


FARM_CROPS = (
    ("wheat", "пшеница", 3),
    ("carrot", "морковь", 2),
    ("apple", "яблоня", 5),
)

POKER_RANKS = "A23456789TJQK"
POKER_SUITS = ("♠", "♥", "♦", "♣")


def poker_deal(seed: str | None = None) -> list[str]:
    rng = random.Random(seed or now().isoformat())
    deck = [f"{r}{s}" for r in POKER_RANKS for s in POKER_SUITS]
    rng.shuffle(deck)
    return deck[:5]


def poker_rank_label(cards: list[str]) -> str:
    ranks = [c[0] for c in cards]
    suits = [c[1] for c in cards]
    if len(set(suits)) == 1:
        return "флеш"
    from collections import Counter
    cnt = Counter(ranks)
    vals = sorted(cnt.values(), reverse=True)
    if vals[0] == 3:
        return "тройка"
    if vals[0] == 2 and vals[1] == 2:
        return "две пары"
    if vals[0] == 2:
        return "пара"
    return "старшая карта"
