"""FB 2009–2010 classic chrome: Places + Questions + Polls + Reviews."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.social import era2010 as e10
from apps.social.forms import (
    CheckinForm, PlaceForm, PlaceReviewForm,
    PollForm, QuestionAnswerForm, QuestionForm,
)
from apps.social.models import ClassicPoll, ClassicPollOption, Place, Question, QuestionAnswer
from apps.social.services import profile_of


@login_required
@require_http_methods(["GET", "POST"])
def places_home(request):
    me = profile_of(request.user)
    form = PlaceForm(request.POST or None, request.FILES or None)
    if request.method == "POST":
        if form.is_valid():
            place = e10.place_create(
                me,
                name=form.cleaned_data["name"],
                city=form.cleaned_data.get("city") or "",
                address=form.cleaned_data.get("address") or "",
                photo=form.cleaned_data.get("photo"),
                lat=form.cleaned_data.get("lat"),
                lon=form.cleaned_data.get("lon"),
            )
            if place:
                messages.success(request, "Место добавлено.")
                return redirect(place)
        messages.error(request, "Укажите название места.")
    from apps.social import osm
    q = (request.GET.get("q") or "").strip()
    city = (request.GET.get("city") or "").strip()
    near_me = request.GET.get("near") == "1"
    near = osm.ensure_profile_geo(me) if near_me else None
    places = e10.places_list(q=q, city=city, near=me if near else None)
    return render(request, "social/places.html", {
        "me": me, "form": form, "places": places,
        "q": q, "city": city, "near": near_me, "nav": "places",
    })


@login_required
@require_http_methods(["GET", "POST"])
def place_show(request, pk):
    me = profile_of(request.user)
    place = get_object_or_404(Place, pk=pk)
    checkin_form = CheckinForm()
    review_form = PlaceReviewForm()
    mine = e10.my_place_review(me, place)
    if mine:
        review_form = PlaceReviewForm(initial={"stars": mine.stars, "body": mine.body})

    if request.method == "POST":
        action = (request.POST.get("action") or "checkin").strip()
        if action == "review":
            review_form = PlaceReviewForm(request.POST)
            if review_form.is_valid():
                e10.place_review_upsert(
                    me, place,
                    stars=review_form.cleaned_data["stars"],
                    body=review_form.cleaned_data.get("body") or "",
                )
                messages.success(request, "Отзыв сохранён.")
                return redirect(place)
            messages.error(request, "Укажите оценку.")
        else:
            checkin_form = CheckinForm(request.POST, request.FILES)
            if checkin_form.is_valid():
                e10.place_checkin(
                    me, place,
                    checkin_form.cleaned_data.get("message") or "",
                    photo=checkin_form.cleaned_data.get("photo"),
                )
                messages.success(request, "Вы отметились здесь.")
                return redirect(place)
            messages.error(request, "Не удалось отметиться.")

    from apps.social import osm
    map_ctx = None
    if osm.has_coords(place):
        map_ctx = osm.map_context(place.lat, place.lon, zoom=16, title=place.name)
    elif place.city or place.address:
        hit = osm.geocode_parts(place.name, place.address, place.city)
        if hit:
            place.lat, place.lon = hit.lat, hit.lon
            place.osm_type, place.osm_id = hit.osm_type, hit.osm_id
            try:
                place.save(update_fields=["lat", "lon", "osm_type", "osm_id"])
            except Exception:
                pass
            map_ctx = osm.map_context(place.lat, place.lon, zoom=16, title=place.name)
    return render(request, "social/place.html", {
        "me": me, "place": place,
        "form": checkin_form, "review_form": review_form, "my_review": mine,
        "checkins": e10.place_checkins(place),
        "reviews": e10.place_reviews(place),
        "map": map_ctx,
        "can_manage": e10.can_manage_place(me, place),
        "nav": "places",
    })


@login_required
@require_http_methods(["GET", "POST"])
def place_edit(request, pk):
    me = profile_of(request.user)
    place = get_object_or_404(Place, pk=pk)
    if not e10.can_manage_place(me, place):
        messages.error(request, "Редактировать может только автор места.")
        return redirect(place)
    initial = {
        "name": place.name, "city": place.city or "", "address": place.address or "",
        "lat": place.lat, "lon": place.lon,
    }
    form = PlaceForm(request.POST or None, request.FILES or None, initial=None if request.method == "POST" else initial)
    if request.method == "POST" and form.is_valid():
        if e10.place_update(
            me, place,
            name=form.cleaned_data["name"],
            city=form.cleaned_data.get("city") or "",
            address=form.cleaned_data.get("address") or "",
            photo=form.cleaned_data.get("photo"),
            lat=form.cleaned_data.get("lat"),
            lon=form.cleaned_data.get("lon"),
        ):
            messages.success(request, "Место сохранено.")
            return redirect(place)
        messages.error(request, "Не удалось сохранить.")
    return render(request, "social/place_edit.html", {
        "me": me, "place": place, "form": form, "nav": "places",
    })


@login_required
@require_POST
def place_delete(request, pk):
    me = profile_of(request.user)
    place = get_object_or_404(Place, pk=pk)
    name = place.name
    if e10.place_delete(me, place):
        messages.info(request, f"Место «{name}» удалено.")
        return redirect("places")
    messages.error(request, "Удалить может только автор места.")
    return redirect(place)


@login_required
@require_http_methods(["GET", "POST"])
def questions_home(request):
    me = profile_of(request.user)
    form = QuestionForm(request.POST or None, request.FILES or None)
    mine = request.GET.get("mine") == "1"
    if request.method == "POST":
        if form.is_valid():
            q = e10.question_create(
                me, form.cleaned_data["body"], photo=form.cleaned_data.get("photo"),
            )
            if q:
                messages.success(request, "Вопрос задан.")
                return redirect(q)
        messages.error(request, "Напишите вопрос.")
    return render(request, "social/questions.html", {
        "me": me, "form": form, "mine": mine,
        "items": e10.questions_feed(me, mine=mine), "nav": "questions",
    })


@login_required
@require_http_methods(["GET", "POST"])
def question_show(request, pk):
    me = profile_of(request.user)
    question = get_object_or_404(
        Question.objects.select_related("social_user"), pk=pk,
    )
    form = QuestionAnswerForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            ans = e10.question_answer(me, question, form.cleaned_data["body"])
            if ans:
                messages.success(request, "Ответ добавлен.")
                return redirect(question)
        messages.error(request, "Напишите ответ.")
    is_own = bool(me and me.id == question.social_user_id)
    return render(request, "social/question.html", {
        "me": me, "question": question, "form": form,
        "answers": e10.question_answers(question, viewer=me),
        "is_own": is_own, "nav": "questions",
    })


@login_required
@require_http_methods(["GET", "POST"])
def question_edit(request, pk):
    me = profile_of(request.user)
    question = get_object_or_404(Question, pk=pk, social_user=me)
    form = QuestionForm(
        request.POST or None, request.FILES or None,
        initial=None if request.method == "POST" else {"body": question.body},
    )
    if request.method == "POST" and form.is_valid():
        if e10.question_update(
            me, question,
            body=form.cleaned_data["body"],
            photo=form.cleaned_data.get("photo"),
        ):
            messages.success(request, "Вопрос сохранён.")
            return redirect(question)
        messages.error(request, "Напишите вопрос.")
    return render(request, "social/question_edit.html", {
        "me": me, "question": question, "form": form, "nav": "questions",
    })


@login_required
@require_POST
def question_delete(request, pk):
    me = profile_of(request.user)
    question = get_object_or_404(Question, pk=pk)
    if e10.question_delete(me, question):
        messages.info(request, "Вопрос удалён.")
        return redirect("questions")
    messages.error(request, "Удалить можно только свой вопрос.")
    return redirect(question)


@login_required
@require_POST
def question_vote(request, pk, answer_id):
    me = profile_of(request.user)
    question = get_object_or_404(Question, pk=pk)
    answer = get_object_or_404(QuestionAnswer, pk=answer_id, question=question)
    out = e10.toggle_vote(me, answer)
    if out == "voted":
        messages.success(request, "Голос учтён.")
    elif out == "unvoted":
        messages.info(request, "Голос снят.")
    return redirect(request.POST.get("next") or question)


@login_required
@require_http_methods(["GET", "POST"])
def polls_home(request):
    me = profile_of(request.user)
    form = PollForm(request.POST or None)
    mine = request.GET.get("mine") == "1"
    if request.method == "POST":
        if form.is_valid():
            poll = e10.poll_create(
                me, form.cleaned_data["question"], form.cleaned_data["options"],
            )
            if poll:
                messages.success(request, "Опрос создан.")
                return redirect(poll)
        messages.error(request, "Нужны вопрос и минимум два варианта.")
    return render(request, "social/polls.html", {
        "me": me, "form": form, "mine": mine,
        "items": e10.polls_feed(me, mine=mine), "nav": "polls",
    })


@login_required
@require_http_methods(["GET", "HEAD"])
def poll_show(request, pk):
    me = profile_of(request.user)
    poll = get_object_or_404(
        ClassicPoll.objects.select_related("social_user"), pk=pk,
    )
    options, my_option, total = e10.poll_options(poll, viewer=me)
    is_own = bool(me and me.id == poll.social_user_id)
    return render(request, "social/poll.html", {
        "me": me, "poll": poll, "options": options,
        "my_option": my_option, "total": total, "is_own": is_own, "nav": "polls",
    })


@login_required
@require_http_methods(["GET", "POST"])
def poll_edit(request, pk):
    me = profile_of(request.user)
    poll = get_object_or_404(ClassicPoll, pk=pk, social_user=me)
    if request.method == "POST":
        if e10.poll_update(me, poll, question=request.POST.get("question") or ""):
            messages.success(request, "Опрос сохранён.")
            return redirect(poll)
        messages.error(request, "Укажите текст вопроса.")
    return render(request, "social/poll_edit.html", {
        "me": me, "poll": poll, "nav": "polls",
    })


@login_required
@require_POST
def poll_delete(request, pk):
    me = profile_of(request.user)
    poll = get_object_or_404(ClassicPoll, pk=pk)
    if e10.poll_delete(me, poll):
        messages.info(request, "Опрос удалён.")
        return redirect("polls")
    messages.error(request, "Удалить можно только свой опрос.")
    return redirect(poll)


@login_required
@require_POST
def poll_vote(request, pk, option_id):
    me = profile_of(request.user)
    poll = get_object_or_404(ClassicPoll, pk=pk)
    option = get_object_or_404(ClassicPollOption, pk=option_id, poll=poll)
    out = e10.poll_vote(me, poll, option)
    if out == "voted":
        messages.success(request, "Голос учтён.")
    elif out == "changed":
        messages.success(request, "Голос изменён.")
    elif out == "unvoted":
        messages.info(request, "Голос снят.")
    return redirect(request.POST.get("next") or poll)
