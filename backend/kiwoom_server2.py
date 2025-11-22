# backend/kiwoom_server.py (REST 버전)

import os
import time
import random
from threading import Thread, Lock
from typing import List

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from zoneinfo import ZoneInfo

from pykrx import stock as krx_stock

# 네 래퍼에 맞게 import 경로는 필요시 조정
from kiwoom_python.api import KiwoomAPI
from kiwoom_python.endpoints.account import Account
from kiwoom_python.endpoints.chart import Chart
# from kiwoom_python.endpoints.order import Order  # 실제 래퍼에 있다면 사용
# from kiwoom_python.exceptions import KiwoomApiError

from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
from psycopg import errors as pg_errors

from user_management.user_repository import fetch_user_by_email
from user_management.secret_manager import decrypt_dict

from dotenv import load_dotenv   
load_dotenv()                
    
KST = ZoneInfo("Asia/Seoul")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# 전역 상태
# -----------------------------

# 자동매매 상태
auto_trade_stocks: List[str] = []
auto_trade_running: bool = False
auto_trade_thread: Thread | None = None
auto_trade_amount_per_stock: int = 1_000_000

# 종목 캐시
stock_cache: List[dict] = []
stock_cache_loading: bool = False

# ==============================
# DB 연결 설정 (rest_server.py 참조)
# ==============================
DB_CONNECT_STRING = os.getenv("DB_CONNECT_STRING")
pool: AsyncConnectionPool | None = None

# Kiwoom REST 클라이언트 (단일 계정용)
kiwoom_api: KiwoomAPI | None = None
account_client: Account | None = None
chart_client: Chart | None = None


rest_lock = Lock()


# -----------------------------
# Pydantic 모델
# -----------------------------

class AutoTradeStart(BaseModel):
    stocks: List[str]
    amount_per_stock: int = 1_000_000


class OrderRequest(BaseModel):
    symbol: str
    side: str      # "BUY" | "SELL"
    type: str      # "MARKET" | "LIMIT"
    price: float
    qty: int


# -----------------------------
# Kiwoom REST 초기화 / 헬퍼
# -----------------------------

def _ensure_kiwoom_ready():
    if not kiwoom_api or not account_client or not chart_client:
        raise HTTPException(status_code=503, detail="Kiwoom REST API not initialized")


def _fetch_positions() -> List[dict]:
    """
    REST 기반 계좌 보유 종목 조회
    - rest_server.py 에서 쓰던 Account / Chart 패턴과 동일한 스타일로 작성
    """
    _ensure_kiwoom_ready()

    positions: List[dict] = []

    with rest_lock:
        try:
            resp = account_client.get_account_profit_rate()  # type: ignore
        except Exception as e:
            print(f"[Kiwoom REST] get_account_profit_rate 에러: {e}")
            return []

    for item in resp:
        # 래퍼의 필드 이름은 rest_server에서 사용하던 것 기준으로 추정
        qty = int(getattr(item, "remainder_quantity", 0))
        if qty <= 0:
            continue

        code = getattr(item, "stock_code", "").strip()
        name = getattr(item, "stock_name", "").strip()
        avg_price = int(getattr(item, "purchase_price", 0))

        last_price = avg_price
        try:
            ticks = chart_client.get_stock_tick_chart(code, True, 1, 1)  # type: ignore
            if ticks:
                last_price = int(ticks[0].close)
        except Exception as e:
            print(f"[Kiwoom REST] tick 조회 실패 ({code}): {e}")

        pnl = (last_price - avg_price) * qty
        pnl_pct = (last_price / avg_price - 1.0) if avg_price > 0 else 0.0

        positions.append(
            {
                "symbol": code,
                "name": name,
                "qty": str(qty),
                "avgPrice": str(avg_price),
                "lastPrice": str(last_price),
                "pnl": str(pnl),
                "pnlPct": f"{pnl_pct:.3f}",
            }
        )

    return positions


