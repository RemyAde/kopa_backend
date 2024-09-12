from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    MONGODB_URL: str
    SECRET_KEY: str
    ALGORITM: str

    class Config:
        env_file = ".env"


settings = Settings()