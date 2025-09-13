import yfinance as yf
import pandas as pd
import ta
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, CCIIndicator, EMAIndicator
from fastapi import FastAPI
from pydantic import BaseModel
import torch
import torch.nn as nn
import torch.nn.functional as F
from fastapi.middleware.cors import CORSMiddleware

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

# 모델 로드
INPUT_DIM = 14
OUTPUT_DIM = 2

buy_model = DQN(INPUT_DIM, OUTPUT_DIM)
buy_model.load_state_dict(torch.load("buy_model.pth", map_location=torch.device('cpu')))
buy_model.eval()

sell_model = DQN(INPUT_DIM, OUTPUT_DIM)
sell_model.load_state_dict(torch.load("sell_model.pth", map_location=torch.device('cpu')))
sell_model.eval()

# FastAPI 앱
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 📦 상태 추출 함수 수정
def get_state_from_yfinance(ticker):
    df_origin = pd.read_csv('AAPL.csv')

    df = pd.DataFrame()

    # 기본적인 변화량
    df['Open_Change']   = df_origin['Open'].diff(1)
    df['High_Change']   = df_origin['High'].diff(1)
    df['Low_Change']    = df_origin['Low'].diff(1)
    df['Close_Change']  = df_origin['Close'].diff(1)
    df['Volume_Change'] = df_origin['Volume'].diff(1)

    # 20일 EWM
    ema20 = EMAIndicator(close=df_origin['Close'], window=20)
    df_origin['EWM20'] = ema20.ema_indicator()
    df['EWM20_Change'] = df_origin['EWM20'].diff(1)

    # KDJ
    stoch = StochasticOscillator(
        high=df_origin['High'],
        low=df_origin['Low'],
        close=df_origin['Close'],
        window=5,
        smooth_window=3
    )
    df['FastK'] = stoch.stoch()
    df['SlowD'] = stoch.stoch_signal()
    df['SlowJ'] = 3 * df['FastK'] - 2 * df['SlowD']

    # MACD
    macd = MACD(
        close=df_origin['Close'],
        window_slow=26,
        window_fast=12,
        window_sign=9
    )
    df['MACD']  = macd.macd()
    df['MACDS'] = macd.macd_signal()
    df['MACDO'] = df['MACD'] - df['MACDS']

    # CCI
    cci = CCIIndicator(
        high=df_origin['High'],
        low=df_origin['Low'],
        close=df_origin['Close'],
        window=14,
        constant=0.015
    )
    df['CCI'] = cci.cci()

    # RSI
    rsi = RSIIndicator(
        close=df_origin['Close'],
        window=14
    )
    df['RSI'] = rsi.rsi()

    # 마지막 날짜 가져오기
    last_date = df_origin['Date'].iloc[-1][:10] if 'Date' in df_origin.columns else 'N/A'

    # 마지막 유효 상태 1줄 추출
    latest_state = df.dropna().iloc[-1].values.astype(float)

    return latest_state, last_date

@app.get("/predict/{ticker}/{agent}")
def predict_ticker(ticker: str, agent: str):
    try:
        state, last_date = get_state_from_yfinance(ticker)
    except Exception as e:
        return {"error": str(e)}

    input_tensor = torch.FloatTensor([state])

    with torch.no_grad():
        if agent == "buy":
            q_values = buy_model(input_tensor).numpy().tolist()[0]
        elif agent == "sell":
            q_values = sell_model(input_tensor).numpy().tolist()[0]
        else:
            return {"error": "agent must be 'buy' or 'sell'"}

    action = int(torch.argmax(torch.tensor(q_values)))
    return {
        "q_values": q_values,
        "action": action,
        "state": state.tolist(),
        "date": last_date
    }
