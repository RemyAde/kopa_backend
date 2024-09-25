from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone

UTC = timezone.utc


class Blog(BaseModel):
    title: str
    content: str
    media: Optional[str] = None
    author: str
    likes: int = 0
    liked_by: Optional[List[str]] = None
    comments: List[str] = []
    created_at: datetime = datetime.now(UTC)
    updated_at: Optional[datetime] = None