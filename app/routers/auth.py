from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated
from datetime import timedelta
from app.models.user import User
from app.db import get_db
from jose import jwt
from app.utils import hash_password, verify_password, authenticate_user, create_access_token, Token, get_current_user
from fastapi import Form


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

'''
class OAuth2EmailRequestForm:
    def __init__(
        self, 
        email: str = Form(...), 
        password: str = Form(...),
    ):
        self.email = email
        self.password = password
'''

router = APIRouter()


@router.post("/signup")
async def singup(user: User, db=Depends(get_db)):
    new_user = User(
        username = user.username,
        email = user.email,
        password = hash_password(password=user.password)
    )
    db['users'].insert_one(new_user.model_dump())
    return {"message": "User created successfully"}


@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestFormEmail = Depends(), db=Depends(get_db)):
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


@router.get("/me")
async def read_user_details(user = Depends(get_current_user)):
    if user is None:
        print("user dependency returned None")
        raise HTTPException(status_code=401, detail="Authentication failed")
    
    return user