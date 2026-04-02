# dynamic_premium_final.py

import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
import joblib
import os

# -------------------------------
# GLOBAL SCALER
# -------------------------------
scaler = StandardScaler()


# -------------------------------
# STEP 1: TRAIN MODEL (ML PART)
# -------------------------------
def train_model():

    # Features: [rainfall, temperature, aqi, safe_zone]
    X = np.array([
        [10, 30, 100, 0.9],
        [70, 38, 250, 0.2],
        [50, 35, 300, 0.4],
        [5, 28, 80, 0.95],
        [80, 40, 350, 0.1],
        [20, 32, 150, 0.8],
        [60, 36, 280, 0.3],
        [90, 42, 400, 0.1],
        [30, 34, 120, 0.7],
        [100, 45, 450, 0.05]
    ])

    # Risk scores (training targets)
    y = np.array([
        0.2, 0.9, 0.7, 0.1, 1.0,
        0.3, 0.8, 1.0, 0.4, 1.0
    ])

    X_scaled = scaler.fit_transform(X)

    model = LinearRegression()
    model.fit(X_scaled, y)

    return model


def save_model(model, path: str = "model.joblib"):
    """Persist trained model and scaler together."""
    joblib.dump({"model": model, "scaler": scaler}, path)


def load_model(path: str = "model.joblib"):
    """Load trained model and set global scaler. Raises FileNotFoundError if absent."""
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    data = joblib.load(path)
    # restore scaler globally
    global scaler
    scaler = data.get("scaler", scaler)
    return data.get("model")


# -------------------------------
# STEP 2: HYBRID AI RISK MODEL
# -------------------------------
def predict_risk(model, rainfall, temperature, aqi, safe_zone):

    # ML prediction
    features = np.array([[rainfall, temperature, aqi, safe_zone]])
    features_scaled = scaler.transform(features)
    ml_risk = model.predict(features_scaled)[0]

    # Strong domain logic (more reliable)
    rule_risk = (
        (rainfall / 100) * 0.5 +     # increase weight
        (temperature / 50) * 0.2 +
        (aqi / 500) * 0.4 -
        (safe_zone * 0.15)           # reduce safe zone impact
    )

    # Final hybrid (more weight to rule)
    final_risk = 0.3 * ml_risk + 0.7 * rule_risk

    return max(0, min(round(final_risk, 2), 1))

# -------------------------------
# STEP 3: PREMIUM CALCULATION
# -------------------------------
def calculate_premium(risk_score, safe_zone):

    base_price = 25
    multiplier = 20

    premium = base_price + (risk_score * multiplier)

    # Safe zone discount
    if safe_zone > 0.7:
        premium -= 2

    # High risk surcharge
    if risk_score > 0.7:
        premium += 5

    return round(max(premium, 15), 2)


# -------------------------------
# STEP 4: COVERAGE ADJUSTMENT
# -------------------------------
def adjust_coverage(risk_score):

    if risk_score > 0.7:
        return "Extended Coverage (10 hrs/day)"
    elif risk_score > 0.4:
        return "Standard Coverage (6 hrs/day)"
    else:
        return "Basic Coverage (4 hrs/day)"


# -------------------------------
# FINAL PIPELINE
# -------------------------------
def dynamic_pricing_pipeline(model, rainfall, temperature, aqi, safe_zone):

    risk_score = predict_risk(model, rainfall, temperature, aqi, safe_zone)

    premium = calculate_premium(risk_score, safe_zone)

    coverage = adjust_coverage(risk_score)

    return {
        "risk_score": risk_score,
        "weekly_premium": premium,
        "coverage": coverage
    }


# -------------------------------
# RUN DEMO
# -------------------------------
if __name__ == "__main__":

    print("=== AI Dynamic Premium Calculator ===")

    # Train AI model
    model = train_model()

    # User inputs
    rainfall = float(input("Rainfall (mm): "))
    temperature = float(input("Temperature (°C): "))
    aqi = float(input("AQI: "))
    safe_zone = float(input("Zone Safety Score (0-1): "))

    result = dynamic_pricing_pipeline(model, rainfall, temperature, aqi, safe_zone)

    print("\n--- RESULT ---")
    print(f"Risk Score: {result['risk_score']}")
    print(f"Weekly Premium: ₹{result['weekly_premium']}")
    print(f"Coverage: {result['coverage']}")