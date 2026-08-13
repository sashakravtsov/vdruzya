"""Unmanaged poker tables (created by deploy/ensure-poker-modules.py)."""
from django.db import models

from apps.social.models import SocialProfile


class PokerProfile(models.Model):
    social_user = models.OneToOneField(
        SocialProfile, on_delete=models.DO_NOTHING, primary_key=True, db_column="social_user_id",
        related_name="+",
    )
    chips = models.BigIntegerField(default=1_000_000)
    games = models.IntegerField(default=0)
    wins = models.IntegerField(default=0)
    losses = models.IntegerField(default=0)
    ties = models.IntegerField(default=0)
    biggest_pot = models.BigIntegerField(default=0)
    puzzle_solved = models.IntegerField(default=0)
    puzzle_streak = models.IntegerField(default=0)
    best_puzzle_streak = models.IntegerField(default=0)
    last_puzzle_on = models.DateField(null=True, blank=True)
    learn_xp = models.IntegerField(default=0)
    bankrupt_until = models.DateTimeField(null=True, blank=True)
    reset_count = models.IntegerField(default=0)
    rating = models.IntegerField(default=1200)
    rated_games = models.IntegerField(default=0)
    play_streak = models.IntegerField(default=0)
    last_play_on = models.DateField(null=True, blank=True)
    daily_bonus_on = models.DateField(null=True, blank=True)
    achievements = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "poker_profiles"


class PokerChampionship(models.Model):
    id = models.BigAutoField(primary_key=True)
    week_key = models.CharField(max_length=12)
    title = models.CharField(max_length=120)
    starts_on = models.DateField()
    ends_on = models.DateField()
    status = models.CharField(max_length=12, default="open")
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "poker_championships"


class PokerChampEntry(models.Model):
    id = models.BigAutoField(primary_key=True)
    championship = models.ForeignKey(
        PokerChampionship, on_delete=models.DO_NOTHING, db_column="championship_id", related_name="+",
    )
    social_user = models.ForeignKey(
        SocialProfile, on_delete=models.DO_NOTHING, db_column="social_user_id", related_name="+",
    )
    points = models.IntegerField(default=0)
    wins = models.IntegerField(default=0)
    losses = models.IntegerField(default=0)
    ties = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = "poker_champ_entries"


class PokerRoom(models.Model):
    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=80)
    owner = models.ForeignKey(
        SocialProfile, on_delete=models.DO_NOTHING, db_column="owner_id", related_name="+",
    )
    stake_key = models.CharField(max_length=16, default="micro")
    is_private = models.BooleanField(default=False)
    join_code = models.CharField(max_length=12, blank=True, default="")
    p1 = models.ForeignKey(
        SocialProfile, on_delete=models.DO_NOTHING, null=True, blank=True,
        db_column="p1_id", related_name="+",
    )
    p2 = models.ForeignKey(
        SocialProfile, on_delete=models.DO_NOTHING, null=True, blank=True,
        db_column="p2_id", related_name="+",
    )
    status = models.CharField(max_length=16, default="open")  # open|playing|closed
    current_game = models.ForeignKey(
        "PokerGame", on_delete=models.DO_NOTHING, null=True, blank=True,
        db_column="current_game_id", related_name="+",
    )
    in_champ = models.BooleanField(default=True)
    hands_played = models.IntegerField(default=0)
    max_seats = models.IntegerField(default=2)
    seats_json = models.TextField(blank=True, default="[]")
    button_seat = models.IntegerField(default=0)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "poker_rooms"


class PokerGame(models.Model):
    id = models.BigAutoField(primary_key=True)
    p1 = models.ForeignKey(
        SocialProfile, on_delete=models.DO_NOTHING, db_column="p1_id", related_name="+",
    )
    p2 = models.ForeignKey(
        SocialProfile, on_delete=models.DO_NOTHING, db_column="p2_id", related_name="+",
    )
    invited_by = models.ForeignKey(
        SocialProfile, on_delete=models.DO_NOTHING, null=True, blank=True,
        db_column="invited_by_id", related_name="+",
    )
    status = models.CharField(max_length=16, default="pending")  # pending|active|done|cancelled
    result = models.CharField(max_length=12, default="*")  # p1|p2|tie|*|cancel|multi
    winner = models.ForeignKey(
        SocialProfile, on_delete=models.DO_NOTHING, null=True, blank=True,
        db_column="winner_id", related_name="+",
    )
    small_blind = models.IntegerField(default=500)
    big_blind = models.IntegerField(default=1000)
    buy_in = models.IntegerField(default=20000)
    button = models.SmallIntegerField(default=1)  # HU: 1/2; multi: 0-based idx
    to_act = models.SmallIntegerField(default=1)
    street = models.CharField(max_length=12, default="preflop")
    pot = models.BigIntegerField(default=0)
    p1_stack = models.BigIntegerField(default=0)
    p2_stack = models.BigIntegerField(default=0)
    p1_bet = models.BigIntegerField(default=0)
    p2_bet = models.BigIntegerField(default=0)
    p1_hole = models.CharField(max_length=16, default="")
    p2_hole = models.CharField(max_length=16, default="")
    board = models.CharField(max_length=40, default="")
    deck = models.TextField(default="")
    last_action = models.CharField(max_length=120, default="")
    hand_label = models.CharField(max_length=120, default="")
    room = models.ForeignKey(
        PokerRoom, on_delete=models.DO_NOTHING, null=True, blank=True,
        db_column="room_id", related_name="+",
    )
    championship = models.ForeignKey(
        PokerChampionship, on_delete=models.DO_NOTHING, null=True, blank=True,
        db_column="championship_id", related_name="+",
    )
    is_rated = models.BooleanField(default=True)
    mode = models.CharField(max_length=12, default="hu")  # hu|multi
    seats_json = models.TextField(blank=True, default="[]")
    current_bet = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "poker_games"


class PokerAction(models.Model):
    id = models.BigAutoField(primary_key=True)
    game = models.ForeignKey(
        PokerGame, on_delete=models.DO_NOTHING, db_column="game_id", related_name="+",
    )
    ply = models.IntegerField()
    actor = models.ForeignKey(
        SocialProfile, on_delete=models.DO_NOTHING, db_column="actor_id", related_name="+",
    )
    action = models.CharField(max_length=16)
    amount = models.BigIntegerField(default=0)
    street = models.CharField(max_length=12, default="")
    pot_after = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "poker_actions"


class PokerLessonProgress(models.Model):
    id = models.BigAutoField(primary_key=True)
    social_user = models.ForeignKey(
        SocialProfile, on_delete=models.DO_NOTHING, db_column="social_user_id", related_name="+",
    )
    lesson_slug = models.CharField(max_length=40)
    quiz_ok = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "poker_lesson_progress"


class PokerPuzzleProgress(models.Model):
    id = models.BigAutoField(primary_key=True)
    social_user = models.ForeignKey(
        SocialProfile, on_delete=models.DO_NOTHING, db_column="social_user_id", related_name="+",
    )
    puzzle_id = models.CharField(max_length=40)
    attempts = models.IntegerField(default=0)
    solved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "poker_puzzle_progress"
