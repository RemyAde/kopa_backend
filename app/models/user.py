from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class User(BaseModel):
    username: Optional[str] = None
    email: EmailStr
    password: str
    verification_code: Optional[int] = None
    expiration_time: Optional[datetime] = None
    is_active: bool = False