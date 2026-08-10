"""Analytics schemas — summary response models."""

from pydantic import BaseModel


class DailyCount(BaseModel):
    """Conversation count for a single day."""

    date: str
    count: int


class AnalyticsResponse(BaseModel):
    """Aggregated analytics snapshot for a tenant."""

    total_conversations: int
    answered_count: int
    unanswered_count: int
    answer_rate: float
    conversations_today: int
    top_sources: list[str]
    daily_counts: list[DailyCount]
    unanswered_questions: list[str]
