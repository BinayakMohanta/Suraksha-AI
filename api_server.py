from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

import dynamic_pricing_xgb as dp
import os

MODEL_PATH = "model.joblib"

app = FastAPI(title="Dynamic Pricing API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080", "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PredictRequest(BaseModel):
    rainfall: float
    temperature: float
    aqi: float
    safe_zone: float


@app.on_event("startup")
def startup_event():
    global model
    # try to load persisted model first
    try:
        model = dp.load_model(MODEL_PATH)
        print(f"Loaded model from {MODEL_PATH}")
    except FileNotFoundError:
        print("No persisted model found, training new model...")
        model = dp.train_model()
        try:
            dp.save_model(model, MODEL_PATH)
            print(f"Saved trained model to {MODEL_PATH}")
        except Exception as e:
            print("Warning: failed to save model:", e)


@app.post("/predict")
def predict(req: PredictRequest):
    res = dp.dynamic_pricing_pipeline(model, req.rainfall, req.temperature, req.aqi, req.safe_zone)
    return res
