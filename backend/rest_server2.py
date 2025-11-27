from kiwoom_python.api import KiwoomAPI
from kiwoom_python.endpoints.account import *
from kiwoom_python.endpoints.chart import Chart
from kiwoom_python.endpoints.stock_info import StockInfo as KiwoomStockInfo
from kiwoom_python.model import AccountEntry
from kiwoom_python.exceptions import KiwoomApiError
from kiwoom_python.endpoints.order import Order, TradeType

from fastapi import FastAPI, Depends, HTTPException, Request, status, Query
from fastapi.responses import HTMLResponse, JSONResponse
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

from typing import List, Optional   # 파일 상단 import 에 추가

import time
from threading import Thread, Event, Lock
import requests

# Kiwoom REST 클라이언트 (단일 계정용)
kiwoom_api: KiwoomAPI | None = None
account_client: Account | None = None
chart_client: Chart | None = None

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

# ===== 자동매매 쿨다운 설정 =====
AUTO_TRADE_MIN_INTERVAL_SEC = 7200  # ✅ 종목별 최소 2시간(7200초) 간격
last_trade_at: dict[str, float] = {}

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
    interval: str
    amount: int
    base_date: str | None = None   # 옵션

    
class Stock(BaseModel):
    symbol: str
    name: str
    market: Optional[str] = None

class StockInfo(BaseModel):
    symbol: str
    name: str
    price: float
    changePct: float          # 0.0123 = +1.23%
    volume: Optional[int] = None
    marketCap: Optional[float] = None

class AutoTradeStart(BaseModel):
    stocks: List[str]
    amount_per_stock: int = 1_000_000

class OrderRequest(BaseModel):
    symbol: str
    side: str      # "BUY" | "SELL"
    type: str      # "MARKET" | "LIMIT"
    price: float
    qty: int

origins = [
    "http://localhost",
    "http://localhost:8081",
    "http://192.168.0.5:8081",
    "http://100.*:8081",
    "http://100.100.182.104:8081",
]

if os.path.exists("stock_master.json"):
    with open("stock_master.json", "r", encoding="utf-8") as f:
        tmp = json.load(f)
        STOCK_MASTER_STATIC = [Stock(**s) for s in tmp]
else:
    STOCK_MASTER_STATIC = []

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

# 유저 - api 매핑
apis = dict()
def get_api_for_user(email: str, secrets: dict) -> KiwoomAPI:
    if email in apis:
        return apis[email]
    user_appkey = secrets.get("appkey")
    user_secretkey = secrets.get("secretkey")
    mock = secrets.get("mock", True)
    assert user_appkey is not None and user_secretkey is not None, "API key not set properly."
    api = KiwoomAPI(user_appkey, user_secretkey, mock)
    apis[email] = api
    return api

# Add the CORS middleware to your app
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods (GET, POST, etc.)
    allow_headers=["*"], # Allows all headers
)

