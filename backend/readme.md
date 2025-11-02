# DQN 자동매매 봇 백엔드
## 구조
- `user_management`
    - `database.py` : 사용하지 않음
    - `email_verification.py` : 인증 토큰 생성, 검증 및 인증 메일 전송
    - `session_manager.py` : (WIP) JWT 토큰 관리 (token 버전 관리로 무효화 가능)
    - `user_data.py` : 유저 데이터 관련 dto
- `rest_server.py`
    - REST API를 사용하는 서버
    - 키움 API 관련 엔드포인트 함수들 (인증키를 다른 곳에서 받아올 수 있도록 수정할 필요가 있어보임)
        - `get_portfolio`
        - `get_chart`
        - `get_positions`
        - 구현해야 할 기능
            - 종목 검색
            - 수동 매매
    - 유저 관리 엔드포인트 함수들
        - `send_verification`
        - `verify_email`
        - `register`
        - `login`
        - 구현해야 할 기능(아래로 갈수록 우선도 낮음)
            - `save_secret`: API키 저장. 직렬화하고 비밀번호로 암호화 해서 db에 저장하고 나중에 로그인 할 때 복호화
            - `logout` : 토큰 무효화
            - `delete_user` : db 업데이트
            - `change_password`  : 토큰 무효화, db 업데이트
            - `change_name` : db 업데이트
    - 봇 관련 함수들
        - 아직 없음
- `realtime_manager.py` : 사용하지 않음
## 사전 요구 사항
### 파이썬 의존성 설치
```bash
pip install -r requirements.txt
```
### 환경 변수 파일 설정
```dotenv
# 키움 REST API 비밀키
APP_KEY="..."
SECRET_KEY="..."

# Gmail 앱 비밀번호 설정
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587  # TLS
SENDER_EMAIL = "...@gmail.com" 
SENDER_PASSWORD = "..." # 앱 비밀번호

# 인증 링크 생성용 비밀키
# 32바이트 난수 문자열
# openssl rand -hex 32 로 생성
AUTH_SECRET_KEY = "56045b8c6751909cb50f73bacf12527b172524502eb413c2a751f13f7e208848"

# 데이터베이스 연결 문자열
DB_CONNECT_STRING = "postgresql://<username>:<password>@<ipaddr>/<table>"
```