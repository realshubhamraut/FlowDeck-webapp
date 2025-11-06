import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DATABASE = os.environ.get('DATABASE') or 'flowdeck.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
