"""Bcrypt verify/hash ($2b$; also accepts $2y$ hashes already in DB)."""
from __future__ import annotations

import bcrypt
from django.contrib.auth.backends import ModelBackend


def check_password(password: str, encoded: str) -> bool:
    if not password or not encoded:
        return False
    raw = encoded.encode("utf-8")
    if raw.startswith(b"$2y$"):
        raw = b"$2b$" + raw[4:]
    try:
        return bcrypt.checkpw(password.encode("utf-8"), raw)
    except (ValueError, TypeError):
        return False


def make_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


class BcryptBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        email = kwargs.get("email") or username
        if not email or password is None:
            return None
        User = self.user_model
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return None
        if check_password(password, user.password) and self.user_can_authenticate(user):
            return user
        return None

    @property
    def user_model(self):
        from django.contrib.auth import get_user_model
        return get_user_model()
