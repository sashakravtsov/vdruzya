"""Farm domain: plots, animals, neighbors, economy, bankruptcy, engagement."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.social import notify
from apps.social.models import SocialProfile
from apps.social.services import friend_ids

from . import catalog
from . import lessons as farm_lessons
from .models import FarmAnimal, FarmPlot, FarmProfile, FarmVisitLog

BADGES = [
    ("first_plant", "Первая грядка", "Посадите культуру"),
    ("first_harvest", "Первый урожай", "Соберите грядку"),
    ("water_pro", "Поливальщик", "Полейте 10 грядок"),
    ("helper", "Добрый сосед", "Помогите другу 5 раз"),
    ("bandit", "Полевой займ", "Возьмите часть чужого урожая"),
    ("barn", "Хлебосол", "Купите животное"),
    ("streak_3", "3 дня на ферме", "Серия заходов 3"),
    ("streak_7", "Неделя в поле", "Серия 7"),
    ("expand", "Межа шире", "Купите новую грядку"),
    ("student", "Агрошкола", "Пройдите 3 урока"),
    ("comeback", "Второе дыхание", "Сбросьте банкротство"),
]


def _now() -> datetime:
    return timezone.now().replace(tzinfo=None)


def _today() -> date:
    return date.today()


def _fmt(n: int) -> str:
    return f"{int(n):,}".replace(",", " ")


def _ach_set(p: FarmProfile) -> set[str]:
    raw = (p.achievements or "").strip()
    return {x for x in raw.split(",") if x} if raw else set()


def _ach_save(p: FarmProfile, keys: set[str]) -> None:
    p.achievements = ",".join(sorted(keys))
    p.updated_at = _now()
    p.save(update_fields=["achievements", "updated_at"])


def _unlock(p: FarmProfile, key: str) -> bool:
    keys = _ach_set(p)
    if key in keys:
        return False
    keys.add(key)
    _ach_save(p, keys)
    return True


def _lesson_set(p: FarmProfile) -> set[str]:
    raw = (p.lesson_slugs or "").strip()
    return {x for x in raw.split(",") if x} if raw else set()


def is_bankrupt(p: FarmProfile) -> bool:
    until = p.bankrupt_until
    if not until:
        return False
    if timezone.is_aware(until):
        until = timezone.make_naive(until, timezone.get_current_timezone())
    return until > _now()


def bankrupt_days_left(p: FarmProfile) -> int:
    until = p.bankrupt_until
    if not until:
        return 0
    if timezone.is_aware(until):
        until = timezone.make_naive(until, timezone.get_current_timezone())
    sec = (until - _now()).total_seconds()
    if sec <= 0:
        return 0
    return max(1, int((sec + 86399) // 86400))


def get_or_create_profile(user: SocialProfile) -> FarmProfile:
    p = FarmProfile.objects.filter(pk=user.id).first()
    if p:
        return _touch_streak(p)
    now = _now()
    p = FarmProfile.objects.create(
        social_user=user,
        chips=catalog.STARTING_CHIPS,
        plots_unlocked=catalog.START_PLOTS,
        water_cans=5,
        fertilizer=1,
        created_at=now,
        updated_at=now,
        last_play_on=_today(),
        play_streak=1,
    )
    _ensure_plots(user, p.plots_unlocked)
    return p


def _touch_streak(p: FarmProfile) -> FarmProfile:
    today = _today()
    if p.last_play_on == today:
        return p
    if p.last_play_on == today - timedelta(days=1):
        p.play_streak = int(p.play_streak or 0) + 1
    else:
        p.play_streak = 1
    p.best_streak = max(int(p.best_streak or 0), int(p.play_streak or 0))
    p.last_play_on = today
    p.updated_at = _now()
    p.save(update_fields=["play_streak", "best_streak", "last_play_on", "updated_at"])
    if p.play_streak >= 3:
        _unlock(p, "streak_3")
    if p.play_streak >= 7:
        _unlock(p, "streak_7")
    return p


def _ensure_plots(user: SocialProfile, n: int) -> list[FarmPlot]:
    existing = list(FarmPlot.objects.filter(owner=user).order_by("idx"))
    have = {pl.idx for pl in existing}
    for i in range(int(n)):
        if i not in have:
            existing.append(FarmPlot.objects.create(owner=user, idx=i, state="empty"))
    return sorted(existing, key=lambda x: x.idx)


def _require_playable(p: FarmProfile) -> None:
    if is_bankrupt(p):
        raise ValueError(
            f"Банкротство: игра недоступна ещё ~{bankrupt_days_left(p)} дн. "
            "Потом можно сбросить профиль."
        )


def _maybe_enter_bankruptcy(user: SocialProfile, p: FarmProfile) -> bool:
    if is_bankrupt(p):
        return True
    active = FarmPlot.objects.filter(owner=user, state__in=["growing", "ready"]).exists()
    animals = FarmAnimal.objects.filter(owner=user).exists()
    if int(p.chips) < catalog.MIN_PLAY_CHIPS and not active and not animals:
        p.bankrupt_until = _now() + timedelta(hours=catalog.BANKRUPT_HOURS)
        p.updated_at = _now()
        p.save(update_fields=["bankrupt_until", "updated_at"])
        return True
    return False


@transaction.atomic
def reset_after_bankruptcy(user: SocialProfile) -> FarmProfile:
    p = get_or_create_profile(user)
    if is_bankrupt(p):
        raise ValueError("Срок банкротства ещё не истёк")
    if not p.bankrupt_until:
        raise ValueError("Сброс доступен только после банкротства")
    FarmPlot.objects.filter(owner=user).delete()
    FarmAnimal.objects.filter(owner=user).delete()
    now = _now()
    p.chips = catalog.STARTING_CHIPS
    p.xp = 0
    p.plots_unlocked = catalog.START_PLOTS
    p.water_cans = 5
    p.fertilizer = 1
    p.boosts = 0
    p.harvests = 0
    p.plants = 0
    p.bankrupt_until = None
    p.reset_count = int(p.reset_count or 0) + 1
    p.updated_at = now
    p.save()
    _ensure_plots(user, p.plots_unlocked)
    _unlock(p, "comeback")
    return p


def _as_naive(dt: datetime | None) -> datetime | None:
    if not dt:
        return None
    if timezone.is_aware(dt):
        return timezone.make_naive(dt, timezone.get_current_timezone())
    return dt


def _refresh_plot(pl: FarmPlot) -> FarmPlot:
    now = _now()
    ready_at = _as_naive(pl.ready_at)
    wither_at = _as_naive(pl.wither_at)
    if pl.state == "growing" and ready_at and ready_at <= now:
        pl.state = "ready"
        pl.ready_at = ready_at
        if not wither_at:
            pl.wither_at = ready_at + timedelta(hours=6)
        pl.save(update_fields=["state", "ready_at", "wither_at"])
    if pl.state == "ready" and wither_at and wither_at <= now:
        pl.state = "withered"
        pl.save(update_fields=["state"])
    return pl


def _refresh_animal(an: FarmAnimal) -> FarmAnimal:
    return an


def plots_view(user: SocialProfile) -> list[dict]:
    p = get_or_create_profile(user)
    rows = []
    for pl in _ensure_plots(user, p.plots_unlocked):
        pl = _refresh_plot(pl)
        crop = catalog.crop_by_slug(pl.crop_slug) if pl.crop_slug else None
        left = 0
        if pl.state == "growing" and pl.ready_at:
            left = max(0, int((pl.ready_at - _now()).total_seconds()))
        rows.append({
            "id": pl.id,
            "idx": pl.idx,
            "state": pl.state,
            "crop": crop,
            "watered": pl.watered,
            "fertilized": pl.fertilized,
            "stolen": pl.stolen,
            "ready_at": pl.ready_at.isoformat(sep=" ") if pl.ready_at else "",
            "left_sec": left,
            "label": crop["title"] if crop else "пусто",
        })
    return rows


def animals_view(user: SocialProfile) -> list[dict]:
    out = []
    for an in FarmAnimal.objects.filter(owner=user).order_by("id"):
        meta = catalog.animal_by_slug(an.kind)
        ready = bool(an.ready_at and an.ready_at <= _now())
        left = 0
        if an.ready_at and not ready:
            left = max(0, int((an.ready_at - _now()).total_seconds()))
        out.append({
            "id": an.id,
            "kind": an.kind,
            "meta": meta,
            "ready": ready,
            "left_sec": left,
            "ready_at": an.ready_at.isoformat(sep=" ") if an.ready_at else "",
        })
    return out


@transaction.atomic
def plant(user: SocialProfile, plot_id: int, crop_slug: str) -> FarmPlot:
    p = get_or_create_profile(user)
    _require_playable(p)
    crop = catalog.crop_by_slug(crop_slug)
    if not crop:
        raise ValueError("Неизвестная культура")
    prog = catalog.xp_progress(p.xp)
    if prog["level"] < 1 + (crop["tier"] - 1) * 2:
        raise ValueError(f"Нужен уровень {1 + (crop['tier'] - 1) * 2}")
    if p.chips < crop["cost"]:
        _maybe_enter_bankruptcy(user, p)
        raise ValueError(f"Не хватает фишек (нужно {_fmt(crop['cost'])})")
    pl = FarmPlot.objects.select_for_update().filter(pk=plot_id, owner=user).first()
    if not pl:
        raise ValueError("Грядка не найдена")
    pl = _refresh_plot(pl)
    if pl.state not in ("empty", "withered"):
        raise ValueError("Грядка занята")
    now = _now()
    p.chips -= crop["cost"]
    p.plants = int(p.plants or 0) + 1
    p.xp = int(p.xp or 0) + 1
    p.updated_at = now
    p.save(update_fields=["chips", "plants", "xp", "updated_at"])
    pl.crop_slug = crop["slug"]
    pl.state = "growing"
    pl.planted_at = now
    pl.watered = False
    pl.fertilized = False
    pl.stolen = False
    pl.helper_id = None
    pl.ready_at = now + timedelta(seconds=crop["grow_sec"])
    pl.wither_at = pl.ready_at + timedelta(hours=6)
    pl.save()
    _unlock(p, "first_plant")
    _maybe_enter_bankruptcy(user, p)
    return pl


@transaction.atomic
def water_plot(user: SocialProfile, plot_id: int) -> FarmPlot:
    p = get_or_create_profile(user)
    _require_playable(p)
    pl = FarmPlot.objects.select_for_update().filter(pk=plot_id, owner=user).first()
    if not pl:
        raise ValueError("Грядка не найдена")
    pl = _refresh_plot(pl)
    if pl.state != "growing":
        raise ValueError("Поливать можно только растущую грядку")
    if pl.watered:
        raise ValueError("Уже полито")
    if int(p.water_cans or 0) < 1:
        raise ValueError("Нет леек — купите в лавке")
    p.water_cans -= 1
    p.xp = int(p.xp or 0) + 1
    p.updated_at = _now()
    p.save(update_fields=["water_cans", "xp", "updated_at"])
    pl.watered = True
    pl.save(update_fields=["watered"])
    # track watered count via achievements threshold using helps field? use plants proxy
    if int(p.plants or 0) >= 10:
        _unlock(p, "water_pro")
    return pl


@transaction.atomic
def fertilize_plot(user: SocialProfile, plot_id: int) -> FarmPlot:
    p = get_or_create_profile(user)
    _require_playable(p)
    pl = FarmPlot.objects.select_for_update().filter(pk=plot_id, owner=user).first()
    if not pl:
        raise ValueError("Грядка не найдена")
    pl = _refresh_plot(pl)
    if pl.state != "growing":
        raise ValueError("Удобрять можно растущую грядку")
    if pl.fertilized:
        raise ValueError("Уже удобрено")
    if int(p.fertilizer or 0) < 1:
        raise ValueError("Нет удобрений")
    p.fertilizer -= 1
    p.updated_at = _now()
    p.save(update_fields=["fertilizer", "updated_at"])
    left = max(0, int((pl.ready_at - _now()).total_seconds())) if pl.ready_at else 0
    pl.ready_at = _now() + timedelta(seconds=max(15, left // 2))
    pl.wither_at = pl.ready_at + timedelta(hours=6)
    pl.fertilized = True
    pl.save(update_fields=["ready_at", "wither_at", "fertilized"])
    return pl


@transaction.atomic
def boost_plot(user: SocialProfile, plot_id: int) -> FarmPlot:
    p = get_or_create_profile(user)
    _require_playable(p)
    pl = FarmPlot.objects.select_for_update().filter(pk=plot_id, owner=user).first()
    if not pl:
        raise ValueError("Грядка не найдена")
    pl = _refresh_plot(pl)
    if pl.state != "growing" or not pl.ready_at:
        raise ValueError("Нечего ускорять")
    if int(p.boosts or 0) < 1:
        raise ValueError("Нет ускорителей")
    p.boosts -= 1
    p.updated_at = _now()
    p.save(update_fields=["boosts", "updated_at"])
    total = max(1, int((pl.ready_at - (pl.planted_at or _now())).total_seconds()))
    cut = int(total * 0.30)
    pl.ready_at = max(_now() + timedelta(seconds=10), pl.ready_at - timedelta(seconds=cut))
    pl.wither_at = pl.ready_at + timedelta(hours=6)
    pl.save(update_fields=["ready_at", "wither_at"])
    return _refresh_plot(pl)


@transaction.atomic
def harvest(user: SocialProfile, plot_id: int) -> dict:
    p = get_or_create_profile(user)
    _require_playable(p)
    pl = FarmPlot.objects.select_for_update().filter(pk=plot_id, owner=user).first()
    if not pl:
        raise ValueError("Грядка не найдена")
    pl = _refresh_plot(pl)
    if pl.state == "withered":
        pl.state = "empty"
        pl.crop_slug = ""
        pl.save(update_fields=["state", "crop_slug"])
        raise ValueError("Урожай увял — грядка очищена")
    if pl.state != "ready":
        raise ValueError("Ещё не готово")
    crop = catalog.crop_by_slug(pl.crop_slug)
    if not crop:
        raise ValueError("Культура повреждена")
    amount = int(crop["yield"])
    if not pl.watered:
        amount = int(amount * 0.55)
    if pl.stolen:
        amount = int(amount * (1 - catalog.STEAL_SHARE))
    xp = int(crop["xp"])
    p.chips = int(p.chips) + amount
    p.xp = int(p.xp or 0) + xp
    p.harvests = int(p.harvests or 0) + 1
    p.updated_at = _now()
    p.save(update_fields=["chips", "xp", "harvests", "updated_at"])
    pl.state = "empty"
    pl.crop_slug = ""
    pl.watered = False
    pl.fertilized = False
    pl.stolen = False
    pl.planted_at = None
    pl.ready_at = None
    pl.wither_at = None
    pl.helper_id = None
    pl.save()
    _unlock(p, "first_harvest")
    return {"amount": amount, "xp": xp, "crop": crop, "chips": p.chips}


@transaction.atomic
def clear_withered(user: SocialProfile, plot_id: int) -> None:
    pl = FarmPlot.objects.select_for_update().filter(pk=plot_id, owner=user).first()
    if not pl:
        raise ValueError("Грядка не найдена")
    pl = _refresh_plot(pl)
    if pl.state != "withered":
        raise ValueError("Грядка не увяла")
    pl.state = "empty"
    pl.crop_slug = ""
    pl.save(update_fields=["state", "crop_slug"])


@transaction.atomic
def expand_field(user: SocialProfile) -> FarmProfile:
    p = get_or_create_profile(user)
    _require_playable(p)
    if p.plots_unlocked >= catalog.MAX_PLOTS:
        raise ValueError("Поле уже максимального размера")
    cost = catalog.expand_cost(p.plots_unlocked)
    if p.chips < cost:
        raise ValueError(f"Нужно {_fmt(cost)} фишек")
    p.chips -= cost
    p.plots_unlocked += 1
    p.updated_at = _now()
    p.save(update_fields=["chips", "plots_unlocked", "updated_at"])
    _ensure_plots(user, p.plots_unlocked)
    _unlock(p, "expand")
    _maybe_enter_bankruptcy(user, p)
    return p


@transaction.atomic
def buy_shop(user: SocialProfile, item: str, qty: int = 1) -> FarmProfile:
    p = get_or_create_profile(user)
    _require_playable(p)
    qty = max(1, min(20, int(qty or 1)))
    row = next((s for s in catalog.SHOP if s["slug"] == item), None)
    if not row:
        raise ValueError("Нет такого товара")
    cost = row["price"] * qty
    if p.chips < cost:
        raise ValueError(f"Нужно {_fmt(cost)} фишек")
    p.chips -= cost
    if item == "water":
        p.water_cans = int(p.water_cans or 0) + qty
    elif item == "fertilizer":
        p.fertilizer = int(p.fertilizer or 0) + qty
    elif item == "boost":
        p.boosts = int(p.boosts or 0) + qty
    p.updated_at = _now()
    p.save()
    _maybe_enter_bankruptcy(user, p)
    return p


@transaction.atomic
def buy_animal(user: SocialProfile, kind: str) -> FarmAnimal:
    p = get_or_create_profile(user)
    _require_playable(p)
    meta = catalog.animal_by_slug(kind)
    if not meta:
        raise ValueError("Неизвестное животное")
    if FarmAnimal.objects.filter(owner=user).count() >= catalog.MAX_ANIMALS:
        raise ValueError("Хлев полон")
    if p.chips < meta["buy"]:
        raise ValueError(f"Нужно {_fmt(meta['buy'])} фишек")
    p.chips -= meta["buy"]
    p.updated_at = _now()
    p.save(update_fields=["chips", "updated_at"])
    an = FarmAnimal.objects.create(owner=user, kind=kind, created_at=_now())
    _unlock(p, "barn")
    _maybe_enter_bankruptcy(user, p)
    return an


@transaction.atomic
def feed_animal(user: SocialProfile, animal_id: int) -> FarmAnimal:
    p = get_or_create_profile(user)
    _require_playable(p)
    an = FarmAnimal.objects.select_for_update().filter(pk=animal_id, owner=user).first()
    if not an:
        raise ValueError("Животное не найдено")
    meta = catalog.animal_by_slug(an.kind)
    if not meta:
        raise ValueError("Порода неизвестна")
    if an.ready_at and an.ready_at > _now():
        raise ValueError("Ещё рано — ждите продукцию или заберите готовую")
    if an.ready_at and an.ready_at <= _now():
        raise ValueError("Сначала заберите продукцию")
    if p.chips < meta["feed_cost"]:
        raise ValueError(f"Корм стоит {_fmt(meta['feed_cost'])}")
    p.chips -= meta["feed_cost"]
    p.updated_at = _now()
    p.save(update_fields=["chips", "updated_at"])
    an.fed_at = _now()
    an.ready_at = _now() + timedelta(seconds=meta["product_sec"])
    an.save(update_fields=["fed_at", "ready_at"])
    return an


@transaction.atomic
def collect_animal(user: SocialProfile, animal_id: int) -> dict:
    p = get_or_create_profile(user)
    _require_playable(p)
    an = FarmAnimal.objects.select_for_update().filter(pk=animal_id, owner=user).first()
    if not an:
        raise ValueError("Животное не найдено")
    meta = catalog.animal_by_slug(an.kind)
    if not meta or not an.ready_at or an.ready_at > _now():
        raise ValueError("Продукция ещё не готова")
    amount = meta["product_yield"]
    p.chips = int(p.chips) + amount
    p.xp = int(p.xp or 0) + meta["xp"]
    p.updated_at = _now()
    p.save(update_fields=["chips", "xp", "updated_at"])
    an.ready_at = None
    an.fed_at = None
    an.save(update_fields=["ready_at", "fed_at"])
    return {"amount": amount, "meta": meta, "chips": p.chips}


@transaction.atomic
def help_neighbor(me: SocialProfile, owner_id: int, plot_id: int) -> dict:
    if me.id == owner_id:
        raise ValueError("Свою грядку поливайте в своём поле")
    if owner_id not in friend_ids(me):
        raise ValueError("Помогать можно только друзьям")
    p = get_or_create_profile(me)
    _require_playable(p)
    owner = SocialProfile.objects.filter(pk=owner_id).first()
    if not owner:
        raise ValueError("Ферма не найдена")
    get_or_create_profile(owner)
    pl = FarmPlot.objects.select_for_update().filter(pk=plot_id, owner=owner).first()
    if not pl:
        raise ValueError("Грядка не найдена")
    pl = _refresh_plot(pl)
    if pl.state != "growing" or pl.watered:
        raise ValueError("Этой грядке помощь не нужна")
    if FarmVisitLog.objects.filter(actor=me, plot=pl, kind="help").exists():
        raise ValueError("Вы уже помогали на этой посадке")
    pl.watered = True
    pl.helper_id = me.id
    pl.save(update_fields=["watered", "helper_id"])
    p.xp = int(p.xp or 0) + catalog.HELP_XP
    p.chips = int(p.chips) + catalog.HELP_TIP
    p.helps = int(p.helps or 0) + 1
    p.updated_at = _now()
    p.save(update_fields=["xp", "chips", "helps", "updated_at"])
    FarmVisitLog.objects.create(
        actor=me, owner=owner, plot=pl, kind="help",
        amount=catalog.HELP_TIP, created_at=_now(),
    )
    if p.helps >= 5:
        _unlock(p, "helper")
    notify.push(
        owner.id,
        title="Ферма",
        body=f"{me.name} полил(а) вашу грядку",
        type="message",
        url=reverse("apps.canvas", args=["farm"]) + "?tab=field",
    )
    return {"tip": catalog.HELP_TIP, "xp": catalog.HELP_XP}


@transaction.atomic
def steal_neighbor(me: SocialProfile, owner_id: int, plot_id: int) -> dict:
    if me.id == owner_id:
        raise ValueError("Нельзя собирать у себя через визит")
    if owner_id not in friend_ids(me):
        raise ValueError("Только фермы друзей")
    p = get_or_create_profile(me)
    _require_playable(p)
    owner = SocialProfile.objects.filter(pk=owner_id).first()
    if not owner:
        raise ValueError("Ферма не найдена")
    pl = FarmPlot.objects.select_for_update().filter(pk=plot_id, owner=owner).first()
    if not pl:
        raise ValueError("Грядка не найдена")
    pl = _refresh_plot(pl)
    if pl.state != "ready":
        raise ValueError("Урожай ещё не готов")
    if pl.stolen:
        raise ValueError("С этой грядки уже брали")
    crop = catalog.crop_by_slug(pl.crop_slug)
    if not crop:
        raise ValueError("Пусто")
    amount = int(crop["yield"] * catalog.STEAL_SHARE)
    if not pl.watered:
        amount = int(amount * 0.55)
    pl.stolen = True
    pl.save(update_fields=["stolen"])
    p.chips = int(p.chips) + amount
    p.steals = int(p.steals or 0) + 1
    p.xp = int(p.xp or 0) + 2
    p.updated_at = _now()
    p.save(update_fields=["chips", "steals", "xp", "updated_at"])
    FarmVisitLog.objects.create(
        actor=me, owner=owner, plot=pl, kind="steal", amount=amount, created_at=_now(),
    )
    _unlock(p, "bandit")
    notify.push(
        owner.id,
        title="Ферма",
        body=f"{me.name} забрал(а) часть урожая ({_fmt(amount)})",
        type="message",
        url=reverse("apps.canvas", args=["farm"]) + "?tab=field",
    )
    return {"amount": amount, "crop": crop}


@transaction.atomic
def claim_daily_bonus(user: SocialProfile) -> dict:
    p = get_or_create_profile(user)
    _require_playable(p)
    if p.daily_bonus_on == _today():
        raise ValueError("Бонус уже получен сегодня")
    streak = max(1, int(p.play_streak or 1))
    amount = 3_000 + min(20_000, streak * 1_500)
    p.chips = int(p.chips) + amount
    p.daily_bonus_on = _today()
    p.xp = int(p.xp or 0) + 3
    p.updated_at = _now()
    p.save(update_fields=["chips", "daily_bonus_on", "xp", "updated_at"])
    return {"amount": amount, "streak": streak}


@transaction.atomic
def complete_lesson(user: SocialProfile, slug: str, choice: str) -> dict:
    les = farm_lessons.lesson_by_slug(slug)
    if not les:
        raise ValueError("Урок не найден")
    ok = choice == les["quiz"]["answer"]
    p = get_or_create_profile(user)
    keys = _lesson_set(p)
    first = slug not in keys
    if ok:
        keys.add(slug)
        p.lesson_slugs = ",".join(sorted(keys))
        if first:
            p.xp = int(p.xp or 0) + 8
            p.chips = int(p.chips) + 500
        p.updated_at = _now()
        p.save(update_fields=["lesson_slugs", "xp", "chips", "updated_at"])
        if len(keys) >= 3:
            _unlock(p, "student")
    return {"ok": ok, "explain": les["quiz"]["explain"], "first": first and ok}


def friend_farms(me: SocialProfile, limit: int = 12) -> list[dict]:
    fids = list(friend_ids(me))[:40]
    if not fids:
        return []
    out = []
    for sp in SocialProfile.objects.filter(pk__in=fids).order_by("name")[:limit]:
        fp = FarmProfile.objects.filter(pk=sp.id).first()
        ready_n = FarmPlot.objects.filter(owner=sp, state="ready").count()
        need_water = FarmPlot.objects.filter(owner=sp, state="growing", watered=False).count()
        out.append({
            "profile": sp,
            "chips": fp.chips if fp else catalog.STARTING_CHIPS,
            "level": catalog.xp_progress(fp.xp if fp else 0)["level"],
            "ready_n": ready_n,
            "need_water": need_water,
        })
    out.sort(key=lambda r: (-r["need_water"], -r["ready_n"], r["profile"].name))
    return out


def visit_farm(me: SocialProfile, owner_id: int) -> dict:
    owner = SocialProfile.objects.filter(pk=owner_id).first()
    if not owner:
        raise ValueError("Игрок не найден")
    if owner.id != me.id and owner.id not in friend_ids(me):
        raise ValueError("Фермы друзей открыты для друзей")
    get_or_create_profile(owner)
    return {
        "owner": owner,
        "plots": plots_view(owner),
        "animals": animals_view(owner),
        "strip": engagement_strip(owner) if owner.id == me.id else None,
        "is_self": owner.id == me.id,
    }


def engagement_strip(user: SocialProfile) -> dict:
    p = get_or_create_profile(user)
    _maybe_enter_bankruptcy(user, p)
    p = FarmProfile.objects.filter(pk=user.id).first() or p
    prog = catalog.xp_progress(p.xp)
    growing = FarmPlot.objects.filter(owner=user, state="growing").count()
    ready = FarmPlot.objects.filter(owner=user, state="ready").count()
    goals = [
        {"key": "plant", "title": "Посадить 3 культуры", "done": int(p.plants or 0) >= 3 and p.last_play_on == _today(), "n": min(3, p.plants % 100), "need": 3},
        {"key": "harvest", "title": "Собрать 2 урожая", "done": ready == 0 and int(p.harvests or 0) > 0 and p.last_play_on == _today(), "n": min(2, p.harvests), "need": 2},
        {"key": "bonus", "title": "Забрать дневной бонус", "done": p.daily_bonus_on == _today(), "n": 1 if p.daily_bonus_on == _today() else 0, "need": 1},
        {"key": "lesson", "title": "Пройти урок", "done": bool(_lesson_set(p)), "n": len(_lesson_set(p)), "need": 1},
    ]
    # better daily plant/harvest tracking via today's actions approx using streak day
    today_plants = p.plants  # simplified
    goals[0] = {
        "key": "plant",
        "title": "Посадить культуру сегодня",
        "done": p.last_play_on == _today() and int(p.plants or 0) >= 1,
        "n": 1 if int(p.plants or 0) >= 1 else 0,
        "need": 1,
    }
    goals[1] = {
        "key": "harvest",
        "title": "Собрать урожай / забрать продукцию",
        "done": int(p.harvests or 0) >= 1 and p.last_play_on == _today(),
        "n": 1 if int(p.harvests or 0) >= 1 else 0,
        "need": 1,
    }
    done = sum(1 for g in goals if g["done"])
    unlocked = _ach_set(p)
    badges = [
        {"key": k, "title": t, "hint": h, "unlocked": k in unlocked}
        for k, t, h in BADGES
    ]
    return {
        "chips": p.chips,
        "chips_fmt": _fmt(p.chips),
        "xp": p.xp,
        "level": prog["level"],
        "xp_into": prog["into"],
        "xp_need": prog["need"],
        "xp_pct": prog["pct"],
        "streak": p.play_streak,
        "water_cans": p.water_cans,
        "fertilizer": p.fertilizer,
        "boosts": p.boosts,
        "plots_unlocked": p.plots_unlocked,
        "growing": growing,
        "ready": ready,
        "bankrupt": is_bankrupt(p),
        "bankrupt_days_left": bankrupt_days_left(p),
        "can_reset": bool(p.bankrupt_until) and not is_bankrupt(p),
        "daily_claimed": p.daily_bonus_on == _today(),
        "expand_cost": catalog.expand_cost(p.plots_unlocked),
        "expand_cost_fmt": _fmt(catalog.expand_cost(p.plots_unlocked)),
        "goals": {"items": goals, "done": done, "total": len(goals), "pct": int(100 * done / len(goals))},
        "badges": badges,
        "lessons_done": len(_lesson_set(p)),
    }


def crops_catalog_for(user: SocialProfile) -> list[dict]:
    p = get_or_create_profile(user)
    return catalog.crops_for_level(catalog.xp_progress(p.xp)["level"])