def _fetch_portfolio() -> dict:
    """
    REST 기반 포트폴리오 요약 조회
    """
    _ensure_kiwoom_ready()

    with rest_lock:
        try:
            evaluation = account_client.get_account_evaluation("KRX")  # type: ignore
        except Exception as e:
            print(f"[Kiwoom REST] get_account_evaluation 에러: {e}")
            return {
                "currency": "KRW",
                "totalEquity": "0",
                "cash": "0",
                "pnlDay": "0",
                "pnlDayPct": "0.0",
                "updatedAt": "",
            }

    now = datetime.now(KST).astimezone(ZoneInfo("UTC"))

    return {
        "currency": "KRW",
        "totalEquity": str(getattr(evaluation, "total_estimated", 0)),
        "cash": str(getattr(evaluation, "deposit", 0)),
        "pnlDay": str(getattr(evaluation, "daily_profit", 0)),
        "pnlDayPct": str(getattr(evaluation, "daily_profit_rate", 0.0)),
        "updatedAt": now.isoformat(),
    }


def _get_current_price(symbol: str) -> int:
    """
    REST 기반 현재가 조회 (가장 최근 틱/일봉 close 사용)
    """
    _ensure_kiwoom_ready()

    try:
        with rest_lock:
            ticks = chart_client.get_stock_tick_chart(symbol, True, 1, 1)  # type: ignore

        if ticks:
            return int(ticks[0].close)
    except Exception as e:
        print(f"[Kiwoom REST] tick 가격 조회 실패 ({symbol}): {e}")

    # 틱 조회 실패 시 일봉으로 fallback
    try:
        base_date = datetime.now(KST).strftime("%Y%m%d")
        with rest_lock:
            candles = chart_client.get_stock_daily_chart(symbol, base_date, True, 1)  # type: ignore

        if candles:
            return int(candles[0].close)
    except Exception as e:
        print(f"[Kiwoom REST] 일봉 가격 조회 실패 ({symbol}): {e}")

    return 0


def _send_order_rest(order_type: str, symbol: str, qty: int, price: int = 0) -> bool:
    """
    REST 주문 전송 (실제 주문 래퍼/직접 REST 호출을 여기에 연결)

    order_type: "BUY" 또는 "SELL"
    qty: 수량
    price: 0이면 시장가, 그 외 지정가 (예시)
    """
    _ensure_kiwoom_ready()

    # ⚠ 여기서부터는 네 kiwoom_python 래퍼 또는 직접 REST 호출 규격에 맞게 구현해야 함.
    # 예: Order(kiwoom_api).stock_buy(...) 또는 /api/dostk/ordr POST 등.
    # 아래는 "실제 주문은 아직 연결 안 된 더미" 구현이므로 반드시 교체할 것.

    print(
        f"[ORDER-REST-STUB] {order_type} {symbol} {qty}주 @ {price if price else 'MARKET'} (실제 주문 로직은 TODO)"
    )
    # 실제 구현에서는 try/except로 래퍼 호출하고 성공 여부 반환
    # return True on success / False on failure
    return False


# -----------------------------
# 종목 캐시 (pykrx 이용)
# -----------------------------

def _load_all_stocks():
    global stock_cache, stock_cache_loading
    if stock_cache_loading:
        return

    stock_cache_loading = True
    print("[STOCK-CACHE] pykrx로 KOSPI/KOSDAQ 종목 로딩 시작...")

    try:
        stocks: List[dict] = []

        # KOSPI
        try:
            kospi_codes = krx_stock.get_market_ticker_list(market="KOSPI")
            for code in kospi_codes:
                name = krx_stock.get_market_ticker_name(code)
                stocks.append({"symbol": code, "name": name, "market": "KOSPI"})
        except Exception as e:
            print(f"[STOCK-CACHE] KOSPI 로딩 실패: {e}")

        # KOSDAQ
        try:
            kosdaq_codes = krx_stock.get_market_ticker_list(market="KOSDAQ")
            for code in kosdaq_codes:
                name = krx_stock.get_market_ticker_name(code)
                stocks.append({"symbol": code, "name": name, "market": "KOSDAQ"})
        except Exception as e:
            print(f"[STOCK-CACHE] KOSDAQ 로딩 실패: {e}")

        stock_cache = stocks
        print(
            f"[STOCK-CACHE] 로드 완료: total={len(stock_cache)}, "
            f"KOSPI={len([s for s in stock_cache if s['market']=='KOSPI'])}, "
            f"KOSDAQ={len([s for s in stock_cache if s['market']=='KOSDAQ'])}"
        )

    finally:
        stock_cache_loading = False


