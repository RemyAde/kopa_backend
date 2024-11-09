from pydantic import BaseModel
from typing import List
from datetime import datetime, timezone

UTC = timezone.utc


class Message(BaseModel):
    sender: str
    content: str
    timestamp: datetime = datetime.now(UTC)

class ChatRoom(BaseModel):
    name: str
    members: List[str] = []
    messages: List[Message]