"""Canvas controller for Ферма."""
from __future__ import annotations

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse

from apps.social.services import friend_ids

from . import catalog
from . import lessons as farm_lessons
from . import service as farm
from apps.social.live.broadcast import notify_farm

def _live_farm(me, *extra_ids):
    try:
        notify_farm(me.id)
        for uid in extra_ids:
            if uid:
                notify_farm(int(uid))
    except Exception:
        pass

from .forms import (
    AnimalActionForm, AnimalBuyForm, LessonQuizForm, PlantForm, PlotActionForm, ShopForm, VisitActionForm,
)


def _url(tab: str = "field", **extra) -> str:
    q = [f"tab={tab}"]
    for k, v in extra.items():
        if v is None or v == "":
            continue
        q.append(f"{k}={v}")
    return reverse("apps.canvas", args=["farm"]) + "?" + "&".join(q)


def render_farm_canvas(request, me, app):
    tab = (request.GET.get("tab") or request.POST.get("tab") or "field").strip()
    if tab not in ("field", "barn", "shop", "neighbors", "visit", "learn", "bank"):
        tab = "field"

    strip = farm.engagement_strip(me)
    plots = []
    animals = []
    crops = farm.crops_catalog_for(me)
    shop = catalog.SHOP
    animal_catalog = [catalog.animal_by_slug(a[0]) for a in catalog.ANIMALS]
    friends = []
    visit = None
    lesson = None
    chapters = []
    lesson_done = set()

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        try:
            allowed_when_broke = {"reset", "lesson_quiz"}
            if strip["bankrupt"] and action not in allowed_when_broke:
                raise ValueError(
                    f"Банкротство: подождите ~{strip['bankrupt_days_left']} дн. "
                    "После срока можно обнулить профиль на вкладке Банк."
                )

            if action == "plant":
                form = PlantForm(request.POST)
                if not form.is_valid():
                    raise ValueError("Выберите грядку и культуру")
                farm.plant(me, form.cleaned_data["plot_id"], form.cleaned_data["crop"])
                messages.success(request, "Посажено! Не забудьте полить.")
                _live_farm(me)

                return redirect(_url("field"))

            if action == "water":
                form = PlotActionForm(request.POST)
                if not form.is_valid():
                    raise ValueError("Грядка?")
                farm.water_plot(me, form.cleaned_data["plot_id"])
                messages.success(request, "Полито — урожай будет полным.")
                _live_farm(me)

                return redirect(_url("field"))

            if action == "fertilize":
                form = PlotActionForm(request.POST)
                if not form.is_valid():
                    raise ValueError("Грядка?")
                farm.fertilize_plot(me, form.cleaned_data["plot_id"])
                messages.success(request, "Удобрено — рост ускорен.")
                _live_farm(me)

                return redirect(_url("field"))

            if action == "boost":
                form = PlotActionForm(request.POST)
                if not form.is_valid():
                    raise ValueError("Грядка?")
                farm.boost_plot(me, form.cleaned_data["plot_id"])
                messages.success(request, "Ускоритель применён.")
                _live_farm(me)

                return redirect(_url("field"))

            if action == "harvest":
                form = PlotActionForm(request.POST)
                if not form.is_valid():
                    raise ValueError("Грядка?")
                res = farm.harvest(me, form.cleaned_data["plot_id"])
                messages.success(
                    request,
                    f"Собрано {res['crop']['title']}: +{res['amount']:,} фишек, +{res['xp']} XP".replace(",", " "),
                )
                _live_farm(me)

                return redirect(_url("field"))

            if action == "clear":
                form = PlotActionForm(request.POST)
                if not form.is_valid():
                    raise ValueError("Грядка?")
                farm.clear_withered(me, form.cleaned_data["plot_id"])
                messages.info(request, "Увядшая грядка очищена.")
                _live_farm(me)

                return redirect(_url("field"))

            if action == "expand":
                farm.expand_field(me)
                messages.success(request, "Новая грядка открыта!")
                _live_farm(me)

                return redirect(_url("field"))

            if action == "shop":
                form = ShopForm(request.POST)
                if not form.is_valid():
                    raise ValueError("Товар?")
                farm.buy_shop(me, form.cleaned_data["item"], form.cleaned_data["qty"])
                messages.success(request, "Покупка в лавке успешна.")
                _live_farm(me)

                return redirect(_url("shop"))

            if action == "buy_animal":
                form = AnimalBuyForm(request.POST)
                if not form.is_valid():
                    raise ValueError("Кого купить?")
                an = farm.buy_animal(me, form.cleaned_data["kind"])
                meta = catalog.animal_by_slug(an.kind)
                messages.success(request, f"В хлеву новая {meta['title']}!")
                _live_farm(me)

                return redirect(_url("barn"))

            if action == "feed":
                form = AnimalActionForm(request.POST)
                if not form.is_valid():
                    raise ValueError("Животное?")
                farm.feed_animal(me, form.cleaned_data["animal_id"])
                messages.success(request, "Накормлено — ждите продукцию.")
                _live_farm(me)

                return redirect(_url("barn"))

            if action == "collect":
                form = AnimalActionForm(request.POST)
                if not form.is_valid():
                    raise ValueError("Животное?")
                res = farm.collect_animal(me, form.cleaned_data["animal_id"])
                messages.success(
                    request,
                    f"Продукция {res['meta']['title']}: +{res['amount']:,}".replace(",", " "),
                )
                _live_farm(me)

                return redirect(_url("barn"))

            if action == "daily":
                res = farm.claim_daily_bonus(me)
                messages.success(
                    request,
                    f"Дневной бонус: +{res['amount']:,} (серия {res['streak']})".replace(",", " "),
                )
                _live_farm(me)

                return redirect(_url("bank"))

            if action == "reset":
                farm.reset_after_bankruptcy(me)
                messages.success(request, "Профиль обнулён. Снова 1 000 000 фишек — удачной пахоты!")
                _live_farm(me)

                return redirect(_url("field"))

            if action == "help":
                form = VisitActionForm(request.POST)
                if not form.is_valid():
                    raise ValueError("Грядка?")
                res = farm.help_neighbor(
                    me, form.cleaned_data["owner_id"], form.cleaned_data["plot_id"]
                )
                messages.success(request, f"Помогли соседу! +{res['tip']} фишек, +{res['xp']} XP")
                _live_farm(me)

                return redirect(_url("visit", owner=form.cleaned_data["owner_id"]))

            if action == "steal":
                form = VisitActionForm(request.POST)
                if not form.is_valid():
                    raise ValueError("Грядка?")
                res = farm.steal_neighbor(
                    me, form.cleaned_data["owner_id"], form.cleaned_data["plot_id"]
                )
                messages.info(
                    request,
                    f"Взяли часть «{res['crop']['title']}»: +{res['amount']:,}".replace(",", " "),
                )
                _live_farm(me)

                return redirect(_url("visit", owner=form.cleaned_data["owner_id"]))

            if action == "lesson_quiz":
                form = LessonQuizForm(request.POST)
                if not form.is_valid():
                    raise ValueError("Ответ?")
                les = farm_lessons.lesson_by_slug(form.cleaned_data["lesson_slug"])
                if not les:
                    raise ValueError("Урок не найден")
                # allow quiz even if bankrupt? learning ok - bypass by clearing check
                # temporarily: complete_lesson doesn't check bankrupt in service - good
                meta = farm.complete_lesson(
                    me, form.cleaned_data["lesson_slug"], form.cleaned_data["choice"]
                )
                if meta["ok"]:
                    messages.success(request, f"Верно! {meta['explain']}")
                else:
                    messages.error(request, "Пока не то.")
                _live_farm(me)

                return redirect(_url("learn", lesson=les["slug"]))
        except ValueError as exc:
            messages.error(request, str(exc))
        except Exception:
            messages.error(request, "Не удалось выполнить действие.")

    strip = farm.engagement_strip(me)
    p = farm.get_or_create_profile(me)
    lesson_done = set(x for x in (p.lesson_slugs or "").split(",") if x)

    if tab == "field":
        plots = farm.plots_view(me)
        crops = farm.crops_catalog_for(me)
    if tab == "barn":
        animals = farm.animals_view(me)
    if tab == "neighbors":
        friends = farm.friend_farms(me)
    if tab == "visit":
        try:
            oid = int(request.GET.get("owner") or 0)
        except (TypeError, ValueError):
            oid = 0
        if oid and (oid == me.id or oid in friend_ids(me)):
            try:
                visit = farm.visit_farm(me, oid)
            except ValueError as exc:
                messages.error(request, str(exc))
                tab = "neighbors"
                friends = farm.friend_farms(me)
        else:
            messages.error(request, "Ферма недоступна.")
            tab = "neighbors"
            friends = farm.friend_farms(me)
    if tab == "learn":
        chapters = farm_lessons.lessons_by_chapter()
        lesson = farm_lessons.lesson_by_slug((request.GET.get("lesson") or "").strip())
        if not lesson and chapters and chapters[0]["lessons"]:
            lesson = chapters[0]["lessons"][0]

    return render(
        request,
        "social/apps/canvas_farm.html",
        {
            "me": me,
            "app": app,
            "nav": "apps",
            "installed": True,
            "tab": tab,
            "strip": strip,
            "plots": plots,
            "animals": animals,
            "crops": crops,
            "shop": shop,
            "animal_catalog": animal_catalog,
            "friends": friends,
            "visit": visit,
            "lesson": lesson,
            "chapters": chapters,
            "lesson_done": lesson_done,
            "starting_chips": catalog.STARTING_CHIPS,
        },
    )
