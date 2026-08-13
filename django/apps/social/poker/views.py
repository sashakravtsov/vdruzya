"""Canvas controller for Покер."""
from __future__ import annotations

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse

from apps.social import notify
from apps.social import platform_apps as pa
from apps.social.models import SocialProfile
from apps.social.services import friend_ids

from . import lessons as poker_lessons
from . import puzzles as poker_puzzles
from . import service as poker
from .forms import ChallengeForm, GameActionForm, LessonQuizForm, PuzzleAnswerForm


def render_poker_canvas(request, me, app):
    tab = (request.GET.get("tab") or request.POST.get("tab") or "play").strip()
    if tab not in ("play", "table", "learn", "puzzles", "bank", "leaders"):
        tab = "play"

    friends = pa.friends_for_app(me)
    profile = poker.get_or_create_profile(me)
    strip = poker.engagement_strip(me)
    challenge_form = ChallengeForm(friends=friends)
    game = None
    view = None
    actions = []
    lesson = None
    puzzle = None
    puzzle_meta = None
    learn_meta = None
    leaders = None
    recent = None

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        try:
            if action == "challenge":
                form = ChallengeForm(request.POST, friends=friends)
                if not form.is_valid():
                    challenge_form = form
                    raise ValueError("Проверьте друга и лимит")
                if strip["bankrupt"]:
                    raise ValueError("Банкротство: играть нельзя")
                fid = form.cleaned_data["friend_id"]
                if fid not in friend_ids(me):
                    raise ValueError("Выберите друга из списка")
                peer = SocialProfile.objects.filter(pk=fid).first()
                if not peer:
                    raise ValueError("Соперник не найден")
                g = poker.challenge(me, peer, stake_key=form.cleaned_data["stake"])
                notify.push(
                    peer,
                    f"{me.name} вызывает вас на покер",
                    url=reverse("apps.canvas", args=["poker"]) + f"?tab=table&id={g.id}",
                )
                messages.success(request, "Вызов отправлен — ждём принятия.")
                return redirect(reverse("apps.canvas", args=["poker"]) + f"?tab=table&id={g.id}")

            if action == "accept":
                gid = int(request.POST.get("game_id") or 0)
                g = poker.accept_challenge(me, gid)
                messages.success(request, "Раздача началась. Удачи!")
                return redirect(reverse("apps.canvas", args=["poker"]) + f"?tab=table&id={g.id}")

            if action == "decline":
                poker.decline_challenge(me, int(request.POST.get("game_id") or 0))
                messages.info(request, "Вызов отклонён.")
                return redirect(reverse("apps.canvas", args=["poker"]) + "?tab=play")

            if action == "cancel":
                poker.cancel_challenge(me, int(request.POST.get("game_id") or 0))
                messages.info(request, "Вызов отменён.")
                return redirect(reverse("apps.canvas", args=["poker"]) + "?tab=play")

            if action == "act":
                form = GameActionForm(request.POST)
                if not form.is_valid():
                    raise ValueError("Некорректное действие")
                g = poker.act(
                    me,
                    form.cleaned_data["game_id"],
                    form.cleaned_data["play"],
                    raise_to=int(form.cleaned_data.get("raise_to") or 0),
                )
                if g.status == "done":
                    messages.success(request, f"Раздача окончена: {g.last_action}")
                else:
                    messages.success(request, g.last_action or "Ход принят")
                return redirect(reverse("apps.canvas", args=["poker"]) + f"?tab=table&id={g.id}")

            if action == "reset_bankruptcy":
                poker.reset_after_bankruptcy(me)
                messages.success(
                    request,
                    f"Профиль обнулён. На ваш счёт зачислено {poker.STARTING_CHIPS:,} фишек.".replace(",", " "),
                )
                return redirect(reverse("apps.canvas", args=["poker"]) + "?tab=bank")

            if action == "lesson_quiz":
                form = LessonQuizForm(request.POST)
                if not form.is_valid():
                    raise ValueError("Выберите ответ")
                slug = form.cleaned_data["lesson"]
                result = poker.submit_lesson_quiz(me, slug, form.cleaned_data["choice"])
                msg = "Верно! " + result["explain"]
                if result.get("newly_completed"):
                    msg += " Урок пройден."
                messages.success(request, msg)
                return redirect(reverse("apps.canvas", args=["poker"]) + f"?tab=learn&lesson={slug}")

            if action == "lesson_done":
                slug = (request.POST.get("lesson") or "").strip()
                poker.mark_lesson_done(me, slug)
                messages.success(request, "Урок отмечен.")
                return redirect(reverse("apps.canvas", args=["poker"]) + f"?tab=learn&lesson={slug}")

            if action == "puzzle":
                form = PuzzleAnswerForm(request.POST)
                if not form.is_valid():
                    raise ValueError("Выберите ответ")
                pz = poker_puzzles.puzzle_by_id(form.cleaned_data["puzzle_id"])
                if not pz:
                    raise ValueError("Задача не найдена")
                ok = poker_puzzles.check_answer(pz, form.cleaned_data["choice"])
                meta = poker.record_puzzle_attempt(me, pz["id"], ok)
                if ok:
                    extra = ""
                    if meta["first_solve"]:
                        extra = f" Серия: {meta['streak']}."
                        if meta.get("xp_gain"):
                            extra += f" +{meta['xp_gain']} XP."
                    messages.success(request, f"Верно! {pz['explain']}{extra}")
                else:
                    messages.error(request, "Пока не то. Откройте подсказку.")
                    return redirect(
                        reverse("apps.canvas", args=["poker"])
                        + f"?tab=puzzles&puzzle={pz['id']}&hint=1"
                    )
                return redirect(reverse("apps.canvas", args=["poker"]) + f"?tab=puzzles&puzzle={pz['id']}")
        except ValueError as exc:
            messages.error(request, str(exc))
        except Exception:
            messages.error(request, "Не удалось выполнить действие.")

    hub = strip if tab == "play" else None

    if tab == "table":
        try:
            gid = int(request.GET.get("id") or 0)
        except (TypeError, ValueError):
            gid = 0
        game = poker.game_for(me, gid) if gid else None
        if game:
            view = poker.table_view(game, me)
            from .models import PokerAction
            actions = list(PokerAction.objects.filter(game=game).select_related("actor").order_by("ply")[:40])
        else:
            messages.error(request, "Раздача не найдена.")
            tab = "play"
            hub = strip

    if tab in ("learn", "puzzles", "play"):
        learn_meta = poker.learn_stats(me)
    if tab == "learn":
        lesson = poker_lessons.lesson_by_slug((request.GET.get("lesson") or "").strip())
    if tab == "puzzles":
        theme = (request.GET.get("theme") or "все").strip()
        puzzle_meta = poker.puzzle_stats(me)
        puzzle_meta["theme"] = theme
        puzzle_meta["theme_list"] = poker_puzzles.puzzles_by_theme(theme)
        if request.GET.get("daily"):
            pid = puzzle_meta["daily"]["id"]
        else:
            pid = (request.GET.get("puzzle") or puzzle_meta["daily"]["id"]).strip()
        puzzle = poker_puzzles.puzzle_by_id(pid) or puzzle_meta["daily"]
    if tab == "leaders":
        leaders = poker.leaderboard(25)
    if tab == "bank":
        recent = poker.recent_finished(me, 12)
        profile = poker.get_or_create_profile(me)
        strip = poker.engagement_strip(me)

    show_hint = (request.GET.get("hint") or "") in ("1", "yes", "true")

    return render(request, "social/apps/canvas_poker.html", {
        "me": me, "app": app, "friends": friends, "tab": tab,
        "strip": strip, "hub": hub, "profile": profile,
        "challenge_form": challenge_form,
        "game": game, "view": view, "actions": actions,
        "learn_meta": learn_meta, "lesson": lesson,
        "chapters": (learn_meta or {}).get("chapters") or [],
        "puzzle": puzzle, "puzzle_meta": puzzle_meta,
        "puzzles": (puzzle_meta or {}).get("theme_list") or poker_puzzles.PUZZLES,
        "show_hint": show_hint,
        "leaders": leaders, "recent": recent,
        "stake_levels": poker.STAKE_LEVELS,
        "nav": "apps", "installed": True,
    })
