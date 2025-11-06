import jwt
import datetime
from dotenv import load_dotenv
load_dotenv()
import os
from enum import Enum

SECRET_KEY = os.getenv('SECRET_KEY')
UTC = datetime.timezone.utc

def create_jwt(email, user_id, token_version):
    payload = {
        'user_id': user_id,
        'email': email,
        'token_version': token_version,
        'exp': datetime.datetime.now(UTC) + datetime.timedelta(hours=1)  # 1시간 유효
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
    return token

def verify_jwt(token) -> tuple[bool, dict | str]:
    """
    JWT 토큰을 검증하고 페이로드를 반환
    is_valid가 False인 경우 payload는 에러 메시지 문자열
    is_valid가 True인 경우 payload는 토큰 페이로드 딕셔너리
    이 함수에서 is_valid가 True인 경우 payload의 'email'과 'token_version' 키가 None이 아님을 보장
    :param token: JWT 토큰 문자열
    :return: (is_valid: bool, payload or error message)
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        email = payload.get('email')
        session_token_version = payload.get('token_version')
        if email is None or session_token_version is None:
            return False, "Invalid token payload"
        return True, payload
    except jwt.ExpiredSignatureError:
        return False, "Token expired"
    except jwt.InvalidTokenError:
        return False, "Invalid token"