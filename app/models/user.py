from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timezone

UTC = timezone.utc


class User(BaseModel):
    username: Optional[str] = None
    full_name: str
    email: EmailStr
    gender: Optional[str] = None
    password: str
    bio: Optional[str] = None
    verification_code: Optional[int] = None
    verification_sent_at: Optional[datetime] = None
    expiration_time: Optional[datetime] = None
    is_verified: bool = False
    created_at: datetime = datetime.now(UTC)