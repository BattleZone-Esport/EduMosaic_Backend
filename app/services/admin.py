"""Admin service placeholder"""

from sqlalchemy.orm import Session


class AdminService:
    @staticmethod
    def get_dashboard_stats(db):
        return {"total_users": 0, "active_users": 0, "total_quizzes": 0, "total_questions": 0}

    @staticmethod
    def get_users(db, role, is_active, skip, limit):
        return []

    @staticmethod
    def update_user_status(db, user_id, is_active):
        return {"success": True}

    @staticmethod
    def update_user_role(db, user_id, role):
        return {"success": True}
