"""OAuth-lite + signed_request for developer apps (Django signing / HMAC).

Soft ban: no third-party iframe canvas — apps launch via redirect + REST API.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import timedelta
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

from django.utils import timezone

from apps.social.services import friend_ids, now


def _utc_naive():
    """UTC naive timestamps for OAuth rows (matches USE_TZ DB storage)."""
    t = timezone.now()
    return timezone.make_naive(t, timezone.utc) if timezone.is_aware(t) else t


def new_api_key() -> str:
    return "vd_" + secrets.token_hex(12)


def new_api_secret() -> str:
    return secrets.token_hex(32)


def new_oauth_code() -> str:
    return "vc_" + secrets.token_urlsafe(24)


def new_access_token() -> str:
    return "vat_" + secrets.token_urlsafe(32)


def ensure_app_credentials(app) -> None:
    """Backfill api_key / api_secret on legacy rows."""
    changed = False
    if not (app.api_key or "").strip():
        app.api_key = new_api_key()
        changed = True
    if not (app.api_secret or "").strip():
        app.api_secret = new_api_secret()
        changed = True
    if changed:
        app.updated_at = now()
        app.save(update_fields=["api_key", "api_secret", "updated_at"])


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def make_signed_request(app, profile, *, extra=None) -> str:
    """Facebook-style signed_request: HMAC-SHA256(secret, payload).payload"""
    ensure_app_credentials(app)
    payload = {
        "algorithm": "HMAC-SHA256",
        "issued_at": int(timezone.now().timestamp()),
        "user_id": profile.id,
        "name": profile.name,
        "app_slug": app.slug,
        "app_id": app.api_key,
    }
    if extra:
        payload.update(extra)
    raw = _b64url(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(app.api_secret.encode("utf-8"), raw.encode("ascii"), hashlib.sha256).digest()
    return _b64url(sig) + "." + raw


def verify_signed_request(app, signed: str) -> dict | None:
    try:
        sig_b64, raw = (signed or "").split(".", 1)
    except ValueError:
        return None
    expect = hmac.new(app.api_secret.encode("utf-8"), raw.encode("ascii"), hashlib.sha256).digest()
    if not hmac.compare_digest(_b64url(expect), sig_b64):
        return None
    try:
        data = json.loads(_b64url_decode(raw).decode("utf-8"))
    except Exception:
        return None
    if data.get("app_slug") != app.slug:
        return None
    # 2h window
    issued = int(data.get("issued_at") or 0)
    if abs(int(timezone.now().timestamp()) - issued) > 7200:
        return None
    return data


def append_query(url: str, params: dict) -> str:
    parts = urlparse(url)
    q = dict(parse_qsl(parts.query, keep_blank_values=True))
    q.update({k: str(v) for k, v in params.items() if v is not None})
    return urlunparse(parts._replace(query=urlencode(q)))


def same_origin_or_path(callback: str, allowed: str) -> bool:
    """Allow callback if it matches registered callback / website origin."""
    callback = (callback or "").strip()
    allowed = (allowed or "").strip()
    if not callback or not allowed:
        return False
    if not callback.startswith(("http://", "https://")):
        return False
    c, a = urlparse(callback), urlparse(allowed)
    if c.scheme not in ("http", "https") or a.scheme not in ("http", "https"):
        return False
    return (c.scheme, c.netloc.lower()) == (a.scheme, a.netloc.lower())


def allowed_redirect(app, redirect_uri: str) -> bool:
    redirect_uri = (redirect_uri or "").strip()
    if not redirect_uri:
        return False
    for base in (app.callback_url, app.website_url):
        if base and same_origin_or_path(redirect_uri, base):
            return True
    return False


def create_oauth_code(app, profile, redirect_uri: str):
    from apps.social.models import AppOAuthCode
    ensure_app_credentials(app)
    code = new_oauth_code()
    AppOAuthCode.objects.create(
        app_slug=app.slug,
        social_user=profile,
        code=code,
        redirect_uri=redirect_uri[:255],
        created_at=_utc_naive(),
    )
    return code


def exchange_code(app, code: str, redirect_uri: str):
    from apps.social.models import AppAccessToken, AppOAuthCode
    row = (
        AppOAuthCode.objects.filter(app_slug=app.slug, code=code, used_at__isnull=True)
        .select_related("social_user")
        .first()
    )
    if not row:
        return None, "invalid_code"
    tnow = _utc_naive()
    created = row.created_at or tnow
    if timezone.is_aware(created):
        created = timezone.make_naive(created, timezone.utc)
    if (tnow - created) > timedelta(minutes=10):
        return None, "expired_code"
    if (row.redirect_uri or "") and redirect_uri and row.redirect_uri != redirect_uri:
        return None, "redirect_mismatch"
    row.used_at = tnow
    row.save(update_fields=["used_at"])
    token = new_access_token()
    expires = tnow + timedelta(days=30)
    AppAccessToken.objects.create(
        app_slug=app.slug,
        social_user=row.social_user,
        token=token,
        created_at=tnow,
        expires_at=expires,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 30 * 24 * 3600,
        "user_id": row.social_user_id,
    }, None


def token_profile(token: str):
    from apps.social.models import AppAccessToken
    row = (
        AppAccessToken.objects.filter(token=token)
        .select_related("social_user")
        .first()
    )
    if not row:
        return None, None
    if row.expires_at:
        exp = row.expires_at
        if timezone.is_aware(exp):
            exp = timezone.make_naive(exp, timezone.utc)
        if exp < _utc_naive():
            return None, None
    return row, row.social_user


def profile_public(p) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "city": (p.city or "").strip(),
        "url": f"/profile/{p.id}",
    }


def friends_public(me, limit=40) -> list[dict]:
    from apps.social.models import SocialProfile
    from apps.social.services import profile_related
    fids = list(friend_ids(me))[:limit]
    if not fids:
        return []
    rows = SocialProfile.objects.filter(id__in=fids).defer(*profile_related()).order_by("name")
    return [profile_public(p) for p in rows]


def install_count(slug: str) -> int:
    from apps.social.models import AppInstall
    return AppInstall.objects.filter(app_slug=slug).count()
