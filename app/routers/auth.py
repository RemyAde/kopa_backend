from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from starlette import status
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated
from datetime import datetime, timedelta, timezone
from app.models.user import User
from app.db import get_db
# from app.schemas import single_user_serializer
from app.utils import (Token, UserCreate, hash_password, authenticate_user, create_access_token, create_verification_code, verify_verification_code, send_verification_code)
from fastapi import Form


UTC = timezone.utc
router = APIRouter()


class OAuth2PasswordRequestFormEmail(OAuth2PasswordRequestForm):
    def __init__(
        self,
        email: str = Form(...),  # Use 'email' instead of 'username'
        password: str = Form(...),
        scope: str = Form(""),
        client_id: str = Form(None),
        client_secret: str = Form(None),
    ):
        super().__init__(username=email, password=password, scope=scope, client_id=client_id, client_secret=client_secret)


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def singup(user: UserCreate, background_tasks: BackgroundTasks, db=Depends(get_db)):
    """
   - Description: Create a new user account.
   - Request Body:
     - user: UserCreate (includes `full_name`, `email`, and `password`)
   - Response:
     - 201 Created: User created successfully. Check your email for your verification code.
     - 400 Bad Request: User already exists.
     """
    new_user = User(
        full_name=user.full_name,
        email = user.email,
        password = hash_password(password=user.password)
    )

    existing_user = await db.users.find_one({"email": new_user.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists.")
    
    db['users'].insert_one(new_user.model_dump())

    code, expiration_time = create_verification_code()
    await db["users"].update_one({"email": new_user.email}, {"$set": {"verification_code": code, "expiration_time": expiration_time, "verification_sent_at": datetime.now(UTC)}})
    await send_verification_code(new_user.email, code, background_tasks)

    # user_data = single_user_serializer(await db.users.find_one({"email": new_user.email}))

    return {"message": "User created successfully. Check your email for your verification code."}


@router.post("/resend-verification")
async def resend_verification_code(email: str, background_tasks: BackgroundTasks, db=Depends(get_db)):
    """
    - Description: Resend the verification code to the user's email.
   - Request Body:
     - email: str
   - Response:
     - 200 OK: A new verification code has been sent to your email.
     - 404 Not Found: User not found.
     - 400 Bad Request: User already verified.
     - 429 Too Many Requests: You can only request a new verification email every 1 minute.
     """
    # Retrieve user from the database
    user = await db["users"].find_one({"email": email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    # Check if the user is already verified
    if user.get("is_verified"):
        raise HTTPException(status_code=400, detail="User already verified.")

    # Rate-limit resend requests
    last_sent_time = user.get("verification_sent_at")
    if last_sent_time is not None and last_sent_time.tzinfo is None:
        last_sent_time = last_sent_time.replace(tzinfo=UTC)

    if last_sent_time and (datetime.now(UTC) - last_sent_time).total_seconds() < 60:  # Cooldown of 1 minute
        raise HTTPException(status_code=429, detail="You can only request a new verification email every 1 minute.")

    # Generate a new verification code and expiration time
    code, expiration_time = create_verification_code()

    # Update the user with the new verification code and expiration time
    await db["users"].update_one(
        {"email": email},
        {"$set": {"verification_code": code, "expiration_time": expiration_time, "verification_sent_at": datetime.now(UTC)}}
    )

    # Resend the verification email
    await send_verification_code(email, code, background_tasks)

    return {"message": "A new verification code has been sent to your email."}


@router.get("/verify-email")
async def verify_email(code: int, db=Depends(get_db)):
    """
     - Description: Verify the user's email using the provided code.
   - Query Parameters:
     - code: int
   - Response:
     - 200 OK: Email verified successfully.
     - 400 Bad Request: Invalid or expired token.
     - 404 Not Found: User not found.
     """
    email = await verify_verification_code(code, db)
    if email is None:
        raise HTTPException(status_code=400, detail="Invalid or expired token.")
    user = await db.users.find_one({"email": email})
    if user:
        await db.users.update_one({"email": email}, {"$set": {"is_verified": True}})
        return {"message": "Email verfied successfully."}
    else:
        raise HTTPException(status_code=404, detail="User not found.")


@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestFormEmail = Depends(), db=Depends(get_db)):
    """
    - Description: Authenticate the user and provide an access token.
   - Request Body:
     - form_data: OAuth2PasswordRequestFormEmail (includes `email` and `password`)
   - Response:
     - 200 OK: Returns an access token and token type.
     - 401 Unauthorized: Invalid email or password.
     """
    user = await authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token_expires = timedelta(minutes=60)
    token = create_access_token(user['email'], str(user["_id"]), expires_delta=token_expires)
    return {"access_token": token, "token_type": "bearer"}
