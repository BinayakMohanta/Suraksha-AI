from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import json
import traceback
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import dynamic_pricing as dp
import policy_management as pm
import claims_management as cm
import os


def _load_env_file(path: str) -> None:
    if not os.path.isfile(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        # Keep startup resilient even if env file has malformed lines.
        pass


# Make backend read local frontend env files too, so Supabase keys are available.
_load_env_file(".env")
_load_env_file(".env.local")

MODEL_PATH = "model.joblib"
SUPABASE_URL = os.getenv("SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL")
SUPABASE_ANON_KEY = (
    os.getenv("SUPABASE_ANON_KEY")
    or os.getenv("SUPABASE_PUBLISHABLE_KEY")
    or os.getenv("VITE_SUPABASE_PUBLISHABLE_KEY")
    or os.getenv("VITE_SUPABASE_ANON_KEY")
)

app = FastAPI(title="Dynamic Pricing API")

# Add CORS middleware BEFORE other middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for testing
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods including OPTIONS
    allow_headers=["*"],  # Allow all headers
    expose_headers=["*"],
)

# Note: Static files will be mounted after API routes to avoid intercepting POSTs to /api


class PredictRequest(BaseModel):
    rainfall: float = Field(ge=0, description="Rainfall in mm")
    temperature: float = Field(ge=-50, le=60, description="Temperature in Celsius")
    aqi: float = Field(ge=0, description="Air Quality Index")
    safe_zone: float = Field(ge=0, le=1, description="Safe zone score between 0 and 1")


class PolicyBase(BaseModel):
    worker_name: str = Field(..., description="Worker name for the policy")
    policy_number: str = Field(..., description="Unique policy number")
    coverage_type: str = Field(..., description="Selected coverage tier")
    weekly_premium: float = Field(ge=0, description="Weekly premium amount")
    active: bool = Field(default=True, description="Whether the policy is currently active")
    notes: Optional[str] = Field(None, description="Optional policy notes")


class PolicyCreate(PolicyBase):
    pass


class PolicyUpdate(BaseModel):
    worker_name: Optional[str] = None
    policy_number: Optional[str] = None
    coverage_type: Optional[str] = None
    weekly_premium: Optional[float] = None
    active: Optional[bool] = None
    notes: Optional[str] = None


class PolicyResponse(PolicyBase):
    id: str


class ClaimBase(BaseModel):
    policy_id: str = Field(..., description="Policy id linked to the claim")
    claim_number: str = Field(..., description="Unique claim number for this user")
    title: str = Field(..., description="Claim title")
    description: str = Field(..., description="Claim details")
    claim_amount: float = Field(ge=0, description="Claim amount requested")
    status: str = Field(default="pending", description="Claim status")
    admin_notes: Optional[str] = Field(None, description="Admin notes")


class ClaimCreate(ClaimBase):
    pass


class ClaimUpdate(BaseModel):
    policy_id: Optional[str] = None
    claim_number: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    claim_amount: Optional[float] = None
    status: Optional[str] = None
    admin_notes: Optional[str] = None


class ClaimResponse(ClaimBase):
    id: str


def _fetch_supabase_user(token: str) -> Dict[str, Any]:
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise HTTPException(
            status_code=500,
            detail=(
                "Supabase auth is not configured on backend. "
                "Set SUPABASE_URL and SUPABASE_ANON_KEY (or VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY)."
            ),
        )

    req = Request(
        f"{SUPABASE_URL.rstrip('/')}/auth/v1/user",
        headers={
            "Authorization": f"Bearer {token}",
            "apikey": SUPABASE_ANON_KEY,
        },
        method="GET",
    )

    try:
        with urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except HTTPError:
        raise HTTPException(status_code=401, detail="Invalid or expired auth token")
    except URLError:
        raise HTTPException(status_code=503, detail="Auth provider unavailable")


def require_user_id(authorization: Optional[str] = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1].strip()
    user = _fetch_supabase_user(token)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid authenticated user")
    return str(user_id)


@app.options("/api/predict")
async def options_predict():
    """Handle CORS preflight requests"""
    return {"message": "OK"}


