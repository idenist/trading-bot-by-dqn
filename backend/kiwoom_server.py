import sys
import requests
from PyQt5.QAxContainer import QAxWidget
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QEventLoop
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import uvicorn
from threading import Thread, Lock
import time
import random
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

auto_trade_stocks = []
auto_trade_running = False
auto_trade_thread = None
auto_trade_amount_per_stock = 1000000  # 추가: 종목당 투자금액
stock_cache = []
stock_cache_loading = False

# 추가: 자동매매 시작 모델에 금액 설정
class AutoTradeStart(BaseModel):
    stocks: List[str]
    amount_per_stock: int = 1000000

class Kiwoom(QAxWidget):
    def __init__(self):
        super().__init__()
        self.setControl("KHOPENAPI.KHOpenAPICtrl.1")
        self.OnEventConnect.connect(self._on_event_connect)
        self.OnReceiveTrData.connect(self._on_receive_tr_data)
        self.login_event_loop = None
        self.is_connected = False
        self.account_number = None
        self.tr_data = {}
        self.tr_lock = Lock()
        self.tr_received = False

    def _on_event_connect(self, err_code):
        if err_code == 0:
            print("Kiwoom login success")
            self.is_connected = True
            self.account_number = "8111496111"
            print(f"Account: {self.account_number}")
            self._start_background_stock_loading()
        else:
            print(f"Login failed: {err_code}")
        
        if self.login_event_loop:
            self.login_event_loop.exit()

    def _start_background_stock_loading(self):
        """백그라운드에서 주식 목록 로드"""
        def load_stocks():
            global stock_cache, stock_cache_loading
            if stock_cache_loading:
                return
            stock_cache_loading = True
            print("Starting background stock loading...")
            try:
                self._load_all_stocks()
            except Exception as e:
                print(f"Background stock loading failed: {e}")
            finally:
                stock_cache_loading = False
                
        thread = Thread(target=load_stocks, daemon=True)
        thread.start()

    def _load_all_stocks(self):
        """키움 API에서 모든 주식 목록 로드"""
        global stock_cache
        try:
            print("Loading all stocks from Kiwoom API...")
            kospi_codes = self.dynamicCall("GetCodeListByMarket(QString)", "0")
            kosdaq_codes = self.dynamicCall("GetCodeListByMarket(QString)", "10")
            
            print(f"Raw KOSPI codes length: {len(kospi_codes) if kospi_codes else 0}")
            print(f"Raw KOSDAQ codes length: {len(kosdaq_codes) if kosdaq_codes else 0}")
            
            all_stocks = []
            
            if kospi_codes:
                kospi_list = [code for code in kospi_codes.split(';') if code and len(code) == 6]
                print(f"Processing {len(kospi_list)} KOSPI stocks...")
                
                for i, code in enumerate(kospi_list):
                    try:
                        name = self.dynamicCall("GetMasterCodeName(QString)", code)
                        if name and name.strip():
                            all_stocks.append({
                                "symbol": code,
                                "name": name.strip(),
                                "market": "KOSPI"
                            })
                        
                        if (i + 1) % 200 == 0:
                            print(f"Processed {i + 1}/{len(kospi_list)} KOSPI stocks")
                        
                        if i % 50 == 0:
                            time.sleep(0.1)
                    except Exception as e:
                        print(f"Error processing KOSPI stock {code}: {e}")
                        continue
            
            if kosdaq_codes:
                kosdaq_list = [code for code in kosdaq_codes.split(';') if code and len(code) == 6]
                print(f"Processing {len(kosdaq_list)} KOSDAQ stocks...")
                
                for i, code in enumerate(kosdaq_list):
                    try:
                        name = self.dynamicCall("GetMasterCodeName(QString)", code)
                        if name and name.strip():
                            all_stocks.append({
                                "symbol": code,
                                "name": name.strip(),
                                "market": "KOSDAQ"
                            })
                        
                        if (i + 1) % 200 == 0:
                            print(f"Processed {i + 1}/{len(kosdaq_list)} KOSDAQ stocks")
                        
                        if i % 50 == 0:
                            time.sleep(0.1)
                    except Exception as e:
                        print(f"Error processing KOSDAQ stock {code}: {e}")
                        continue
            
            stock_cache = all_stocks
            print(f"Successfully loaded {len(stock_cache)} stocks from Kiwoom")
            print(f"KOSPI: {len([s for s in stock_cache if s['market'] == 'KOSPI'])}")
            print(f"KOSDAQ: {len([s for s in stock_cache if s['market'] == 'KOSDAQ'])}")
            
        except Exception as e:
            print(f"Failed to load stocks from Kiwoom: {e}")
            stock_cache = []

    def _on_receive_tr_data(self, screen, rqname, trcode, record, next, unused1, unused2, unused3, unused4):
        if rqname == "계좌평가잔고내역요청":
            try:
                cnt = self.dynamicCall("GetRepeatCnt(QString, QString)", trcode, rqname)
                positions = []
                
                for i in range(cnt):
                    code = self.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, i, "종목번호").strip().lstrip('A')
                    name = self.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, i, "종목명").strip()
                    qty = self.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, i, "보유수량").strip().lstrip('0') or "0"
                    avg_price = self.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, i, "매입가").strip().lstrip('0') or "0"
                    cur_price = self.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, i, "현재가").strip().replace('-', '').replace('+', '').lstrip('0') or "0"
                    
                    if int(qty) > 0:
                        positions.append({
                            "symbol": code,
                            "name": name,
                            "qty": str(int(qty)),
                            "avgPrice": str(int(avg_price)),
                            "lastPrice": str(int(cur_price)),
                            "pnl": str((int(cur_price) - int(avg_price)) * int(qty)),
                            "pnlPct": f"{(int(cur_price) / int(avg_price) - 1):.3f}"
                        })
                
                self.tr_data = positions
                self.tr_received = True
                
            except Exception as e:
                print(f"Position error: {e}")
                self.tr_data = []
                self.tr_received = True
        
        elif rqname == "예수금상세현황요청":
            try:
                deposit = self.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, 0, "예수금").strip().lstrip('0') or "0"
                self.tr_data = {"deposit": deposit}
                self.tr_received = True
            except Exception as e:
                print(f"Deposit error: {e}")
                self.tr_data = {}
                self.tr_received = True
        
        elif rqname == "현재가조회":
            try:
                price = self.dynamicCall("GetCommData(QString, QString, int, QString)", trcode, rqname, 0, "현재가").strip().replace('-', '').replace('+', '').lstrip('0') or "0"
                self.tr_data = price
                self.tr_received = True
            except Exception as e:
                self.tr_data = "0"
                self.tr_received = True

    def connect(self):
        self.login_event_loop = QEventLoop()
        self.dynamicCall("CommConnect()")
        self.login_event_loop.exec_()
        return self.is_connected

    def get_positions(self):
        if not self.is_connected:
            return []
        
        with self.tr_lock:
            self.tr_data = []
            self.tr_received = False
            
            self.dynamicCall("SetInputValue(QString, QString)", "계좌번호", self.account_number)
            self.dynamicCall("SetInputValue(QString, QString)", "비밀번호", "")
            self.dynamicCall("SetInputValue(QString, QString)", "비밀번호입력매체구분", "00")
            self.dynamicCall("SetInputValue(QString, QString)", "조회구분", "1")
            
            ret = self.dynamicCall("CommRqData(QString, QString, int, QString)", "계좌평가잔고내역요청", "opw00018", 0, "2000")
            
            if ret == 0:
                for _ in range(50):
                    time.sleep(0.1)
                    QApplication.processEvents()
                    if self.tr_received:
                        break
            
            return self.tr_data if isinstance(self.tr_data, list) else []

    def get_deposit(self):
        if not self.is_connected:
            return {}
        
        with self.tr_lock:
            self.tr_data = {}
            self.tr_received = False
            
            self.dynamicCall("SetInputValue(QString, QString)", "계좌번호", self.account_number)
            self.dynamicCall("SetInputValue(QString, QString)", "비밀번호", "")
            self.dynamicCall("SetInputValue(QString, QString)", "비밀번호입력매체구분", "00")
            
            ret = self.dynamicCall("CommRqData(QString, QString, int, QString)", "예수금상세현황요청", "opw00001", 0, "2003")
            
            if ret == 0:
                for _ in range(50):
                    time.sleep(0.1)
                    QApplication.processEvents()
                    if self.tr_received:
                        break
            
            return self.tr_data if isinstance(self.tr_data, dict) else {}

    def get_price(self, code):
        if not self.is_connected:
            return "0"
        
        with self.tr_lock:
            self.tr_received = False
            self.dynamicCall("SetInputValue(QString, QString)", "종목코드", code)
            self.dynamicCall("CommRqData(QString, QString, int, QString)", "현재가조회", "opt10001", 0, "2001")
            
            for _ in range(50):
                time.sleep(0.1)
                QApplication.processEvents()
                if self.tr_received:
                    break
            
            return self.tr_data

    def send_order(self, order_type, code, qty, price):
        if not self.is_connected:
            return False
        
        order_type_code = 1 if order_type == "BUY" else 2
        hoga_gb = "03" if price == 0 else "00"
        
        result = self.dynamicCall(
            "SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
            ["Order", "2000", self.account_number, order_type_code, code, qty, price, hoga_gb, ""]
        )
        
        print(f"Order: {order_type} {code} {qty}@{price} => {result}")
        return result == 0