def _start_background_stock_loading():
    thread = Thread(target=_load_all_stocks, daemon=True)
    thread.start()


# -----------------------------
# 자동매매 루프 (REST 버전)
# -----------------------------

def auto_trade_loop():
    global auto_trade_running, auto_trade_amount_per_stock

    print("ENHANCED AUTO TRADE LOOP STARTED (REST)")
    print(f"Investment per stock: {auto_trade_amount_per_stock:,}원")

    while auto_trade_running:
        print(
            f"AUTO TRADE LOOP: running={auto_trade_running}, stocks={auto_trade_stocks}"
        )

        if not kiwoom_api or not account_client or not chart_client:
            print("Waiting for Kiwoom REST initialization...")
            time.sleep(5)
            continue

        try:
            # 루프 한 번당 포지션 한 번만 조회
            all_positions = _fetch_positions()
            pos_map = {p["symbol"]: p for p in all_positions}

            for stock_code in auto_trade_stocks:
                if not auto_trade_running:
                    break

                print(f"\n=== Processing {stock_code} ===")

                current_position = pos_map.get(stock_code)
                has_position = (
                    current_position is not None
                    and int(current_position.get("qty", "0")) > 0
                )

                # 1) 보유량 있으면 SELL 에이전트 우선
                if has_position:
                    print(
                        f"[{stock_code}] Has {current_position['qty']} shares, checking SELL agent first..."
                    )
                    try:
                        sell_response = requests.get(
                            f"http://localhost:8001/predict/{stock_code}/sell",
                            timeout=10,
                        )
                        if sell_response.status_code == 200:
                            sell_data = sell_response.json()
                            sell_action = sell_data.get("action", "HOLD")
                            sell_conf = float(sell_data.get("confidence", 0.0))

                            print(
                                f"[{stock_code}] SELL agent: {sell_action} (confidence: {sell_conf:.3f})"
                            )

                            if sell_action == "SELL" and sell_conf > 0.5:
                                qty = int(current_position["qty"])
                                print(f"[{stock_code}] SELLING {qty} shares (REST)")

                                success = _send_order_rest("SELL", stock_code, qty, 0)
                                print(f"[{stock_code}] Sell result: {success}")
                                # 매도 시도 후 이번 종목은 매수 스킵
                                continue
                    except Exception as e:
                        print(f"[{stock_code}] SELL agent error: {e}")

                # 2) BUY 에이전트
                try:
                    buy_response = requests.get(
                        f"http://localhost:8001/predict/{stock_code}/buy", timeout=10
                    )
                    if buy_response.status_code == 200:
                        buy_data = buy_response.json()
                        buy_action = buy_data.get("action", "HOLD")
                        buy_conf = float(buy_data.get("confidence", 0.0))

                        print(
                            f"[{stock_code}] BUY agent: {buy_action} (confidence: {buy_conf:.3f})"
                        )

                        if buy_action == "BUY" and buy_conf > 0.5:
                            current_price = _get_current_price(stock_code)
                            if current_price > 0:
                                qty = max(
                                    1, auto_trade_amount_per_stock // current_price
                                )
                                total_cost = qty * current_price

                                print(
                                    f"[{stock_code}] BUYING {qty} shares @ {current_price:,}원"
                                )
                                print(
                                    f"[{stock_code}] Total cost: {total_cost:,}원 (Budget: {auto_trade_amount_per_stock:,}원)"
                                )

                                success = _send_order_rest(
                                    "BUY", stock_code, qty, 0
                                )
                                print(f"[{stock_code}] Buy result: {success}")
                except Exception as e:
                    print(f"[{stock_code}] BUY agent error: {e}")

                time.sleep(2)  # 종목 간 딜레이

        except Exception as e:
            print(f"Auto trade loop error: {e}")

        print("Auto trade cycle completed. Waiting 60 seconds...")
        time.sleep(60)

    print("AUTO TRADE LOOP STOPPED")


