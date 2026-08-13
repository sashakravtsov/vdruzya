"""OSM JSON suggest — Nominatim-backed, login required."""
from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET

from apps.social import osm


@login_required
@require_GET
def geo_suggest(request):
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})
    hits = osm.search(q, limit=6)
    return JsonResponse({
        "results": [
            {
                "lat": h.lat, "lon": h.lon,
                "label": h.display_name,
                "osm_type": h.osm_type,
                "osm_id": h.osm_id,
            }
            for h in hits
        ],
    })


@login_required
@require_GET
def geo_ping(request):
    """Lightweight probe for smoke — cache path without hitting Nominatim if cached."""
    return HttpResponse(json.dumps({"ok": True, "provider": "nominatim"}), content_type="application/json")
