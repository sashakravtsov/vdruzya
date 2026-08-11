from django.contrib.auth.decorators import login_not_required
from django.conf import settings
from django.shortcuts import redirect, render
from django.views.decorators.cache import cache_page

_KEYS = (
    ("operator_name", "LEGAL_OPERATOR_NAME"),
    ("operator_short", "LEGAL_OPERATOR_SHORT"),
    ("inn", "LEGAL_INN"),
    ("kpp", "LEGAL_KPP"),
    ("ogrn", "LEGAL_OGRN"),
    ("address", "LEGAL_ADDRESS"),
    ("email", "LEGAL_SUPPORT_EMAIL"),
    ("phone", "LEGAL_SUPPORT_PHONE"),
    ("bank_name", "LEGAL_BANK_NAME"),
    ("bank_account", "LEGAL_BANK_ACCOUNT"),
    ("bank_bik", "LEGAL_BANK_BIK"),
    ("bank_corr", "LEGAL_BANK_CORR"),
)


def legal_ctx(title):
    return {"title": title, "legal": {k: getattr(settings, env, "") or "" for k, env in _KEYS}}


def page(request, title, template):
    return render(request, template, legal_ctx(title))


@login_not_required
@cache_page(600)
def terms(request):
    return page(request, "Пользовательское соглашение", "legal/terms.html")


@login_not_required
@cache_page(600)
def privacy(request):
    return page(request, "Конфиденциальность", "legal/privacy.html")


@login_not_required
@cache_page(600)
def about(request):
    return page(request, "О сайте", "legal/about.html")


@login_not_required
@cache_page(600)
def contacts(request):
    return page(request, "Контакты", "legal/contacts.html")


@login_not_required
@cache_page(600)
def payment(request):
    return page(request, "Оплата и возврат", "legal/payment.html")


@login_not_required
@cache_page(600)
def security(request):
    return page(request, "Помощь", "legal/security.html")


@login_not_required
@cache_page(600)
def advertisers(request):
    return page(request, "Рекламодателям", "legal/advertisers.html")


@login_not_required
def promo(_request):
    return redirect("https://promo.vdruzya.ru", permanent=False)


@login_not_required
def landing(_request):
    return redirect("home", permanent=False)
