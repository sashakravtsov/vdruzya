from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = False

    def create_user(self, email, password=None, **extra):
        from apps.accounts.auth import make_password
        user = self.model(email=self.normalize_email(email), **extra)
        user.password = make_password(password or "")
        user.save(using=self._db)
        return user

    def get_by_natural_key(self, email):
        return self.get(email__iexact=email)


class User(AbstractBaseUser):
    """Live `users` table — unmanaged."""
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=255)
    email = models.CharField(max_length=255, unique=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    password = models.CharField(max_length=255)
    remember_token = models.CharField(max_length=100, null=True, blank=True)
    phone = models.CharField(max_length=32, unique=True, null=True, blank=True)
    phone_verified_at = models.DateTimeField(null=True, blank=True)
    last_login = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    is_active = True

    objects = UserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        managed = False
        db_table = "users"

    def __str__(self):
        return self.email

    def has_perm(self, perm, obj=None):
        return bool(self.is_superuser)

    def has_module_perms(self, app_label):
        return bool(self.is_superuser)

    def set_password(self, raw_password):
        from apps.accounts.auth import make_password
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        from apps.accounts.auth import check_password
        return check_password(raw_password, self.password)

    def has_usable_password(self):
        return bool(self.password)