kiwoom = None
qapp = None

def run_kiwoom():
    global kiwoom, qapp
    qapp = QApplication(sys.argv)
    kiwoom = Kiwoom()
    kiwoom.connect()
    qapp.exec_()

# 수정된 자동매매 루프 (매도 에이전트 우선 + 금액 설정)
def auto_trade_loop():
    global auto_trade_running, auto_trade_amount_per_stock
    print("ENHANCED AUTO TRADE LOOP STARTED")
    print(f"Investment per stock: {auto_trade_amount_per_stock:,}원")
    
    while auto_trade_running:
        print(f"AUTO TRADE LOOP: running={auto_trade_running}, stocks={auto_trade_stocks}")
        
        if not kiwoom or not kiwoom.is_connected or len(auto_trade_stocks) == 0:
            print("Waiting for connection or stocks...")
            time.sleep(5)
            continue
        
        try:
            for stock_code in auto_trade_stocks:
                if not auto_trade_running:
                    break
                    
                print(f"\n=== Processing {stock_code} ===")
                
                # 현재 보유 포지션 확인
                positions = kiwoom.get_positions()
                current_position = None
                for pos in positions:
                    if pos["symbol"] == stock_code:
                        current_position = pos
                        break
                
                has_position = current_position and int(current_position["qty"]) > 0
                
                if has_position:
                    # 보유량 있음 → 매도 에이전트 우선 호출
                    print(f"[{stock_code}] Has {current_position['qty']} shares, checking SELL agent first...")
                    
                    try:
                        sell_response = requests.get(
                            f"http://localhost:8001/predict/{stock_code}/sell",
                            timeout=10
                        )
                        
                        if sell_response.status_code == 200:
                            sell_data = sell_response.json()
                            sell_action = sell_data.get("action", "HOLD")
                            sell_confidence = sell_data.get("confidence", 0.0)
                            
                            print(f"[{stock_code}] SELL agent: {sell_action} (confidence: {sell_confidence:.3f})")
                            
                            if sell_action == "SELL" and sell_confidence > 0.5:
                                # 매도 실행
                                qty = int(current_position["qty"])
                                print(f"[{stock_code}] SELLING {qty} shares")
                                
                                success = kiwoom.send_order("SELL", stock_code, qty, 0)
                                print(f"[{stock_code}] Sell result: {success}")
                                continue  # 매도했으면 이번 턴에서는 매수 안함
                        
                    except Exception as e:
                        print(f"[{stock_code}] SELL agent error: {e}")
                
                # 매수 에이전트 호출 (보유량 없거나 매도 안하는 경우)
                try:
                    buy_response = requests.get(
                        f"http://localhost:8001/predict/{stock_code}/buy",
                        timeout=10
                    )
                    
                    if buy_response.status_code == 200:
                        buy_data = buy_response.json()
                        buy_action = buy_data.get("action", "HOLD")
                        buy_confidence = buy_data.get("confidence", 0.0)
                        
                        print(f"[{stock_code}] BUY agent: {buy_action} (confidence: {buy_confidence:.3f})")
                        
                        if buy_action == "BUY" and buy_confidence > 0.5:
                            # 매수 실행 - 설정된 금액으로 수량 계산
                            current_price = int(kiwoom.get_price(stock_code))
                            
                            if current_price > 0:
                                qty = max(1, auto_trade_amount_per_stock // current_price)
                                total_cost = qty * current_price
                                
                                print(f"[{stock_code}] BUYING {qty} shares @ {current_price:,}원")
                                print(f"[{stock_code}] Total cost: {total_cost:,}원 (Budget: {auto_trade_amount_per_stock:,}원)")
                                
                                success = kiwoom.send_order("BUY", stock_code, qty, 0)
                                print(f"[{stock_code}] Buy result: {success}")
                
                except Exception as e:
                    print(f"[{stock_code}] BUY agent error: {e}")
                
                time.sleep(2)  # 종목 간 딜레이
                
        except Exception as e:
            print(f"Auto trade loop error: {e}")
            
        print(f"Auto trade cycle completed. Waiting 60 seconds...")
        time.sleep(60)
    
    print("AUTO TRADE LOOP STOPPED")

class OrderRequest(BaseModel):
    symbol: str
    side: str
    type: str
    price: float
    qty: int

@app.on_event("startup")
async def startup():
    print("Starting Kiwoom Server...")
    kiwoom_thread = Thread(target=run_kiwoom, daemon=True)
    kiwoom_thread.start()
    time.sleep(3)

@app.get("/positions")
def get_positions():
    if kiwoom and kiwoom.is_connected:
        return kiwoom.get_positions()
    return []

@app.get("/portfolio")
def get_portfolio():
    if kiwoom and kiwoom.is_connected:
        try:
            deposit_info = kiwoom.get_deposit()
            positions = kiwoom.get_positions()
            
            cash = int(deposit_info.get("deposit", "0"))
            stock_value = sum(int(pos["lastPrice"]) * int(pos["qty"]) for pos in positions)
            total_equity = cash + stock_value
            
            return {
                "currency": "KRW",
                "totalEquity": str(total_equity),
                "cash": str(cash),
                "pnlDay": "0",
                "pnlDayPct": "0.0",
                "updatedAt": "2025-10-10T16:00:00Z"
            }
        except Exception as e:
            print(f"Portfolio error: {e}")
            return {"currency": "KRW", "totalEquity": "0", "cash": "0", "pnlDay": "0", "pnlDayPct": "0.0", "updatedAt": ""}
    
    return {"currency": "KRW", "totalEquity": "0", "cash": "0", "pnlDay": "0", "pnlDayPct": "0.0", "updatedAt": ""}

@app.get("/quote/{symbol}")
def get_quote(symbol: str):
    if kiwoom and kiwoom.is_connected:
        price = kiwoom.get_price(symbol)
        return {"symbol": symbol, "price": price, "changePct": "0.0", "timestamp": ""}
    return {"symbol": symbol, "price": "0", "changePct": "0.0", "timestamp": ""}

# kiwoom_server.py에서 get_chart_post 함수 수정
@app.post("/chart")
def get_chart_post(request: dict):
    symbol = request.get("symbol", "005930")
    result = []
    base_price = 50000
    
    for i in range(30):
        # 상승/하락을 확실하게 구분되도록 생성
        is_rising = (i % 3 == 0)  # 3분의 1은 상승
        is_falling = (i % 3 == 1)  # 3분의 1은 하락
        # 나머지는 보합
        
        open_price = base_price
        
        if is_rising:
            # 명확한 상승 캔들 (초록색)
            close_price = open_price + random.randint(500, 2000)
        elif is_falling:
            # 명확한 하락 캔들 (빨간색) 
            close_price = open_price - random.randint(500, 2000)
        else:
            # 보합 (작은 변동)
            close_price = open_price + random.randint(-200, 200)
        
        high_price = max(open_price, close_price) + random.randint(0, 500)
        low_price = min(open_price, close_price) - random.randint(0, 500)
        
        result.append({
            "timestamp": int(time.time() * 1000) - (i * 86400000),
            "open": open_price,
            "high": high_price, 
            "low": low_price,
            "close": close_price
        })
        
        base_price = close_price  # 다음 봉의 기준가
    
    return result


@app.post("/order")
def place_order(order: OrderRequest):
    if kiwoom and kiwoom.is_connected:
        price_val = 0 if order.type == "MARKET" else int(order.price)
        success = kiwoom.send_order(order.side, order.symbol, order.qty, price_val)
        return {
            "success": success,
            "orderId": f"ORD{int(time.time())}",
            "message": "Order sent" if success else "Order failed"
        }
    return {"success": False, "orderId": "NONE", "message": "Not connected"}

@app.get("/ai/recommend")
def ai_recommend_proxy(symbol: str = Query(...)):
    """AI 추천을 DQN 서버(8001)로 프록시"""
    import requests
    try:
        print(f"PROXY REQUEST to DQN server for {symbol}")
        resp = requests.get(f"http://localhost:8001/ai/recommend?symbol={symbol}", timeout=5)
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
            "reason": f"DQN server error: {str(e)}"
        }

