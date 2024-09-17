from pydantic import BaseModel
from typing import Optional


def single_user_serializer(user) -> dict:
    return {
        "id": str(user["_id"]),
        "username": user["username"],
        "email": user["email"],
        "state_code": user["state_code"],
        "bio": user["bio"],
        "is_verified": user["is_verified"]
    }


class UserRegistrationForm(BaseModel):
    username: Optional[str] = None
    gender: Optional[str] = None
    state_code: Optional[str] = None