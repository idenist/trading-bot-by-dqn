from kiwoom_python.api import KiwoomAPI
from kiwoom_python.endpoints.account import *
from kiwoom_python.endpoints.chart import Chart
from kiwoom_python.model import AccountEntry

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager

from enum import Enum
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
load_dotenv()  # .env 파일 불러오기
import os
import re
import sys
import uuid
import asyncio

from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row

# ===================================================
# 데이터베이스 연결 설정
# ===================================================
DB_CONNECT_STRING = os.getenv("DB_CONNECT_STRING")

# 전역 변수로 커넥션 풀을 관리
# AsyncConnectionPool: psycopg 3 비동기 커넥션 풀
pool = AsyncConnectionPool(
    conninfo=DB_CONNECT_STRING,
    min_size=2,
    max_size=5,
)

# --- 3. 의존성 주입 (Dependency Injection) ---
# 각 API 요청에 대해 데이터베이스 연결을 제공하고,
# 요청이 완료되면 연결을 풀에 자동으로 반환하는 함수입니다.
async def get_db():
    async with pool.connection() as conn:
        try:
            conn.row_factory = dict_row
            yield conn
        except Exception as e:
            print(f"데이터베이스 연결 또는 작업 오류: {e}", file=sys.stderr)
            raise HTTPException(status_code=500, detail="Database error")

UTC = ZoneInfo("UTC")


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
    "http://192.168.0.5:8081"
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # 앱이 시작될 때 커넥션 풀을 열고 연결을 생성합니다.
        await pool.open()
        yield
        # 'yield' 이후는 앱 종료 시 실행됩니다.
    finally:
        print("🛑 FastAPI 앱 종료... 커넥션 풀을 닫습니다.")
        # 앱이 종료될 때 모든 연결을 안전하게 닫습니다.
        await pool.close()
    yield

# Create a FastAPI instance
app = FastAPI(lifespan=lifespan)
appkey = os.getenv("APP_KEY")
secretkey = os.getenv("SECRET_KEY")
api = KiwoomAPI(appkey, secretkey, mock=True)
acnt = Account(api)
chart = Chart(api)

# Add the CORS middleware to your app
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods (GET, POST, etc.)
    allow_headers=["*"], # Allows all headers
)

# POST request handler
@app.get("/positions")
def get_positions():
    crt = Chart(api)
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
def get_portfolio():
    resp = acnt.get_account_evaluation("KRX")
    pf = Portfolio(
        currency="KRW",
        totalEquity=str(resp.total_estimated),
        cash=str(resp.deposit),
        pnlDay=str(resp.daily_profit),
        pnlDayPct=str(resp.daily_profit_rate),
        updatedAt=datetime.now().astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S") + "Z"
    )
    return pf

@app.post("/chart/")
def get_chart(chart_request: ChartRequest):
    print(chart_request.interval)
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

# ===================================================
# 유저 관리
# ===================================================
from user_management.user_data import *
# 이메일 인증 요청 처리
from user_management.email_verification import EmailVerifier, send_verification_email


class VerificationRequest(BaseModel):
    email: str

@app.post("/auth/send_verification_email/")
async def send_verification(data: VerificationRequest, db=Depends(get_db)):
    email = data.email
    # 1. 이미 인증된 유저인지 검사
    # 1-1. 인증된 유저이면 에러 반환
    # 1-2. 인증된 유저가 아니면 이메일 인증
    try:
        # 'db' 객체(연결)를 의존성 주입으로 받음
        async with db.cursor() as cur:
            await cur.execute("SELECT is_verified FROM users WHERE email = %s", (email,))
            result = await cur.fetchone()
            if result is not None and result["is_verified"]:
                raise HTTPException(status_code=400, detail="User already verified")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")
    # 2. 이메일 인증 토큰 생성
    SECRET_KEY = os.getenv("AUTH_SECRET_KEY")
    verifier = EmailVerifier(SECRET_KEY)
    token = verifier.generate_token(email)
    # 3. 인증 링크 생성
    verification_link = f"http://localhost:8000/auth/verify/?token={token}"
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

@app.get("/auth/verify/")
async def verify_email(token: str, db=Depends(get_db)):
    # 1. 토큰 검증
    SECRET_KEY = os.getenv("AUTH_SECRET_KEY")
    verifier = EmailVerifier(SECRET_KEY)
    is_valid = verifier.verify_token(token)  # 10분 유효
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid or expired token")
    email = verifier.get_email_from_token(token)
    if email is None:
        raise HTTPException(status_code=400, detail="Invalid token data")
    # 2. 유저 인증 상태 업데이트
    try:
        async with db.cursor() as cur:
            await cur.execute(
                "UPDATE users SET is_verified = %s WHERE email = %s;",
                (True, email)
            )
            await db.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update user verification status: {e}")
    return {"message": "Email verified successfully"}

@app.post("/auth/register/")
async def register_user(user: UserRegistration, db=Depends(get_db)):
    print(f"Registering user: {user.email}, {user.password}")
    # 1. 이미 가입한 유저인지 확인
    try:
        async with db.cursor() as cur:
            await cur.execute("SELECT 1 FROM users WHERE email=%s;", (user.email,))
            result = await cur.fetchone()
            if result is not None:
                raise HTTPException(status_code=400, detail="User already registered")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")
    # 2. 비밀번호 해싱
    pwd_processor = PasswordProcessor()
    hashed_password = pwd_processor.hash_password(user.password)
    # 2-1 (임시: 사용자 이름 생성)
    user_name = "user" + uuid.uuid4().hex[:8]
    # 3. 유저 정보 저장
    try:
        async with db.cursor() as cur:
            await cur.execute(
                "INSERT INTO users (email, password_hash, is_verified, user_name) VALUES (%s, %s, %s, %s);",
                (user.email, hashed_password, False, user_name)
            )
            await db.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to register user: {e}")
    return {"message": "User registered successfully"}

@app.post("/auth/login/")
async def login_user(user: UserRegistration, db=Depends(get_db)):
    # 1. 유저 정보 조회
    try:
        async with db.cursor() as cur:
            await cur.execute("SELECT password_hash, is_verified FROM users WHERE email=%s;", (user.email,))
            result = await cur.fetchone()
            # 1-1. 유저 존재 여부
            if result is None:
                raise HTTPException(status_code=400, detail="User not found")
            # 1-2. 이메일 인증 여부
            if not result["is_verified"]:
                raise HTTPException(status_code=400, detail="User not verified")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")
    # 2. 비밀번호 검증
    pwd_processor = PasswordProcessor()
    if not pwd_processor.verify_password(user.password, result["password_hash"]):
        raise HTTPException(status_code=400, detail="Incorrect password")
    # 3. [TODO]: 세션 생성 및 토큰 발급
    return {"message": "Login successful"}




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