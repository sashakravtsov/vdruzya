"""Classic FB Profile page assembly — short helpers, no view bloat."""
from django.db.models import Count, Q
from django.urls import reverse
from django.utils.html import format_html

from apps.social.albums import albums_with_covers, visible_q
from apps.social.forms import CommentForm, PostForm, StatusForm
from apps.social.models import (
    Album, Block, Community, Education, Experience, Friendship, Photo,
)
from apps.social.services import friend_count, mini_feed, wall_posts_for

TABS = frozenset({"wall", "info", "photos", "friends"})
EDIT_SECTIONS = frozenset({"basic", "contact", "personal", "eduwork", "picture", "privacy"})


def networks_for(profile, education=None) -> list[str]:
    """Classic left-rail Networks: city + schools + workplace."""
    if education is None:
        education = list(Education.objects.filter(social_user=profile)[:3])
    out = []
    if profile.city:
        out.append(profile.city)
    for e in education[:3]:
        if e.institution and e.institution not in out:
            out.append(e.institution)
    if profile.workplace and profile.workplace not in out:
        out.append(profile.workplace)
    return out


def recent_photos(profile, viewer, limit=8):
    albums = Album.objects.filter(social_user=profile).filter(visible_q(viewer))
    return list(
        Photo.objects.filter(album__in=albums).exclude(path="")
        .select_related("album").order_by("-id")[:limit]
    )


def profile_albums(profile, viewer, limit=12):
    return list(
        albums_with_covers(
            Album.objects.filter(social_user=profile).filter(visible_q(viewer))
        ).annotate(n_photos=Count("photos")).order_by("-id")[:limit]
    )


def is_friend(relation) -> bool:
    return bool(relation and relation.status == "accepted")


def can_view_full(me, profile, relation) -> bool:
    """Limited Profile: non-friends see only name/pic/networks/actions."""
    if me and me.id == profile.id:
        return True
    vis = getattr(profile, "profile_visibility", None) or "public"
    if vis != "friends":
        return True
    return is_friend(relation)


def can_write_wall(me, profile, relation) -> bool:
    if not me:
        return False
    if me.id == profile.id:
        return True
    write = getattr(profile, "wall_write", None) or "friends"
    if write == "self":
        return False
    return is_friend(relation)


def can_view_wall(me, profile, relation) -> bool:
    if me and me.id == profile.id:
        return True
    view = getattr(profile, "wall_view", None) or "public"
    if view == "self":
        return False
    if view == "friends":
        return is_friend(relation)
    return True


def wall_post_visibility(profile) -> str:
    """Visibility for notes/posts on this wall — matches who may view the wall."""
    return "public" if (getattr(profile, "wall_view", None) or "public") == "public" else "friends"


def friend_tiles(me, profile, *, can_see: bool, relation, limit=6, prefer_mutual=True):
    """Left rail: mutuals when available. Friends tab: owner's friends."""
    from apps.social import friendship as fr
    from apps.social.services import accepted_friends

    if prefer_mutual and me and me.id != profile.id and is_friend(relation):
        mutuals = list(fr.mutual_friends(me, profile, limit))
        if mutuals:
            return mutuals, True
    if can_see:
        return list(accepted_friends(profile)[:limit]), False
    return [], False


def _relation(me, profile):
    if not me or me.id == profile.id:
        return None, False, 0, ""
    from apps.social import friendship as fr

    relation = Friendship.objects.filter(
        Q(user=me, friend=profile) | Q(user=profile, friend=me)
    ).first()
    blocked = Block.objects.filter(blocker=me, blocked=profile).exists()
    mutual = fr.mutual_count(me, profile)
    return relation, blocked, mutual, (fr.mutual_label(mutual) if mutual else "")


def _tag(text):
    from apps.social.templatetags.vd import tag
    return tag(text)


def _tags(text):
    from apps.social.templatetags.vd import tags
    return tags(text)


def _ru(text):
    from apps.social.templatetags.vd import ru_label
    return ru_label(text)


