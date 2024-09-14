from pydantic import BaseModel
from typing import Optional


def single_user_serializer(user) -> dict:
    return {
        "id": str(user["_id"]),
        "username": user["username"],
        "email": user["email"],
        # "verification_code": user["verification_code"],
        "is_verified": user["is_verified"]
    }


class UserRegistrationForm(BaseModel):
    username: Optional[str]
    gender: Optional[str]
    bio: Optional[str]