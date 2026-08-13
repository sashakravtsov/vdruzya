#!/usr/bin/env python3
"""One-shot production social wipe + sequential ID reset.

Keeps: django_* schema meta, auth_permission/groups, sticker catalog, DevApp somneniya.
Creates: Александр Кравцов (id=1) + Django admin (id=2).
Does NOT touch the separate somneniya Docker stack / DB.

Usage (on prod):
  cd /var/www/projects/vdruzya.ru/django && .venv/bin/python3 deploy/purge-battle-reset.py
"""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.auth import make_password

# sticker_packs FK → social_users: CASCADE would wipe the catalog if kept.
# Re-seed Twemoji stickers after users exist (ensure-twemoji-stickers.py).
KEEP_TABLES = {
    "django_migrations",
    "django_content_type",
    "auth_permission",
    "auth_group",
    "auth_group_permissions",
}

BACKUP_DIR = Path("/var/backups/vdruzya")


def db_env():
    db = settings.DATABASES["default"]
    env = os.environ.copy()
    env["PGPASSWORD"] = str(db.get("PASSWORD") or "")
    return env, db


def backup_db() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = BACKUP_DIR / f"vdruzya-pre-purge-{stamp}.dump"
    env, db = db_env()
    cmd = [
        "pg_dump",
        "-Fc",
        "-h", str(db.get("HOST") or "127.0.0.1"),
        "-p", str(db.get("PORT") or "5432"),
        "-U", str(db.get("USER") or "postgres"),
        "-d", str(db.get("NAME") or "vdruzya"),
        "-f", str(out),
    ]
    print("BACKUP", out)
    subprocess.check_call(cmd, env=env)
    return out


def fetch_somneniya(cur):
    cur.execute("SELECT * FROM dev_apps WHERE slug = %s", ["somneniya"])
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    if not row:
        raise SystemExit("FATAL: DevApp somneniya missing — abort")
    return dict(zip(cols, row))


def fetch_me_bits(cur):
    cur.execute(
        "SELECT avatar_path, cover_path, city, invite_code, avatar_color "
        "FROM social_users WHERE user_id = 1 OR id = 1 ORDER BY id LIMIT 1"
    )
    row = cur.fetchone()
    if not row:
        return {
            "avatar_path": None,
            "cover_path": None,
            "city": "Феодосия",
            "invite_code": secrets.token_urlsafe(8)[:10],
            "avatar_color": "#3B5998",
        }
    return {
        "avatar_path": row[0],
        "cover_path": row[1],
        "city": row[2] or "Феодосия",
        "invite_code": row[3] or secrets.token_urlsafe(8)[:10],
        "avatar_color": row[4] or "#3B5998",
    }


def list_public_tables(cur):
    cur.execute(
        """
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY 1
        """
    )
    return [r[0] for r in cur.fetchall()]


