"""Classic FB Profile page assembly — short helpers, no view bloat."""
from django.db.models import Q
from django.utils.html import format_html

from apps.social.models import Album, Block, Education, Experience, Friendship, Photo

TABS = frozenset({"wall", "timeline", "info", "photos", "notes", "friends"})
EDIT_SECTIONS = frozenset({"basic", "contact", "personal", "eduwork", "picture", "privacy"})
# Tab labels (short) + section page titles (archive editprofile)
EDIT_NAV = (
    ("basic", "Основное"),
    ("contact", "Контакты"),
    ("personal", "Личное"),
    ("eduwork", "Учёба и работа"),
    ("picture", "Фото"),
    ("privacy", "Приватность"),
)
EDIT_TITLES = {
    "basic": "Основное",
    "contact": "Контактная информация",
    "personal": "Личная информация",
    "eduwork": "Образование и работа",
    "picture": "Фотография",
    "privacy": "Приватность",
}


def networks_for(profile, education=None, experience=None) -> list[dict]:
    """Classic left-rail Networks: city / school / work → Find Friends filters."""
    from urllib.parse import urlencode

    if education is None:
        education = list(Education.objects.filter(social_user=profile)[:3])
    if experience is None:
        experience = list(
            Experience.objects.filter(social_user=profile).exclude(company_name="").order_by("-id")[:5]
        )
    out, seen = [], set()

    def add(label, **params):
        label = (label or "").strip()
        if not label or label.lower() in seen:
            return
        seen.add(label.lower())
        out.append({"label": label, "href": "/people?" + urlencode({"tab": "search", **params})})

    add(profile.city, city=profile.city or "")
    for e in education[:3]:
        add(e.institution, school=e.institution or "")
    add(profile.workplace, workplace=profile.workplace or "")
    for x in experience[:5]:
        add(x.company_name, workplace=x.company_name or "")
    return out


def recent_photos(profile, viewer, limit=8):
    albums = Album.objects.filter(social_user=profile).visible_to(viewer)
    return list(
        Photo.objects.filter(album__in=albums).exclude(path="")
        .select_related("album").order_by("-id")[:limit]
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
    """Post visibility mirrors wall_view: public / friends / self→private."""
    view = getattr(profile, "wall_view", None) or "public"
    if view == "public":
        return "public"
    if view == "self":
        return "private"
    return "friends"


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



def _people_link(label, **params):
    """Info-tab value → Find Friends filter (FB 2006 Networks / Basic Info)."""
    from urllib.parse import urlencode
    text = str(label or "").strip()
    if not text:
        return ""
    q = {"tab": "search", **{k: v for k, v in params.items() if v}}
    if not any(k in q for k in ("city", "school", "workplace", "gender")):
        q["q"] = text
    return format_html('<a href="/people?{}">{}</a>', urlencode(q), text)


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
    """Info tab — builders live in profile_info (keep import stable)."""
    from apps.social.profile_info import info_boxes as build
    return build(profile, education, experiences)


def build_edit_context(me, request):
    """Context for classic Profile edit (sectioned)."""
    from django.urls import reverse
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

    education = list(Education.objects.filter(social_user=me)[:20])
    experiences = list(Experience.objects.filter(social_user=me)[:20])
    # Row editors: URLs resolved in Python — no fragile {% url name_var %} in templates
    row_editors = [
        {
            "title": "Образование",
            "kind": "edu",
            "param": "edu",
            "rows": education,
            "edit_row": edu_row,
            "form": EducationForm(instance=edu_row) if edu_row else EducationForm(),
            "action": (
                reverse("profile.education.edit", args=[edu_row.pk])
                if edu_row else reverse("profile.education")
            ),
            "delete_name": "profile.education.delete",
        },
        {
            "title": "Работа",
            "kind": "exp",
            "param": "exp",
            "rows": experiences,
            "edit_row": exp_row,
            "form": ExperienceForm(instance=exp_row) if exp_row else ExperienceForm(),
            "action": (
                reverse("profile.experience.edit", args=[exp_row.pk])
                if exp_row else reverse("profile.experience")
            ),
            "delete_name": "profile.experience.delete",
        },
    ]
    return {
        "form": form,
        "me": me,
        "section": section,
        "section_title": EDIT_TITLES.get(section, "Основное"),
        "edit_nav": EDIT_NAV,
        "row_editors": row_editors,
    }


def build_context(profile, me, tab="wall", photos_view="albums", wall_filter="all"):
    """Full template context for classic Profile — builders in profile_ctx."""
    from apps.social.profile_ctx import build_context as build
    return build(profile, me, tab=tab, photos_view=photos_view, wall_filter=wall_filter)
