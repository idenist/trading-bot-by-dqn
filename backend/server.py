# server.py - DQN 모델 전용 (pythoncom 제거)
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import List
from enum import Enum
from datetime import datetime
from zoneinfo import ZoneInfo
import uvicorn

UTC = ZoneInfo("UTC")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DQN 모델
class DQN(nn.Module):
    def __init__(self, input_dim, output_dim):
        super(DQN, self).__init__()
        self.fc1 = nn.Linear(input_dim, 256)
        self.fc2 = nn.Linear(256, 512)
        self.fc3 = nn.Linear(512, 512)
        self.fc4 = nn.Linear(512, 256)
        self.fc5 = nn.Linear(256, output_dim)

    def forward(self, x):
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        x = F.relu(self.fc3(x))
        x = F.relu(self.fc4(x))
        return self.fc5(x)

class Position(BaseModel):
    symbol: str
    name: str
    qty: str
    avgPrice: str
    lastPrice: str
    pnl: str
    pnlPct: str

class Portfolio(BaseModel):
    currency: str
    totalEquity: str
    cash: str
    pnlDay: str
    pnlDayPct: str
    updatedAt: str

class OrderRequest(BaseModel):
    symbol: str
    side: str
    type: str
    price: float
    qty: int

class AIRecommendation(BaseModel):
    symbol: str
    action: str
    confidence: float
    recommended_qty: int
    reason: str

buy_model = None
sell_model = None

@app.on_event("startup")
async def load_models():
    global buy_model, sell_model
    
    try:
        INPUT_DIM = 14
        OUTPUT_DIM = 2
        
        buy_model = DQN(INPUT_DIM, OUTPUT_DIM)
        buy_model.load_state_dict(torch.load("buy_model.pth", map_location='cpu'))
        buy_model.eval()
        print("✅ 매수 모델 로드 완료")
        
        sell_model = DQN(INPUT_DIM, OUTPUT_DIM)
        sell_model.load_state_dict(torch.load("sell_model.pth", map_location='cpu'))
        sell_model.eval()
        print("✅ 매도 모델 로드 완료")
    except Exception as e:
        print(f"⚠️ 모델 로드 실패: {e}")

@app.get("/positions")
def get_positions():
    """키움 서버(8000)에서 조회"""
    import requests
    try:
        resp = requests.get("http://localhost:8000/positions", timeout=2)
        return resp.json()
    except:
        # 키움 서버 미작동 시 Mock
        return [
            Position(
                symbol="005930",
                name="삼성전자",
                qty="10",
                avgPrice="70000",
                lastPrice="72000",
                pnl="20000",
                pnlPct="0.029"
            ).__dict__
        ]

@app.get("/portfolio")
def get_portfolio():
    return Portfolio(
        currency="KRW",
        totalEquity="10000000",
        cash="5000000",
        pnlDay="50000",
        pnlDayPct="0.005",
        updatedAt=datetime.now().astimezone(UTC).isoformat()
    )

@app.post("/order")
def place_order(order: OrderRequest):
    """키움 서버로 주문 전달"""
    import requests
    try:
        resp = requests.post("http://localhost:8000/order", json=order.dict(), timeout=2)
        return resp.json()
    except:
        return {"success": False, "orderId": "MOCK", "message": "키움 서버 미연결"}

@app.get("/quote/{symbol}")
def get_quote(symbol: str):
    import requests
    try:
        resp = requests.get(f"http://localhost:8000/quote/{symbol}", timeout=2)
        return resp.json()
    except:
        return {"symbol": symbol, "price": "72000", "changePct": "0.01", "timestamp": ""}

@app.get("/chart/{symbol}")
def get_chart(symbol: str, interval: str = "1D", start_date: str = "", limit: int = 30):
    result = []
    base_price = 70000
    for i in range(limit):
        variation = np.random.randint(-1000, 1000)
        result.append({
            "timestamp": int(datetime.now().timestamp() * 1000) - (i * 86400000),
            "open": base_price + variation,
            "high": base_price + variation + 800,
            "low": base_price + variation - 600,
            "close": base_price + variation + 200
        })
    return result

@app.get("/search/stocks")
def search_stocks(q: str = Query(..., min_length=1)):
    stocks_db = [
        {"symbol": "005930", "name": "삼성전자", "market": "KOSPI"},
        {"symbol": "000660", "name": "SK하이닉스", "market": "KOSPI"},
        {"symbol": "035420", "name": "NAVER", "market": "KOSPI"},
    ]
    
    query = q.lower()
    results = [s for s in stocks_db if query in s["symbol"] or query in s["name"].lower()]
    return results[:10]

@app.post("/ai/recommend")
async def get_ai_recommendation(symbol: str):
    if not buy_model or not sell_model:
        raise HTTPException(status_code=503, detail="모델 미로드")
    
    features = np.random.rand(14).astype(np.float32)
    
    with torch.no_grad():
        buy_q = buy_model(torch.FloatTensor([features])).numpy()[0]
        buy_action = int(np.argmax(buy_q))
        buy_confidence = float(np.max(buy_q) - np.min(buy_q))
    
    if buy_action == 1 and buy_confidence > 0.3:
        return AIRecommendation(
            symbol=symbol,
            action="BUY",
            confidence=buy_confidence,
            recommended_qty=10,
            reason=f"DQN 매수 추천 (신뢰도: {buy_confidence:.2f})"
        )
    else:
        return AIRecommendation(
            symbol=symbol,
            action="HOLD",
            confidence=0.0,
            recommended_qty=0,
            reason="관망"
        )

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "buy_model_loaded": buy_model is not None,
        "sell_model_loaded": sell_model is not None,
        "port": 8001
    }

@app.get("/")
def root():
    return {"message": "DQN Model Server (64bit)", "port": 8001}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