def break_cycles(cur):
    # poker_rooms.current_game_id ↔ poker_games
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'poker_rooms' AND column_name = 'current_game_id'
        """
    )
    if cur.fetchone():
        cur.execute("UPDATE poker_rooms SET current_game_id = NULL")


def reassign_table_owner(cur, owner: str):
    """Some legacy tables are owned by postgres — TRUNCATE needs ownership."""
    cur.execute(
        """
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public' AND tableowner <> %s
        ORDER BY 1
        """,
        [owner],
    )
    foreign = [r[0] for r in cur.fetchall()]
    for t in foreign:
        cur.execute('ALTER TABLE "%s" OWNER TO %s' % (t, owner))
        print("OWNER", t, "->", owner)
    cur.execute(
        """
        SELECT sequence_name FROM information_schema.sequences
        WHERE sequence_schema = 'public'
        """
    )
    # sequences may still be postgres-owned; fix via pg_class
    cur.execute(
        """
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_roles r ON r.oid = c.relowner
        WHERE n.nspname = 'public' AND c.relkind = 'S' AND r.rolname <> %s
        """,
        [owner],
    )
    for (name,) in cur.fetchall():
        cur.execute('ALTER SEQUENCE "%s" OWNER TO %s' % (name, owner))
        print("OWNER SEQ", name, "->", owner)


def truncate_junk(cur, tables):
    targets = [t for t in tables if t not in KEEP_TABLES]
    if not targets:
        return
    # RESTART IDENTITY + CASCADE clears FKs and resets sequences on truncated tables
    quoted = ", ".join('"%s"' % t for t in targets)
    print("TRUNCATE", len(targets), "tables")
    cur.execute("TRUNCATE TABLE %s RESTART IDENTITY CASCADE" % quoted)


def ensure_admin_columns(cur):
    cur.execute(
        """
        ALTER TABLE users
          ADD COLUMN IF NOT EXISTS is_staff boolean NOT NULL DEFAULT false,
          ADD COLUMN IF NOT EXISTS is_superuser boolean NOT NULL DEFAULT false
        """
    )


def reset_kept_sequences(cur):
    for table in sorted(KEEP_TABLES):
        cur.execute(
            """
            SELECT pg_get_serial_sequence(%s, 'id')
            """,
            [table],
        )
        seq = cur.fetchone()[0]
        if not seq:
            continue
        cur.execute('SELECT COALESCE(MAX(id), 0) FROM "%s"' % table)
        mx = cur.fetchone()[0] or 0
        if mx <= 0:
            cur.execute("SELECT setval(%s, 1, false)", [seq])
        else:
            cur.execute("SELECT setval(%s, %s, true)", [seq, mx])
        print("SEQ", table, "->", mx)


def insert_user(cur, *, user_id, name, email, password, staff=False, superuser=False):
    now = timezone.now().replace(tzinfo=None)
    pw = make_password(password)
    cur.execute(
        """
        INSERT INTO users (
          id, name, email, email_verified_at, password, remember_token,
          phone, phone_verified_at, last_login, created_at, updated_at,
          is_staff, is_superuser
        ) VALUES (
          %s, %s, %s, %s, %s, NULL,
          NULL, NULL, NULL, %s, %s,
          %s, %s
        )
        """,
        [user_id, name, email, now, pw, now, now, staff, superuser],
    )


def insert_profile(cur, *, profile_id, user_id, name, slug, city, birthday,
                   avatar_path, cover_path, invite_code, avatar_color):
    now = timezone.now().replace(tzinfo=None)
    cur.execute(
        """
        INSERT INTO social_users (
          id, user_id, name, slug, city, avatar_color, avatar_path, cover_path,
          verified, birthday, birthday_visibility, invite_code,
          profile_visibility, wall_write, wall_view,
          onboarding_completed_at, created_at, updated_at,
          show_phone, show_email
        ) VALUES (
          %s, %s, %s, %s, %s, %s, %s, %s,
          false, %s, 'full', %s,
          'public', 'friends', 'public',
          %s, %s, %s,
          false, false
        )
        """,
        [
            profile_id, user_id, name, slug, city, avatar_color, avatar_path, cover_path,
            birthday, invite_code, now, now, now,
        ],
    )


def restore_somneniya(cur, app: dict, owner_id: int):
    now = timezone.now().replace(tzinfo=None)
    cur.execute(
        """
        INSERT INTO dev_apps (
          id, owner_id, slug, name, category, blurb, detail,
          website_url, callback_url, api_key, api_secret,
          published, featured, created_at, updated_at
        ) VALUES (
          1, %s, %s, %s, %s, %s, %s,
          %s, %s, %s, %s,
          %s, %s, %s, %s
        )
        """,
        [
            owner_id,
            app["slug"],
            app["name"],
            app.get("category") or "lifestyle",
            app.get("blurb") or "",
            app.get("detail") or "",
            app.get("website_url") or "",
            app.get("callback_url") or "",
            app.get("api_key") or "",
            app.get("api_secret") or "",
            bool(app.get("published")),
            bool(app.get("featured")),
            app.get("created_at") or now,
            now,
        ],
    )
    # install for owner
    cur.execute(
        """
        INSERT INTO app_installs (id, social_user_id, app_slug, created_at)
        VALUES (1, %s, 'somneniya', %s)
        """,
        [owner_id, now],
    )


def verify(cur):
    cur.execute("SELECT id, name, email, is_staff, is_superuser FROM users ORDER BY id")
    users = cur.fetchall()
    cur.execute("SELECT id, user_id, name, birthday, slug FROM social_users ORDER BY id")
    profiles = cur.fetchall()
    cur.execute("SELECT id, owner_id, slug, api_key FROM dev_apps")
    apps = cur.fetchall()
    cur.execute("SELECT COUNT(*) FROM posts")
    posts = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM stickers")
    stickers = cur.fetchone()[0]
    # gap check on non-empty user tables
    bad = []
    for table, cnt_sql in (
        ("users", "SELECT COUNT(*), COALESCE(MAX(id),0) FROM users"),
        ("social_users", "SELECT COUNT(*), COALESCE(MAX(id),0) FROM social_users"),
        ("dev_apps", "SELECT COUNT(*), COALESCE(MAX(id),0) FROM dev_apps"),
        ("stickers", "SELECT COUNT(*), COALESCE(MAX(id),0) FROM stickers"),
    ):
        cur.execute(cnt_sql)
        cnt, mx = cur.fetchone()
        if cnt and mx != cnt:
            bad.append((table, cnt, mx))
    return {
        "users": users,
        "profiles": profiles,
        "apps": apps,
        "posts": posts,
        "stickers": stickers,
        "gaps": bad,
    }


def main():
    if "--i-know" not in sys.argv:
        print("Refusing: pass --i-know to wipe production social data")
        return 2

    dump = backup_db()
    print("OK backup", dump, "size", dump.stat().st_size)

    pw_alex = secrets.token_urlsafe(14)
    pw_admin = secrets.token_urlsafe(14)
    creds = {
        "alexander": {
            "email": "alexandr@vdruzya.ru",
            "password": pw_alex,
            "name": "Александр Кравцов",
            "birthday": "1985-12-20",
            "profile_id": 1,
            "user_id": 1,
        },
        "admin": {
            "email": "admin@vdruzya.ru",
            "password": pw_admin,
            "name": "Администратор",
            "profile_id": 2,
            "user_id": 2,
            "django_admin": "https://vdruzya.ru/djadmin/",
        },
    }

    with connection.cursor() as cur:
        som = fetch_somneniya(cur)
        me = fetch_me_bits(cur)
        tables = list_public_tables(cur)
        missing_keep = KEEP_TABLES - set(tables)
        if missing_keep:
            raise SystemExit("missing keep tables: %s" % missing_keep)

        break_cycles(cur)
        ensure_admin_columns(cur)

    # Ownership fix must run as a superuser (postgres), not app role.
    env, db = db_env()
    owner = str(db.get("USER") or "vdruzya")
    print("REASSIGN owner ->", owner)
    subprocess.check_call(
        [
            "sudo", "-u", "postgres", "psql", "-d", str(db.get("NAME") or "vdruzya"), "-v", "ON_ERROR_STOP=1",
            "-c",
            """
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname='public' AND tableowner <> '%(owner)s'
  LOOP
    EXECUTE format('ALTER TABLE %%I OWNER TO %(owner)s', r.tablename);
  END LOOP;
  FOR r IN
    SELECT c.relname AS seq
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_roles o ON o.oid = c.relowner
    WHERE n.nspname='public' AND c.relkind='S' AND o.rolname <> '%(owner)s'
  LOOP
    EXECUTE format('ALTER SEQUENCE %%I OWNER TO %(owner)s', r.seq);
  END LOOP;
