from fastapi import Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, EmailStr
from typing import Optional, Tuple
import bcrypt
from datetime import datetime, timezone, timedelta
from jose import JWTError, jwt
from bson import ObjectId
from aiosmtplib import send
from email.mime.text import MIMEText
import random
from .db import get_db
from .schemas import single_user_serializer
from .config import settings
from fastapi.security import OAuth2PasswordBearer

UTC = timezone.utc

oauth2_bearer = OAuth2PasswordBearer(tokenUrl='auth/token')

secret_key = settings.SECRET_KEY
algorithm = settings.ALGORITM

smtp_user = settings.SMTP_USER
smtp_pwd = settings.SMTP_USER_PWD
smtp_host = "smtp.gmail.com"
smtp_port = 465


class Token(BaseModel):
    access_token: str
    token_type: str


class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str


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

def create_verification_code(grace_period = timedelta(hours=24)) -> Tuple[int, datetime]:
    random_number = random.randint(1000000, 9999999)
    expiration_time = datetime.now(UTC) + grace_period
    return random_number, expiration_time
    
async def verify_verification_code(verification_code: int, db):
    try:
        user = await db.users.find_one({"verification_code": verification_code})
        if not user:
            raise HTTPException(status_code=400, detail="Invalid verification code")
        
        expiration_time = user.get("expiration_time")
        if expiration_time is not None and expiration_time.tzinfo is None:
            expiration_time = expiration_time.replace(tzinfo=UTC)
        
        if datetime.now(UTC) > expiration_time:
            raise HTTPException(status_code=400, detail="Verification code has expired")
        
        return user.get("email")
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"An error occurred - {e}")

async def send_verification_code(email: str, code: str, background_tasks: BackgroundTasks):
    message = MIMEText(f"Please use the code to verify your email: {code}")
    message["From"] = smtp_user
    message["To"] = email
    message["Subject"] = "Email Verification"

    background_tasks.add_task(send_email_async, message)

async def send_email_async(message):
    await send(message, hostname=smtp_host, port=smtp_port, username=smtp_user, password=smtp_pwd, use_tls=True)
