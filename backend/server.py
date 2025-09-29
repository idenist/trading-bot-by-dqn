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

