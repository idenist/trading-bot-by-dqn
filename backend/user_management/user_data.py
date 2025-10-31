# 비밀번호 해싱
from pydantic import BaseModel

import bcrypt

class PasswordProcessor:
    def __init__(self):
        pass

    def hash_password(self, password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    
class User(BaseModel):
    """basic user data structure"""
    email: str
    password_hash: str
    is_verified: bool = False
    user_name: str | None = None

class UserRegistration(BaseModel):
    """user registration data structure"""
    email: str
    password: str