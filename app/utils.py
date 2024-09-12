from fastapi import Depends, HTTPException
from pydantic import BaseModel
import bcrypt
from datetime import datetime, UTC, timedelta
from jose import JWTError, jwt
from bson import ObjectId
from .db import get_db
from .schemas import single_user_serializer
from .config import settings
from fastapi.security import OAuth2PasswordBearer

oauth2_bearer = OAuth2PasswordBearer(tokenUrl='auth/token')

secret_key = settings.SECRET_KEY
algorithm = settings.ALGORITM


class Token(BaseModel):
    access_token: str
    token_type: str


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed_password

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(email: str, user_id: str, expires_delta: timedelta):
    encode = {"email": email, "id": user_id}
    expires = datetime.now(UTC) + expires_delta
    encode.update({"exp": expires})
    return jwt.encode(encode, secret_key, algorithm)

async def authenticate_user(email: str, password: str, db=Depends(get_db)):
    user =  await db.users.find_one({"email": email})
    if not user:
        return False
    hashed_password = user["password"]
    if not verify_password(plain_password=password, hashed_password=hashed_password):
        return False
    return user

async def get_current_user(token: str = Depends(oauth2_bearer), db = Depends(get_db)):
    try:
        payload = jwt.decode(token, secret_key, algorithms=algorithm)
        email: str = payload.get("email")
        user_id: str = payload.get("id")

        print(f"Decoded Payload: {payload}")
        print(f"Email: {email}, User ID: {user_id}")

        if email is None or user_id is None:
            print("invalid user")
            raise HTTPException(status_code=401, detail="Could not validate user.")
        
        # user_id = ObjectId(user_id) if isinstance(user_id, str) else user_id
        
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if user:
            return single_user_serializer(user)
    
    except JWTError as e:
        print(f"JWT Error {e}")
        raise HTTPException(status_code=401, detail="JWT Error - could not validate user.")