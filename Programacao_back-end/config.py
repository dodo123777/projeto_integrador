import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

print(f"[config] SECRET_KEY definida: {bool(os.getenv('SECRET_KEY'))}")
print(f"[config] GEMINI_API_KEY definida: {bool(os.getenv('GEMINI_API_KEY'))}")
print(f"[config] GEMINI_MODEL: {os.getenv('GEMINI_MODEL')}")

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")

    DB_NAME = os.getenv("DB_NAME")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL")
