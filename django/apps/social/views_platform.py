"""First-party Platform canvas apps + install flow (2007–08 style under 2006 chrome)."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from apps.social import notify
from apps.social import platform_apps as pa
from apps.social.models import AppTruthAsk, Post, SocialProfile
from apps.social.services import bump_news, friend_ids, now, profile_of


def _require_app(slug, viewer=None):
    return pa.app_by_slug(slug, viewer=viewer)


@login_required
@require_POST
def app_install(request, slug):
    me = profile_of(request.user)
    app = _require_app(slug, viewer=me)
    if not app:
        messages.error(request, "Приложение не найдено.")
        return redirect("apps")
    pa.install(me, slug)
    messages.success(request, f"Приложение «{app['name']}» добавлено.")
    next_url = request.POST.get("next") or reverse("apps.canvas", args=[slug])
    return redirect(next_url)


@login_required
@require_POST
def app_uninstall(request, slug):
    me = profile_of(request.user)
    app = _require_app(slug, viewer=me)
    if app and pa.uninstall(me, slug):
        messages.info(request, f"Приложение «{app['name']}» удалено из ваших.")
    return redirect(request.POST.get("next") or "apps")


@login_required
@require_http_methods(["GET", "POST"])
def app_canvas(request, slug):
    me = profile_of(request.user)
    app = _require_app(slug, viewer=me)
    if not app:
        messages.error(request, "Приложение не найдено.")
        return redirect("apps")
    if not pa.is_installed(me, slug):
        pa.install(me, slug)

    if app.get("dev_owned"):
        return _canvas_devapp(request, me, app)

    handlers = {
        "causes": _canvas_causes,
        "quiz": _canvas_quiz,
        "superpoke": _canvas_superpoke,
        "compare": _canvas_compare,
        "truth": _canvas_truth,
        "calculator": _canvas_calculator,
        "weather": _canvas_weather,
        "horoscope": _canvas_horoscope,
        "dating": _canvas_dating,
        "farm": _canvas_farm,
        "billiards": _canvas_billiards,
        "chess": _canvas_chess,
        "tetris": _canvas_tetris,
        "poker": _canvas_poker,
    }
    handler = handlers.get(slug)
    if not handler:
        return redirect("apps.show", slug=slug)
    return handler(request, me, app)


def _canvas_devapp(request, me, app):
    """First-party canvas shell + OAuth/signed launch (no foreign iframe)."""
    from apps.social import platform_oauth as oauth
    from apps.social.models import DevApp
    row = DevApp.objects.filter(slug=app["slug"]).first()
    return render(request, "social/apps/canvas_devapp.html", {
        "me": me, "app": app, "website_url": app.get("website_url") or "",
        "nav": "apps", "installed": True,
        "n_installs": oauth.install_count(app["slug"]) if row else 0,
        "is_owner": bool(row and row.owner_id == me.id),
    })


@login_required
@require_http_methods(["GET", "POST"])
def app_authorize(request, slug):
    """OAuth-lite authorize dialog (2006 FBDialog-style page)."""
    from apps.social import platform_oauth as oauth
    from apps.social.models import DevApp

    me = profile_of(request.user)
    row = DevApp.objects.select_related("owner").filter(slug=slug).first()
    if not row or not (row.published or row.owner_id == me.id):
        messages.error(request, "Приложение не найдено.")
        return redirect("apps")
    oauth.ensure_app_credentials(row)
    redirect_uri = (request.GET.get("redirect_uri") or request.POST.get("redirect_uri") or "").strip()
    if not redirect_uri:
        redirect_uri = (row.callback_url or row.website_url or "").strip()
    client_id = (request.GET.get("client_id") or request.POST.get("client_id") or row.api_key).strip()
    if client_id != row.api_key:
        messages.error(request, "Неверный client_id.")
        return redirect("apps.show", slug=slug)
    if not oauth.allowed_redirect(row, redirect_uri):
        messages.error(request, "redirect_uri не совпадает с сайтом приложения.")
        return redirect("apps.show", slug=slug)

    app = pa.app_by_slug(slug, viewer=me)
    if request.method == "POST":
        if request.POST.get("allow") != "1":
            deny = oauth.append_query(redirect_uri, {"error": "access_denied"})
            return redirect(deny)
        if not pa.is_installed(me, slug):
            pa.install(me, slug)
        code = oauth.create_oauth_code(row, me, redirect_uri)
        signed = oauth.make_signed_request(row, me)
        go = oauth.append_query(redirect_uri, {
            "code": code,
            "signed_request": signed,
            "user_id": me.id,
        })
        return redirect(go)

    return render(request, "social/app_authorize.html", {
        "me": me, "app": app, "dev": row, "nav": "apps",
        "redirect_uri": redirect_uri, "client_id": row.api_key,
        "permissions": pa.permissions_for(app),
    })


@login_required
@require_http_methods(["GET", "POST"])
def app_launch(request, slug):
    """Signed launch to website_url (install + signed_request, no iframe)."""
    from apps.social import platform_oauth as oauth
    from apps.social.models import DevApp

    me = profile_of(request.user)
    row = DevApp.objects.filter(slug=slug).first()
    if not row or not (row.published or row.owner_id == me.id):
        messages.error(request, "Приложение не найдено.")
        return redirect("apps")
    if not (row.website_url or "").strip():
        messages.error(request, "У приложения не указан сайт.")
        return redirect("apps.canvas", slug=slug)
    oauth.ensure_app_credentials(row)
    if not pa.is_installed(me, slug):
        pa.install(me, slug)
    signed = oauth.make_signed_request(row, me)
    go = oauth.append_query(row.website_url, {
        "signed_request": signed,
        "user_id": me.id,
        "app": row.slug,
    })
    return redirect(go)


def _canvas_causes(request, me, app):
    if request.method == "POST":
        cause = (request.POST.get("cause") or "").strip()
        row = pa.join_cause(me, cause)
        if row and row[1]:
            title = next((c["title"] for c in pa.CAUSES if c["slug"] == cause), cause)
            Post.objects.create(
                social_user=me,
                body=f"присоединился(ась) к делу «{title}» через приложение Дела",
                kind="text",
                visibility="friends",
                created_at=now(), updated_at=now(),
            )
            bump_news()
            messages.success(request, "Вы присоединились к делу.")
        elif row:
            messages.info(request, "Вы уже в этом деле.")
        else:
            messages.error(request, "Не удалось присоединиться.")
        return redirect("apps.canvas", slug="causes")

    counts = pa.cause_join_counts()
    mine = pa.my_causes(me)
    causes = [
        {**c, "n": counts.get(c["slug"], 0), "joined": c["slug"] in mine}
        for c in pa.CAUSES
    ]
    return render(request, "social/apps/canvas_causes.html", {
        "me": me, "app": app, "causes": causes, "nav": "apps", "installed": True,
    })


def _canvas_quiz(request, me, app):
    result = None
    if request.method == "POST":
        share_title = (request.POST.get("share_title") or "").strip()[:80]
        share_blurb = (request.POST.get("share_blurb") or "").strip()[:200]
        if share_title:
            Post.objects.create(
                social_user=me,
                body=f"результат викторины: «{share_title}» — {share_blurb}",
                kind="text",
                visibility="friends",
                created_at=now(), updated_at=now(),
            )
            bump_news()
            messages.success(request, "Результат опубликован на стене.")
            result = {"key": "", "title": share_title, "blurb": share_blurb}
        else:
            answers = {q["id"]: request.POST.get(q["id"]) for q in pa.QUIZ_QUESTIONS}
            key, title, blurb = pa.score_quiz(answers)
            result = {"key": key, "title": title, "blurb": blurb}
    return render(request, "social/apps/canvas_quiz.html", {
        "me": me, "app": app, "questions": pa.QUIZ_QUESTIONS,
        "result": result, "nav": "apps", "installed": True,
    })


def _canvas_superpoke(request, me, app):
    friends = pa.friends_for_app(me)
    if request.method == "POST":
        try:
            fid = int(request.POST.get("friend_id") or 0)
        except (TypeError, ValueError):
            fid = 0
        poke_type = (request.POST.get("poke_type") or "poke").strip()
        labels = dict(pa.SUPERPOKE_TYPES)
        if fid not in friend_ids(me) or poke_type not in labels:
            messages.error(request, "Выберите друга и тип подмигивания.")
            return redirect("apps.canvas", slug="superpoke")
        peer = get_object_or_404(SocialProfile, pk=fid)
        if poke_type == "poke":
            out = notify.poke(me, peer)
            if out == "pending":
                messages.info(request, "Подмигивание уже ожидает прочтения.")
                return redirect("apps.canvas", slug="superpoke")
            if out != "ok":
                messages.error(request, "Не удалось подмигнуть.")
                return redirect("apps.canvas", slug="superpoke")
        else:
            notify.push(
                peer.id,
                title="Супер-подмигивание",
                body=f"{me.name}: {labels[poke_type]}",
                type="poke",
                url=f"/profile/{me.id}",
            )
        messages.success(request, f"Отправлено: {labels[poke_type]} → {peer.name}")
        return redirect("apps.canvas", slug="superpoke")
    return render(request, "social/apps/canvas_superpoke.html", {
        "me": me, "app": app, "friends": friends,
        "poke_types": pa.SUPERPOKE_TYPES, "nav": "apps", "installed": True,
    })


def _canvas_compare(request, me, app):
    friends = pa.friends_for_app(me)
    rows = None
    left = right = None
    if request.method == "POST":
        try:
            a_id = int(request.POST.get("a") or 0)
            b_id = int(request.POST.get("b") or 0)
        except (TypeError, ValueError):
            a_id = b_id = 0
        fids = friend_ids(me)
        if a_id in fids and b_id in fids and a_id != b_id:
            left = SocialProfile.objects.filter(pk=a_id).first()
            right = SocialProfile.objects.filter(pk=b_id).first()
            if left and right:
                rows = pa.compare_profiles(left, right)
        else:
            messages.error(request, "Выберите двух разных друзей.")
    return render(request, "social/apps/canvas_compare.html", {
        "me": me, "app": app, "friends": friends,
        "rows": rows, "left": left, "right": right,
        "nav": "apps", "installed": True,
    })


def _canvas_truth(request, me, app):
    friends = pa.friends_for_app(me)
    if request.method == "POST":
        action = (request.POST.get("action") or "ask").strip()
        if action == "answer":
            try:
                ask_id = int(request.POST.get("ask_id") or 0)
            except (TypeError, ValueError):
                ask_id = 0
            ask = AppTruthAsk.objects.filter(pk=ask_id, to_user=me).first()
            answer = (request.POST.get("answer") or "").strip()[:500]
            if ask and answer:
                ask.answer = answer
                ask.answered_at = now()
                ask.save(update_fields=["answer", "answered_at"])
                notify.push(
                    ask.from_user_id,
                    title=f"{me.name} ответил(а) на вопрос",
                    body=answer[:120],
                    type="message",
                    url=reverse("apps.canvas", args=["truth"]),
                )
                messages.success(request, "Ответ сохранён.")
            return redirect("apps.canvas", slug="truth")

        try:
            fid = int(request.POST.get("friend_id") or 0)
        except (TypeError, ValueError):
            fid = 0
        question = (request.POST.get("question") or "").strip()[:300]
        if fid not in friend_ids(me) or not question:
            messages.error(request, "Укажите друга и вопрос.")
            return redirect("apps.canvas", slug="truth")
        peer = get_object_or_404(SocialProfile, pk=fid)
        AppTruthAsk.objects.create(
            from_user=me, to_user=peer, question=question, created_at=now(),
        )
        notify.push(
            peer.id,
            title=f"{me.name} задал(а) вопрос",
            body=question[:120],
            type="message",
            url=reverse("apps.canvas", args=["truth"]),
        )
        messages.success(request, f"Вопрос отправлен {peer.name}.")
        return redirect("apps.canvas", slug="truth")

    incoming = list(
        AppTruthAsk.objects.filter(to_user=me)
        .select_related("from_user")
        .order_by("-id")[:20]
    )
    outgoing = list(
        AppTruthAsk.objects.filter(from_user=me)
        .select_related("to_user")
        .order_by("-id")[:20]
    )
    return render(request, "social/apps/canvas_truth.html", {
        "me": me, "app": app, "friends": friends,
        "incoming": incoming, "outgoing": outgoing,
        "nav": "apps", "installed": True,
    })


def _canvas_calculator(request, me, app):
    result = None
    a = b = "0"
    op = "+"
    if request.method == "POST":
        a = (request.POST.get("a") or "0")[:40]
        b = (request.POST.get("b") or "0")[:40]
        op = (request.POST.get("op") or "+")[:1]
        result = pa.calc_eval(a, op, b)
    return render(request, "social/apps/canvas_calculator.html", {
        "me": me, "app": app, "a": a, "b": b, "op": op, "result": result,
        "nav": "apps", "installed": True,
    })


def _canvas_weather(request, me, app):
    city = (me.city or "").strip() or "Москва"
    forecast = None
    if request.method == "POST":
        city = (request.POST.get("city") or city)[:80]
        forecast = pa.weather_for_city(city)
    elif request.method == "GET" and request.GET.get("city"):
        city = request.GET.get("city")[:80]
        forecast = pa.weather_for_city(city)
    return render(request, "social/apps/canvas_weather.html", {
        "me": me, "app": app, "city": city, "forecast": forecast,
        "nav": "apps", "installed": True,
    })


def _canvas_horoscope(request, me, app):
    sign = (request.POST.get("sign") or request.GET.get("sign") or "aries").strip().lower()
    reading = pa.horoscope_for(sign) if request.method == "POST" or request.GET.get("sign") else None
    return render(request, "social/apps/canvas_horoscope.html", {
        "me": me, "app": app, "signs": pa.ZODIAC, "sign": sign,
        "reading": reading, "nav": "apps", "installed": True,
    })


def _canvas_dating(request, me, app):
    matches = pa.dating_matches(me)
    return render(request, "social/apps/canvas_dating.html", {
        "me": me, "app": app, "matches": matches,
        "nav": "apps", "installed": True,
    })


def _canvas_farm(request, me, app):
    crop = None
    planted = harvested = None
    if request.method == "POST":
        action = (request.POST.get("action") or "plant").strip()
        slug = (request.POST.get("crop") or "wheat").strip()
        crops = {c[0]: c for c in pa.FARM_CROPS}
        crop = crops.get(slug) or pa.FARM_CROPS[0]
        if action == "harvest":
            harvested = crop[1]
            Post.objects.create(
                social_user=me,
                body=f"собрал(а) урожай «{harvested}» в приложении Ферма",
                kind="text", visibility="friends",
                created_at=now(), updated_at=now(),
            )
            bump_news()
            messages.success(request, f"Урожай «{harvested}» собран.")
            return redirect("apps.canvas", slug="farm")
        planted = crop[1]
        messages.info(request, f"Посажено: {planted}. Загляните позже за сбором.")
    return render(request, "social/apps/canvas_farm.html", {
        "me": me, "app": app, "crops": pa.FARM_CROPS,
        "planted": planted, "nav": "apps", "installed": True,
    })


def _canvas_billiards(request, me, app):
    score = None
    if request.method == "POST":
        import random
        score = random.randint(1, 15)
        messages.success(request, f"Удар! Забито шаров: {score}.")
    return render(request, "social/apps/canvas_billiards.html", {
        "me": me, "app": app, "score": score, "nav": "apps", "installed": True,
    })


def _canvas_chess(request, me, app):
    friends = pa.friends_for_app(me)
    move = None
    peer = None
    if request.method == "POST":
        try:
            fid = int(request.POST.get("friend_id") or 0)
        except (TypeError, ValueError):
            fid = 0
        piece = (request.POST.get("piece") or "пешка").strip()[:20]
        square = (request.POST.get("square") or "e4").strip()[:4]
        if fid in friend_ids(me):
            peer = SocialProfile.objects.filter(pk=fid).first()
            move = f"{piece} → {square}"
            if peer:
                notify.push(
                    peer.id,
                    title="Шахматы",
                    body=f"{me.name}: {move}",
                    type="message",
                    url=reverse("apps.canvas", args=["chess"]),
                )
                messages.success(request, f"Ход отправлен {peer.name}: {move}")
        else:
            messages.error(request, "Выберите друга.")
    return render(request, "social/apps/canvas_chess.html", {
        "me": me, "app": app, "friends": friends, "move": move, "peer": peer,
        "nav": "apps", "installed": True,
    })


def _canvas_tetris(request, me, app):
    score = None
    if request.method == "POST":
        try:
            lines = int(request.POST.get("lines") or 0)
        except (TypeError, ValueError):
            lines = 0
        lines = max(0, min(lines, 40))
        score = lines * 100
        messages.success(request, f"Счёт: {score} ({lines} линий).")
    return render(request, "social/apps/canvas_tetris.html", {
        "me": me, "app": app, "score": score, "nav": "apps", "installed": True,
    })


def _canvas_poker(request, me, app):
    cards = None
    label = None
    if request.method == "POST":
        cards = pa.poker_deal()
        label = pa.poker_rank_label(cards)
    return render(request, "social/apps/canvas_poker.html", {
        "me": me, "app": app, "cards": cards, "label": label,
        "nav": "apps", "installed": True,
    })