# 수정된 자동매매 시작 API (금액 설정 포함)
@app.post("/auto-trade/start")
def start_auto_trade(request: AutoTradeStart):
    global auto_trade_stocks, auto_trade_running, auto_trade_thread, auto_trade_amount_per_stock
    
    print(f"AUTO TRADE START REQUEST: stocks={request.stocks}, amount_per_stock={request.amount_per_stock:,}원")
    
    try:
        if not request.stocks or len(request.stocks) == 0:
            print("ERROR: No stocks provided")
            return {"success": False, "message": "No stocks provided", "stocks": []}
        
        if not kiwoom or not kiwoom.is_connected:
            print("ERROR: Kiwoom not connected")
            return {"success": False, "message": "Kiwoom not connected", "stocks": request.stocks}
        
        # 기존 자동매매 중지
        if auto_trade_running:
            print("Stopping existing auto trade...")
            auto_trade_running = False
            time.sleep(2)
        
        # 새로운 설정으로 자동매매 시작
        auto_trade_stocks = request.stocks
        auto_trade_amount_per_stock = request.amount_per_stock  # 금액 설정
        auto_trade_running = True
        
        auto_trade_thread = Thread(target=auto_trade_loop, daemon=True)
        auto_trade_thread.start()
        
        print(f"AUTO TRADE THREAD STARTED")
        
        response = {
            "success": True,
            "message": f"Auto trade started for {len(request.stocks)} stocks with {request.amount_per_stock:,}원 each",
            "stocks": request.stocks,
            "amount_per_stock": request.amount_per_stock
        }
        
        print(f"AUTO TRADE START RESPONSE: {response}")
        return response
        
    except Exception as e:
        print(f"AUTO TRADE START ERROR: {e}")
        return {"success": False, "message": f"Error: {str(e)}", "stocks": request.stocks}

