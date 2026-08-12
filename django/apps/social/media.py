"""Media helpers — URL + save. One place for all uploads."""
from __future__ import annotations

import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage


def media_url(path: str | None) -> str | None:
    if not path:
        return None
    p = str(path).strip()
    if p.startswith(("http://", "https://")):
        return p
    if p.startswith("/storage/"):
        p = p[len("/storage/") :]
    elif p.startswith("/"):
        return p
    try:
        url = default_storage.url(p)
        if url.startswith("http"):
            return url
        base = (getattr(settings, "MEDIA_URL", "/storage/") or "/storage/").rstrip("/")
        return f"{base}/{p.lstrip('/')}"
    except Exception:
        base = (
            getattr(settings, "AWS_URL", None)
            or getattr(settings, "MEDIA_URL", "/storage/")
            or "/storage/"
        ).rstrip("/")
        return f"{base}/{p.lstrip('/')}"


def save_image(upload, folder: str) -> str:
    ext = Path(upload.name).suffix.lower() or ".jpg"
    if ext not in {".jpg", ".jpeg", ".png", ".gif"}:
        ext = ".jpg"
    return default_storage.save(f"{folder}/{uuid.uuid4().hex}{ext}", upload)
