from django.conf import settings
from django.contrib.auth.decorators import login_not_required
from django.contrib.sitemaps import Sitemap
from django.contrib.sitemaps.views import sitemap as django_sitemap
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import cache_page

from apps.social.models import SocialProfile

_LEGAL_KEYS = (
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


class ProfileSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6
    limit = 500

    def items(self):
        return SocialProfile.objects.order_by("-id").only("id", "updated_at")[:500]

    def location(self, obj):
        return f"/profile/{obj.pk}"

    def lastmod(self, obj):
        return obj.updated_at


class StaticSitemap(Sitemap):
    priority = 0.5
    changefreq = "monthly"

    def items(self):
        return ["/", "/about", "/terms", "/privacy", "/contacts", "/advertisers", "/security"]

    def location(self, item):
        return item


SITEMAPS = {"static": StaticSitemap, "profiles": ProfileSitemap}


def _legal_ctx(title):
    return {"title": title, "legal": {k: getattr(settings, env, "") or "" for k, env in _LEGAL_KEYS}}


def _legal_page(request, title, template):
    return render(request, template, _legal_ctx(title))


@login_not_required
def up(_request):
    return HttpResponse("ok", content_type="text/plain")


@login_not_required
def robots(_request):
    return HttpResponse(
        "User-agent: *\nAllow: /\nSitemap: https://vdruzya.ru/sitemap.xml\n",
        content_type="text/plain",
    )


@login_not_required
def sitemap(request):
    return django_sitemap(request, sitemaps=SITEMAPS)


@login_not_required
def page_not_found(request, exception):
    return render(request, "errors/404.html", status=404)


@login_not_required
def server_error(request):
    return render(request, "errors/500.html", status=500)


@login_not_required
def csrf_failure(request, reason=""):
    return render(request, "errors/csrf.html", {"reason": reason}, status=403)


@login_not_required
@cache_page(600)
def terms(request):
    return _legal_page(request, "Пользовательское соглашение", "legal/terms.html")


@login_not_required
@cache_page(600)
def privacy(request):
    return _legal_page(request, "Конфиденциальность", "legal/privacy.html")


@login_not_required
@cache_page(600)
def about(request):
    return _legal_page(request, "О сайте", "legal/about.html")


@login_not_required
@cache_page(600)
def contacts(request):
    return _legal_page(request, "Контакты", "legal/contacts.html")


@login_not_required
@cache_page(600)
def payment(request):
    return _legal_page(request, "Оплата и возврат", "legal/payment.html")


@login_not_required
@cache_page(600)
def security(request):
    return _legal_page(request, "Помощь", "legal/security.html")


@login_not_required
@cache_page(600)
def advertisers(request):
    return _legal_page(request, "Рекламодателям", "legal/advertisers.html")


@login_not_required
def promo(_request):
    return redirect("https://promo.vdruzya.ru", permanent=False)


@login_not_required
def landing(_request):
    return redirect("home", permanent=False)
