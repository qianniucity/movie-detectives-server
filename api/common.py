from pydantic import BaseModel, ConfigDict
from datetime import datetime

class BaseQuestion(BaseModel):
    question: str
    hint1: str
    hint2: str


class BaseAnswer(BaseModel):
    points: int
    answer: str
    
    
class SessionData(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    quiz_id: str
    # chat: ChatSession
    question: BaseQuestion
    movie: dict
    started_at: datetime


class UserAnswer(BaseModel):
    answer: str


class StartQuizResponse(BaseModel):
    quiz_id: str
    question: BaseQuestion
    movie: dict


class FinishQuizResponse(BaseModel):
    quiz_id: str
    question: BaseQuestion
    movie: dict
    user_answer: str
    result: BaseAnswer


class SessionResponse(BaseModel):
    quiz_id: str
    question: BaseQuestion
    movie: dict
    started_at: datetime


class LimitResponse(BaseModel):
    daily_limit: int
    quiz_count: int
    last_reset_time: datetime
    last_reset_date: datetime
    current_date: datetime


class Stats(BaseModel):
    quiz_count_total: int = 0
    points_total: int = 0


class StatsResponse(BaseModel):
    stats: Stats
    limit: LimitResponse