# -----------------------------
# FastAPI 이벤트 & 엔드포인트
# -----------------------------

@app.on_event("startup")
async def startup():
    """
    1) DB 커넥션 풀 초기화
    2) BOT_USER_EMAIL에 해당하는 유저 레코드 조회
    3) apisecret 복호화 → appkey/secretkey/mock 추출
    4) KiwoomAPI / Account / Chart 초기화
    5) 종목 캐시 백그라운드 로딩
    """
    global pool, kiwoom_api, account_client, chart_client

    print("Starting Kiwoom REST Trading Server...")

    if not DB_CONNECT_STRING:
        print("❌ DB_CONNECT_STRING 환경변수가 설정되지 않았습니다.")
        return

    # 1) 커넥션 풀 생성
    pool = AsyncConnectionPool(
        conninfo=DB_CONNECT_STRING,
        min_size=1,
        max_size=5,
    )
    await pool.open()
    print("✅ DB connection pool opened")

    # 2) 어떤 유저의 API 키를 쓸 것인가?
    #    - 여기서는 .env 의 BOT_USER_EMAIL 에 해당하는 유저를 "봇 계정"으로 사용
    bot_email = os.getenv("BOT_USER_EMAIL")
    if not bot_email:
        print("⚠ BOT_USER_EMAIL 이 설정되지 않았습니다. Kiwoom API 초기화 생략")
        return

    try:
        async with pool.connection() as conn:
            conn.row_factory = dict_row
            # rest_server.py 에서 사용하던 것과 동일한 함수
            user = await fetch_user_by_email(conn, bot_email)
    except Exception as e:
        print(f"❌ fetch_user_by_email 실패: {e}")
        return

    if user.get("apisecret") is None:
        print(f"⚠ 유저 {bot_email} 에 apisecret 이 없습니다. Kiwoom API 초기화 불가")
        return

    # 3) apisecret 복호화
    AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY")
    if not AUTH_SECRET_KEY:
        print("❌ AUTH_SECRET_KEY 가 설정되지 않았습니다.")
        return

    try:
        secrets = decrypt_dict(user["apisecret"], AUTH_SECRET_KEY)
        appkey = secrets.get("appkey")
        secretkey = secrets.get("secretkey")
        mock = secrets.get("mock", True)
    except Exception as e:
        print(f"❌ apisecret 복호화 실패: {e}")
        return

    if not appkey or not secretkey:
        print("❌ appkey/secretkey 가 복호화 결과에 없습니다.")
        return

    # 4) Kiwoom REST 세션 초기화
    try:
        kiwoom_api = KiwoomAPI(appkey, secretkey, mock)
        account_client = Account(kiwoom_api)
        chart_client = Chart(kiwoom_api)
        print(f"✅ Kiwoom REST API 초기화 완료 (bot user: {bot_email}, mock={mock})")
    except Exception as e:
        print(f"❌ Kiwoom REST 초기화 실패: {e}")
        kiwoom_api = None
        account_client = None
        chart_client = None
        return

    # 5) pykrx 기반 종목 리스트 백그라운드 로딩
    _start_background_stock_loading()

@app.on_event("shutdown")
async def shutdown():
    global pool
    if pool is not None:
        await pool.close()
        print("🔻 DB connection pool closed")


@app.get("/positions")
def get_positions():
    if not kiwoom_api:
        return []
    return _fetch_positions()


@app.get("/portfolio")
def get_portfolio():
    if not kiwoom_api:
        return {
            "currency": "KRW",
            "totalEquity": "0",
            "cash": "0",
            "pnlDay": "0",
            "pnlDayPct": "0.0",
            "updatedAt": "",
        }
    return _fetch_portfolio()


@app.get("/quote/{symbol}")
def get_quote(symbol: str):
    price = _get_current_price(symbol)
    return {
        "symbol": symbol,
        "price": str(price),
        "changePct": "0.0",  # 원하면 일봉 두 개로 전일 대비 % 계산 가능
        "timestamp": datetime.now(KST).isoformat(),
    }