@app.post("/auto-trade/stop")
def stop_auto_trade():
    global auto_trade_running, auto_trade_stocks
    print("AUTO TRADE STOP REQUEST")
    
    try:
        auto_trade_running = False
        auto_trade_stocks = []
        response = {"success": True, "message": "Auto trade stopped"}
        print(f"AUTO TRADE STOP RESPONSE: {response}")
        return response
    except Exception as e:
        print(f"AUTO TRADE STOP ERROR: {e}")
        return {"success": False, "message": f"Error: {str(e)}"}

@app.get("/auto-trade/status")
def get_auto_trade_status():
    status = {
        "running": auto_trade_running,
        "stocks": auto_trade_stocks,
        "count": len(auto_trade_stocks),
        "amount_per_stock": auto_trade_amount_per_stock if auto_trade_running else 0
    }
    
    print(f"AUTO TRADE STATUS: {status}")
    return status

@app.get("/search/stocks")
def search_stocks(q: str = Query(..., min_length=1)):
    global stock_cache, stock_cache_loading
    
    if stock_cache_loading:
        return [{"symbol": "LOADING", "name": "주식 목록을 로딩 중입니다...", "market": "INFO"}]
    
    if not stock_cache and kiwoom and kiwoom.is_connected:
        kiwoom._start_background_stock_loading()
        return [{"symbol": "LOADING", "name": "주식 목록 로딩을 시작합니다...", "market": "INFO"}]
    
    if not stock_cache:
        return [{"symbol": "ERROR", "name": "키움 서버가 연결되지 않았습니다", "market": "ERROR"}]
    
    query = q.lower()
    results = []
    
    for stock in stock_cache:
        if (query in stock["symbol"].lower() or
            query in stock["name"].lower()):
            results.append(stock)
            
            if len(results) >= 100:
                break
    
    print(f"Search '{q}': found {len(results)} results out of {len(stock_cache)} total stocks")
    return results

