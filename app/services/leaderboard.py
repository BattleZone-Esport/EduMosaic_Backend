"""Leaderboard service placeholder"""

from sqlalchemy.orm import Session


class LeaderboardService:
    @staticmethod
    def get_global_leaderboard(db, period, limit):
        return []

    @staticmethod
    def get_category_leaderboard(db, category_id, period, limit):
        return []

    @staticmethod
    def get_user_rank(db, user_id, category_id):
        return {"rank": 0, "score": 0}
