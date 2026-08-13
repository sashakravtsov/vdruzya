"""OpenStreetMap helpers — Nominatim geocode/search + haversine (no GPS tracking)."""
from __future__ import annotations

import hashlib
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from django.conf import settings
from django.db import connection
from django.core.cache import cache

NOMINATIM = "https://nominatim.openstreetmap.org"
USER_AGENT = getattr(
    settings, "OSM_USER_AGENT",
    "VDruzyaClassic/1.0 (https://vdruzya.ru; osm@vdruzya.ru)",
)
_RATE_KEY = "osm:nominatim:last"
_RATE_LOCK = "osm:nominatim:lock"
CACHE_DAYS = 30


@dataclass(frozen=True)
class GeoHit:
    lat: float
    lon: float
    display_name: str = ""
    osm_type: str = ""
    osm_id: int | None = None


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance in km."""
    try:
        la1, lo1, la2, lo2 = map(float, (lat1, lon1, lat2, lon2))
    except (TypeError, ValueError):
        return float("inf")
    r = 6371.0
    p1, p2 = math.radians(la1), math.radians(la2)
    dphi = math.radians(la2 - la1)
    dlmb = math.radians(lo2 - lo1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def has_coords(obj) -> bool:
    lat = getattr(obj, "lat", None)
    lon = getattr(obj, "lon", None)
    try:
        return lat is not None and lon is not None and float(lat) == float(lat) and float(lon) == float(lon)
    except (TypeError, ValueError):
        return False


def parse_coords(lat, lon) -> tuple[float, float] | None:
    try:
        la, lo = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if not (-90 <= la <= 90 and -180 <= lo <= 180):
        return None
    return la, lo


def _query_key(kind: str, text: str) -> str:
    raw = f"{kind}|{(text or '').strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:64]


def _cache_get(key: str) -> GeoHit | None:
    with connection.cursor() as cur:
        cur.execute(
            "SELECT lat, lon, display_name, osm_type, osm_id FROM geo_cache WHERE query_key=%s",
            [key],
        )
        row = cur.fetchone()
    if not row or row[0] is None or row[1] is None:
        return None
    return GeoHit(
        lat=float(row[0]), lon=float(row[1]),
        display_name=row[2] or "", osm_type=row[3] or "",
        osm_id=int(row[4]) if row[4] is not None else None,
    )


def _cache_put(key: str, text: str, hit: GeoHit | None, payload: str = ""):
    from apps.social.services import now
    t = now()
    with connection.cursor() as cur:
        cur.execute(
            """
            INSERT INTO geo_cache
              (query_key, query_text, lat, lon, display_name, osm_type, osm_id, payload, created_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (query_key) DO UPDATE SET
              query_text=EXCLUDED.query_text,
              lat=EXCLUDED.lat, lon=EXCLUDED.lon,
              display_name=EXCLUDED.display_name,
              osm_type=EXCLUDED.osm_type, osm_id=EXCLUDED.osm_id,
              payload=EXCLUDED.payload, updated_at=EXCLUDED.updated_at
            """,
            [
                key, (text or "")[:500],
                hit.lat if hit else None, hit.lon if hit else None,
                (hit.display_name if hit else "")[:500],
                (hit.osm_type if hit else "")[:20],
                hit.osm_id if hit else None,
                (payload or "")[:8000], t, t,
            ],
        )


def _throttle():
    """Respect Nominatim ≤1 req/s."""
    for _ in range(20):
        if cache.add(_RATE_LOCK, "1", timeout=2):
            try:
                last = cache.get(_RATE_KEY) or 0.0
                wait = 1.05 - (time.time() - float(last))
                if wait > 0:
                    time.sleep(min(wait, 1.2))
                cache.set(_RATE_KEY, time.time(), timeout=60)
                return
            finally:
                cache.delete(_RATE_LOCK)
        time.sleep(0.05)


def _http_get(url: str) -> list | dict | None:
    _throttle()
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Accept-Language": "ru,en",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return None


def _hit_from_row(row: dict) -> GeoHit | None:
    try:
        lat, lon = float(row["lat"]), float(row["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    osm_id = row.get("osm_id")
    try:
        osm_id = int(osm_id) if osm_id is not None else None
    except (TypeError, ValueError):
        osm_id = None
    return GeoHit(
        lat=lat, lon=lon,
        display_name=(row.get("display_name") or "")[:500],
        osm_type=(row.get("osm_type") or "")[:20],
        osm_id=osm_id,
    )


def search(query: str, *, limit: int = 5, country_codes: str = "ru") -> list[GeoHit]:
    """Nominatim free-text search (cached per first hit; live list for UI)."""
    q = (query or "").strip()
    if len(q) < 2:
        return []
    limit = max(1, min(int(limit or 5), 8))
    params = {
        "q": q, "format": "jsonv2", "limit": str(limit),
        "addressdetails": "0",
    }
    if country_codes:
        params["countrycodes"] = country_codes
    data = _http_get(f"{NOMINATIM}/search?{urllib.parse.urlencode(params)}")
    if not isinstance(data, list):
        return []
    hits = []
    for row in data:
        hit = _hit_from_row(row)
        if hit:
            hits.append(hit)
    if hits:
        _cache_put(_query_key("search", q), q, hits[0], json.dumps(data[:3], ensure_ascii=False))
    return hits


def geocode(query: str, *, country_codes: str = "ru", network: bool = True) -> GeoHit | None:
    q = (query or "").strip()
    if len(q) < 2:
        return None
    key = _query_key("geocode", q)
    cached = _cache_get(key)
    if cached:
        return cached
    if not network:
        return None
    hits = search(q, limit=1, country_codes=country_codes)
    hit = hits[0] if hits else None
    _cache_put(key, q, hit)
    return hit


def geocode_parts(*parts: str, country_codes: str = "ru", network: bool = True) -> GeoHit | None:
    bits = [str(p).strip() for p in parts if p and str(p).strip()]
    if not bits:
        return None
    return geocode(", ".join(bits), country_codes=country_codes, network=network)


def apply_hit(obj, hit: GeoHit | None, *, fields_extra: list[str] | None = None) -> bool:
    """Set lat/lon/(osm_*) on model instance; returns True if coords applied."""
    if not obj or not hit:
        return False
    obj.lat = hit.lat
    obj.lon = hit.lon
    extras = fields_extra or []
    if hasattr(obj, "osm_type") and "osm_type" in extras:
        obj.osm_type = hit.osm_type or ""
    if hasattr(obj, "osm_id") and "osm_id" in extras:
        obj.osm_id = hit.osm_id
    return True


def ensure_profile_geo(profile, *, force: bool = False, network: bool = True) -> GeoHit | None:
    """Geocode profile city (and persist lat/lon) for Nearby / Safety radius."""
    if not profile:
        return None
    if has_coords(profile) and not force:
        return GeoHit(float(profile.lat), float(profile.lon), display_name=profile.city or "")
    city = (profile.city or profile.hometown or "").strip()
    if not city:
        return None
    hit = geocode_parts(city, profile.country or "", network=network)
    if not hit and network and profile.country:
        hit = geocode(city, network=True)
    if not hit:
        return None
    profile.lat = hit.lat
    profile.lon = hit.lon
    try:
        profile.save(update_fields=["lat", "lon"])
    except Exception:
        pass
    return hit


def map_context(lat, lon, *, zoom: int = 15, title: str = "", markers: list | None = None) -> dict | None:
    """Template context for classic OSM map box."""
    coords = parse_coords(lat, lon)
    if not coords and not markers:
        return None
    ms = []
    for m in markers or []:
        c = parse_coords(m.get("lat"), m.get("lon"))
        if not c:
            continue
        ms.append({
            "lat": c[0], "lon": c[1],
            "title": (m.get("title") or "")[:120],
            "url": m.get("url") or "",
        })
    if coords:
        la, lo = coords
    elif ms:
        la, lo = ms[0]["lat"], ms[0]["lon"]
    else:
        return None
    if coords and not any(abs(m["lat"] - la) < 1e-6 and abs(m["lon"] - lo) < 1e-6 for m in ms):
        ms.insert(0, {"lat": la, "lon": lo, "title": (title or "")[:120], "url": ""})
    return {
        "lat": la, "lon": lo, "zoom": int(zoom),
        "title": (title or "")[:120],
        "markers_json": json.dumps(ms, ensure_ascii=False),
        "osm_link": f"https://www.openstreetmap.org/?mlat={la}&mlon={lo}#map={int(zoom)}/{la}/{lo}",
    }


def sort_by_distance(origin, rows, *, limit: int = 40) -> list:
    """Annotate .distance_km and sort; rows without coords go last."""
    if not has_coords(origin):
        return list(rows)[:limit]
    scored = []
    for row in rows:
        if has_coords(row):
            d = haversine_km(origin.lat, origin.lon, row.lat, row.lon)
            row.distance_km = round(d, 1)
            scored.append((d, 0, row))
        else:
            row.distance_km = None
            scored.append((float("inf"), 1, row))
    scored.sort(key=lambda x: (x[0], x[1]))
    return [r for _, __, r in scored[:limit]]


def within_radius(origin, point, radius_km: float) -> bool:
    if not has_coords(origin) or not has_coords(point):
        return False
    try:
        r = float(radius_km or 0)
    except (TypeError, ValueError):
        r = 0
    if r <= 0:
        return True
    return haversine_km(origin.lat, origin.lon, point.lat, point.lon) <= r