@app.get("/refresh-stocks")
def refresh_stocks():
    """주식 캐시를 강제로 새로고침"""
    global stock_cache, stock_cache_loading
    
    if stock_cache_loading:
        return {"message": "Already loading stocks", "status": "loading"}
    
    stock_cache = []
    if kiwoom and kiwoom.is_connected:
        kiwoom._start_background_stock_loading()
        return {"message": "Stock cache refresh started", "status": "started"}
    else:
        return {"message": "Kiwoom not connected", "status": "error"}

@app.get("/stocks-count")
def get_stocks_count():
    """현재 로드된 주식 개수 및 상태 확인"""
    global stock_cache_loading
    return {
        "total_stocks": len(stock_cache),
        "kospi_count": len([s for s in stock_cache if s["market"] == "KOSPI"]),
        "kosdaq_count": len([s for s in stock_cache if s["market"] == "KOSDAQ"]),
        "loading": stock_cache_loading,
        "kiwoom_connected": kiwoom.is_connected if kiwoom else False,
        "sample": stock_cache[:10] if stock_cache else []
    }

@app.get("/clear-cache")
def clear_cache():
    """캐시 완전 삭제 (재시작과 같은 효과)"""
    global stock_cache, stock_cache_loading
    stock_cache = []
    stock_cache_loading = False
    print("Stock cache completely cleared")
    return {
        "message": "Stock cache completely cleared",
        "status": "cleared",
        "total_stocks": len(stock_cache)
    }

