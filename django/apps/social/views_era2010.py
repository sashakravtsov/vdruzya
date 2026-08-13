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
            )
            if place:
                messages.success(request, "Место добавлено.")
                return redirect(place)
        messages.error(request, "Укажите название места.")
    q = (request.GET.get("q") or "").strip()
    city = (request.GET.get("city") or "").strip()
    return render(request, "social/places.html", {
        "me": me, "form": form, "places": e10.places_list(q=q, city=city),
        "q": q, "city": city, "nav": "places",
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

    return render(request, "social/place.html", {
        "me": me, "place": place,
        "form": checkin_form, "review_form": review_form, "my_review": mine,
        "checkins": e10.place_checkins(place),
        "reviews": e10.place_reviews(place),
        "nav": "places",
    })


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
    return render(request, "social/question.html", {
        "me": me, "question": question, "form": form,
        "answers": e10.question_answers(question, viewer=me), "nav": "questions",
    })


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
    return render(request, "social/poll.html", {
        "me": me, "poll": poll, "options": options,
        "my_option": my_option, "total": total, "nav": "polls",
    })


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
