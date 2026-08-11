"""Short vanity slugs for groups & profiles — 5..32 chars, unique."""
from __future__ import annotations

import re

from django.core.exceptions import ValidationError
from django.utils.text import slugify

_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{3,30}[a-z0-9]$")
_RESERVED = frozenset({
    "edit", "members", "join", "leave", "invite", "events", "message", "posts",
    "comments", "status", "avatar", "education", "experience", "block",
    "new", "create", "admin", "me", "mine",
})


def clean_short_slug(value: str) -> str:
    s = (value or "").strip().lower()
    if not s:
        raise ValidationError("Укажите короткое имя.")
    if len(s) < 5 or len(s) > 32:
        raise ValidationError("От 5 до 32 символов.")
    if not _RE.match(s):
        raise ValidationError("Латиница, цифры, - и _; начинается и заканчивается буквой/цифрой.")
    if s in _RESERVED:
        raise ValidationError("Это имя занято системой.")
    if s.isdigit():
        raise ValidationError("Короткое имя не может быть только цифрами.")
    return s


def unique_slug(model, base: str, *, exclude_pk=None, fallback="group") -> str:
    raw = slugify(base, allow_unicode=False) or fallback
    raw = re.sub(r"[^a-z0-9_-]", "", raw.lower())[:32] or fallback
    if len(raw) < 5:
        raw = (raw + fallback)[:5]
    if raw.isdigit():
        raw = f"g{raw}"[:32]
    slug, n = raw[:32], 0
    qs = model.objects.all()
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    while qs.filter(slug=slug).exists() or slug in _RESERVED:
        n += 1
        suf = f"-{n}"
        slug = f"{raw[: 32 - len(suf)]}{suf}"
    return slug