def info_boxes(profile, education, experiences) -> list[dict]:
    """Structured Info tab — one place for fields, short template."""
    from apps.social.templatetags.vd import birthday_tags, external_url

    boxes = []
    basic = []
    if profile.gender:
        basic.append(("Пол", _tag(_ru(profile.gender)), False))
    if profile.birthday_display():
        basic.append(("День рождения", birthday_tags(profile), False))
    if profile.city:
        city = _tag(profile.city)
        if profile.country:
            city = format_html("{}, {}", city, _tag(profile.country))
        basic.append(("Город", city, False))
    if profile.hometown:
        basic.append(("Родной город", _tag(profile.hometown), False))
    if profile.relationship_status:
        rel = _tag(_ru(profile.relationship_status))
        partner = getattr(profile, "relationship_with", None)
        if partner:
            rel = format_html(
                '{} с <a href="{}">{}</a>',
                rel, reverse("profile", args=[partner.id]), partner.name,
            )
        basic.append(("Отношения", rel, False))
    if profile.interested_in_label():
        basic.append(("Интересуюсь", _tags(profile.interested_in_label()), False))
    if profile.looking_for_label():
        basic.append(("Ищу", _tags(profile.looking_for_label()), False))
    if profile.political_views:
        basic.append(("Политика", _tag(_ru(profile.political_views)), False))
    if profile.religious_views:
        basic.append(("Религия", _tag(profile.religious_views), False))
    if profile.languages_label():
        basic.append(("Языки", _tags(profile.languages_label()), False))
    if profile.created_at:
        basic.append(("На сайте с", profile.created_at, True))
    if basic:
        boxes.append({"title": "Основная информация", "section": "basic", "rows": basic})

    contact = []
    email = getattr(getattr(profile, "user", None), "email", None)
    if profile.show_email and email:
        contact.append(("Email", email, False))
    if profile.show_phone and profile.phone:
        contact.append(("Телефон", profile.phone, False))
    if profile.telegram_username:
        contact.append(("Имя в сети", profile.telegram_username, False))
    if profile.website:
        contact.append((
            "Сайт",
            format_html(
                '<a href="{}" rel="nofollow noopener">{}</a>',
                external_url(profile.website), profile.website,
            ),
            False,
        ))
    if contact:
        boxes.append({"title": "Контактная информация", "section": "contact", "rows": contact})

    personal = []
    for label, val, linked in (
        ("Обо мне", profile.bio, False),
        ("Интересы", profile.interests, True),
        ("Хобби", profile.hobbies, True),
        ("Музыка", profile.favorite_music, True),
        ("Фильмы", profile.favorite_movies, True),
        ("ТВ", profile.favorite_tv, True),
        ("Книги", profile.favorite_books, True),
        ("Игры", profile.favorite_games, True),
        ("Цитаты", profile.favorite_quotes, False),
    ):
        if val:
            personal.append((label, _tags(val) if linked else val, False))
    if personal:
        boxes.append({"title": "Личная информация", "section": "personal", "rows": personal})

    subs = []
    if education or profile.education_note:
        items = []
        for e in education:
            line = _tag(e.institution)
            if e.degree:
                line = format_html("{} — {}", line, e.degree)
            if e.field:
                line = format_html("{}, {}", line, e.field)
            if e.start_year or e.end_year:
                line = format_html(
                    '{} <span class="muted">({}–{})</span>',
                    line, e.start_year or "", e.end_year or "",
                )
            items.append(line)
        subs.append({
            "h5": "Образование",
            "note": _tag(profile.education_note) if profile.education_note else "",
            "items": items,
        })
    if experiences or profile.workplace:
        items = []
        for e in experiences:
            line = format_html("<b>{}</b> · {}", e.position, _tag(e.company_name))
            if e.period:
                line = format_html('{} <span class="muted">{}</span>', line, e.period)
            if e.description:
                line = format_html('{}<div class="muted">{}</div>', line, e.description)
            items.append(line)
        subs.append({
            "h5": "Работа",
            "note": _tag(profile.workplace) if profile.workplace else "",
            "items": items,
        })
    if subs:
        boxes.append({"title": "Образование и работа", "section": "eduwork", "subsections": subs})
    return boxes


