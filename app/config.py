from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    MONGODB_URL: str
    SECRET_KEY: str
    ALGORITM: str
    SMTP_USER: str
    SMTP_USER_PWD: str


    class Config:
        env_file = ".env"


settings = Settings()