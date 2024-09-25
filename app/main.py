from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from .routers import auth, users, blogs
from fastapi.staticfiles import StaticFiles
import os 

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
directory = os.path.join(BASE_DIR, "static")

app = FastAPI()
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(users.router, prefix="/user", tags=["users"])
app.include_router(blogs.router, prefix="/newsfeed", tags=["newsfeed"])


# Static files
app.mount("/static", StaticFiles(directory=directory), name="static")

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