def build_edit_context(me, request):
    """Context for classic Profile edit (sectioned)."""
    from apps.social.forms import EducationForm, ExperienceForm, ProfileForm

    section = (request.GET.get("section") or request.POST.get("section") or "basic").lower()
    edu_id, exp_id = request.GET.get("edu"), request.GET.get("exp")
    edu_row = Education.objects.filter(pk=edu_id, social_user=me).first() if edu_id else None
    exp_row = Experience.objects.filter(pk=exp_id, social_user=me).first() if exp_id else None
    if edu_row or exp_row:
        section = "eduwork"
    elif section not in EDIT_SECTIONS:
        section = "basic"
    form = ProfileForm(request.POST or None, instance=me, section=section)
    return {
        "form": form,
        "me": me,
        "section": section,
        "edu_form": EducationForm(instance=edu_row) if edu_row else EducationForm(),
        "exp_form": ExperienceForm(instance=exp_row) if exp_row else ExperienceForm(),
        "edu_edit": edu_row,
        "exp_edit": exp_row,
        "education": Education.objects.filter(social_user=me)[:20],
        "experiences": Experience.objects.filter(social_user=me)[:20],
    }


def build_context(profile, me, tab="wall"):
    """Full template context for classic Profile — load only what the tab needs."""
    from apps.social import friendship as fr

    tab = tab if tab in TABS else "wall"
    relation, blocked, mutual, mutual_text = _relation(me, profile)
    can_see = fr.can_see_friends(me, profile)
    is_own = bool(me and me.id == profile.id)
    full = can_view_full(me, profile, relation)
    can_wall = can_write_wall(me, profile, relation) if full else False
    show_wall = can_view_wall(me, profile, relation) if full else False
    wall = tab == "wall" and full

    education = experiences = []
    boxes = []
    if full and tab == "info":
        education = list(Education.objects.filter(social_user=profile)[:10])
        experiences = list(Experience.objects.filter(social_user=profile)[:10])
        edu_rail = education[:3]
        boxes = info_boxes(profile, education, experiences)
    else:
        edu_rail = list(Education.objects.filter(social_user=profile)[:3])

    communities = (
        list(Community.objects.filter(memberships__social_user=profile).distinct()[:12])
        if full else []
    )
    friends_rail, friends_are_mutual = friend_tiles(
        me, profile, can_see=can_see, relation=relation, limit=6, prefer_mutual=True,
    )
    if tab == "friends":
        friends_tab, _ = friend_tiles(
            me, profile, can_see=can_see, relation=relation, limit=30, prefer_mutual=False,
        )
    else:
        friends_tab = friends_rail

    vis_albums = Album.objects.filter(social_user=profile).filter(visible_q(me)) if full else Album.objects.none()
    rail_photos = recent_photos(profile, me, 4) if full else []
    albums = profile_albums(profile, me, 12) if full and tab == "photos" else []

    return {
        "profile": profile, "me": me, "is_own": is_own, "limited": not full, "tab": tab,
        "friends": friends_rail, "friends_tab": friends_tab,
        "friends_are_mutual": friends_are_mutual,
        "communities": communities,
        "rail_photos": rail_photos,
        "albums": albums,
        "posts": wall_posts_for(profile, 20, viewer=me) if wall and show_wall else [],
        "relation": relation, "blocked": blocked,
        "mutual": mutual, "mutual_text": mutual_text,
        "info_boxes": boxes,
        "networks": networks_for(profile, edu_rail),
        "stats": {
            "friends": friend_count(profile) if can_see else 0,
            "photos": Photo.objects.filter(album__in=vis_albums).count() if full else 0,
            "groups": (
                Community.objects.filter(memberships__social_user=profile).distinct().count()
                if full else 0
            ),
        },
        "form": PostForm(simple=True) if wall and can_wall else None,
        "comment_form": CommentForm() if wall and me and show_wall else None,
        "can_wall": can_wall,
        "show_wall": show_wall,
        "can_see_friends": can_see,
        "mini": mini_feed(profile, viewer=me) if wall else [],
        "status_form": StatusForm(initial={"headline": profile.headline or ""}) if is_own else None,
        "wall_owner": profile,
    }