@app.get("/api/policies", response_model=List[PolicyResponse])
def list_policies(user_id: str = Depends(require_user_id)):
    try:
        return pm.list_policies(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/policies/{policy_id}", response_model=PolicyResponse)
def get_policy(policy_id: str, user_id: str = Depends(require_user_id)):
    try:
        policy = pm.get_policy(policy_id, user_id)
        if not policy:
            raise HTTPException(status_code=404, detail="Policy not found")
        return policy
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/policies", response_model=PolicyResponse)
def create_policy(policy: PolicyCreate, user_id: str = Depends(require_user_id)):
    try:
        return pm.create_policy(policy.dict(), user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/policies/{policy_id}", response_model=PolicyResponse)
def update_policy(policy_id: str, update: PolicyUpdate, user_id: str = Depends(require_user_id)):
    try:
        updated = pm.update_policy(policy_id, update.dict(exclude_none=True), user_id)
        if not updated:
            raise HTTPException(status_code=404, detail="Policy not found")
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/policies/{policy_id}")
def delete_policy(policy_id: str, user_id: str = Depends(require_user_id)):
    try:
        deleted = pm.delete_policy(policy_id, user_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Policy not found")
        return {"deleted": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/claims", response_model=List[ClaimResponse])
def list_claims(user_id: str = Depends(require_user_id)):
    try:
        return cm.list_claims(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/claims/{claim_id}", response_model=ClaimResponse)
def get_claim(claim_id: str, user_id: str = Depends(require_user_id)):
    try:
        claim = cm.get_claim(claim_id, user_id)
        if not claim:
            raise HTTPException(status_code=404, detail="Claim not found")
        return claim
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/claims", response_model=ClaimResponse)
def create_claim(claim: ClaimCreate, user_id: str = Depends(require_user_id)):
    try:
        return cm.create_claim(claim.dict(), user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/claims/{claim_id}", response_model=ClaimResponse)
def update_claim(claim_id: str, update: ClaimUpdate, user_id: str = Depends(require_user_id)):
    try:
        updated = cm.update_claim(claim_id, update.dict(exclude_none=True), user_id)
        if not updated:
            raise HTTPException(status_code=404, detail="Claim not found")
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/claims/{claim_id}")
def delete_claim(claim_id: str, user_id: str = Depends(require_user_id)):
    try:
        deleted = cm.delete_claim(claim_id, user_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Claim not found")
        return {"deleted": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
def startup_event():
    global model
    try:
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
    except Exception as e:
        print(f"Critical error during startup: {e}")
        traceback.print_exc()
        raise


@app.get("/health")
def health_check():
    """Simple health check for readiness probes."""
    return {"status": "ok"}


@app.get("/api/public-config")
def public_config(response: Response):
    """Runtime-safe config for frontend bootstrap (Render Docker runtime envs)."""
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return {
        "supabaseUrl": SUPABASE_URL or "",
        "supabasePublishableKey": SUPABASE_ANON_KEY or "",
    }


@app.post("/api/predict")
def predict(req: PredictRequest):
    try:
        # Validate inputs
        if not isinstance(req.rainfall, (int, float)) or not isinstance(req.temperature, (int, float)):
            raise HTTPException(status_code=400, detail="Invalid rainfall or temperature")
        
        if not isinstance(req.aqi, (int, float)) or not isinstance(req.safe_zone, (int, float)):
            raise HTTPException(status_code=400, detail="Invalid AQI or safe zone")

        # Ensure model is loaded
        if 'model' not in globals() or model is None:
            raise HTTPException(status_code=500, detail="Model not initialized")

        # Call the dynamic pricing pipeline
        res = dp.dynamic_pricing_pipeline(model, req.rainfall, req.temperature, req.aqi, req.safe_zone)
        
        # Validate response
        if not res or not isinstance(res, dict):
            raise HTTPException(status_code=500, detail="Invalid response from model")
        
        if "risk_score" not in res or "weekly_premium" not in res or "coverage" not in res:
            raise HTTPException(status_code=500, detail="Missing fields in response")
        
        # Ensure values are in valid ranges
        if not (0 <= float(res["risk_score"]) <= 1):
            raise HTTPException(status_code=500, detail=f"Risk score out of range: {res['risk_score']}")
        
        if float(res["weekly_premium"]) < 0:
            raise HTTPException(status_code=500, detail=f"Invalid premium: {res['weekly_premium']}")
        
        return res
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in predict: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# Serve frontend static files after API is defined so API routes aren't shadowed.
if os.path.isdir("dist"):
    app.mount("/", StaticFiles(directory="dist", html=True), name="static")
