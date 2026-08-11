from django.contrib.auth.decorators import login_not_required
from django.contrib.sitemaps import Sitemap
from django.contrib.sitemaps.views import sitemap as django_sitemap
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.shortcuts import render

from apps.social.models import SocialProfile


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
def vapid_config(_request):
    return JsonResponse({"publicKey": getattr(settings, "VAPID_PUBLIC_KEY", "") or ""})


@login_not_required
def page_not_found(request, exception):
    return render(request, "errors/404.html", status=404)


@login_not_required
def server_error(request):
    return render(request, "errors/500.html", status=500)


@login_not_required
def csrf_failure(request, reason=""):
    return render(request, "errors/csrf.html", {"reason": reason}, status=403)