@app.get("/force-reload-stocks")
def force_reload_stocks():
    """강제로 주식 목록 다시 로드"""
    global stock_cache, stock_cache_loading
    if stock_cache_loading:
        return {"message": "Already loading", "status": "loading"}
    
    if not kiwoom or not kiwoom.is_connected:
        return {"message": "Kiwoom not connected", "status": "error"}
    
    stock_cache = []
    kiwoom._start_background_stock_loading()
    return {"message": "Force reload started", "status": "started"}

@app.get("/health")
def health():
    status = {
        "status": "healthy",
        "connected": kiwoom.is_connected if kiwoom else False,
        "auto_trade_running": auto_trade_running,
        "auto_trade_stocks": len(auto_trade_stocks),
        "total_stocks": len(stock_cache),
        "stocks_loading": stock_cache_loading,
        "port": 8000
    }
    
    print(f"HEALTH CHECK: {status}")
    return status

@app.get("/")
def root():
    return {
        "message": "Kiwoom Trading Server",
        "account": kiwoom.account_number if kiwoom and kiwoom.is_connected else None,
        "connected": kiwoom.is_connected if kiwoom else False,
        "auto_trade": {
            "running": auto_trade_running,
            "stocks": auto_trade_stocks
        },
        "stock_cache": {
            "total": len(stock_cache),
            "loading": stock_cache_loading
        }
    }

if __name__ == "__main__":
    print("Starting Kiwoom Server on port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
