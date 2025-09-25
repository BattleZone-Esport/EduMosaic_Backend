"""Leaderboard schemas"""

from datetime import datetime

from pydantic import BaseModel


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: int
    username: str
    score: int
    quizzes_taken: int
    accuracy: float
