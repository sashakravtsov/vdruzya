"""Dating domain: discovery, likes, matches, engagement."""
from __future__ import annotations

import json
import hashlib
from datetime import date, datetime, timedelta

from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.social import notify
from apps.social.models import SocialProfile
from apps.social.services import friend_ids

from . import tips as dating_tips
from .models import DatingMatch, DatingProfile, DatingSwipe, DatingVisit

INTENT_LABELS = {
    "dating": "Знакомства",
    "friendship": "Дружба",
    "chat": "Общение",
    "serious": "Серьёзно",
}

BADGES = [
    ("first_like", "Первый лайк", "Отправьте первый символ интереса"),
    ("first_match", "Искра", "Получите взаимный матч"),
    ("streak_3", "3 дня подряд", "Заходите 3 дня подряд"),
    ("streak_7", "Неделя огня", "Серия 7 дней"),
    ("profile_pro", "Анкета PRO", "Заголовок, о себе и 2 ответа"),
    ("super_fan", "Суперсигнал", "Отправьте суперлайк"),
    ("city_spark", "Городская искра", "Матч с человеком из вашего города"),
    ("student", "Школа знакомств", "Пройдите 3 совета с квизом"),
]


def _now() -> datetime:
    return timezone.now().replace(tzinfo=None)


def _today() -> date:
    return date.today()


def _age(profile: SocialProfile) -> int | None:
    b = getattr(profile, "birthday", None)
    if not b:
        return None
    today = _today()
    return today.year - b.year - ((today.month, today.day) < (b.month, b.day))


