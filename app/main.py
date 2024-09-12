from fastapi import FastAPI
from .routers import auth


app = FastAPI()
app.include_router(auth.router, prefix="/auth")

@app.get("/")
async def root():
    return {"message": "Hello World!"}