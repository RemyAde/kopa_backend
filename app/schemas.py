from fastapi import File, Form, UploadFile
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

UTC = timezone.utc

def single_user_serializer(user) -> dict:
    return {
        "id": str(user["_id"]),
        "username": user["username"],
        "full_name": user["full_name"],
        "state_code": user["state_code"],
        "email": user["email"],
        "state_code": user["state_code"],
        "bio": user["bio"],
        "is_verified": user["is_verified"]
    }


class UserRegistrationForm(BaseModel):
    username: str
    gender: str
    state_code: str
    profile_image: Optional[UploadFile] = None


class BlogPostCreation(BaseModel):
    title: str
    content: str
    media: Optional[UploadFile] = None


class BlogPostUpdate(BaseModel):
    title: str
    content: str
    updated_at: datetime = datetime.now(UTC)


def single_blog_serializer(blog, user):
    return {
        "id": str(blog["_id"]),
        "title": blog["title"],
        "content": blog["content"],
        "likes": blog["likes"],
        "comments": blog["comments"],
        "posted_at": blog["created_at"],
        "updated_at": blog["updated_at"],
        "author": user["full_name"],
        "state_code": user["state_code"]
    }