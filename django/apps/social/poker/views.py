"""Canvas controller for Покер."""
from __future__ import annotations

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse

from apps.social import notify
from apps.social import platform_apps as pa
from apps.social.models import SocialProfile
from apps.social.services import friend_ids

from . import engine as poker_engine
from . import lessons as poker_lessons
from . import puzzles as poker_puzzles
from . import realtime as poker_rt
from . import service as poker
from .forms import (
    ChallengeForm, GameActionForm, LessonQuizForm, PuzzleAnswerForm,
    RoomCreateForm, RoomJoinCodeForm,
)


def _poker_url(tab: str, **params) -> str:
    q = [f"tab={tab}"]
    for k, v in params.items():
        if v is not None and v != "":
            q.append(f"{k}={v}")
    return reverse("apps.canvas", args=["poker"]) + "?" + "&".join(q)


def render_poker_canvas(request, me, app):
    tab = (request.GET.get("tab") or request.POST.get("tab") or "play").strip()
    allowed = (
        "play", "rooms", "room", "table", "learn", "puzzles",
        "bank", "leaders", "ratings", "champs",
    )
    if tab not in allowed:
        tab = "play"

    friends = pa.friends_for_app(me)
    profile = poker.get_or_create_profile(me)
    strip = poker.engagement_strip(me)
    challenge_form = ChallengeForm(friends=friends)
    room_form = RoomCreateForm()
    join_form = RoomJoinCodeForm()
    game = None
    view = None
    actions = []
    lesson = None
    puzzle = None
    puzzle_meta = None
    learn_meta = None
    leaders = None
    ratings = None
    recent = None
    rooms = None
    room = None
    room_meta = None
    champ = None
    standings = None
    past_champs = None
    my_entry = None

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
                g = poker.challenge(
                    me, peer,
                    stake_key=form.cleaned_data["stake"],
                    in_champ=bool(form.cleaned_data.get("in_champ")),
                )
                notify.push(
                    peer,
                    f"{me.name} вызывает вас на покер",
                    url=_poker_url("table", id=g.id),
                )
                messages.success(request, "Вызов отправлен — ждём принятия.")
                return redirect(_poker_url("table", id=g.id))

            if action == "accept":
                gid = int(request.POST.get("game_id") or 0)
                g = poker.accept_challenge(me, gid)
                poker_rt.notify_game(g, event="deal")
                messages.success(request, "Раздача началась. Удачи!")
                return redirect(_poker_url("table", id=g.id))

            if action == "decline":
                poker.decline_challenge(me, int(request.POST.get("game_id") or 0))
                messages.info(request, "Вызов отклонён.")
                return redirect(_poker_url("play"))

            if action == "cancel":
                poker.cancel_challenge(me, int(request.POST.get("game_id") or 0))
                messages.info(request, "Вызов отменён.")
                return redirect(_poker_url("play"))

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
                poker_rt.notify_game(g, event="acted")
                if g.status == "done":
                    messages.success(request, f"Раздача окончена: {g.last_action}")
                    if g.room_id:
                        return redirect(_poker_url("room", id=g.room_id))
                else:
                    messages.success(request, g.last_action or "Ход принят")
                return redirect(_poker_url("table", id=g.id))

            if action == "create_room":
                form = RoomCreateForm(request.POST)
                if not form.is_valid():
                    room_form = form
                    raise ValueError("Проверьте параметры комнаты")
                if strip["bankrupt"]:
                    raise ValueError("Банкротство: комнату создать нельзя")
                r = poker.create_room(
                    me,
                    title=form.cleaned_data.get("title") or "",
                    stake_key=form.cleaned_data["stake"],
                    is_private=bool(form.cleaned_data.get("is_private")),
                    in_champ=bool(form.cleaned_data.get("in_champ")),
                    max_seats=int(form.cleaned_data.get("max_seats") or 6),
                )
                poker.mark_host_achievement(me)
                poker_rt.broadcast_room(r.id, "created")
                msg = f"Комната на {r.max_seats} мест создана."
                if r.is_private and r.join_code:
                    msg += f" Код: {r.join_code}"
                messages.success(request, msg)
                return redirect(_poker_url("room", id=r.id))

            if action == "daily_bonus":
                got = poker.claim_daily_bonus(me)
                messages.success(
                    request,
                    f"Ежедневный бонус: +{poker_engine.format_chips(got['amount'])} фишек "
                    f"(серия {got['streak']} дн.).",
                )
                return redirect(_poker_url("play"))

            if action == "join_room":
                rid = int(request.POST.get("room_id") or 0)
                r = poker.join_room(me, room_id=rid or None)
                poker_rt.broadcast_room(r.id, "join")
                messages.success(request, "Вы за столом.")
                return redirect(_poker_url("room", id=r.id))

            if action == "join_code":
                form = RoomJoinCodeForm(request.POST)
                if not form.is_valid():
                    join_form = form
                    raise ValueError("Введите код комнаты")
                r = poker.join_room(me, join_code=form.cleaned_data["join_code"])
                poker_rt.broadcast_room(r.id, "join")
                messages.success(request, f"Вход в «{r.title}».")
                return redirect(_poker_url("room", id=r.id))

            if action == "leave_room":
                rid = int(request.POST.get("room_id") or 0)
                poker.leave_room(me, rid)
                poker_rt.broadcast_room(rid, "leave")
                messages.info(request, "Вы вышли из комнаты.")
                return redirect(_poker_url("rooms"))

            if action == "close_room":
                rid = int(request.POST.get("room_id") or 0)
                poker.close_room(me, rid)
                poker_rt.broadcast_room(rid, "closed")
                messages.info(request, "Комната закрыта.")
                return redirect(_poker_url("rooms"))

            if action == "start_hand":
                rid = int(request.POST.get("room_id") or 0)
                g = poker.start_room_hand(me, rid)
                poker_rt.notify_game(g, event="deal")
                poker_rt.broadcast_room(rid, "playing")
                messages.success(request, "Новая раздача!")
                return redirect(_poker_url("table", id=g.id))

            if action == "reset_bankruptcy":
                poker.reset_after_bankruptcy(me)
                messages.success(
                    request,
                    f"Профиль обнулён. На ваш счёт зачислено {poker.STARTING_CHIPS:,} фишек.".replace(",", " "),
                )
                return redirect(_poker_url("bank"))

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
                return redirect(_poker_url("learn", lesson=slug))

            if action == "lesson_done":
                slug = (request.POST.get("lesson") or "").strip()
                poker.mark_lesson_done(me, slug)
                messages.success(request, "Урок отмечен.")
                return redirect(_poker_url("learn", lesson=slug))

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
                    return redirect(_poker_url("puzzles", puzzle=pz["id"], hint=1))
                return redirect(_poker_url("puzzles", puzzle=pz["id"]))
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
            actions = list(
                PokerAction.objects.filter(game=game).select_related("actor").order_by("ply")[:40]
            )
        else:
            messages.error(request, "Раздача не найдена.")
            tab = "play"
            hub = strip

    if tab == "rooms":
        rooms = poker.list_open_rooms(40)
        room_form = RoomCreateForm()
        join_form = RoomJoinCodeForm()

    if tab == "room":
        try:
            rid = int(request.GET.get("id") or 0)
        except (TypeError, ValueError):
            rid = 0
        room = poker.room_for(me, rid) if rid else None
        if room and room.status != "closed":
            room_meta = poker.room_view(room, me)
            if room_meta.get("active_game"):
                return redirect(_poker_url("table", id=room_meta["active_game"].id))
        else:
            messages.error(request, "Комната не найдена.")
            tab = "rooms"
            rooms = poker.list_open_rooms(40)

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
    if tab == "ratings":
        try:
            page_num = int(request.GET.get("p") or 1)
        except (TypeError, ValueError):
            page_num = 1
        ratings = poker.ratings_page(page_num, 25)
    if tab == "champs":
        champ = poker.ensure_week_championship()
        standings = poker.championship_standings(champ, 40)
        past_champs = poker.recent_championships(6)
        my_entry = next((e for e in standings if e.social_user_id == me.id), None)
    if tab == "bank":
        recent = poker.recent_finished(me, 12)
        profile = poker.get_or_create_profile(me)
        strip = poker.engagement_strip(me)

    show_hint = (request.GET.get("hint") or "") in ("1", "yes", "true")

    return render(request, "social/apps/canvas_poker.html", {
        "me": me, "app": app, "friends": friends, "tab": tab,
        "strip": strip, "hub": hub, "profile": profile,
        "challenge_form": challenge_form,
        "room_form": room_form, "join_form": join_form,
        "rooms": rooms, "room": room, "room_meta": room_meta,
        "game": game, "view": view, "actions": actions,
        "learn_meta": learn_meta, "lesson": lesson,
        "chapters": (learn_meta or {}).get("chapters") or [],
        "puzzle": puzzle, "puzzle_meta": puzzle_meta,
        "puzzles": (puzzle_meta or {}).get("theme_list") or poker_puzzles.PUZZLES,
        "show_hint": show_hint,
        "leaders": leaders, "ratings": ratings, "recent": recent,
        "champ": champ or strip.get("champ"),
        "standings": standings, "past_champs": past_champs, "my_entry": my_entry,
        "stake_levels": poker.STAKE_LEVELS,
        "nav": "apps", "installed": True,
    })
