import yfinance as yf
import pandas as pd
import ta
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, CCIIndicator, EMAIndicator
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import torch
import torch.nn as nn
import torch.nn.functional as F
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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

INPUT_DIM = 14
OUTPUT_DIM = 2

# 모델 로딩 (파일이 없으면 더미 모델)
try:
    buy_model = DQN(INPUT_DIM, OUTPUT_DIM)
    if os.path.exists("buy_model.pth"):
        buy_model.load_state_dict(torch.load("buy_model.pth", map_location=torch.device('cpu')))
        print("Buy model loaded from buy_model.pth")
    else:
        print("WARNING: buy_model.pth not found, using untrained model")
    buy_model.eval()

    sell_model = DQN(INPUT_DIM, OUTPUT_DIM)
    if os.path.exists("sell_model.pth"):
        sell_model.load_state_dict(torch.load("sell_model.pth", map_location=torch.device('cpu')))
        print("Sell model loaded from sell_model.pth")
    else:
        print("WARNING: sell_model.pth not found, using untrained model")
    sell_model.eval()

    print("Buy and Sell models initialized successfully")

except Exception as e:
    print(f"Model loading error: {e}")
    # 에러 시 더미 모델 생성
    buy_model = DQN(INPUT_DIM, OUTPUT_DIM)
    sell_model = DQN(INPUT_DIM, OUTPUT_DIM)
    buy_model.eval()
    sell_model.eval()

def map_korean_ticker(symbol):
    """한국 주식 코드를 yfinance 형식으로 변환"""
    if symbol.isdigit() and len(symbol) == 6:
        return f"{symbol}.KS"
    return symbol

