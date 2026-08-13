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


def _require_app(slug):
    return pa.app_by_slug(slug)


@login_required
@require_POST
def app_install(request, slug):
    me = profile_of(request.user)
    app = _require_app(slug)
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
    app = _require_app(slug)
    if app and pa.uninstall(me, slug):
        messages.info(request, f"Приложение «{app['name']}» удалено из ваших.")
    return redirect(request.POST.get("next") or "apps")


@login_required
@require_http_methods(["GET", "POST"])
def app_canvas(request, slug):
    me = profile_of(request.user)
    app = _require_app(slug)
    if not app:
        messages.error(request, "Приложение не найдено.")
        return redirect("apps")
    if not pa.is_installed(me, slug):
        pa.install(me, slug)

    handlers = {
        "causes": _canvas_causes,
        "quiz": _canvas_quiz,
        "superpoke": _canvas_superpoke,
        "compare": _canvas_compare,
        "truth": _canvas_truth,
    }
    handler = handlers.get(slug)
    if not handler:
        return redirect("apps.show", slug=slug)
    return handler(request, me, app)


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