def _parse_prompts(raw: str) -> list[dict]:
    try:
        data = json.loads(raw or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    out = []
    labels = dict(dating_tips.PROMPTS)
    for row in data[:3]:
        if not isinstance(row, dict):
            continue
        key = (row.get("key") or "").strip()
        ans = (row.get("answer") or "").strip()
        if key and ans:
            out.append({"key": key, "label": labels.get(key, key), "answer": ans[:160]})
    return out


def _dump_prompts(rows: list[dict]) -> str:
    return json.dumps(rows[:3], ensure_ascii=False)


def _ach_set(p: DatingProfile) -> set[str]:
    raw = (p.achievements or "").strip()
    return {x for x in raw.split(",") if x} if raw else set()


def _ach_save(p: DatingProfile, keys: set[str]) -> None:
    p.achievements = ",".join(sorted(keys))
    p.updated_at = _now()
    p.save(update_fields=["achievements", "updated_at"])


def _unlock(p: DatingProfile, key: str) -> bool:
    keys = _ach_set(p)
    if key in keys:
        return False
    keys.add(key)
    _ach_save(p, keys)
    return True


def get_or_create_profile(user: SocialProfile) -> DatingProfile:
    p = DatingProfile.objects.filter(pk=user.id).first()
    if p:
        return p
    now = _now()
    return DatingProfile.objects.create(
        social_user=user,
        headline="",
        about=(user.bio or "")[:500],
        intent="dating",
        prompts_json="[]",
        discoverable=True,
        created_at=now,
        updated_at=now,
    )


def _roll_daily(p: DatingProfile) -> DatingProfile:
    today = _today()
    dirty = []
    if p.daily_on != today:
        p.daily_on = today
        p.views_today = 0
        p.likes_today = 0
        dirty += ["daily_on", "views_today", "likes_today"]
    if p.superlikes_on != today:
        p.superlikes_on = today
        p.superlikes_left = 3
        dirty += ["superlikes_on", "superlikes_left"]
    if p.last_active_on != today:
        if p.last_active_on == today - timedelta(days=1):
            p.streak = int(p.streak or 0) + 1
        elif p.last_active_on != today:
            p.streak = 1
        p.best_streak = max(int(p.best_streak or 0), int(p.streak or 0))
        p.last_active_on = today
        dirty += ["streak", "best_streak", "last_active_on"]
    if dirty:
        p.updated_at = _now()
        dirty.append("updated_at")
        p.save(update_fields=list(dict.fromkeys(dirty)))
    if int(p.streak or 0) >= 3:
        _unlock(p, "streak_3")
    if int(p.streak or 0) >= 7:
        _unlock(p, "streak_7")
    return p


def profile_completeness(p: DatingProfile) -> dict:
    prompts = _parse_prompts(p.prompts_json)
    checks = [
        ("headline", bool((p.headline or "").strip())),
        ("about", len((p.about or "").strip()) >= 20),
        ("prompts", len(prompts) >= 2),
        ("discoverable", bool(p.discoverable)),
    ]
    done = sum(1 for _, ok in checks if ok)
    total = len(checks)
    return {
        "done": done,
        "total": total,
        "pct": int(100 * done / total) if total else 0,
        "items": [{"key": k, "ok": ok} for k, ok in checks],
        "prompts": prompts,
    }


def save_profile(user: SocialProfile, data: dict) -> DatingProfile:
    p = get_or_create_profile(user)
    p.headline = (data.get("headline") or "").strip()[:120]
    p.about = (data.get("about") or "").strip()[:2000]
    p.intent = (data.get("intent") or "dating").strip()[:24]
    if p.intent not in INTENT_LABELS:
        p.intent = "dating"
    p.age_min = max(18, min(99, int(data.get("age_min") or 18)))
    p.age_max = max(p.age_min, min(99, int(data.get("age_max") or 99)))
    pref = (data.get("gender_pref") or "any").strip()
    p.gender_pref = pref if pref in ("any", "male", "female") else "any"
    p.discoverable = bool(data.get("discoverable"))
    rows = []
    for i in (1, 2, 3):
        key = (data.get(f"prompt{i}_key") or "").strip()
        ans = (data.get(f"prompt{i}_answer") or "").strip()
        if key and ans:
            rows.append({"key": key, "answer": ans[:160]})
    p.prompts_json = _dump_prompts(rows)
    p.updated_at = _now()
    p.save()
    comp = profile_completeness(p)
    if comp["pct"] >= 75:
        _unlock(p, "profile_pro")
    return p


def compatibility(me: SocialProfile, other: SocialProfile, my_d: DatingProfile | None = None) -> dict:
    """0–100 score with human notes."""
    score = 48
    notes = []
    my_city = (me.city or "").strip().lower()
    o_city = (other.city or "").strip().lower()
    if my_city and o_city and my_city == o_city:
        score += 18
        notes.append("один город")
    my_friends = set(friend_ids(me))
    o_friends = set(friend_ids(other))
    mutual = len(my_friends & o_friends)
    if mutual:
        score += min(16, 4 + mutual * 2)
        notes.append(f"общих друзей: {mutual}")
    looking_me = set(me.looking_for or []) if isinstance(me.looking_for, list) else set()
    looking_o = set(other.looking_for or []) if isinstance(other.looking_for, list) else set()
    if looking_me & looking_o:
        score += 8
        notes.append("похожие цели")
    elif "dating" in looking_o or "relationship" in looking_o:
        score += 4
    # interested_in vs gender
    interest = set(me.interested_in or []) if isinstance(me.interested_in, list) else set()
    og = (other.gender or "").strip().lower()
    if interest:
        if ("women" in interest and og in ("female", "f", "ж", "woman")) or (
            "men" in interest and og in ("male", "m", "м", "man")
        ):
            score += 6
            notes.append("по интересу")
    a1, a2 = _age(me), _age(other)
    if a1 and a2 and abs(a1 - a2) <= 6:
        score += 6
        notes.append("близкий возраст")
    # light personalization salt so pairs feel distinct but stable
    salt = int(hashlib.md5(f"dating:{min(me.id, other.id)}:{max(me.id, other.id)}".encode()).hexdigest()[:6], 16)
    score += salt % 7
    if my_d and my_d.intent == "serious":
        score += 2
    score = max(40, min(98, score))
    if not notes:
        notes.append("по кругу и интересам")
    return {"score": score, "notes": notes, "note": " · ".join(notes[:2]), "mutual": mutual}


def _gender_ok(pref: str, other: SocialProfile) -> bool:
    if pref == "any":
        return True
    g = (other.gender or "").strip().lower()
    if pref == "female":
        return g in ("female", "f", "ж", "woman", "женщина")
    if pref == "male":
        return g in ("male", "m", "м", "man", "мужчина")
    return True


def _age_ok(p: DatingProfile, other: SocialProfile) -> bool:
    age = _age(other)
    if age is None:
        return True
    return int(p.age_min or 18) <= age <= int(p.age_max or 99)


def _already_swiped_ids(me: SocialProfile) -> set[int]:
    return set(
        DatingSwipe.objects.filter(from_user=me).values_list("to_user_id", flat=True)[:2000]
    )


def discovery_queue(me: SocialProfile, limit: int = 12) -> list[dict]:
    """Ranked candidates: friends first, then city / looking_for dating."""
    d = _roll_daily(get_or_create_profile(me))
    swiped = _already_swiped_ids(me)
    swiped.add(me.id)
    matched = set()
    for row in DatingMatch.objects.filter(Q(user_a=me) | Q(user_b=me)).values_list("user_a_id", "user_b_id")[:500]:
        matched.add(row[0] if row[1] == me.id else row[1])
    swiped |= matched

    fids = [i for i in friend_ids(me) if i not in swiped][:80]
    candidates: dict[int, SocialProfile] = {}
    if fids:
        for p in SocialProfile.objects.filter(pk__in=fids):
            candidates[p.id] = p

    city = (me.city or "").strip()
    qs = SocialProfile.objects.exclude(pk__in=list(swiped)[:500]).order_by("-id")
    if city:
        qs = qs.filter(city__iexact=city)
    for p in qs[:120]:
        if p.id in candidates:
            continue
        # prefer people with dating intent on classic profile or dating profile
        looking = p.looking_for if isinstance(p.looking_for, list) else []
        dp = DatingProfile.objects.filter(pk=p.id, discoverable=True).first()
        if dp or "dating" in looking or "relationship" in looking or "friendship" in looking:
            candidates[p.id] = p
        if len(candidates) >= 60:
            break

    # also include discoverable dating profiles without city match
    if len(candidates) < 20:
        for dp in DatingProfile.objects.filter(discoverable=True).exclude(
            social_user_id__in=list(swiped)[:500]
        ).order_by("-spark_points", "-updated_at")[:40]:
            if dp.social_user_id in candidates or dp.social_user_id == me.id:
                continue
            sp = SocialProfile.objects.filter(pk=dp.social_user_id).first()
            if sp:
                candidates[sp.id] = sp

    rows = []
    for p in candidates.values():
        if not _gender_ok(d.gender_pref, p):
            continue
        if not _age_ok(d, p):
            continue
        their = DatingProfile.objects.filter(pk=p.id).first()
        if their and not their.discoverable:
            continue
        if their and not _gender_ok(their.gender_pref, me):
            # soft filter: they wouldn't want to see me — skip
            pass
        comp = compatibility(me, p, d)
        boost = 8 if p.id in fids else 0
        if their:
            boost += min(10, int(their.spark_points or 0) // 5)
        rows.append({
            "profile": p,
            "dating": their,
            "score": comp["score"] + boost,
            "comp": comp,
            "is_friend": p.id in fids,
            "age": _age(p),
            "intent": INTENT_LABELS.get((their.intent if their else "dating"), "Знакомства"),
            "headline": (their.headline if their and their.headline else (p.headline or p.bio or ""))[:120],
            "about": (their.about if their and their.about else (p.bio or ""))[:400],
            "prompts": _parse_prompts(their.prompts_json) if their else [],
            "city": (p.city or "").strip(),
        })
    rows.sort(key=lambda r: (-r["score"], -r["profile"].id))
    return rows[:limit]


def record_visit(me: SocialProfile, other: SocialProfile) -> None:
    if me.id == other.id:
        return
    # one counted view per pair per day
    start = datetime.combine(_today(), datetime.min.time())
    if DatingVisit.objects.filter(viewer=me, viewed=other, created_at__gte=start).exists():
        return
    d = _roll_daily(get_or_create_profile(me))
    d.views_today = int(d.views_today or 0) + 1
    d.spark_points = int(d.spark_points or 0) + 1
    d.updated_at = _now()
    d.save(update_fields=["views_today", "spark_points", "updated_at"])
    DatingVisit.objects.create(viewer=me, viewed=other, created_at=_now())


def _ordered_pair(a: SocialProfile, b: SocialProfile) -> tuple[SocialProfile, SocialProfile]:
    return (a, b) if a.id < b.id else (b, a)


@transaction.atomic
def swipe(me: SocialProfile, target_id: int, action: str) -> dict:
    action = (action or "").strip()
    if action not in ("like", "pass", "super"):
        raise ValueError("Неизвестное действие")
    other = SocialProfile.objects.filter(pk=int(target_id)).first()
    if not other or other.id == me.id:
        raise ValueError("Пользователь не найден")
    if DatingSwipe.objects.filter(from_user=me, to_user=other).exists():
        raise ValueError("Уже оценивали этого человека")

    d = _roll_daily(get_or_create_profile(me))
    if action == "super":
        if int(d.superlikes_left or 0) <= 0:
            raise ValueError("Суперлайки на сегодня закончились (завтра будут новые)")
        d.superlikes_left = int(d.superlikes_left) - 1

    DatingSwipe.objects.create(from_user=me, to_user=other, action=action, created_at=_now())
    record_visit(me, other)

    matched = None
    if action in ("like", "super"):
        d.likes_today = int(d.likes_today or 0) + 1
        d.likes_sent = int(d.likes_sent or 0) + 1
        d.spark_points = int(d.spark_points or 0) + (5 if action == "super" else 2)
        _unlock(d, "first_like")
        if action == "super":
            _unlock(d, "super_fan")
        # inbound like?
        inbound = DatingSwipe.objects.filter(
            from_user=other, to_user=me, action__in=["like", "super"]
        ).first()
        if inbound:
            a, b = _ordered_pair(me, other)
            matched = DatingMatch.objects.filter(user_a=a, user_b=b).first()
            if not matched:
                opener = ""
                their = DatingProfile.objects.filter(pk=other.id).first()
                prompts = _parse_prompts(their.prompts_json) if their else []
                if prompts:
                    opener = (
                        f"Насчёт «{prompts[0]['answer'][:80]}» — расскажите больше?"
                    )
                else:
                    first = other.name.split()[0] if other.name else ""
                    opener = f"Приятно взаимно, {first}!"
                matched = DatingMatch.objects.create(
                    user_a=a,
                    user_b=b,
                    opener=opener[:200],
                    created_at=_now(),
                )
                d.matches_n = int(d.matches_n or 0) + 1
                od = get_or_create_profile(other)
                od.matches_n = int(od.matches_n or 0) + 1
                od.likes_got = int(od.likes_got or 0) + 1
                od.spark_points = int(od.spark_points or 0) + 8
                od.updated_at = _now()
                od.save(update_fields=["matches_n", "likes_got", "spark_points", "updated_at"])
                _unlock(d, "first_match")
                _unlock(od, "first_match")
                if (me.city or "").strip() and (me.city or "").strip().lower() == (other.city or "").strip().lower():
                    _unlock(d, "city_spark")
                url = reverse("apps.canvas", args=["dating"]) + f"?tab=matches&match={matched.id}"
                notify.push(
                    other.id,
                    title="Знакомства",
                    body=f"Взаимная симпатия с {me.name}!",
                    type="message",
                    url=url,
                )
                notify.push(
                    me.id,
                    title="Знакомства",
                    body=f"Взаимная симпатия с {other.name}!",
                    type="message",
                    url=url,
                )
        else:
            od = get_or_create_profile(other)
            od.likes_got = int(od.likes_got or 0) + 1
            od.updated_at = _now()
            od.save(update_fields=["likes_got", "updated_at"])
            if action == "super":
                notify.push(
                    other.id,
                    title="Знакомства",
                    body="Кто-то отправил вам суперлайк — загляните в «Вас лайкнули».",
                    type="message",
                    url=reverse("apps.canvas", args=["dating"]) + "?tab=likes",
                )

    d.updated_at = _now()
    d.save()
    return {
        "ok": True,
        "action": action,
        "match": matched,
        "peer": other,
        "superlikes_left": d.superlikes_left,
    }


def likes_you(me: SocialProfile, limit: int = 20) -> list[dict]:
    """People who liked you and you haven't matched / swiped yet."""
    matched = set()
    for a, b in DatingMatch.objects.filter(Q(user_a=me) | Q(user_b=me)).values_list("user_a_id", "user_b_id"):
        matched.add(a if b == me.id else b)
    my_swipes = set(
        DatingSwipe.objects.filter(from_user=me).values_list("to_user_id", flat=True)[:2000]
    )
    rows = []
    for s in (
        DatingSwipe.objects.filter(to_user=me, action__in=["like", "super"])
        .select_related("from_user")
        .order_by("-id")[:80]
    ):
        if s.from_user_id in matched or s.from_user_id in my_swipes:
            continue
        p = s.from_user
        comp = compatibility(me, p)
        rows.append({
            "profile": p,
            "action": s.action,
            "is_super": s.action == "super",
            "comp": comp,
            "city": (p.city or "").strip(),
            "age": _age(p),
        })
        if len(rows) >= limit:
            break
    return rows


def my_matches(me: SocialProfile, limit: int = 30) -> list[dict]:
    out = []
    for m in (
        DatingMatch.objects.filter(Q(user_a=me) | Q(user_b=me))
        .select_related("user_a", "user_b")
        .order_by("-id")[:limit]
    ):
        peer = m.user_b if m.user_a_id == me.id else m.user_a
        seen = m.seen_a if m.user_a_id == me.id else m.seen_b
        out.append({
            "match": m,
            "peer": peer,
            "opener": m.opener,
            "seen": seen,
            "comp": compatibility(me, peer),
            "is_new": not seen,
        })
    return out


def mark_match_seen(me: SocialProfile, match_id: int) -> None:
    m = DatingMatch.objects.filter(pk=match_id).filter(Q(user_a=me) | Q(user_b=me)).first()
    if not m:
        return
    if m.user_a_id == me.id and not m.seen_a:
        m.seen_a = True
        m.save(update_fields=["seen_a"])
    elif m.user_b_id == me.id and not m.seen_b:
        m.seen_b = True
        m.save(update_fields=["seen_b"])


def visitors(me: SocialProfile, limit: int = 15) -> list[dict]:
    seen = set()
    out = []
    for v in (
        DatingVisit.objects.filter(viewed=me)
        .exclude(viewer=me)
        .select_related("viewer")
        .order_by("-id")[:80]
    ):
        if v.viewer_id in seen:
            continue
        seen.add(v.viewer_id)
        out.append({"profile": v.viewer, "when": v.created_at})
        if len(out) >= limit:
            break
    return out


def spark_leaders(me: SocialProfile, limit: int = 10) -> list[dict]:
    city = (me.city or "").strip()
    qs = DatingProfile.objects.filter(discoverable=True).order_by("-spark_points", "-matches_n")[:80]
    out = []
    for dp in qs:
        sp = SocialProfile.objects.filter(pk=dp.social_user_id).first()
        if not sp or sp.id == me.id:
            continue
        if city and (sp.city or "").strip() and (sp.city or "").strip().lower() != city.lower():
            continue
        out.append({
            "profile": sp,
            "points": dp.spark_points,
            "matches_n": dp.matches_n,
            "city": (sp.city or "").strip(),
        })
        if len(out) >= limit:
            break
    if len(out) < limit:
        # fill without city filter
        for dp in DatingProfile.objects.filter(discoverable=True).order_by("-spark_points")[:40]:
            if any(r["profile"].id == dp.social_user_id for r in out):
                continue
            sp = SocialProfile.objects.filter(pk=dp.social_user_id).first()
            if not sp or sp.id == me.id:
                continue
            out.append({
                "profile": sp,
                "points": dp.spark_points,
                "matches_n": dp.matches_n,
                "city": (sp.city or "").strip(),
            })
            if len(out) >= limit:
                break
    return out


def engagement_strip(me: SocialProfile) -> dict:
    d = _roll_daily(get_or_create_profile(me))
    comp = profile_completeness(d)
    goals = [
        {"key": "view", "title": "Посмотреть 5 анкет", "done": int(d.views_today or 0) >= 5, "n": d.views_today, "need": 5},
        {"key": "like", "title": "Отправить 3 лайка", "done": int(d.likes_today or 0) >= 3, "n": d.likes_today, "need": 3},
        {"key": "profile", "title": "Анкета ≥ 75%", "done": comp["pct"] >= 75, "n": comp["pct"], "need": 75},
        {"key": "streak", "title": "Зайти сегодня", "done": d.last_active_on == _today(), "n": 1 if d.last_active_on == _today() else 0, "need": 1},
    ]
    done = sum(1 for g in goals if g["done"])
    badges = []
    unlocked = _ach_set(d)
    for key, title, hint in BADGES:
        badges.append({"key": key, "title": title, "hint": hint, "unlocked": key in unlocked})
    likes_n = DatingSwipe.objects.filter(to_user=me, action__in=["like", "super"]).count()
    # approximate unseen likes
    unseen_likes = len(likes_you(me, limit=50))
    new_matches = sum(1 for m in my_matches(me, limit=40) if m["is_new"])
    return {
        "streak": d.streak,
        "best_streak": d.best_streak,
        "superlikes_left": d.superlikes_left,
        "matches_n": d.matches_n,
        "likes_sent": d.likes_sent,
        "likes_got": likes_n,
        "unseen_likes": unseen_likes,
        "new_matches": new_matches,
        "spark_points": d.spark_points,
        "completeness": comp,
        "goals": {"items": goals, "done": done, "total": len(goals), "pct": int(100 * done / len(goals))},
        "badges": badges,
        "discoverable": d.discoverable,
        "intent": INTENT_LABELS.get(d.intent, "Знакомства"),
    }


def record_tip_quiz(me: SocialProfile, slug: str, choice: str) -> dict:
    tip = dating_tips.tip_by_slug(slug)
    if not tip:
        raise ValueError("Совет не найден")
    ok = choice == tip["quiz"]["answer"]
    d = get_or_create_profile(me)
    keys = _ach_set(d)
    tip_key = f"tip:{slug}"
    first = tip_key not in keys
    if ok:
        keys.add(tip_key)
        tip_solved = len([k for k in keys if k.startswith("tip:")])
        if tip_solved >= 3:
            keys.add("student")
        _ach_save(d, keys)
        if first:
            d.spark_points = int(d.spark_points or 0) + 3
            d.updated_at = _now()
            d.save(update_fields=["spark_points", "updated_at"])
    return {"ok": ok, "explain": tip["quiz"]["explain"], "first": first and ok}
