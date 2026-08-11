from django.conf import settings
from django.contrib.auth.decorators import login_not_required
from django.contrib.sitemaps import Sitemap
from django.contrib.sitemaps.views import sitemap as django_sitemap
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from apps.social.models import SocialProfile

_LEGAL = (
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

# Full-page HTML includes auth chrome — never public-cache (breaks logged-in nav/sidebar).
_PAGES = {
    "terms": ("Пользовательское соглашение", "legal/terms.html"),
    "privacy": ("Конфиденциальность", "legal/privacy.html"),
    "about": ("О сайте", "legal/about.html"),
    "contacts": ("Контакты", "legal/contacts.html"),
    "security": ("Помощь", "legal/security.html"),
}


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
        return ["/", "/about", "/terms", "/privacy", "/contacts", "/security"]

    def location(self, item):
        return item


SITEMAPS = {"static": StaticSitemap, "profiles": ProfileSitemap}


def _legal(request, key):
    title, template = _PAGES[key]
    ctx = {"title": title, "legal": {k: getattr(settings, env, "") or "" for k, env in _LEGAL}}
    return render(request, template, ctx)


def _page(key):
    @login_not_required
    @never_cache
    def view(request):
        return _legal(request, key)
    view.__name__ = view.__qualname__ = key
    return view


terms = _page("terms")
privacy = _page("privacy")
about = _page("about")
contacts = _page("contacts")
security = _page("security")


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
