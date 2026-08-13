"""Unmanaged chess tables (created by deploy/ensure-chess-modules.py)."""
from django.db import models

from apps.social.models import SocialProfile


class ChessRating(models.Model):
    social_user = models.OneToOneField(
        SocialProfile, on_delete=models.DO_NOTHING, primary_key=True, db_column="social_user_id",
        related_name="+",
    )
    rating = models.IntegerField(default=1200)
    games = models.IntegerField(default=0)
    wins = models.IntegerField(default=0)
    losses = models.IntegerField(default=0)
    draws = models.IntegerField(default=0)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "chess_ratings"


class ChessChampionship(models.Model):
    id = models.BigAutoField(primary_key=True)
    week_key = models.CharField(max_length=12)  # 2026-W33
    title = models.CharField(max_length=120)
    starts_on = models.DateField()
    ends_on = models.DateField()
    status = models.CharField(max_length=12, default="open")  # open|closed
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "chess_championships"


class ChessChampEntry(models.Model):
    id = models.BigAutoField(primary_key=True)
    championship = models.ForeignKey(
        ChessChampionship, on_delete=models.DO_NOTHING, db_column="championship_id", related_name="+",
    )
    social_user = models.ForeignKey(
        SocialProfile, on_delete=models.DO_NOTHING, db_column="social_user_id", related_name="+",
    )
    points = models.IntegerField(default=0)
    wins = models.IntegerField(default=0)
    losses = models.IntegerField(default=0)
    draws = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = "chess_champ_entries"


class ChessGame(models.Model):
    id = models.BigAutoField(primary_key=True)
    white = models.ForeignKey(
        SocialProfile, on_delete=models.DO_NOTHING, db_column="white_id", related_name="+",
    )
    black = models.ForeignKey(
        SocialProfile, on_delete=models.DO_NOTHING, db_column="black_id", related_name="+",
    )
    fen = models.CharField(max_length=100)
    status = models.CharField(max_length=16, default="active")  # active|check|mate|draw|resign|timeout
    result = models.CharField(max_length=8, default="*")  # 1-0|0-1|1/2-1/2|*
    turn = models.CharField(max_length=1, default="w")
    championship = models.ForeignKey(
        ChessChampionship, on_delete=models.DO_NOTHING, null=True, blank=True,
        db_column="championship_id", related_name="+",
    )
    winner = models.ForeignKey(
        SocialProfile, on_delete=models.DO_NOTHING, null=True, blank=True,
        db_column="winner_id", related_name="+",
    )
    draw_offer_by = models.ForeignKey(
        SocialProfile, on_delete=models.DO_NOTHING, null=True, blank=True,
        db_column="draw_offer_by_id", related_name="+",
    )
    # Chess clocks (0 = unlimited). Time runs only on the side to move.
    time_control_sec = models.IntegerField(default=0)
    increment_sec = models.IntegerField(default=0)
    white_clock_ms = models.BigIntegerField(default=0)
    black_clock_ms = models.BigIntegerField(default=0)
    clock_running_since = models.DateTimeField(null=True, blank=True)
    moves_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "chess_games"

    @property
    def result_label(self) -> str:
        return {
            "1-0": "победа белых",
            "0-1": "победа чёрных",
            "1/2-1/2": "ничья",
            "*": "идёт партия",
        }.get(self.result, self.result)


class ChessMove(models.Model):
    id = models.BigAutoField(primary_key=True)
    game = models.ForeignKey(
        ChessGame, on_delete=models.DO_NOTHING, db_column="game_id", related_name="+",
    )
    ply = models.IntegerField()
    from_sq = models.CharField(max_length=2)
    to_sq = models.CharField(max_length=2)
    san = models.CharField(max_length=16)
    fen_after = models.CharField(max_length=100)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "chess_moves"


class ChessLessonProgress(models.Model):
    id = models.BigAutoField(primary_key=True)
    social_user = models.ForeignKey(
        SocialProfile, on_delete=models.DO_NOTHING, db_column="social_user_id", related_name="+",
    )
    lesson_slug = models.CharField(max_length=40)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "chess_lesson_progress"