def get_state_from_yfinance(ticker):
    """yfinance에서 데이터를 가져와서 DQN 입력 상태 벡터 생성"""
    mapped_ticker = map_korean_ticker(ticker)
    try:
        print(f"Fetching data for {ticker} ({mapped_ticker})")
        df_origin = yf.download(mapped_ticker, period="2mo", interval="1d", progress=False)

        if df_origin.empty:
            raise ValueError(f"No data available for {ticker}")

        # pandas 오류 해결: dropna() 먼저 적용
        df_origin = df_origin.dropna()
        if len(df_origin) < 21:  # EMA20 계산을 위해 최소 21일 필요
            raise ValueError(f"Insufficient data for {ticker} (only {len(df_origin)} days)")

        df = pd.DataFrame()

        # 변화량 계산 (안전하게)
        df['Open_Change'] = df_origin['Open'].diff(1).fillna(0)
        df['High_Change'] = df_origin['High'].diff(1).fillna(0)
        df['Low_Change'] = df_origin['Low'].diff(1).fillna(0)
        df['Close_Change'] = df_origin['Close'].diff(1).fillna(0)
        df['Volume_Change'] = df_origin['Volume'].diff(1).fillna(0)

        # EMA20 계산 (안전하게)
        try:
            ema20 = EMAIndicator(close=df_origin['Close'], window=20)
            ema_values = ema20.ema_indicator()
            df['EWM20_Change'] = ema_values.diff(1).fillna(0)
        except Exception as e:
            print(f"EMA calculation error: {e}, using simple moving average")
            df['EWM20_Change'] = df_origin['Close'].rolling(20).mean().diff(1).fillna(0)

        # KDJ (안전하게)
        try:
            stoch = StochasticOscillator(
                high=df_origin['High'],
                low=df_origin['Low'],
                close=df_origin['Close'],
                window=5,
                smooth_window=3
            )
            df['FastK'] = stoch.stoch().fillna(50)
            df['SlowD'] = stoch.stoch_signal().fillna(50)
            df['SlowJ'] = (3 * df['FastK'] - 2 * df['SlowD']).fillna(50)
        except Exception as e:
            print(f"KDJ calculation error: {e}, using default values")
            df['FastK'] = pd.Series([50] * len(df_origin), index=df_origin.index)
            df['SlowD'] = pd.Series([50] * len(df_origin), index=df_origin.index)
            df['SlowJ'] = pd.Series([50] * len(df_origin), index=df_origin.index)

        # MACD (안전하게)
        try:
            macd = MACD(close=df_origin['Close'], window_slow=26, window_fast=12, window_sign=9)
            df['MACD'] = macd.macd().fillna(0)
            df['MACDS'] = macd.macd_signal().fillna(0)
            df['MACDO'] = (df['MACD'] - df['MACDS']).fillna(0)
        except Exception as e:
            print(f"MACD calculation error: {e}, using default values")
            df['MACD'] = pd.Series([0] * len(df_origin), index=df_origin.index)
            df['MACDS'] = pd.Series([0] * len(df_origin), index=df_origin.index)
            df['MACDO'] = pd.Series([0] * len(df_origin), index=df_origin.index)

        # CCI (안전하게)
        try:
            cci = CCIIndicator(
                high=df_origin['High'],
                low=df_origin['Low'],
                close=df_origin['Close'],
                window=14
            )
            df['CCI'] = cci.cci().fillna(0)
        except Exception as e:
            print(f"CCI calculation error: {e}, using default values")
            df['CCI'] = pd.Series([0] * len(df_origin), index=df_origin.index)

        # RSI (안전하게)
        try:
            rsi = RSIIndicator(close=df_origin['Close'], window=14)
            df['RSI'] = rsi.rsi().fillna(50)
        except Exception as e:
            print(f"RSI calculation error: {e}, using default values")
            df['RSI'] = pd.Series([50] * len(df_origin), index=df_origin.index)

        # 최종 상태 벡터 (NaN 제거)
        state_features = [
            'Open_Change', 'High_Change', 'Low_Change', 'Close_Change', 'Volume_Change',
            'EWM20_Change', 'FastK', 'SlowD', 'SlowJ',
            'MACD', 'MACDS', 'MACDO', 'CCI', 'RSI'
        ]

        latest_state = df[state_features].fillna(0).iloc[-1].values.astype(float)
        last_date = df_origin.index[-1].strftime('%Y-%m-%d')
        last_price = float(df_origin['Close'].iloc[-1])

        print(f"{ticker} state extracted: RSI={latest_state[-1]:.2f}, MACD={latest_state[9]:.4f}, Price={last_price:,.0f}, Date={last_date}")

        return latest_state, last_date, last_price

    except Exception as e:
        print(f"yfinance error for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get data for {ticker}: {str(e)}")

