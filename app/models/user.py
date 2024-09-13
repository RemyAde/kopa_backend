from pydantic import BaseModel, EmailStr
from typing import Optional


class User(BaseModel):
    username: str
    email: EmailStr
    password: str
    verification_code: Optional[int] = None
    is_active: bool = False