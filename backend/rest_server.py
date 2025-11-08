from kiwoom_python.api import KiwoomAPI
from kiwoom_python.endpoints.account import *
from kiwoom_python.endpoints.chart import Chart
from kiwoom_python.model import AccountEntry

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from contextlib import asynccontextmanager

from enum import Enum
import datetime
from dotenv import load_dotenv
load_dotenv()  # .env 파일 불러오기
import os
import re
import sys
import uuid
import asyncio

from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
from psycopg import errors as pg_errors


# ===================================================
# 디버그용 파라미터
# ===================================================
VERIFY_SESSION = True

# ===================================================
# 데이터베이스 연결 설정
# ===================================================
DB_CONNECT_STRING = os.getenv("DB_CONNECT_STRING")

# 전역 변수로 커넥션 풀을 관리
# AsyncConnectionPool: psycopg 3 비동기 커넥션 풀
# NOTE: don't instantiate the pool at import time. Create it on app startup to avoid
# the deprecation warning about opening the pool in the constructor.
pool = None

# --- 3. 의존성 주입 (Dependency Injection) ---
# 각 API 요청에 대해 데이터베이스 연결을 제공하고,
# 요청이 완료되면 연결을 풀에 자동으로 반환하는 함수입니다.
async def get_db() -> AsyncConnectionPool.connection:
    async with pool.connection() as conn:
        try:
            conn.row_factory = dict_row
            yield conn
        except pg_errors.DatabaseError as e:
            print(f"데이터베이스 오류: {e}", file=sys.stderr)
            raise HTTPException(status_code=500, detail="Database error")

UTC = datetime.timezone.utc


# Pydantic model for data validation in POST request
class Position(BaseModel):
    symbol: str
    name: str
    qty: str
    avgPrice: str
    lastPrice: str
    pnl: str
    pnlPct: str


class Currency(str, Enum):
    KRW = "KRW"
    USD = "USD"


class Portfolio(BaseModel):
    currency: Currency
    totalEquity: str
    cash: str
    pnlDay: str
    pnlDayPct: str
    updatedAt: str


class PositionRequest(BaseModel):
    symbol: str


class ChartRequest(BaseModel):
    symbol: str
    base_date: str
    interval: str
    amount: int


origins = [
    "http://localhost",
    "http://localhost:8081",
    "http://192.168.0.5:8081",
    "http://100.*:8081"
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    try:
        # 앱이 시작될 때 풀 객체를 생성하고 명시적으로 연다.
        pool = AsyncConnectionPool(
            conninfo=DB_CONNECT_STRING,
            min_size=2,
            max_size=5,
        )
        await pool.open()
        yield
    finally:
        print("🛑 FastAPI 앱 종료... 커넥션 풀을 닫습니다.")
        # 앱이 종료될 때 모든 연결을 안전하게 닫습니다.
        if pool is not None:
            await pool.close()

# Create a FastAPI instance
app = FastAPI(lifespan=lifespan)
security = HTTPBearer()
appkey = os.getenv("APP_KEY")
secretkey = os.getenv("SECRET_KEY")
# 디버그용
api = KiwoomAPI(appkey, secretkey, mock=True)
acnt = Account(api)
chart = Chart(api)
# 유저 - api 매핑
apis = dict()
def get_api_for_user(secrets: dict) -> KiwoomAPI:
    user_appkey = secrets.get("appkey")
    user_secretkey = secrets.get("secretkey")
    mock = secrets.get("mock", True)
    assert user_appkey is not None and user_secretkey is not None, "API key not set properly."
    return KiwoomAPI(user_appkey, user_secretkey, mock)

# Add the CORS middleware to your app
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods (GET, POST, etc.)
    allow_headers=["*"], # Allows all headers
)

# ===================================================
# 유저 관리
# ===================================================
from user_management.user_data import *
# 이메일 인증 요청 처리
from user_management.email_verification import *
from user_management.session_manager import *
from user_management.user_repository import *
from user_management.secret_manager import *

# TODO: 가입 절차를 (생성 -> 인증 메일 발송 -> 업데이트) 에서 (인증 메일 발송 -> 생성) 으로 간소화

class VerificationRequest(BaseModel):
    email: str

class LoginResponse(BaseModel):
    message: str
    accessToken: str