@app.post("/chart")
def get_chart_post(request: dict):
    """
    기존에 랜덤 캔들 생성하던 /chart 엔드포인트를
    Kiwoom REST 일봉 차트 기반으로 재구현
    """
    _ensure_kiwoom_ready()

    symbol = request.get("symbol", "005930")
    limit = int(request.get("limit", 30))
    interval = request.get("interval", "1D")

    base_date = datetime.now(KST).strftime("%Y%m%d")

    with rest_lock:
        if interval == "1W":
            candles = chart_client.get_stock_weekly_chart(symbol, base_date, True, limit)  # type: ignore
        elif interval == "1M":
            candles = chart_client.get_stock_monthly_chart(symbol, base_date, True, limit)  # type: ignore
        else:
            candles = chart_client.get_stock_daily_chart(symbol, base_date, True, limit)  # type: ignore

    result: List[dict] = []
    now_ts = int(time.time() * 1000)

    # 최신 봉이 앞에 온다고 가정하면, 시간 역순으로 정렬
    for idx, c in enumerate(reversed(candles)):
        result.append(
            {
                "timestamp": now_ts - idx * 86_400_000,
                "open": int(c.open),
                "high": int(c.high),
                "low": int(c.low),
                "close": int(c.close),
            }
        )

    return result


@app.post("/order")
def place_order(order: OrderRequest):
    if not kiwoom_api:
        return {"success": False, "orderId": "NONE", "message": "Kiwoom REST not initialized"}

    price_val = 0 if order.type.upper() == "MARKET" else int(order.price)
    success = _send_order_rest(order.side.upper(), order.symbol, order.qty, price_val)

    return {
        "success": success,
        "orderId": f"ORD{int(time.time())}",
        "message": "Order sent (REST stub)" if success else "Order failed (REST stub)",
    }


@app.get("/ai/recommend")
def ai_recommend_proxy(symbol: str = Query(...)):
    """
    AI 추천을 DQN 서버(8001)로 프록시
    (기존 구조 유지)
    """
    try:
        print(f"PROXY REQUEST to DQN server for {symbol}")
        resp = requests.get(
            f"http://localhost:8001/ai/recommend",
            params={"symbol": symbol},
            timeout=5,
        )
        if resp.status_code == 200:
            result = resp.json()
            print(f"PROXY RESPONSE: {result}")
            return result
        else:
            print(f"PROXY ERROR: HTTP {resp.status_code}")
            raise Exception(f"HTTP {resp.status_code}")
    except Exception as e:
        print(f"DQN server error: {e}")
        return {
            "symbol": symbol,
            "action": "HOLD",
            "confidence": 0.0,
            "recommended_qty": 0,
            "reason": f"DQN server error: {str(e)}",
        }


@app.post("/auto-trade/start")
def start_auto_trade(request: AutoTradeStart):
    global auto_trade_stocks, auto_trade_running, auto_trade_thread, auto_trade_amount_per_stock

    print(
        f"AUTO TRADE START REQUEST (REST): "
        f"stocks={request.stocks}, amount_per_stock={request.amount_per_stock:,}원"
    )

    if not request.stocks:
        return {"success": False, "message": "No stocks provided", "stocks": []}

    if not kiwoom_api:
        return {"success": False, "message": "Kiwoom REST not initialized", "stocks": request.stocks}

    # 기존 자동매매 중지
    if auto_trade_running:
        print("Stopping existing auto trade...")
        auto_trade_running = False
        time.sleep(2)

    auto_trade_stocks = request.stocks
    auto_trade_amount_per_stock = request.amount_per_stock
    auto_trade_running = True

    auto_trade_thread = Thread(target=auto_trade_loop, daemon=True)
    auto_trade_thread.start()

    response = {
        "success": True,
        "message": (
            f"Auto trade started for {len(request.stocks)} stocks "
            f"with {request.amount_per_stock:,}원 each (REST)"
        ),
        "stocks": request.stocks,
        "amount_per_stock": request.amount_per_stock,
    }

    print(f"AUTO TRADE START RESPONSE: {response}")
    return response


