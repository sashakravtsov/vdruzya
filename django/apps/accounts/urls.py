from django.conf import settings
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_not_required
from django.urls import path, reverse_lazy
from . import views
from .forms import PasswordResetForm, StyledSetPasswordForm

_reset = dict(
    template_name="accounts/password_reset.html",
    email_template_name="accounts/password_reset_email.txt",
    subject_template_name="accounts/password_reset_subject.txt",
    success_url=reverse_lazy("password_reset_done"),
    form_class=PasswordResetForm,
    from_email=settings.DEFAULT_FROM_EMAIL,
    extra_email_context={"site_name": "ВДрузья"},
)

urlpatterns = [
    path("login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),
    path("register", views.register_view, name="register"),
    path("account", views.account, name="account"),
    path("password-reset", login_not_required(auth_views.PasswordResetView.as_view(**_reset)), name="password_reset"),
    path(
        "password-reset/done",
        login_not_required(auth_views.PasswordResetDoneView.as_view(template_name="accounts/password_reset_done.html")),
        name="password_reset_done",
    ),
    path(
        "password-reset/<uidb64>/<token>",
        login_not_required(
            auth_views.PasswordResetConfirmView.as_view(
                template_name="accounts/password_reset_confirm.html",
                form_class=StyledSetPasswordForm,
                success_url=reverse_lazy("password_reset_complete"),
            )
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete",
        login_not_required(
            auth_views.PasswordResetCompleteView.as_view(template_name="accounts/password_reset_complete.html")
        ),
        name="password_reset_complete",
    ),
]
