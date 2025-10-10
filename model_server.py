# model_server.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import List
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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

class PredictionRequest(BaseModel):
    features: List[float]
    model_type: str

class PredictionResponse(BaseModel):
    action: int
    q_values: List[float]
    confidence: float

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
        print("매수 모델 로드 완료: buy_model.pth")
        
        sell_model = DQN(INPUT_DIM, OUTPUT_DIM)
        sell_model.load_state_dict(torch.load("sell_model.pth", map_location='cpu'))
        sell_model.eval()
        print("매도 모델 로드 완료: sell_model.pth")
        
    except Exception as e:
        print(f"모델 로드 실패: {e}")

@app.post("/predict", response_model=PredictionResponse)
async def predict_action(request: PredictionRequest):
    if buy_model is None or sell_model is None:
        raise HTTPException(status_code=500, detail="모델이 로드되지 않았습니다")
    
    try:
        features = np.array(request.features, dtype=np.float32)
        
        if len(features) != 14:
            raise HTTPException(status_code=400, detail=f"특징 개수 오류. 예상: 14, 실제: {len(features)}")
        
        input_tensor = torch.FloatTensor([features])
        
        if request.model_type == "buy":
            model = buy_model
        elif request.model_type == "sell":
            model = sell_model
        else:
            raise HTTPException(status_code=400, detail="model_type은 'buy' 또는 'sell'이어야 합니다")
        
        with torch.no_grad():
            q_values = model(input_tensor).numpy()[0]
        
        action = int(torch.argmax(torch.tensor(q_values)))
        confidence = max(q_values) - min(q_values)
        
        return PredictionResponse(
            action=action,
            q_values=q_values.tolist(),
            confidence=confidence
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"예측 실패: {str(e)}")

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "buy_model_loaded": buy_model is not None,
        "sell_model_loaded": sell_model is not None
    }

@app.get("/")
async def root():
    return {"message": "PyTorch DQN 모델 서버 실행 중"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
