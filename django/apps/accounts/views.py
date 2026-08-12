from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_not_required, login_required
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.models import User
from apps.social.forms import PasswordForm
from apps.social.models import SocialProfile
from apps.social.services import now, profile_of


def _login_key(request):
    return f"loginfail:{request.META.get('REMOTE_ADDR', '?')}"


@login_not_required
@sensitive_post_parameters("password")
@require_http_methods(["GET", "HEAD", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("feed")
    error = None
    if request.method == "POST":
        key = _login_key(request)
        fails = cache.get(key, 0)
        if fails >= 25:
            error = "Слишком много попыток. Подождите пару минут."
        else:
            user = authenticate(
                request,
                email=request.POST.get("email", "").strip(),
                password=request.POST.get("password", ""),
            )
            if user:
                cache.delete(key)
                login(request, user)
                return redirect(request.GET.get("next") or "feed")
            cache.set(key, fails + 1, 300)
            error = "Неверный E-mail или пароль."
    return render(request, "accounts/login.html", {"error": error})


@login_not_required
@require_POST
def logout_view(request):
    logout(request)
    return redirect("home")


def _unique_slug(name: str) -> str:
    from apps.social.slugs import unique_slug
    return unique_slug(SocialProfile, name, fallback="user")


@login_not_required
@sensitive_post_parameters("password")
@require_http_methods(["GET", "HEAD", "POST"])
def register_view(request):
    if request.user.is_authenticated:
        return redirect("feed")

    from apps.social import friendship as fr

    # Persist invite from URL into cookie for the form flow
    url_invite = (request.GET.get("invite") or "").strip()
    if url_invite and fr.find_inviter(url_invite):
        pass  # set cookie on response below

    invite_code = fr.invite_code_from_request(request)
    inviter = fr.find_inviter(invite_code) if invite_code else None
    need_invite = fr.registration_requires_invite()
    error = None

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        email = (request.POST.get("email") or "").strip().lower()
        password = request.POST.get("password") or ""
        invite_code = (request.POST.get("invite") or invite_code or "").strip()
        inviter = fr.find_inviter(invite_code) if invite_code else None

        if need_invite and not inviter:
            error = "Регистрация только по приглашению. Укажите действительный код или откройте ссылку друга."
        elif not name or not email:
            error = "Укажите имя и E-mail."
        elif not request.POST.get("terms"):
            error = "Нужно принять правила использования."
        elif User.objects.filter(email__iexact=email).exists():
            error = "Этот E-mail уже зарегистрирован."
        else:
            try:
                validate_password(password)
            except ValidationError as exc:
                error = " ".join(exc.messages)
            else:
                stamp = now()
                with transaction.atomic():
                    user = User.objects.create_user(
                        email=email, password=password, name=name, created_at=stamp, updated_at=stamp
                    )
                    SocialProfile.objects.create(
                        user=user, name=name, slug=_unique_slug(name), city="",
                        avatar_color="#3B5998", created_at=stamp, updated_at=stamp,
                    )
                login(request, user, backend="apps.accounts.auth.BcryptBackend")
                me = profile_of(user)
                linked = fr.apply_invite(request, me, code=invite_code)
                resp = redirect("feed")
                resp.delete_cookie("vdruzya_invite")
                if linked:
                    messages.info(request, f"Заявка в друзья отправлена {linked.name}.")
                return resp

    ctx = {
        "error": error,
        "invite": invite_code,
        "inviter": inviter,
        "need_invite": need_invite,
        "can_register": (not need_invite) or bool(inviter) or request.method == "POST",
    }
    resp = render(request, "accounts/register.html", ctx)
    if url_invite and fr.find_inviter(url_invite):
        resp.set_cookie("vdruzya_invite", url_invite, max_age=60 * 60 * 24 * 14)
    return resp


@login_required
@sensitive_post_parameters("old", "new1", "new2")
@require_http_methods(["GET", "HEAD", "POST"])
def account(request):
    from apps.social import friendship as fr
    me = profile_of(request.user)
    form = PasswordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if not request.user.check_password(form.cleaned_data["old"]):
            form.add_error("old", "Неверный текущий пароль.")
        else:
            try:
                validate_password(form.cleaned_data["new1"], user=request.user)
            except ValidationError as exc:
                form.add_error("new1", exc)
            else:
                request.user.set_password(form.cleaned_data["new1"])
                request.user.updated_at = timezone.now()
                request.user.save(update_fields=["password", "updated_at"])
                update_session_auth_hash(request, request.user)
                messages.success(request, "Пароль обновлён.")
                return redirect("account")
    return render(
        request, "accounts/account.html",
        {
            "form": form, "me": me, "user_obj": request.user, "nav": "account",
            "invite_url": fr.invite_url(me, request) if me else "",
            "invite_code": fr.ensure_invite_code(me) if me else "",
        },
    )
