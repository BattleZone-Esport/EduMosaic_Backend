"""Achievement service placeholder"""

from sqlalchemy.orm import Session


class AchievementService:
    @staticmethod
    def get_all_achievements(db):
        return []

    @staticmethod
    def get_user_achievements(db, user_id):
        return []

    @staticmethod
    def get_all_badges(db):
        return []

    @staticmethod
    def get_user_badges(db, user_id):
        return []

    @staticmethod
    def check_and_award_achievements(db, current_user):
        return []
