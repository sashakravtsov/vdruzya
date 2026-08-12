"""FB 2009–2010 classic chrome: Places + Questions."""
from django.contrib import messages
from django.contrib.auth.decorators import login_not_required, login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.social import era2010 as e10
from apps.social.forms import CheckinForm, PlaceForm, QuestionAnswerForm, QuestionForm
from apps.social.models import Place, Question, QuestionAnswer
from apps.social.services import profile_of


@login_required
@require_http_methods(["GET", "POST"])
def places_home(request):
    me = profile_of(request.user)
    form = PlaceForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            place = e10.place_create(
                me,
                name=form.cleaned_data["name"],
                city=form.cleaned_data.get("city") or "",
                address=form.cleaned_data.get("address") or "",
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
    form = CheckinForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            e10.place_checkin(me, place, form.cleaned_data.get("message") or "")
            messages.success(request, "Вы отметились здесь.")
            return redirect(place)
        messages.error(request, "Не удалось отметиться.")
    return render(request, "social/place.html", {
        "me": me, "place": place, "form": form,
        "checkins": e10.place_checkins(place), "nav": "places",
    })


@login_required
@require_http_methods(["GET", "POST"])
def questions_home(request):
    me = profile_of(request.user)
    form = QuestionForm(request.POST or None)
    mine = request.GET.get("mine") == "1"
    if request.method == "POST":
        if form.is_valid():
            q = e10.question_create(me, form.cleaned_data["body"])
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
