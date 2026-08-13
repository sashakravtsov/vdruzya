"""Canvas controller for Знакомства."""
from __future__ import annotations

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse

from . import service as dating
from . import tips as dating_tips
from apps.social.live.broadcast import notify_dating

def _live_dating(me, *extra_ids):
    try:
        notify_dating(me.id)
        for uid in extra_ids:
            if uid:
                notify_dating(int(uid))
    except Exception:
        pass

from .forms import ProfileForm, SwipeForm, TipQuizForm


def _url(tab: str = "discover", **extra) -> str:
    q = [f"tab={tab}"]
    for k, v in extra.items():
        if v is None or v == "":
            continue
        q.append(f"{k}={v}")
    return reverse("apps.canvas", args=["dating"]) + "?" + "&".join(q)


def render_dating_canvas(request, me, app):
    tab = (request.GET.get("tab") or request.POST.get("tab") or "discover").strip()
    if tab not in ("discover", "likes", "matches", "profile", "tips", "spark"):
        tab = "discover"

    strip = dating.engagement_strip(me)
    my_dating = dating.get_or_create_profile(me)
    card = None
    queue = []
    likes = []
    matches = []
    visitors = []
    leaders = []
    tip = None
    tip_chapters = []
    profile_form = None
    match_flash = None
    tip_solved = {
        k[4:] for k in (my_dating.achievements or "").split(",") if k.startswith("tip:")
    }

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        try:
            if action == "swipe":
                form = SwipeForm(request.POST)
                if not form.is_valid():
                    raise ValueError("Некорректное действие")
                result = dating.swipe(
                    me,
                    form.cleaned_data["target_id"],
                    form.cleaned_data["swipe_action"],
                )
                peer = result.get("peer")
                _live_dating(me, peer.id if peer else None)
                if result.get("match"):
                    messages.success(
                        request,
                        f"Взаимная симпатия с {result['peer'].name}! Напишите первым.",
                    )
                    return redirect(_url("matches", match=result["match"].id, spark=1))
                if form.cleaned_data["swipe_action"] == "pass":
                    messages.info(request, "Пропущено — следующий человек.")
                elif form.cleaned_data["swipe_action"] == "super":
                    messages.success(request, "Суперлайк отправлен.")
                else:
                    messages.success(request, "Лайк отправлен.")
                next_tab = (request.POST.get("tab") or request.GET.get("tab") or "discover").strip()
                if next_tab not in ("discover", "likes"):
                    next_tab = "discover"
                return redirect(_url(next_tab))

            if action == "save_profile":
                form = ProfileForm(request.POST)
                if not form.is_valid():
                    profile_form = form
                    raise ValueError("Проверьте анкету")
                dating.save_profile(me, form.cleaned_data)
                messages.success(request, "Анкета сохранена.")
                _live_dating(me)
                return redirect(_url("profile"))

            if action == "tip_quiz":
                form = TipQuizForm(request.POST)
                if not form.is_valid():
                    raise ValueError("Выберите ответ")
                tip_obj = dating_tips.tip_by_slug(form.cleaned_data["tip_slug"])
                if not tip_obj:
                    raise ValueError("Совет не найден")
                meta = dating.record_tip_quiz(
                    me, form.cleaned_data["tip_slug"], form.cleaned_data["choice"]
                )
                if meta["ok"]:
                    messages.success(request, f"Верно! {meta['explain']}")
                else:
                    messages.error(request, "Пока не то — перечитайте совет.")
                return redirect(_url("tips", tip=tip_obj["slug"]))

            if action == "toggle_discover":
                p = dating.get_or_create_profile(me)
                p.discoverable = not p.discoverable
                p.save(update_fields=["discoverable", "updated_at"])
                messages.info(
                    request,
                    "Вы снова в ленте." if p.discoverable else "Анкета скрыта из ленты.",
                )
                return redirect(_url("profile"))

            if action == "unmatch":
                try:
                    mid = int(request.POST.get("match_id") or 0)
                except (TypeError, ValueError):
                    mid = 0
                if dating.unmatch(me, mid):
                    messages.info(request, "Матч удалён.")
                    _live_dating(me)
                else:
                    messages.error(request, "Не удалось удалить матч.")
                return redirect(_url("matches"))
        except ValueError as exc:
            messages.error(request, str(exc))
        except Exception:
            messages.error(request, "Не удалось выполнить действие.")

    strip = dating.engagement_strip(me)
    my_dating = dating.get_or_create_profile(me)

    if tab == "discover":
        queue = dating.discovery_queue(me, limit=8)
        if queue:
            card = queue[0]
            dating.record_visit(me, card["profile"])
            strip = dating.engagement_strip(me)

    if tab == "likes":
        likes = dating.likes_you(me)

    if tab == "matches":
        matches = dating.my_matches(me)
        mid = request.GET.get("match")
        if mid:
            try:
                dating.mark_match_seen(me, int(mid))
            except (TypeError, ValueError):
                pass
            matches = dating.my_matches(me)
            for row in matches:
                if str(row["match"].id) == str(mid):
                    match_flash = row
                    break
        visitors = dating.visitors(me)

    if tab == "profile":
        prompts = dating.profile_completeness(my_dating)["prompts"]
        initial = {
            "headline": my_dating.headline,
            "about": my_dating.about,
            "intent": my_dating.intent,
            "age_min": my_dating.age_min,
            "age_max": my_dating.age_max,
            "gender_pref": my_dating.gender_pref,
            "discoverable": my_dating.discoverable,
        }
        for i, row in enumerate(prompts[:3], start=1):
            initial[f"prompt{i}_key"] = row["key"]
            initial[f"prompt{i}_answer"] = row["answer"]
        profile_form = profile_form or ProfileForm(initial=initial)

    if tab == "tips":
        tip_chapters = dating_tips.tips_by_chapter()
        tip = dating_tips.tip_by_slug((request.GET.get("tip") or "").strip())
        if not tip and tip_chapters and tip_chapters[0]["tips"]:
            tip = tip_chapters[0]["tips"][0]

    if tab == "spark":
        leaders = dating.spark_leaders(me)

    return render(
        request,
        "social/apps/canvas_dating.html",
        {
            "me": me,
            "app": app,
            "nav": "apps",
            "installed": True,
            "tab": tab,
            "strip": strip,
            "my_dating": my_dating,
            "card": card,
            "queue_n": len(queue),
            "likes": likes,
            "matches": matches,
            "visitors": visitors,
            "leaders": leaders,
            "tip": tip,
            "tip_chapters": tip_chapters,
            "tip_solved": tip_solved,
            "profile_form": profile_form,
            "match_flash": match_flash,
            "spark_celebrate": request.GET.get("spark") in ("1", "yes"),
            "prompts_catalog": dating_tips.PROMPTS,
        },
    )
