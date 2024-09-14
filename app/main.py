from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from .routers import auth, users

app = FastAPI()
app.include_router(auth.router, prefix="/auth")
app.include_router(users.router, prefix="/users")

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins = [""],
    allow_credentials = True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Hello World!"}