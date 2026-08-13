"""REST API for developer apps (OAuth-lite token + me/friends)."""
from __future__ import annotations

import json

from django.contrib.auth.decorators import login_not_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from apps.social import platform_oauth as oauth
from apps.social.models import DevApp


def _json_error(msg, status=400):
    return JsonResponse({"error": msg}, status=status)


def _bearer(request) -> str:
    auth = request.META.get("HTTP_AUTHORIZATION") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return (request.GET.get("access_token") or request.POST.get("access_token") or "").strip()


def _load_app_by_key(client_id: str):
    client_id = (client_id or "").strip()
    if not client_id:
        return None
    return DevApp.objects.filter(api_key=client_id, published=True).first()


@login_not_required
@csrf_exempt
@require_http_methods(["POST", "GET"])
def oauth_access_token(request):
    """Exchange authorization code for access_token (client_id + client_secret)."""
    if request.method == "POST":
        if request.content_type and "application/json" in request.content_type:
            try:
                body = json.loads(request.body.decode("utf-8") or "{}")
            except Exception:
                body = {}
        else:
            body = request.POST
    else:
        body = request.GET
    client_id = (body.get("client_id") or body.get("api_key") or "").strip()
    client_secret = (body.get("client_secret") or body.get("api_secret") or "").strip()
    code = (body.get("code") or "").strip()
    redirect_uri = (body.get("redirect_uri") or "").strip()
    app = _load_app_by_key(client_id)
    if not app or not client_secret or app.api_secret != client_secret:
        return _json_error("invalid_client", 401)
    data, err = oauth.exchange_code(app, code, redirect_uri)
    if err:
        return _json_error(err, 400)
    return JsonResponse(data)


@login_not_required
@require_GET
def api_me(request):
    token = _bearer(request)
    row, profile = oauth.token_profile(token)
    if not row or not profile:
        return _json_error("invalid_token", 401)
    data = oauth.profile_public(profile)
    data["app_slug"] = row.app_slug
    return JsonResponse(data)


@login_not_required
@require_GET
def api_friends(request):
    token = _bearer(request)
    row, profile = oauth.token_profile(token)
    if not row or not profile:
        return _json_error("invalid_token", 401)
    return JsonResponse({"data": oauth.friends_public(profile)})


@login_not_required
@csrf_exempt
@require_http_methods(["POST"])
def api_verify_signed(request):
    """Optional: app server verifies signed_request with api_secret."""
    if request.content_type and "application/json" in request.content_type:
        try:
            body = json.loads(request.body.decode("utf-8") or "{}")
        except Exception:
            body = {}
    else:
        body = request.POST
    client_id = (body.get("client_id") or "").strip()
    client_secret = (body.get("client_secret") or "").strip()
    signed = (body.get("signed_request") or "").strip()
    app = _load_app_by_key(client_id)
    if not app or app.api_secret != client_secret:
        return _json_error("invalid_client", 401)
    data = oauth.verify_signed_request(app, signed)
    if not data:
        return _json_error("invalid_signature", 400)
    return JsonResponse({"ok": True, "data": data})
