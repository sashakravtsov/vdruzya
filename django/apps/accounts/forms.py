from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm as DjangoPasswordResetForm
from django.contrib.auth.forms import SetPasswordForm as DjangoSetPasswordForm
from django.contrib.auth.forms import _unicode_ci_compare

UserModel = get_user_model()


class PasswordResetForm(DjangoPasswordResetForm):
    """User.has_usable_password is custom; is_active is class attr — skip ORM is_active filter."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.update({"class": "inputtext", "size": "30"})

    def get_users(self, email):
        email_field_name = UserModel.get_email_field_name()
        users = UserModel._default_manager.filter(
            **{"%s__iexact" % email_field_name: email}
        )
        return (
            u
            for u in users
            if u.has_usable_password()
            and getattr(u, "is_active", True)
            and _unicode_ci_compare(email, getattr(u, email_field_name))
        )


class StyledSetPasswordForm(DjangoSetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("new_password1", "new_password2"):
            self.fields[name].widget.attrs.update({"class": "inputtext", "size": "30"})
