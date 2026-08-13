from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("djadmin/", admin.site.urls),
    path("", include("apps.accounts.urls")),
    path("", include("apps.social.urls")),
]

handler404 = "apps.social.views_meta.page_not_found"
handler500 = "apps.social.views_meta.server_error"
