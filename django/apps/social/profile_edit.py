"""Profile edit context — profile_page.build_edit_context re-exports."""
from __future__ import annotations

from django.urls import reverse

from apps.social.forms import EducationForm, ExperienceForm, ProfileForm
from apps.social.models import Education, Experience
from apps.social.profile_page import EDIT_NAV, EDIT_SECTIONS, EDIT_TITLES


def _row_editor(*, title, kind, param, rows, edit_row, form_cls, add_name, edit_name, delete_name):
    return {
        "title": title,
        "kind": kind,
        "param": param,
        "rows": rows,
        "edit_row": edit_row,
        "form": form_cls(instance=edit_row) if edit_row else form_cls(),
        "action": (
            reverse(edit_name, args=[edit_row.pk]) if edit_row else reverse(add_name)
        ),
        "delete_name": delete_name,
    }


def build_edit_context(me, request):
    """Context for classic Profile edit (sectioned)."""
    section = (request.GET.get("section") or request.POST.get("section") or "basic").lower()
    edu_id, exp_id = request.GET.get("edu"), request.GET.get("exp")
    edu_row = Education.objects.filter(pk=edu_id, social_user=me).first() if edu_id else None
    exp_row = Experience.objects.filter(pk=exp_id, social_user=me).first() if exp_id else None
    if edu_row or exp_row:
        section = "eduwork"
    elif section not in EDIT_SECTIONS:
        section = "basic"
    education = list(Education.objects.filter(social_user=me)[:20])
    experiences = list(Experience.objects.filter(social_user=me)[:20])
    return {
        "form": ProfileForm(request.POST or None, instance=me, section=section),
        "me": me,
        "section": section,
        "section_title": EDIT_TITLES.get(section, "Основное"),
        "edit_nav": EDIT_NAV,
        "row_editors": [
            _row_editor(
                title="Образование", kind="edu", param="edu", rows=education,
                edit_row=edu_row, form_cls=EducationForm,
                add_name="profile.education", edit_name="profile.education.edit",
                delete_name="profile.education.delete",
            ),
            _row_editor(
                title="Работа", kind="exp", param="exp", rows=experiences,
                edit_row=exp_row, form_cls=ExperienceForm,
                add_name="profile.experience", edit_name="profile.experience.edit",
                delete_name="profile.experience.delete",
            ),
        ],
    }
