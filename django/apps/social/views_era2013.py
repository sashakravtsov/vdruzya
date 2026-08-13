"""FB 2013 FBVs — Graph Search, Hashtags, Nearby Friends."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from apps.social import era2013 as e13
from apps.social.services import profile_of


@login_required
@require_GET
def graph_search(request):
    me = profile_of(request.user)
    q = (request.GET.get("q") or "").strip()
    city = (request.GET.get("city") or "").strip()
    like = (request.GET.get("like") or "").strip()
    tag = (request.GET.get("tag") or "").strip()
    data = e13.graph_search(me, q=q, city=city, like=like, tag=tag)
    return render(request, "social/graph_search.html", {
        "me": me, "q": q, "city": city or data["parsed"].get("city", ""),
        "like": like or data["parsed"].get("like", ""),
        "tag": tag or data["parsed"].get("tag", ""),
        "people": data["people"], "posts": data["posts"],
        "parsed": data["parsed"], "nav": "graph",
    })


@login_required
@require_GET
def hashtag_show(request, name):
    me = profile_of(request.user)
    tag_name = e13.normalize_tag(name)
    if not tag_name:
        return redirect("feed")
    tag, posts = e13.hashtag_posts(me, tag_name, limit=40)
    use_count = 0
    if tag:
        from apps.social.models import PostHashtag
        use_count = PostHashtag.objects.filter(hashtag=tag).count()
    return render(request, "social/hashtag.html", {
        "me": me, "tag": tag, "tag_name": tag_name,
        "use_count": use_count, "posts": posts, "nav": "hashtag",
    })


@login_required
@require_GET
def nearby_friends(request):
    from apps.social import osm
    me = profile_of(request.user)
    city = (request.GET.get("city") or "").strip()
    people, used_city = e13.nearby_friends(me, city=city or None, limit=40)
    map_ctx = None
    if me and osm.ensure_profile_geo(me, network=True):
        markers = []
        for p in people:
            d = getattr(p, "distance_km", None)
            if d is not None:
                p.headline = f"{d} км"
            if osm.has_coords(p):
                markers.append({
                    "lat": p.lat, "lon": p.lon,
                    "title": p.name, "url": f"/profile/{p.id}",
                })
        if markers or osm.has_coords(me):
            map_ctx = osm.map_context(
                me.lat, me.lon, zoom=11,
                title=used_city or me.city or "Рядом",
                markers=markers,
            )
    return render(request, "social/nearby_friends.html", {
        "me": me, "people": people, "city": used_city or (me.city if me else ""),
        "map": map_ctx,
        "nav": "nearby",
    })


@login_required
@require_GET
def trending_home(request):
    me = profile_of(request.user)
    topics = e13.trending_topics(me, 30)
    return render(request, "social/trending.html", {
        "me": me, "topics": topics, "nav": "trending",
    })