async def verify_jwt_token(db = Depends(get_db), credentials: HTTPAuthorizationCredentials = Depends(security)):
    # 1. 헤더에서 토큰 추출
    token = credentials.credentials
    # 2. 토큰 복호화 및 검증
    is_valid, payload = verify_jwt(token)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=payload
        )
    # 3. 토큰 버전 쿼리
    email = payload["email"]
    session_token_version = payload["token_version"]
    result = await fetch_user_by_email(db, email)
    current_token_version = result["token_version"]
    # 4. 토큰 버전 비교
    if int(session_token_version) != current_token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token has been invalidated, {type(session_token_version)} vs {type(current_token_version)}"
        )
    # 5. api 키 복호화
    if result["apisecret"] is None:
        result['api'] = None
    else:
        AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY")
        secrets = decrypt_dict(result["apisecret"], AUTH_SECRET_KEY)
        result['api'] = get_api_for_user(secrets)
    # 6. 페이로드에 유저 정보 추가
    result["token"] = payload
    return result


# ===================================================
# API 엔드포인트


# POST request handler
@app.get("/positions")
def get_positions(user=Depends(verify_jwt_token)):
    if user["api"] is None:
        raise HTTPException(status_code=400, detail="API keys not set")
    crt = Chart(user["api"])
    resp = acnt.get_account_profit_rate()
    # positions: list[AccountEntry] = [
    #     AccountEntry("20771122", "005930", "삼성전자", 100000, 70000, 100, 100, 1.1, 1.2, 0.1)
    # ]
    ls = []
    for i in resp:
        time.sleep(1)
        if i.remainder_quantity == 0:
            continue
        current_price = crt.get_stock_tick_chart(i.stock_code, True, 1, 1)[0].close
        pos = Position(
            symbol=i.stock_code,
            name=i.stock_name,
            qty=str(i.remainder_quantity),
            avgPrice=str(i.purchase_price),
            lastPrice=str(current_price),
            pnl=str((current_price - i.purchase_price) * i.remainder_quantity),
            pnlPct=f"{current_price / i.purchase_price - 1:.3f}"
        )
        ls.append(pos)
    if len(ls) == 0:
        raise HTTPException(status_code=404, detail="Stock not found in account")
    return ls


@app.get("/portfolio")
def get_portfolio(user=Depends(verify_jwt_token)):
    if user["api"] is None:
        raise HTTPException(status_code=400, detail="API keys not set")
    acnt = Account(user["api"])
    resp = acnt.get_account_evaluation("KRX")
    pf = Portfolio(
        currency="KRW",
        totalEquity=str(resp.total_estimated),
        cash=str(resp.deposit),
        pnlDay=str(resp.daily_profit),
        pnlDayPct=str(resp.daily_profit_rate),
        updatedAt=datetime.datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S") + "Z"
    )
    return pf

@app.post("/chart/")
def get_chart(chart_request: ChartRequest, user=Depends(verify_jwt_token)):
    if user["api"] is None:
        raise HTTPException(status_code=400, detail="API keys not set")
    chart = Chart(user["api"])
    if chart_request.interval == "1D":
        resp = chart.get_stock_daily_chart(chart_request.symbol, chart_request.base_date, True, amount=chart_request.amount)
    elif chart_request.interval == "1W":
        resp = chart.get_stock_weekly_chart(chart_request.symbol, chart_request.base_date, True, amount=chart_request.amount)
    elif chart_request.interval == "1M":
        resp = chart.get_stock_monthly_chart(chart_request.symbol, chart_request.base_date, True, amount=chart_request.amount)
    else:
        raise HTTPException(status_code=422, detail=f"Unknown interval {chart_request.interval}")
    ret = [x.to_minimal_dict() for x in resp][-1:-chart_request.amount - 1:-1]
    return ret


@app.post("/auth/register/")
async def send_verification(data: UserAuthData, db=Depends(get_db)):
    email = data.email
    # 1. 이미 인증된 유저인지 검사
    # 1-1. 인증된 유저이면 에러 반환
    # 1-2. 인증된 유저가 아니면 이메일 인증
    try:
        if await is_user_exists(db, email):
            print("User already exists")
            raise HTTPException(status_code=400, detail="User already exists")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")
    # 2. 이메일 인증 토큰 생성
    AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY")
    verifier = EmailVerifier(AUTH_SECRET_KEY)
    token = verifier.generate_token(data.model_dump())
    # 3. 인증 링크 생성
    backend_base_url = os.getenv("BACKEND_BASE_URL", "http://localhost:8000")
    verification_link = f"{backend_base_url}/auth/verify/?token={token}"
    # 4. 이메일 발송
    email_sent = False
    counter = 0
    while not email_sent and counter < 3:  # 최대 3회 재시도
        email_sent = await send_verification_email(email, verification_link)
        if not email_sent:
            counter += 1
            await asyncio.sleep(2)  # 재시도 전 대기 시간
    if not email_sent:
        raise HTTPException(status_code=500, detail="Failed to send verification email")
    return {"message": "Verification email sent"}

