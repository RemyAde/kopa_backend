from fastapi import Depends, HTTPException, BackgroundTasks, Request, UploadFile, Form, File
from pydantic import BaseModel, EmailStr, ValidationError
from typing import Optional, Tuple
import bcrypt
from datetime import datetime, timezone, timedelta
from jose import JWTError, jwt
from bson import ObjectId
from aiosmtplib import send
from email.mime.text import MIMEText
import random
from .db import get_db
from .schemas import single_user_serializer, UserRegistrationForm, BlogPostCreation
from .config import settings
from fastapi.security import OAuth2PasswordBearer
import secrets
import os

UTC = timezone.utc

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USER_UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads", "users")
BLOG_UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads", "blogs")

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

async def get_current_user(request: Request, token: str = Depends(oauth2_bearer), db = Depends(get_db)):
    try:
        payload = jwt.decode(token, secret_key, algorithms=algorithm)
        email: str = payload.get("email")
        user_id: str = payload.get("id")

        # print(f"Decoded Payload: {payload}")
        # print(f"Email: {email}, User ID: {user_id}")

        if email is None or user_id is None:
            print("invalid user")
            raise HTTPException(status_code=401, detail="Could not validate user.")
        
        # user_id = ObjectId(user_id) if isinstance(user_id, str) else user_id
        
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if user and user["is_verified"]:
            return single_user_serializer(user, request)
    
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


async def fetch_user_details(user_id: str, db):
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if user:
        return {"full_name": user["full_name"], "state_code": user.get("state_code", "Unknown")}
    return {"full_name": "Unknown", "state_code": "Unknown"}


def create_upload_directory(type: str):
    if type == "users":
        os.makedirs(USER_UPLOAD_DIR, exist_ok=True)
    elif type == "blogs":
        os.makedirs(BLOG_UPLOAD_DIR, exist_ok=True)


def validate_file_extension(type: str, filename: str):
    image_extension_list = ["png", "jpg", "jpeg", "webp"]
    if type == "users":
        extension_list = image_extension_list
    elif type == "blogs":
        extension_list = image_extension_list + ["gif" "mp4", "mkv", "webm", "mpg", "mpeg"]
    extension = os.path.splitext(filename)[-1].lower().replace(".", "")
    if extension not in extension_list:
        raise HTTPException(status_code=400, detail="Invalid file format")
    return extension


async def save_file(file: UploadFile, type: str, filename: str):
    file_content = await file.read()
    if type == "users":
        file_path = os.path.join(USER_UPLOAD_DIR, filename)
    elif type == "blogs":
        file_path = os.path.join(BLOG_UPLOAD_DIR, filename)
    with open(file_path, "wb") as document:
        document.write(file_content)
    return file_path


async def create_media_file(type: str, file: UploadFile):
    filename = file.filename
    validate_file_extension(type=type, filename=filename)
    create_upload_directory(type=type)
    extension = os.path.splitext(filename)[-1].lower().replace(".", "")
    token_name = secrets.token_hex(10) + "." + extension
    file_path = await save_file(file=file, type=type, filename=token_name)

    return token_name, file_path


async def user_registration_form(
        username: str = Form(...),
        gender: str = Form(...),
        state_code: str = Form(..., regex=r'^[A-Z]{2}/(2[4-9]|[3-9][0-9])[ABC]/\d{4}$'),
        profile_image: UploadFile = File(None)
):
    try:
        return UserRegistrationForm(
            username=username,
            gender=gender,
            state_code=state_code,
            profile_image=profile_image

        )
    except ValidationError as e:
       raise HTTPException(status_code=422, detail=e.errors())
    except ValueError as e:
     raise HTTPException(status_code=400, detail=str(e))
    

async def blog_creation_form(
        title: str = Form(...),
        content: str = Form(...),
        media: UploadFile = File(None)
):
    try:
        return BlogPostCreation(
            title=title,
            content=content,
            media=media

        )
    except ValidationError as e:
       raise HTTPException(status_code=422, detail=e.errors())
    except ValueError as e:
       raise HTTPException(status_code=400, detail=str(e))