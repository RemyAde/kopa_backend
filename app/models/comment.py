from pydantic import BaseModel
from datetime import datetime, timezone

UTC = timezone.utc


class CommentCreate(BaseModel):
    content: str


class Comment(CommentCreate):
    user_id: int
    created_at: datetime = datetime.now(UTC)