def decide_action(ticker, agent_type):
    """DQN 모델을 사용하여 매수/매도 결정"""
    try:
        state, last_date, last_price = get_state_from_yfinance(ticker)
        input_tensor = torch.FloatTensor([state])

        with torch.no_grad():
            if agent_type == "buy":
                q_values = buy_model(input_tensor).numpy().tolist()[0]
                action = int(torch.argmax(torch.tensor(q_values)))
                confidence = max(q_values)
                action_name = "BUY" if action == 1 else "HOLD"

            elif agent_type == "sell":
                q_values = sell_model(input_tensor).numpy().tolist()[0]
                action = int(torch.argmax(torch.tensor(q_values)))
                confidence = max(q_values)
                action_name = "SELL" if action == 1 else "HOLD"

            else:
                raise ValueError("Invalid agent type")

        print(f"DQN {agent_type.upper()} for {ticker}: {action_name} (confidence: {confidence:.4f})")

        return {
            "action": action_name,
            "confidence": float(abs(confidence)),
            "reason": f"DQN {agent_type} model prediction (Price: {last_price:,.0f})",
            "date": last_date,
            "price": last_price
        }

    except Exception as e:
        print(f"Decision error for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=f"Decision failed for {ticker}: {str(e)}")

@app.get("/ai/recommend")
def ai_recommend(symbol: str = Query(...)):
    """AI 추천 API (GET 방식)"""
    print(f"AI recommendation request: {symbol}")
    try:
        # 매수 및 매도 모델로부터 결정 받기
        buy_dec = decide_action(symbol, "buy")
        sell_dec = decide_action(symbol, "sell")

        # 최종 결정 로직
        if buy_dec["action"] == "BUY" and buy_dec["confidence"] > 0.5:
            final_action = "BUY"
            confidence = buy_dec["confidence"]
            reason = buy_dec["reason"]
        elif sell_dec["action"] == "SELL" and sell_dec["confidence"] > 0.5:
            final_action = "SELL"
            confidence = sell_dec["confidence"]
            reason = sell_dec["reason"]
        else:
            final_action = "HOLD"
            confidence = max(buy_dec["confidence"], sell_dec["confidence"])
            reason = "Hold (low confidence)"

        result = {
            "symbol": symbol,
            "action": final_action,
            "confidence": confidence,
            "recommended_qty": 10 if final_action in ["BUY", "SELL"] else 0,
            "reason": reason,
            "date": buy_dec["date"],
            "price": buy_dec["price"]
        }

        print(f"{symbol} final recommendation: {final_action} (confidence: {confidence:.4f})")
        return result

    except Exception as e:
        print(f"AI recommend error for {symbol}: {e}")
        # 에러 시 기본 HOLD 응답
        return {
            "symbol": symbol,
            "action": "HOLD",
            "confidence": 0.0,
            "recommended_qty": 0,
            "reason": f"Data fetch failed: {str(e)}",
            "date": "N/A",
            "price": 0
        }

# 추가: 분리된 매수 에이전트 API
@app.get("/predict/{ticker}/buy")
def predict_buy(ticker: str):
    """매수 에이전트 전용 API"""
    print(f"BUY agent prediction for {ticker}")
    try:
        return decide_action(ticker, "buy")
    except Exception as e:
        return {
            "action": "HOLD",
            "confidence": 0.0,
            "reason": f"Error: {str(e)}",
            "date": "N/A",
            "price": 0
        }

# 추가: 분리된 매도 에이전트 API
@app.get("/predict/{ticker}/sell")
def predict_sell(ticker: str):
    """매도 에이전트 전용 API"""
    print(f"SELL agent prediction for {ticker}")
    try:
        return decide_action(ticker, "sell")
    except Exception as e:
        return {
            "action": "HOLD",
            "confidence": 0.0,
            "reason": f"Error: {str(e)}",
            "date": "N/A",
            "price": 0
        }

@app.get("/predict/{ticker}/{agent}")
def predict_ticker(ticker: str, agent: str):
    """개별 예측 API (매수/매도 모델 개별 테스트용)"""
    return decide_action(ticker, agent)

@app.get("/health")
def health_check():
    """서버 상태 확인"""
    return {
        "status": "healthy",
        "buy_model_loaded": buy_model is not None,
        "sell_model_loaded": sell_model is not None,
        "port": 8001,
        "message": "DQN AI Server Running"
    }

@app.get("/test/{symbol}")
def test_data_fetch(symbol: str):
    """데이터 가져오기 테스트용"""
    try:
        state, date, price = get_state_from_yfinance(symbol)
        return {
            "symbol": symbol,
            "date": date,
            "price": price,
            "state_vector_length": len(state),
            "rsi": float(state[-1]),
            "macd": float(state[9]),
            "status": "success"
        }
    except Exception as e:
        return {
            "symbol": symbol,
            "status": "error",
            "error": str(e)
        }

@app.get("/")
def root():
    """루트 엔드포인트"""
    return {
        "message": "DQN AI Trading Server",
        "port": 8001,
        "models_loaded": buy_model is not None and sell_model is not None,
        "endpoints": [
            "/ai/recommend?symbol=005930",
            "/predict/005930/buy",
            "/predict/005930/sell",
            "/predict/005930/buy",
            "/predict/005930/sell",
            "/test/005930",
            "/health"
        ]
    }

if __name__ == "__main__":
    print("Starting DQN AI Server on port 8001...")
    uvicorn.run(app, host="0.0.0.0", port=8001)
