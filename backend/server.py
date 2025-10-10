from kiwoom_python.api import KiwoomAPI
from kiwoom_python.endpoints.account import *
from kiwoom_python.endpoints.chart import Chart
from kiwoom_python.model import AccountEntry

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from enum import Enum
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import os

import asyncio
from typing import Dict, Set
from threading import Lock

from pykrx import stock

UTC = ZoneInfo("UTC")

# Create a FastAPI instance
app = FastAPI()
load_dotenv()  # .env 파일 불러오기
appkey = os.getenv("APP_KEY")
secretkey = os.getenv("SECRET_KEY")
api = KiwoomAPI(appkey, secretkey, mock=True)
acnt = Account(api)
chart = Chart(api)


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

class QuoteCache:
    def __init__(self):
        self.data: Dict[str, dict] = {}   # {symbol: {"price":..., "prevClose":..., "ts":...}}
        self.watch: Set[str] = set()      # 구독된 심볼 집합
        self.lock = Lock()
        self.running = False

    def add(self, symbol: str):
        with self.lock:
            self.watch.add(symbol)

    def remove(self, symbol: str):
        with self.lock:
            self.watch.discard(symbol)

    def get(self, symbol: str):
        return self.data.get(symbol)

    async def run(self, interval=1.5):
        """주기적으로 watch 목록의 시세를 갱신"""
        self.running = True
        while self.running:
            syms = list(self.watch)
            for sym in syms:
                try:
                    ticks = chart.get_stock_tick_chart(sym, True, 1, 1)
                    if not ticks:
                        continue
                    price = float(ticks[0].close)
                    dailies = chart.get_stock_daily_chart(sym, "", True, amount=2)
                    prev = float(dailies[1].close) if len(dailies) >= 2 else None

                    self.data[sym] = {
                        "symbol": sym,
                        "price": price,
                        "prevClose": prev,
                        "ts": datetime.now(tz=UTC).isoformat(),
                    }
                except Exception as e:
                    # 필요 시 로깅
                    pass
                await asyncio.sleep(0)  # 이벤트 루프 양보
            await asyncio.sleep(interval)

    def stop(self):
        self.running = False

qcache = QuoteCache()

class Quote(BaseModel):
    symbol: str
    name: str | None = None
    price: float
    prevClose: float | None = None
    ts: str

origins = [
    "http://localhost",
    "http://localhost:8081",
    "http://192.168.0.5:8081"
]

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
    resp = acnt.get_account_profit_rate()
    if not resp:
        raise HTTPException(404, "보유 종목이 없습니다.")
    
    total_eval = 0.0
    total_profit = 0.0

    for e in resp:
        # 평가금액 = 현재가 × 수량
        eval_amt = e.current_price * e.remainder_quantity
        profit = (e.current_price - e.purchase_price) * e.remainder_quantity

        total_eval += eval_amt
        total_profit += profit

    pnl_rate = total_profit / (total_eval - total_profit) if total_eval != 0 else 0

    pf = Portfolio(
        currency="KRW",
        totalEquity=str(round(total_eval, 2)),
        cash="0",  # 예수금 따로 표시하려면 acnt.get_account_evaluation()에서 deposit 가져와 합산
        pnlDay=str(round(total_profit, 2)),
        pnlDayPct=f"{pnl_rate:.4f}",
        updatedAt=datetime.now().astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S") + "Z"
    )
    return pf

# @app.post("/chart/")
# def get_chart(chart_request: ChartRequest):
#     if chart_request.interval == "1D":
#         resp = chart.get_stock_daily_chart(chart_request.symbol, chart_request.base_date, True, amount=chart_request.amount)
#     elif chart_request.interval == "1W":
#         resp = chart.get_stock_weekly_chart(chart_request.symbol, chart_request.base_date, True, amount=chart_request.amount)
#     elif chart_request.interval == "1M":
#         resp = chart.get_stock_monthly_chart(chart_request.symbol, chart_request.base_date, True, amount=chart_request.amount)
#     else:
#         raise HTTPException(status_code=422, detail=f"Unknown interval {chart_request.interval}")
#     ret = [x.to_minimal_dict() for x in resp][-1:-chart_request.amount - 1:-1]
#     return ret

@app.post("/chart")
def get_chart(req: ChartRequest):
    # 1) base_date 정규화
    base = (req.base_date or "").replace("-", "")
    if base == "" or base.lower() in ("latest", "today"):
        base = datetime.now().strftime("%Y%m%d")   # mock에서도 안전한 오늘 날짜

    amount = max(1, min(req.amount, 500))  # 가드

    try:
        if req.interval == "1D":
            resp = chart.get_stock_daily_chart(req.symbol, base, True, amount=amount*2)
        elif req.interval == "1W":
            resp = chart.get_stock_weekly_chart(req.symbol, base, True, amount=amount*2)
        elif req.interval == "1M":
            resp = chart.get_stock_monthly_chart(req.symbol, base, True, amount=amount*2)
        else:
            raise HTTPException(status_code=422, detail=f"Unknown interval {req.interval}")
    except Exception as e:
        raise HTTPException(500, f"provider error: {e}")

    items = [x.to_minimal_dict() for x in (resp or [])]

    # 5) mock에서 가끔 빈 배열이 오면, 아주 큰 날짜로 재시도 (최신 스냅)
    if not items:
        try:
            fallback_base = "20991231"
            if req.interval == "1D":
                resp = chart.get_stock_daily_chart(req.symbol, fallback_base, True, amount=amount*2)
            elif req.interval == "1W":
                resp = chart.get_stock_weekly_chart(req.symbol, fallback_base, True, amount=amount*2)
            else:
                resp = chart.get_stock_monthly_chart(req.symbol, fallback_base, True, amount=amount*2)
            items = [x.to_minimal_dict() for x in (resp or [])]
        except:
            pass

    if not items:
        # 그래도 없으면 404
        raise HTTPException(404, "차트 데이터를 가져올 수 없습니다.")

    # 2) 시간 오름차순 정렬
    items.sort(key=lambda d: d["timestamp"])

    # 3) 초 → 밀리초 보정
    for it in items:
        if it["timestamp"] < 10**12:
            it["timestamp"] *= 1000

    # 4) 마지막 N개만 반환
    return items[-amount:]

@app.on_event("startup")
async def _startup():
    # 자주 쓰는 종목을 미리 등록해도 좋다.
    # qcache.add("005930"); qcache.add("000660")
    asyncio.create_task(qcache.run(interval=1.5))
    
def get_name_krx(code: str) -> str | None:
    try:
        return stock.get_market_ticker_name(code)  # '삼성전자' 같은 이름 반환
    except Exception:
        return None

@app.get("/quote/{symbol}", response_model=Quote)
def get_quote(symbol: str):
    ticks = chart.get_stock_tick_chart(symbol, True, 1, 1)
    if not ticks:
        raise HTTPException(404, "틱 데이터를 가져올 수 없습니다.")
    last = ticks[0].close

    # ✅ 전일종가 구하기 (일봉 2개 조회)
    dailies = chart.get_stock_daily_chart(symbol, datetime.today().strftime("%Y%m%d"), True, amount=2)
    prev_close = dailies[1].close if len(dailies) >= 2 else None
    name = get_name_krx(symbol)

    return Quote(
        symbol=symbol,
        name=name,
        price=float(last),
        prevClose=float(prev_close) if prev_close else None,
        ts=datetime.now(tz=UTC).isoformat()
    )