END $$;
""" % {"owner": owner},
        ]
    )

    with connection.cursor() as cur:
        tables = list_public_tables(cur)
        with transaction.atomic():
            truncate_junk(cur, tables)
            # sequences on kept tables
            reset_kept_sequences(cur)

            # Force user/profile sequences to start clean before explicit ids
            for table in ("users", "social_users", "dev_apps", "app_installs"):
                cur.execute("SELECT pg_get_serial_sequence(%s, 'id')", [table])
                seq = cur.fetchone()[0]
                if seq:
                    cur.execute("SELECT setval(%s, 1, false)", [seq])

            insert_user(
                cur,
                user_id=1,
                name="Александр Кравцов",
                email="alexandr@vdruzya.ru",
                password=pw_alex,
                staff=False,
                superuser=False,
            )
            insert_user(
                cur,
                user_id=2,
                name="Администратор",
                email="admin@vdruzya.ru",
                password=pw_admin,
                staff=True,
                superuser=True,
            )
            insert_profile(
                cur,
                profile_id=1,
                user_id=1,
                name="Александр Кравцов",
                slug="aleksandr-kravtsov",
                city=me["city"],
                birthday=date(1985, 12, 20),
                avatar_path=me["avatar_path"],
                cover_path=me["cover_path"],
                invite_code=me["invite_code"],
                avatar_color=me["avatar_color"],
            )
            insert_profile(
                cur,
                profile_id=2,
                user_id=2,
                name="Администратор",
                slug="admin",
                city="Феодосия",
                birthday=None,
                avatar_path=None,
                cover_path=None,
                invite_code=secrets.token_urlsafe(8)[:10],
                avatar_color="#333333",
            )
            restore_somneniya(cur, som, owner_id=1)

            # bump sequences past explicit ids
            for table, mx in (("users", 2), ("social_users", 2), ("dev_apps", 1), ("app_installs", 1)):
                cur.execute("SELECT pg_get_serial_sequence(%s, 'id')", [table])
                seq = cur.fetchone()[0]
                if seq:
                    cur.execute("SELECT setval(%s, %s, true)", [seq, mx])

        report = verify(cur)

    # Re-seed system sticker pack with contiguous ids 1..N
    seed = Path(__file__).resolve().parent / "ensure-twemoji-stickers.py"
    print("SEED stickers", seed)
    subprocess.check_call([sys.executable, str(seed)], cwd=str(Path(__file__).resolve().parent.parent))

    with connection.cursor() as cur:
        report = verify(cur)

    # flush redis cache/sessions if configured
    try:
        from django.core.cache import cache
        cache.clear()
        print("OK cache.clear()")
    except Exception as e:
        print("WARN cache.clear", e)

    cred_path = BACKUP_DIR / "vdruzya-creds-latest.json"
    cred_path.write_text(json.dumps(creds, ensure_ascii=False, indent=2), encoding="utf-8")
    os.chmod(cred_path, 0o600)

    print("REPORT", json.dumps(report, ensure_ascii=False, default=str, indent=2))
    print("CREDS_FILE", cred_path)
    print("CREDS_JSON", json.dumps(creds, ensure_ascii=False))
    if report["gaps"]:
        print("WARN id gaps remain on:", report["gaps"])
        return 1
    if report["posts"] != 0:
        print("WARN posts not empty")
        return 1
    if not report["apps"] or report["apps"][0][2] != "somneniya":
        print("WARN somneniya missing after restore")
        return 1
    if report["stickers"] < 1:
        print("WARN stickers empty")
        return 1
    print("OK purge complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