# ===================================================
# 키움 API 에러 핸들러
# ===================================================
@app.exception_handler(KiwoomApiError)
async def key_error_exception_handler(request: Request, exc: KiwoomApiError):
    return JSONResponse(
        status_code=500, 
        content={
            "kiwoom_error_code": exc.error_code,
            "reason": exc.reason,
            "detail": exc.detail,
        }
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
def verify_jwt_token(get_api=False):
    async def __f(db = Depends(get_db), credentials: HTTPAuthorizationCredentials = Depends(security)):
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
            result['api'] = get_api_for_user(email, secrets)

        # 6. 페이로드에 유저 정보 추가
        result["token"] = payload
        return result
    return __f
    
def _send_order_rest(
    api: KiwoomAPI,
    side: str,
    symbol: str,
    qty: int,
    price: int,
    stex_type: str = "KRX",
) -> tuple[bool, str | None, str | None]:
    """
    실제 키움 REST 주문 래핑

    returns: (success, order_no, error_message)
    """
    # side 정규화
    side = side.upper()

    # 가격/매매 타입 매핑
    # - price == 0  → 시장가
    # - price > 0   → 보통(지정가)
    if price and price > 0:
        trade_type = TradeType.보통.value       # 지정가
        order_unit_value = price
    else:
        trade_type = TradeType.시장가.value    # 시장가
        order_unit_value = 0

    order_client = Order(api)

    try:
        if side == "BUY":
            ord_no = order_client.buy(
                stex_type=stex_type,             # "KRX" (모의투자도 KRX)
                stock_code=symbol,
                order_quantity=qty,
                trade_type=trade_type,
                order_unit_value=order_unit_value,
                conditional_unit_value=0,
            )
        elif side == "SELL":
            ord_no = order_client.sell(
                stex_type=stex_type,
                stock_code=symbol,
                order_quantity=qty,
                trade_type=trade_type,
                order_unit_value=order_unit_value,
                conditional_unit_value=0,
            )
        else:
            return False, None, f"unknown side: {side}"

        # 이 래퍼는 실패 시 print만 하고 ord_no를 리턴하니까,
        # 일단 ord_no가 비어 있지 않으면 성공으로 간주
        print("SEX")
        if not ord_no:
            return False, None, "empty order number"

        return True, ord_no, None

    except KiwoomApiError as e:
        # 전역 핸들러도 있긴 하지만 /order는 200 + 실패 메시지 주는 게 프론트에서 다루기 편함
        return False, None, f"{e.reason} ({e.error_code})"

    except Exception as e:
        return False, None, str(e)

def _send_order_with_api(
    api: KiwoomAPI,
    side: str,
    symbol: str,
    qty: int,
    price: int = 0,   # 0 이면 시장가
) -> tuple[bool, str, str | None]:
    """
    실제 Kiwoom REST 주문 실행

    returns: (success, message, order_no or None)
    """
    ord_client = Order(api)

    side = side.upper()
    is_market = (price == 0)
    trade_type = TradeType.시장가.value if is_market else TradeType.보통.value

    try:
        if side == "BUY":
            ord_no = ord_client.buy("KRX", symbol, qty, trade_type, price)
        elif side == "SELL":
            ord_no = ord_client.sell("KRX", symbol, qty, trade_type, price)
        else:
            return False, f"Unknown side: {side}", None

        return True, "OK", ord_no
    except KiwoomApiError as e:
        # kiwoom_python 이 파싱해준 reason을 우선 사용
        msg = e.reason or e.detail or "Kiwoom API error"
        print(f"[ORDER-ERROR] {symbol} {side} x{qty} @ {price or 'MKT'}: {msg}")
        return False, msg, None
    except Exception as e:
        msg = f"Unexpected error: {e}"
        print(f"[ORDER-ERROR] {symbol} {side} x{qty} @ {price or 'MKT'}: {msg}")
        return False, msg, None

def _auto_trade_worker(
    user_id: int,
    api: KiwoomAPI,
    stocks: list[str],
    amount_per_stock: int,
    stop_event: Event,
):
    global last_trade_at  # ✅ 전역 쿨다운 딕셔너리 사용

    print(f"[AUTO] worker started: user={user_id}, stocks={stocks}, amount={amount_per_stock}")

    acnt = Account(api)
    crt = Chart(api)

    while not stop_event.is_set():
        try:
            # 1) 현재 포지션 한 번만 조회해서 딕셔너리로 캐시
            try:
                resp = acnt.get_account_profit_rate()
                pos_map = {}
                for i in resp:
                    if i.remainder_quantity > 0:
                        pos_map[i.stock_code] = i
            except Exception as e:
                print(f"[AUTO] user={user_id} get_account_profit_rate error: {e}")
                pos_map = {}

            # 2) 각 종목별로 SELL → BUY 순서로 처리
            for code in stocks:
                if stop_event.is_set():
                    break
                
                 # ✅ 1) 종목별 쿨다운 체크
                now = time.time()
                last_t = last_trade_at.get(code)
                if last_t is not None:
                    elapsed = now - last_t
                    if elapsed < AUTO_TRADE_MIN_INTERVAL_SEC:
                        continue  # 이번 라운드에서는 이 종목 건너뛰기

                pos = pos_map.get(code)
                has_position = pos is not None and pos.remainder_quantity > 0

                pos = pos_map.get(code)
                has_position = pos is not None and pos.remainder_quantity > 0

                # 2-1) SELL 에이전트
                if has_position:
                    try:
                        r = requests.get(
                            f"http://localhost:8001/predict/{code}/sell", timeout=5
                        )
                        if r.status_code == 200:
                            data = r.json()
                            action = data.get("action", "HOLD")
                            conf = float(data.get("confidence", 0.0))
                            print(f"[AUTO] user={user_id} {code} SELL agent: {action} ({conf:.3f})")

                            if action == "SELL" and conf > 0.5:
                                qty = int(pos.remainder_quantity)
                                ok, msg, ord_no = _send_order_with_api(api, "SELL", code, qty, 0)
                                print(
                                    f"[AUTO] SELL {code} x{qty}: ok={ok}, ord={ord_no}, msg={msg}"
                                )
                                if ok:
                                    # ✅ 이 종목은 지금 막 거래했으니, 쿨다운 기록
                                    last_trade_at[code] = time.time()

                                # 매도했으면 이번 턴에 BUY는 패스
                                continue
                    except Exception as e:
                        print(f"[AUTO] user={user_id} DQN SELL error {code}: {e}")

                # 🔴 이미 포지션이 있으면 추가 매수는 하지 않는다
                if has_position:
                    # SELL 에이전트가 HOLD 했으면 그대로 보유 유지
                    print(f"[AUTO] user={user_id} {code}: position exists, skip BUY")
                    continue

                # 2-2) BUY 에이전트 (포지션 없을 때만)
                try:
                    r = requests.get(
                        f"http://localhost:8001/predict/{code}/buy", timeout=5
                    )
                    if r.status_code == 200:
                        data = r.json()
                        action = data.get("action", "HOLD")
                        conf = float(data.get("confidence", 0.0))
                        print(f"[AUTO] user={user_id} {code} BUY agent: {action} ({conf:.3f})")

                        if action == "BUY" and conf > 0.5:
                            # 현재가: 틱 1개
                            try:
                                tick = crt.get_stock_tick_chart(code, True, 1, 1)[0]
                                last_price = float(tick.close)
                            except Exception as e:
                                print(f"[AUTO] user={user_id} tick error {code}: {e}")
                                continue

                            if last_price <= 0:
                                print(f"[AUTO] user={user_id} invalid price for {code}: {last_price}")
                                continue

                            # amount_per_stock 만큼만 첫 진입
                            qty = max(1, int(amount_per_stock // last_price))
                            ok, msg, ord_no = _send_order_with_api(api, "BUY", code, qty, 0)
                            print(
                                f"[AUTO] BUY {code} x{qty} @MKT: ok={ok}, ord={ord_no}, msg={msg}"
                            )
                            if ok:
                                # ✅ 매수 성공 → 쿨다운 기록
                                last_trade_at[code] = time.time()
                except Exception as e:
                    print(f"[AUTO] user={user_id} DQN BUY error {code}: {e}")

                # 종목 간 딜레이 (키움 호출 너무 몰리지 않게)
                for _ in range(2):
                    if stop_event.is_set():
                        break
                    time.sleep(1)

        except Exception as loop_e:
            print(f"[AUTO] worker loop error user={user_id}: {loop_e}")

        # 한 라운드 끝난 뒤 60초 휴식
        for _ in range(60):
            if stop_event.is_set():
                break
            time.sleep(1)

    print(f"[AUTO] worker stopped: user={user_id}")


# ==============================
#  자동매매 상태 (유저별)
# ==============================
auto_trade_states: dict[int, dict] = {}
auto_trade_lock = Lock()

# ===================================================
# API 엔드포인트


# POST request handler
@app.get("/positions")
def get_positions(user=Depends(verify_jwt_token(get_api=True))):
    if user["api"] is None:
        raise HTTPException(status_code=400, detail="API keys not set")

    acnt = Account(user["api"])
    crt = Chart(user["api"])

    resp = acnt.get_account_profit_rate()
    ls: list[Position] = []

    for i in resp:
        if i.remainder_quantity <= 0:
            continue

        # 1) 평균 매수가
        try:
            avg_price = float(getattr(i, "purchase_price", 0) or 0)
        except Exception:
            avg_price = 0.0

        # 2) 현재가: AccountEntry에 있으면 그걸 쓰고, 없으면 틱에서 가져오기
        cur = getattr(i, "current_price", None)
        if cur is None:
            try:
                cur = crt.get_stock_tick_chart(i.stock_code, True, 1, 1)[0].close
            except Exception:
                cur = 0
        current_price = float(cur or 0)

        # 3) 평가손익 / 평가수익률은 **키움이 계산한 값 그대로** 사용
        #    (필드명은 라이브러리 정의에 따라 하나 골라 쓰면 됨)
        raw_pnl = (
            getattr(i, "evaluation_profit", None)
            or getattr(i, "valuation_profit", None)
            or getattr(i, "unrealized_profit", None)
        )
        if raw_pnl is not None:
            pnl_val = float(raw_pnl)
        else:
            # 못 찾으면 마지막 fallback만 직접 계산
            pnl_val = (current_price - avg_price) * i.remainder_quantity if avg_price else 0.0

        raw_rate = (
            getattr(i, "evaluation_profit_rate", None)
            or getattr(i, "valuation_profit_rate", None)
        )
        if raw_rate is not None:
            # 키움은 보통 "-0.75" 이런 식으로 %값을 줌 → 0.0075로 바꿔서 프론트에 전달
            pnl_pct_value = float(raw_rate) / 100.0
        else:
            pnl_pct_value = (current_price / avg_price - 1.0) if avg_price else 0.0

        ls.append(
            Position(
                symbol=i.stock_code,
                name=i.stock_name,
                qty=str(i.remainder_quantity),
                avgPrice=str(avg_price),
                lastPrice=str(current_price),
                pnl=str(int(round(pnl_val))),          # "-14000" 이런 느낌
                pnlPct=f"{pnl_pct_value:.4f}",         # 0.0075 → 프론트에서 x100 해서 0.75%
            )
        )

    return ls

@app.get("/portfolio")
def get_portfolio(user=Depends(verify_jwt_token(get_api=True))):
    if user["api"] is None:
        raise HTTPException(status_code=400, detail="API keys not set")

    acnt = Account(user["api"])
    resp = acnt.get_account_evaluation("KRX")

    # ① 추정자산(네가 MTS에서 보는 그 값)을 그대로 사용
    try:
        total_equity = float(getattr(resp, "presumed_asset", 0) or 0)
    except Exception:
        total_equity = 0.0

    # ② 예수금(현금) – 필요하면 이것도 MTS에서 보는 예수금이랑 맞는 필드로 골라
    try:
        cash = float(getattr(resp, "deposit", 0) or 0)
    except Exception:
        cash = 0.0

    pf = Portfolio(
        currency="KRW",
        totalEquity=str(int(total_equity)),
        cash=str(int(cash)),
        pnlDay=str(getattr(resp, "daily_profit", 0)),
        pnlDayPct=str(getattr(resp, "daily_profit_rate", 0)),
        updatedAt=datetime.datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S") + "Z",
    )
    return pf


@app.post("/chart")
def get_chart(chart_request: ChartRequest, user=Depends(verify_jwt_token(get_api=True))):
    if user["api"] is None:
        raise HTTPException(status_code=400, detail="API keys not set")

    chart = Chart(user["api"])

    # 1) base_date
    if not chart_request.base_date:
        base_date = datetime.datetime.now(UTC).strftime("%Y%m%d")
    else:
        base_date = chart_request.base_date.replace("-", "")

    # 2) 구간별 차트 호출 (amount 인자로 정확히 chart_request.amount 사용)
    if chart_request.interval == "1D":
        resp = chart.get_stock_daily_chart(
            chart_request.symbol, base_date, True, chart_request.amount
        )
    elif chart_request.interval == "1W":
        resp = chart.get_stock_weekly_chart(
            chart_request.symbol, base_date, True, chart_request.amount
        )
    elif chart_request.interval == "1M":
        resp = chart.get_stock_monthly_chart(
            chart_request.symbol, base_date, True, chart_request.amount
        )
    else:
        raise HTTPException(status_code=422, detail=f"Unknown interval {chart_request.interval}")

    candles: list[dict] = []

    for pole in resp:
        # ⚠ 여기서 date 필드 이름이 다르면 한 줄만 고치면 됨.
        # 예: pole.date 가 "20250113" 이런 형식이면:
        if hasattr(pole, "date"):
            d = str(pole.date)
            dt = datetime.datetime.strptime(d, "%Y%m%d").replace(tzinfo=UTC)
        elif hasattr(pole, "dt"):
            dt = pole.dt.replace(tzinfo=UTC)
        else:
            dt = datetime.datetime.now(UTC)

        ts_ms = int(dt.timestamp() * 1000)

        candles.append(
            {
                "timestamp": ts_ms,
                "open": float(pole.open),
                "high": float(pole.high),
                "low": float(pole.low),
                "close": float(pole.close),
            }
        )

    # Kiwoom 은 보통 최신 → 과거 순서로 줌 → 프론트는 과거 → 최신이 편하니 뒤집기
    candles = candles[::-1]

    return candles


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
        print("Incorrect password")
        raise HTTPException(status_code=400, detail="Incorrect password")
    # 3. 기존 JWT 토큰 무효화 (토큰 버전 증가) (다중 접속 방지)
    await update_user_token_version(db, result["id"], result["token_version"] + 1)
    # 4. 토큰 발급
    return {"message": "Login successful", "accessToken": create_jwt(user.email, result["id"], result["token_version"] + 1)}

@app.get("/auth/logout/")
async def logout_user(db=Depends(get_db), user=Depends(verify_jwt_token())):
    # 1. 토큰 검증 및 파싱
    # 2. JWT 토큰 무효화 (토큰 버전 증가)
    token = user["token"]
    await update_user_token_version(db, token["user_id"], token["token_version"] + 1)
    return {"message": "Logout successful"}

@app.post("/auth/set_api_keys/")
async def set_api_keys(api_keys: APIKeyData, db=Depends(get_db), user=Depends(verify_jwt_token())):
    # 1. 키 검증
    _ = KiwoomAPI(api_keys.appkey, api_keys.secretkey, api_keys.mock)
    # 2. API 키 암호화
    AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY")
    encrypted_keys = encrypt_dict(api_keys.model_dump(), AUTH_SECRET_KEY)
    # 3. 데이터베이스에 저장
    await update_user_api_keys(db, user["id"], encrypted_keys)
    return {"message": "API keys set successfully"}

@app.get("/auth/get_api_keys/", response_model=APIKeyData)
async def get_api_keys(db=Depends(get_db), user=Depends(verify_jwt_token())):
    if user["apisecret"] is None:
        return APIKeyData(appkey="", secretkey="", mock=True)
    AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY")
    secrets = decrypt_dict(user["apisecret"], AUTH_SECRET_KEY)
    return APIKeyData(**secrets)

@app.delete("/auth/delete_api_keys/")
async def delete_api_keys(db=Depends(get_db), user=Depends(verify_jwt_token())):
    await update_user_api_keys(db, user["id"], None)
    return {"message": "API keys deleted successfully"}

# 전체 종목 마스터 (동적 로딩)
STOCK_MASTER: list[Stock] = []
stock_master_loading = False

def load_stock_master(api: KiwoomAPI):
    """키움 API로부터 전체 종목 목록을 로드"""
    global STOCK_MASTER, stock_master_loading

    if STOCK_MASTER_STATIC:
        STOCK_MASTER = STOCK_MASTER_STATIC
        print(f"[STOCK_MASTER] 정적 파일에서 로딩 완료: 총 {len(STOCK_MASTER)}개")
        return
    
    if stock_master_loading:
        return
    
    stock_master_loading = True
    print("[STOCK_MASTER] 종목 목록 로딩 시작...")
    info = KiwoomStockInfo(api)
    
    try:
        all_stocks = []
        markets = [("0", "KOSPI"), ("10", "KOSDAQ")]
        
        for market_code, market_name in markets:
            stock_list = info.get_stock_list(market_code)
            all_stocks.extend(
                [Stock(symbol=stock["code"], name=stock["name"], market=market_name) for stock in stock_list]
            )
        
        STOCK_MASTER = all_stocks
        print(f"[STOCK_MASTER] 로딩 완료: 총 {len(STOCK_MASTER)}개")
        print(f"  - KOSPI: {len([s for s in STOCK_MASTER if s.market == 'KOSPI'])}개")
        print(f"  - KOSDAQ: {len([s for s in STOCK_MASTER if s.market == 'KOSDAQ'])}개")
        
    except Exception as e:
        print(f"[STOCK_MASTER] 로딩 실패: {e}")
        # 실패 시 기본 종목
        STOCK_MASTER = [
            Stock(symbol="005930", name="삼성전자", market="KOSPI"),
            Stock(symbol="000660", name="SK하이닉스", market="KOSPI"),
            Stock(symbol="035420", name="NAVER", market="KOSPI"),
        ]
    finally:
        stock_master_loading = False


# @app.get("/stocks/search", response_model=List[Stock])
# def search_stocks(
#     q: str = Query(..., min_length=2, description="종목명 또는 종목코드"),
#     user = Depends(verify_jwt_token(get_api=True)),
# ):
#     """
#     종목명/종목코드 검색용 엔드포인트.
#     프론트의 searchStocks() 가 여기로 요청을 보냄.
#     """
#     if user["api"] is None:
#         raise HTTPException(status_code=400, detail="API keys not set")

#     api: KiwoomAPI = user["api"]

#     # 🔸 여기는 실제로 네가 가지고 있는 Kiwoom 래퍼 함수 이름에 맞게 바꿔줘야 해
#     # 예시는 키움 OpenAPI: GetCodeListByMarket + GetMasterCodeName 패턴
#     markets = ["0", "3", "4", "6", "9", "10"]  # 코스피/코스닥 등 필요한 시장코드
#     seen_codes: set[str] = set()
#     results: list[Stock] = []

#     query_upper = q.upper()

#     for m in markets:
#         # ↓↓↓ 이 두 줄은 네 KiwoomAPI 래퍼 메서드 이름에 맞게 수정 필수 ↓↓↓
#         codes: list[str] = api.get_code_list_by_market(m)      # 예: ["005930", "000660", ...]
#         # ↑ 존재하는 메서드가 없다면, api.get_stock_list_by_market 같은 걸로 바꾸면 됨

#         for code in codes:
#             if code in seen_codes:
#                 continue
#             seen_codes.add(code)

#             # 마찬가지로 종목명 가져오는 메서드 이름 맞게 바꾸기
#             name: str = api.get_master_code_name(code)

#             # 간단한 부분 일치 검색 (코드/이름 둘 다)
#             if query_upper in code or q in name:
#                 # 시장명은 필요하면 더 정교하게 매핑
#                 if m in ("0", "4"):
#                     market_name = "KOSPI"
#                 elif m in ("3", "10"):
#                     market_name = "KOSDAQ"
#                 else:
#                     market_name = "ETC"

#                 results.append(
#                     Stock(symbol=code, name=name, market=market_name)
#                 )

#                 # 너무 많이 안 주도록 상한
#                 if len(results) >= 50:
#                     return results

#     return results

def search_str(stock: Stock, query: str) -> bool:
    start, length = 0, 0
    name, query = stock.name.upper(), query.upper()
    while start < len(name):
        if name[start] != query[0]:
            start += 1
            continue
        break

    while start + length < len(name) and length < len(query):
        if name[start + length] != query[length]:
            break
        length += 1

    return start, length

@app.get("/stocks/search", response_model=List[Stock])
async def search_stocks(
    q: str = Query(..., min_length=2, description="종목명 또는 종목코드"),
    user=Depends(verify_jwt_token(get_api=True)),
):
    """
    종목명/코드 검색:
      - 숫자 6자리면 키움 REST(/api/dostk/stkinfo)로 직접 조회
      - 그 외에는 로컬 STOCK_MASTER 에서 부분 일치 검색
      - STOCK_MASTER가 비어있으면 백그라운드 로딩 시작
    """
    print(q)
    if user["api"] is None:
        raise HTTPException(status_code=400, detail="API keys not set")

    api: KiwoomAPI = user["api"]

    #  STOCK_MASTER가 비어있고 로딩 중이 아니면 백그라운드 로딩 시작
    if not STOCK_MASTER and not stock_master_loading:
        load_stock_master(api)

    #  폴링
    if stock_master_loading:
        return [Stock(symbol="LOADING", name="종목 목록 로딩 중...", market="INFO")]

    query = q.strip()
    if len(query) < 2:
        return []

    results: list[Stock] = []

    # 1) 6자리 숫자 코드인 경우: 키움 REST 로 직접 조회
    if query.isdigit() and len(query) == 6:
        for stock in STOCK_MASTER:
            if stock.symbol == query:
                results.append(stock)
                return results

    query_list = [(x, search_str(x, query)) for x in STOCK_MASTER]
    sorted_query_list = sorted([x for x in query_list if x[1][1] == len(query)], key=lambda x: (x[1][0], -x[1][1], x[0].symbol))

    return [x[0] for x in sorted_query_list][:50]
    
@app.get("/stocks/all")
def get_all_stocks(user=Depends(verify_jwt_token(get_api=True))):
    """전체 종목 목록 반환"""
    if stock_master_loading:
        return {
            "status": "loading",
            "stocks": [],
            "total": 0
        }
    
    return {
        "status": "success",
        "stocks": [s.dict() for s in STOCK_MASTER],
        "total": len(STOCK_MASTER),
        "kospi_count": len([s for s in STOCK_MASTER if s.market == "KOSPI"]),
        "kosdaq_count": len([s for s in STOCK_MASTER if s.market == "KOSDAQ"])
    }


# ====== 엔드포인트 추가 ======
@app.get("/stocks/{symbol}", response_model=StockInfo)
def get_stock_detail(symbol: str, user=Depends(verify_jwt_token(get_api=True))):
    if user["api"] is None:
        raise HTTPException(status_code=400, detail="API keys not set")

    api = user["api"]
    chart = Chart(api)

    # 1) 현재가: 틱 차트에서 가장 최근 1틱
    try:
        ticks = chart.get_stock_tick_chart(symbol, True, 1, 1)
        if not ticks:
            raise HTTPException(status_code=404, detail="Tick data not found")

        last_tick = ticks[0]          # SimplePole 객체
        last_price = float(last_tick.close)
        volume = getattr(last_tick, "volume", None)
    except KiwoomApiError as e:
        raise HTTPException(status_code=500, detail=f"Kiwoom tick error: {e.reason}")

    # 2) 전일 종가: 일봉 2개 받아서 등락률 계산
    try:
        base_date = datetime.datetime.now(UTC).strftime("%Y%m%d")
        daily = chart.get_stock_daily_chart(symbol, base_date, True, amount=2)
        if len(daily) >= 2:
            prev_close = float(daily[1].close)
        elif len(daily) == 1:
            prev_close = float(daily[0].close)
        else:
            prev_close = last_price
    except KiwoomApiError:
        prev_close = last_price

    change_pct = (last_price - prev_close) / prev_close if prev_close else 0.0

    # 3) 이름은 일단 심볼 그대로 (나중에 마스터에서 끌어와도 됨)
    stock_name = symbol

    return StockInfo(
        symbol=symbol,
        name=stock_name,
        price=last_price,
        changePct=change_pct,
        volume=volume,
        marketCap=None,
    )

import traceback  # 파일 상단에 추가

def _send_order_for_user(
    user: dict,
    order_side: str,   # "BUY" or "SELL"
    symbol: str,
    qty: int,
    price: int,
):
    if user["api"] is None:
        return False, "API keys not set"

    api: KiwoomAPI = user["api"]
    ord_client = Order(api)

    stex_type = "KRX"

    if price == 0:
        trade_type = TradeType.시장가.value
        order_unit_value = 0
    else:
        trade_type = TradeType.보통.value
        order_unit_value = price

    try:
        if order_side == "BUY":
            ord_no = ord_client.buy(
                stex_type=stex_type,
                stock_code=symbol,
                order_quantity=qty,
                trade_type=trade_type,
                order_unit_value=order_unit_value,
            )
        else:
            ord_no = ord_client.sell(
                stex_type=stex_type,
                stock_code=symbol,
                order_quantity=qty,
                trade_type=trade_type,
                order_unit_value=order_unit_value,
            )

        return True, ord_no

    except KiwoomApiError as e:
        msg = f"[KiwoomApiError {e.error_code}] {e.reason} - {e.detail}"
        print("❌ KiwoomApiError:", msg)
        return False, msg

    except Exception as e:
        # ★ 여기서 전체 스택트레이스를 찍어서 어느 파일/라인인지 확인
        print("❌ Exception in order:", repr(e))
        traceback.print_exc()
        return False, f"Exception during order: {e}"

@app.post("/order")
def place_order(order: OrderRequest, user=Depends(verify_jwt_token(get_api=True))):
    """
    프론트에서 오는 /order 요청을 받아
    - user["api"]로 Kiwoom REST 주문 래퍼 호출
    - 결과를 success / orderId / message 형태로 반환
    """
    if user["api"] is None:
        return {
            "success": False,
            "orderId": "NONE",
            "message": "API keys not set",
        }

    # 프론트에서 오는 type은 "MARKET" | "LIMIT"
    side = order.side.upper()       # "BUY" / "SELL"
    price_val = 0 if order.type.upper() == "MARKET" else int(order.price)
    qty = int(order.qty)

    ok, detail = _send_order_for_user(
        user=user,
        order_side=side,
        symbol=order.symbol,
        qty=qty,
        price=price_val,
    )

    if ok:
        return {
            "success": True,
            "orderId": detail,  # 래퍼가 돌려준 주문번호
            "message": "Order sent",
        }
    else:
        return {
            "success": False,
            "orderId": "NONE",
            "message": f"Order failed: {detail}",
        }

@app.post("/auto-trade/start")
def start_auto_trade(
    cfg: AutoTradeStart,
    user=Depends(verify_jwt_token(get_api=True)),
):
    """
    자동매매 시작:
    - 해당 유저의 api (KiwoomAPI)로 워커 스레드 생성
    - 기존에 돌던 워커가 있으면 먼저 stop
    """
    if user["api"] is None:
        raise HTTPException(status_code=400, detail="API keys not set")

    if not cfg.stocks:
        raise HTTPException(status_code=400, detail="No stocks provided")

    user_id = user["id"]
    api: KiwoomAPI = user["api"]

    with auto_trade_lock:
        # 기존 워커가 있으면 종료 플래그만 세움
        prev = auto_trade_states.get(user_id)
        if prev and prev.get("running"):
            prev["stop"].set()

        stop_event = Event()
        th = Thread(
            target=_auto_trade_worker,
            args=(user_id, api, cfg.stocks, cfg.amount_per_stock, stop_event),
            daemon=True,
        )

        auto_trade_states[user_id] = {
            "running": True,
            "stocks": cfg.stocks,
            "amount_per_stock": cfg.amount_per_stock,
            "thread": th,
            "stop": stop_event,
        }

        th.start()

    return {
        "success": True,
        "message": f"자동매매 시작: {len(cfg.stocks)}개 종목, {cfg.amount_per_stock:,}원/종목",
        "stocks": cfg.stocks,
        "amount_per_stock": cfg.amount_per_stock,
    }

@app.post("/auto-trade/stop")
def stop_auto_trade(user=Depends(verify_jwt_token(get_api=True))):
    user_id = user["id"]

    with auto_trade_lock:
        st = auto_trade_states.get(user_id)
        if not st or not st.get("running"):
            return {"success": True, "message": "자동매매가 실행 중이 아닙니다."}

        st["stop"].set()
        st["running"] = False

    return {"success": True, "message": "자동매매 중지 요청 완료"}

@app.get("/auto-trade/status")
def get_auto_trade_status(user=Depends(verify_jwt_token(get_api=True))):
    """
    현재 로그인 유저의 자동매매 상태 조회
    """
    user_id = user["id"]

    st = auto_trade_states.get(user_id)
    if not st:
        return {"running": False}

    return {
        "running": bool(st.get("running")),
        "stocks": st.get("stocks", []),
        "amount_per_stock": st.get("amount_per_stock", 0),
    }