@app.get("/auth/verify/", response_class=HTMLResponse)
async def verify_email(token: str, db=Depends(get_db)):
    # 1. 토큰 검증
    AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY")
    verifier = EmailVerifier(AUTH_SECRET_KEY)
    data = verifier.verify_token(token)  # 10분 유효
    if data is None:
        return get_verification_state_page(False, msg="토큰이 만료되었습니다.")
    if any(v is None for v in data.values()):
        return get_verification_state_page(False, msg="토큰이 유효하지 않습니다.")
    # 2. 이미 유저가 존재하는지 검사
    if await is_user_exists(db, data['email']):
        return get_verification_state_page(False, msg="이미 인증된 이메일입니다.")
    # 3. 유저 생성
    await create_user(db, data['email'], "user" + uuid.uuid4().hex[:8], PasswordProcessor().hash_password(data['password']))
    return get_verification_state_page(True)

@app.post("/auth/login/", response_model=LoginResponse)
async def login_user(user: UserAuthData, db=Depends(get_db)):
    # 1. 유저 정보 조회, 유저가 없는 경우는 fetch_user_by_email에서 예외 발생
    try:
        result = await fetch_user_by_email(db, user.email)
    except UserNotFound:
        raise HTTPException(status_code=400, detail="User not found")
    # 2. 비밀번호 검증
    pwd_processor = PasswordProcessor()
    if not pwd_processor.verify_password(user.password, result["password_hash"]):
        raise HTTPException(status_code=400, detail="Incorrect password")
    # 3. 기존 JWT 토큰 무효화 (토큰 버전 증가) (다중 접속 방지)
    await update_user_token_version(db, result["id"], result["token_version"] + 1)
    # 4. 토큰 발급
    return {"message": "Login successful", "accessToken": create_jwt(user.email, result["id"], result["token_version"] + 1)}

@app.get("/auth/logout/")
async def logout_user(db=Depends(get_db), user=Depends(verify_jwt_token)):
    # 1. 토큰 검증 및 파싱
    # 2. JWT 토큰 무효화 (토큰 버전 증가)
    token = user["token"]
    await update_user_token_version(db, token["user_id"], token["token_version"] + 1)
    return {"message": "Logout successful"}

@app.post("/auth/set_api_keys/")
async def set_api_keys(api_keys: APIKeyData, db=Depends(get_db), user=Depends(verify_jwt_token)):
    # 1. API 키 암호화
    AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY")
    encrypted_keys = encrypt_dict(api_keys.model_dump(), AUTH_SECRET_KEY)
    # 2. 데이터베이스에 저장
    await update_user_api_keys(db, user["id"], encrypted_keys)
    return {"message": "API keys set successfully"}

@app.get("/auth/get_api_keys/", response_model=APIKeyData)
async def get_api_keys(db=Depends(get_db), user=Depends(verify_jwt_token)):
    if user["apisecret"] is None:
        return APIKeyData(appkey="", secretkey="", mock=True)
    AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY")
    secrets = decrypt_dict(user["apisecret"], AUTH_SECRET_KEY)
    return APIKeyData(**secrets)

@app.delete("/auth/delete_api_keys/")
async def delete_api_keys(db=Depends(get_db), user=Depends(verify_jwt_token)):
    await update_user_api_keys(db, user["id"], None)
    return {"message": "API keys deleted successfully"}


# ===================================================
# 소켓 연결로 N:M 요청 한번에 처리 (abandoned)
# ===================================================
# from fastapi import FastAPI, Request
# from sse_starlette.sse import EventSourceResponse
# from kiwoom_python.realtime_subscription import KiwoomDataManager
# import asyncio

# @app.get("/sse")
# async def sse_endpoint(request: Request, items: str):
#     # 클라이언트가 쿼리 파라미터로 원하는 종목을 보냄 (예: /sse?items=005930,000660)
#     requested_items = items.split(',')
#     client_id = id(request) # 클라이언트 식별자

#     # ⭐️ 각 클라이언트의 요청을 DataManager에 등록
#     for item in requested_items:
#         await kiwoom_manager.add_subscriber(client_id, item)

#     async def event_generator():
#         try:
#             while True:
#                 # ⭐️ DataManager의 큐에서 새로운 데이터가 들어오기를 기다림
#                 data = await kiwoom_manager.data_queue.get()
#                 item_code = data.get('item', {}).get('code')
                
#                 # ⭐️ 요청한 종목의 데이터인지 확인 후 전송
#                 if item_code and item_code in requested_items:
#                     yield {"event": "realtime_update", "data": json.dumps(data)}
                
#         finally:
#             # ⭐️ 클라이언트 연결이 끊기면 구독 해지
#             for item in requested_items:
#                 await kiwoom_manager.remove_subscriber(client_id, item)

#     return EventSourceResponse(event_generator())