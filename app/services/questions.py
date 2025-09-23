"""Question service placeholder"""

from sqlalchemy.orm import Session


class QuestionService:
    @staticmethod
    def get_questions(db, quiz_id, category_id, skip, limit):
        return []

    @staticmethod
    def get_question(db, question_id):
        return None

    @staticmethod
    def create_question(db, question_data, current_user):
        return {}

    @staticmethod
    def update_question(db, question_id, question_data, current_user):
        return {}

    @staticmethod
    def delete_question(db, question_id):
        pass
