"""Notification service placeholder"""

from sqlalchemy.orm import Session


class NotificationService:
    @staticmethod
    def get_user_notifications(db, user_id, unread_only, skip, limit):
        return []

    @staticmethod
    def mark_as_read(db, notification_id, user_id):
        pass

    @staticmethod
    def mark_all_as_read(db, user_id):
        pass

    @staticmethod
    def delete_notification(db, notification_id, user_id):
        pass
