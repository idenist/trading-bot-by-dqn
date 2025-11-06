# DQN 자동매매 봇 백엔드
## 구조
- `user_management`
    - `database.py` : 사용하지 않음
    - `email_verification.py` : 인증 토큰 생성, 검증 및 인증 메일 전송
    - `session_manager.py` : (WIP) JWT 토큰 관리 (token 버전 관리로 무효화 가능)
    - `user_data.py` : 유저 데이터 관련 dto
    - `database.py` : 사용하지 않음 (user_repository)로 대체
    - `user_repository.py` : DB 연결 추상화 계층
    - `secret_manager.py` : 민감한 정보 암호화/복호화
- `rest_server.py`
    - REST API를 사용하는 서버
    - 키움 API 관련 엔드포인트 함수들 (인증키를 다른 곳에서 받아올 수 있도록 수정할 필요가 있어보임)
        - `get_portfolio`
        - `get_chart`
        - `get_positions`
        - 구현해야 할 기능
            - 종목 검색
            - 수동 매매
    - API 문서
        - 서버를 작동시키고
        - [API Document](http://localhost:8000/docs) 접속
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
# https://myaccount.google.com/apppasswords 접속
# 앱 이름 적당이 작성 후 비밀번호 생성 하여 SENDER_PASSWORD에 복사 붙여넣기
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587  # TLS
SENDER_EMAIL = "...@gmail.com" 
SENDER_PASSWORD = "..." # 앱 비밀번호

# 인증 링크 생성용 비밀키
# 32바이트 난수 문자열
# openssl rand -hex 32 로 생성
AUTH_SECRET_KEY = "..."

# 데이터베이스 연결 문자열
# tailscale을 사용하면 제 서버를 공유해드릴 수 있습니다.
DB_CONNECT_STRING = "postgresql://<username>:<password>@<ipaddr>/<table>"
```
### 데이터베이스
- 테이블 구조
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    user_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    token_version INTEGER NOT NULL DEFAULT 0,
    apisecret TEXT
);
```
- `id`: 인덱스용 아이디
- `user_name`: 유저 이름
- `email`: 이메일 주소
- `password_hash`: 비밀번호 솔트 해쉬
- `token_version`: 토큰 무효화용 값 
    - 만료시간 전 무효화 시키려면 이 값을 변경
- `apisecret`: 암호화된 api키 딕셔너리 (dict -> json -> string -> encrypted)