@app.post("/auto-trade/stop")
def stop_auto_trade():
    global auto_trade_running, auto_trade_stocks
    print("AUTO TRADE STOP REQUEST")
    auto_trade_running = False
    auto_trade_stocks = []
    response = {"success": True, "message": "Auto trade stopped"}
    print(f"AUTO TRADE STOP RESPONSE: {response}")
    return response


@app.get("/auto-trade/status")
def get_auto_trade_status():
    status = {
        "running": auto_trade_running,
        "stocks": auto_trade_stocks,
        "count": len(auto_trade_stocks),
        "amount_per_stock": auto_trade_amount_per_stock if auto_trade_running else 0,
    }
    print(f"AUTO TRADE STATUS: {status}")
    return status


@app.get("/search/stocks")
def search_stocks(q: str = Query(..., min_length=1)):
    """
    기존 OpenAPI+ 기반 종목검색을
    pykrx 캐시 기반으로 동작하게 변경
    """
    global stock_cache, stock_cache_loading

    if stock_cache_loading:
        return [
            {
                "symbol": "LOADING",
                "name": "주식 목록을 로딩 중입니다...",
                "market": "INFO",
            }
        ]

    if not stock_cache:
        _start_background_stock_loading()
        return [
            {
                "symbol": "LOADING",
                "name": "주식 목록 로딩을 시작합니다...",
                "market": "INFO",
            }
        ]

    query = q.lower()
    results: List[dict] = []

    for stock in stock_cache:
        if query in stock["symbol"].lower() or query in stock["name"].lower():
            results.append(stock)
            if len(results) >= 100:
                break

    print(
        f"Search '{q}': found {len(results)} results out of {len(stock_cache)} total stocks"
    )
    return results


@app.get("/refresh-stocks")
def refresh_stocks():
    """주식 캐시를 강제로 새로고침"""
    global stock_cache, stock_cache_loading

    if stock_cache_loading:
        return {"message": "Already loading stocks", "status": "loading"}

    stock_cache = []
    _start_background_stock_loading()
    return {"message": "Stock cache refresh started", "status": "started"}


@app.get("/stocks-count")
def get_stocks_count():
    """현재 로드된 주식 개수 및 상태 확인"""
    return {
        "total_stocks": len(stock_cache),
        "kospi_count": len([s for s in stock_cache if s["market"] == "KOSPI"]),
        "kosdaq_count": len([s for s in stock_cache if s["market"] == "KOSDAQ"]),
        "loading": stock_cache_loading,
        "kiwoom_connected": kiwoom_api is not None,
        "sample": stock_cache[:10] if stock_cache else [],
    }


@app.get("/clear-cache")
def clear_cache():
    """캐시 완전 삭제"""
    global stock_cache, stock_cache_loading
    stock_cache = []
    stock_cache_loading = False
    print("Stock cache completely cleared")
    return {
        "message": "Stock cache completely cleared",
        "status": "cleared",
        "total_stocks": len(stock_cache),
    }


@app.get("/force-reload-stocks")
def force_reload_stocks():
    """강제로 주식 목록 다시 로드"""
    global stock_cache_loading
    if stock_cache_loading:
        return {"message": "Already loading", "status": "loading"}
    _start_background_stock_loading()
    return {"message": "Force reload started", "status": "started"}


@app.get("/health")
def health():
    status = {
        "status": "healthy",
        "connected": kiwoom_api is not None,
        "auto_trade_running": auto_trade_running,
        "auto_trade_stocks": len(auto_trade_stocks),
        "total_stocks": len(stock_cache),
        "stocks_loading": stock_cache_loading,
        "port": 8000,
        "mode": "REST",
    }
    print(f"HEALTH CHECK: {status}")
    return status


@app.get("/")
def root():
    return {
        "message": "Kiwoom REST Trading Server",
        "connected": kiwoom_api is not None,
        "auto_trade": {
            "running": auto_trade_running,
            "stocks": auto_trade_stocks,
        },
        "stock_cache": {
            "total": len(stock_cache),
            "loading": stock_cache_loading,
        },
    }


if __name__ == "__main__":
    print("Starting Kiwoom REST Server on port 8000...")
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
