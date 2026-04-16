from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.responses import FileResponse
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
import user_roles as ur
import advanced_fraud_detection as afd
import instant_payout_system as ips
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


class FraudCheckRequest(BaseModel):
    claim: Dict[str, Any] = Field(..., description="Claim data to analyze")
    include_history: bool = Field(default=True, description="Include user's claim history in analysis")


class FraudCheckResponse(BaseModel):
    is_fraudulent: bool = Field(..., description="Whether claim is flagged as fraudulent")
    risk_score: float = Field(..., description="Risk score from 0.0 to 1.0")
    flags: List[str] = Field(..., description="Specific fraud indicators detected")
    reason: str = Field(..., description="Explanation of fraud determination")
    recommendation: str = Field(..., description="Recommendation for claim handling")


class PayoutRequest(BaseModel):
    claim_id: str = Field(..., description="Claim ID for payout")
    amount: float = Field(gt=0, description="Payout amount")
    recipient_identifier: str = Field(..., description="UPI/Account ID for payout recipient")
    gateway: Optional[str] = Field("upi", description="Payment gateway to use: upi, razorpay, or stripe")


class PayoutResponse(BaseModel):
    payout_id: str = Field(..., description="Unique payout ID")
    status: str = Field(..., description="Payout status: pending, processing, success, failed")
    amount: float = Field(..., description="Payout amount")
    gateway: str = Field(..., description="Payment gateway used")
    transaction_details: Dict[str, Any] = Field(..., description="Gateway-specific transaction details")
    created_at: str = Field(..., description="Timestamp of payout initiation")


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
    # Only accept local mock tokens when backend Supabase config is missing
    if (not SUPABASE_URL) or (not SUPABASE_ANON_KEY):
        if token == "mock-dev-token" or token.startswith("mock-"):
            return "dev-user-demo"

    user = _fetch_supabase_user(token)
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid authenticated user")
    return str(user_id)


def require_admin(authorization: Optional[str] = Header(default=None)) -> str:
    """
    Dependency to verify user is authenticated AND is an admin/insurer.
    Returns user_id if authorized, raises 403 Forbidden if not admin.
    """
    user_id = require_user_id(authorization)
    if not ur.is_admin(user_id):
        raise HTTPException(status_code=403, detail="Admin access required. Only insurers can approve claims.")
    return user_id


def get_user_role(authorization: Optional[str] = Header(default=None)) -> tuple[str, str]:
    """
    Dependency that returns both user_id and role ('admin' or 'worker')
    """
    user_id = require_user_id(authorization)
    role = ur.get_user_role(user_id)
    return user_id, role


@app.options("/api/predict")
async def options_predict():
    """Handle CORS preflight requests"""
    return {"message": "OK"}


# ============================================================================
# User & Role Management Endpoints
# ============================================================================

@app.get("/api/user/profile")
def get_user_profile(user_id_and_role: tuple[str, str] = Depends(get_user_role)):
    """Get current user's profile including role"""
    user_id, role = user_id_and_role
    return {
        "user_id": user_id,
        "role": role,
        "is_admin": role == "admin",
        "role_locked": ur.has_explicit_role(user_id),
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/api/auth/register-role")
def register_own_role(data: dict, user_id: str = Depends(require_user_id)):
    """
    Register the authenticated user's role once.
    After registration, role cannot be changed by self-service login flow.
    """
    role = data.get("role")
    if role not in ["admin", "worker"]:
        raise HTTPException(status_code=400, detail="role must be 'admin' or 'worker'")

    try:
        resolved_role = ur.register_user_role(user_id, role)
        return {
            "success": True,
            "user_id": user_id,
            "role": resolved_role,
            "role_locked": True,
        }
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/api/admin/register")
def register_admin_user(data: dict, admin_id: str = Depends(require_admin)):
    """Admin-only endpoint to register another admin"""
    email = data.get("email")
    new_user_id = data.get("user_id")
    if not email or not new_user_id:
        raise HTTPException(status_code=400, detail="email and user_id required")
    ur.register_admin(email, new_user_id)
    return {"success": True, "message": f"Registered {email} as admin"}


@app.get("/api/admin/list-admins")
def list_all_admins(admin_id: str = Depends(require_admin)):
    """Admin-only: List all admin users"""
    return {"admins": ur.list_admins()}


@app.post("/api/auth/set-role")
def set_user_role(data: dict, admin_id: str = Depends(require_admin)):
    """Admin-only: Set a user's role"""
    user_id = data.get("user_id")
    role = data.get("role")  # 'admin' or 'worker'
    if not user_id or role not in ["admin", "worker"]:
        raise HTTPException(status_code=400, detail="user_id and role required")
    ur.set_admin(user_id, role == "admin")
    return {"success": True, "user_id": user_id, "role": role}


@app.options("/api/predict")
async def options_predict_2():
    """Handle CORS preflight requests"""
    return {"message": "OK"}



@app.get("/api/policies", response_model=List[PolicyResponse])
def list_policies(user_id: str = Depends(require_user_id)):
    try:
        # Users can only see their own policies
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
    """Workers can create their own policies"""
    try:
        # Verify user is a worker before allowing policy creation
        role = ur.get_user_role(user_id)
        if role != "worker":
            raise HTTPException(
                status_code=403,
                detail="Only workers can create their own policies. Admins must use /api/admin/policies endpoint."
            )
        return pm.create_policy(policy.dict(), user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
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
    """Workers can only see their own claims"""
    try:
        # Verify user is a worker
        role = ur.get_user_role(user_id)
        if role != "worker":
            raise HTTPException(
                status_code=403,
                detail="Workers can only view their own claims"
            )
        return cm.list_claims(user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
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
    """Workers can create claims for their own policies"""
    try:
        # Verify user is a worker
        role = ur.get_user_role(user_id)
        if role != "worker":
            raise HTTPException(
                status_code=403,
                detail="Only workers can submit claims"
            )
        return cm.create_claim(claim.dict(), user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
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


# ============================================================================
# Admin Claim Management - Fraud Analysis & Approval Workflow
# ============================================================================

class ClaimApprovalRequest(BaseModel):
    status: str = Field(..., description="New claim status: approved, rejected")
    admin_notes: Optional[str] = Field(None, description="Admin decision notes")

class ClaimAnalysisResponse(BaseModel):
    claim_id: str
    is_fraudulent: bool
    risk_score: float
    fraud_flags: List[str]
    fraud_reason: str
    recommendation: str
    worker_history: Dict[str, Any]
    analysis_timestamp: str

@app.get("/api/admin/claims")
def get_all_claims_for_admin(admin_id: str = Depends(require_admin)):
    """
    Admin-only endpoint to view all claims across all workers.
    Returns claims organized by status for approval workflow.
    """
    try:
        # Get all claims (not filtered by user_id since admin sees everything)
        all_claims = cm.get_all_claims()
        
        # Organize by status
        by_status = {
            "pending": [c for c in all_claims if c.get("status") == "pending"],
            "approved": [c for c in all_claims if c.get("status") == "approved"],
            "rejected": [c for c in all_claims if c.get("status") == "rejected"],
            "paid_out": [c for c in all_claims if c.get("status") == "paid_out"],
        }
        
        return {
            "total_claims": len(all_claims),
            "by_status": by_status,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        print(f"Error getting all claims: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/admin/claims/{claim_id}/analyze-fraud")
def analyze_claim_fraud_detailed(claim_id: str, admin_id: str = Depends(require_admin)):
    """
    Admin endpoint to run ADVANCED fraud analysis on a specific claim.
    Uses multi-factor fraud detection:
    - GPS Spoofing Detection
    - Historical Weather Validation  
    - Duplicate Claim Detection
    - Worker Pattern Analysis
    """
    try:
        # Get the claim (admin can see any claim)
        claim = cm.get_claim_admin(claim_id)
        if not claim:
            raise HTTPException(status_code=404, detail="Claim not found")
        
        # Get worker's claim history
        worker_id = claim.get("owner_id", claim.get("user_id"))
        worker_claims = cm.get_claims_by_user(worker_id)
        
        # Prepare data for advanced fraud detection
        claim_data = {
            "claim_id": claim_id,
            "worker_id": worker_id,
            "claim_date": claim.get("created_at", datetime.now().isoformat()).split("T")[0],
            "amount": claim.get("claim_amount", 2000),
            "delivery_zone": claim.get("delivery_zone", "Downtown"),
            "latitude": claim.get("latitude", 28.6),
            "longitude": claim.get("longitude", 77.2),
            "weather_severity": claim.get("weather_severity", 0.5),
            "claim_frequency": len(worker_claims),
            "avg_claim_amount": sum(c.get("claim_amount", 0) for c in worker_claims) / len(worker_claims) if worker_claims else 2000,
            "approval_rate": len([c for c in worker_claims if c.get("status") == "approved"]) / len(worker_claims) if worker_claims else 0.7,
        }
        
        # Run advanced fraud detection
        fraud_result = afd.analyze_claim_for_fraud(claim_data)
        
        # Build detailed response
        return {
            "claim_id": claim_id,
            "risk_score": round(fraud_result["final_risk_score"], 4),
            "fraud_flags": fraud_result["flags"],
            "fraud_indicators": fraud_result["fraud_indicators"],
            "recommendation": fraud_result["recommendation"],
            "analysis_reason": fraud_result["reason"],
            "confidence_scores": fraud_result["confidence_scores"],
            "worker_history": {
                "worker_id": worker_id,
                "total_claims": len(worker_claims),
                "pending_claims": len([c for c in worker_claims if c.get("status") == "pending"]),
                "approved_claims": len([c for c in worker_claims if c.get("status") == "approved"]),
                "rejected_claims": len([c for c in worker_claims if c.get("status") == "rejected"]),
                "avg_claim_amount": round(claim_data["avg_claim_amount"], 2),
                "approval_rate": round(claim_data["approval_rate"] * 100, 1),
            },
            "claim_details": {
                "policy_id": claim.get("policy_id"),
                "title": claim.get("title"),
                "description": claim.get("description"),
                "amount": claim.get("claim_amount"),
                "created_at": claim.get("created_at"),
                "current_status": claim.get("status"),
                "delivery_zone": claim.get("delivery_zone", "Unknown"),
                "weather_severity": claim.get("weather_severity", 0),
            },
            "analysis_timestamp": fraud_result["timestamp"]
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error analyzing claim fraud: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/admin/claims/{claim_id}/approve")
def approve_claim(claim_id: str, approval_req: ClaimApprovalRequest, admin_id: str = Depends(require_admin)):
    """
    Admin endpoint to approve a pending claim.
    Validates claim status before approval.
    """
    try:
        # Get current claim
        claim = cm.get_claim_admin(claim_id)
        if not claim:
            raise HTTPException(status_code=404, detail="Claim not found")
        
        # Validate workflow: can only approve pending claims
        if claim.get("status") not in ["pending"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot approve claim with status '{claim.get('status')}'. Only pending claims can be approved."
            )
        
        # Update claim with approval
        update_data = {
            "status": approval_req.status,  # "approved" or "rejected"
            "admin_notes": approval_req.admin_notes or f"Claim {approval_req.status} by admin {admin_id}"
        }
        
        updated_claim = cm.update_claim_admin(claim_id, update_data)
        
        return {
            "success": True,
            "claim_id": claim_id,
            "new_status": updated_claim.get("status"),
            "admin_notes": updated_claim.get("admin_notes"),
            "approved_by": admin_id,
            "approved_at": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error approving claim: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/admin/claims/{claim_id}/reject")
def reject_claim(claim_id: str, rejection_reason: dict, admin_id: str = Depends(require_admin)):
    """
    Admin endpoint to reject a pending claim.
    Requires reason/notes for audit trail.
    """
    try:
        # Get current claim
        claim = cm.get_claim_admin(claim_id)
        if not claim:
            raise HTTPException(status_code=404, detail="Claim not found")
        
        # Validate workflow
        if claim.get("status") not in ["pending"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot reject claim with status '{claim.get('status')}'. Only pending claims can be rejected."
            )
        
        reason = rejection_reason.get("reason", "Rejected by admin")
        
        # Update claim with rejection
        update_data = {
            "status": "rejected",
            "admin_notes": reason
        }
        
        updated_claim = cm.update_claim_admin(claim_id, update_data)
        
        return {
            "success": True,
            "claim_id": claim_id,
            "new_status": updated_claim.get("status"),
            "rejection_reason": reason,
            "rejected_by": admin_id,
            "rejected_at": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error rejecting claim: {e}")
        traceback.print_exc()
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


@app.get("/api/debug-env")
def debug_env(response: Response):
    """Diagnostic endpoint to check environment variable configuration."""
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    
    # Check all Supabase-related env vars
    env_checks = {
        "SUPABASE_URL": {
            "value": os.getenv("SUPABASE_URL"),
            "set": "SUPABASE_URL" in os.environ,
            "empty": not os.getenv("SUPABASE_URL"),
        },
        "VITE_SUPABASE_URL": {
            "value": os.getenv("VITE_SUPABASE_URL"),
            "set": "VITE_SUPABASE_URL" in os.environ,
            "empty": not os.getenv("VITE_SUPABASE_URL"),
        },
        "SUPABASE_ANON_KEY": {
            "value": os.getenv("SUPABASE_ANON_KEY"),
            "set": "SUPABASE_ANON_KEY" in os.environ,
            "empty": not os.getenv("SUPABASE_ANON_KEY"),
        },
        "SUPABASE_PUBLISHABLE_KEY": {
            "value": os.getenv("SUPABASE_PUBLISHABLE_KEY"),
            "set": "SUPABASE_PUBLISHABLE_KEY" in os.environ,
            "empty": not os.getenv("SUPABASE_PUBLISHABLE_KEY"),
        },
        "VITE_SUPABASE_PUBLISHABLE_KEY": {
            "value": os.getenv("VITE_SUPABASE_PUBLISHABLE_KEY"),
            "set": "VITE_SUPABASE_PUBLISHABLE_KEY" in os.environ,
            "empty": not os.getenv("VITE_SUPABASE_PUBLISHABLE_KEY"),
        },
        "VITE_SUPABASE_ANON_KEY": {
            "value": os.getenv("VITE_SUPABASE_ANON_KEY"),
            "set": "VITE_SUPABASE_ANON_KEY" in os.environ,
            "empty": not os.getenv("VITE_SUPABASE_ANON_KEY"),
        },
    }
    
    return {
        "resolved_url": SUPABASE_URL,
        "resolved_key": SUPABASE_ANON_KEY,
        "url_set": bool(SUPABASE_URL),
        "key_set": bool(SUPABASE_ANON_KEY),
        "environment_variables": env_checks,
        "all_env_keys": sorted([k for k in os.environ.keys() if "SUPABASE" in k or "VITE" in k]),
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


@app.post("/api/fraud-check", response_model=FraudCheckResponse)
def check_claim_fraud(req: FraudCheckRequest, user_id: str = Depends(require_user_id)):
    """
    Analyze a claim for fraud indicators including GPS spoofing and fake weather claims
    """
    try:
        claim = req.claim
        
        # Get user's claim history if requested
        user_claims = []
        if req.include_history:
            user_claims = cm.list_claims(user_id)
        
        # Run fraud analysis
        fraud_result = afd.analyze_claim_for_fraud({
            **claim,
            "worker_id": user_id,
        })

        risk_score = float(fraud_result.get("final_risk_score", 0.0))
        is_fraudulent = risk_score >= 0.5
        recommendation = fraud_result.get("recommendation") or (
            "REVIEW" if is_fraudulent else "APPROVE"
        )

        return FraudCheckResponse(
            is_fraudulent=is_fraudulent,
            risk_score=risk_score,
            flags=fraud_result.get("flags", []),
            reason=fraud_result.get("reason", ""),
            recommendation=recommendation,
        )
    except Exception as e:
        print(f"Error in fraud check: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/payouts", response_model=PayoutResponse)
def create_payout(req: PayoutRequest, user_id_and_role: tuple[str, str] = Depends(get_user_role)):
    """
    Process INSTANT payout for approved claim via selected payment gateway.
    Supports:
    - UPI: Instant (< 5 seconds), no fees
    - Razorpay: 2-5 minutes, 1% fee
    - Stripe: 24 hours, $0.25 flat fee
    """
    try:
        user_id, role = user_id_and_role

        # Validate gateway
        valid_gateways = ["upi", "razorpay", "stripe"]
        gateway = req.gateway.lower() if req.gateway else "upi"
        if gateway not in valid_gateways:
            raise HTTPException(status_code=400, detail=f"Invalid gateway. Must be one of: {valid_gateways}")

        claim = cm.get_claim_admin(req.claim_id)
        if not claim:
            raise HTTPException(status_code=404, detail="Claim not found")

        claim_owner_id = claim.get("owner_id")
        if role != "admin" and claim_owner_id != user_id:
            raise HTTPException(status_code=403, detail="Workers can only payout their own approved claims")

        if claim.get("status") == "paid_out":
            raise HTTPException(status_code=400, detail="Claim is already paid out")

        if ips.payout_system.has_active_or_successful_payout(req.claim_id):
            raise HTTPException(status_code=409, detail="A payout has already been initiated for this claim")

        if claim.get("status") not in ["approved", "pending"]:
            raise HTTPException(status_code=400, detail="Only approved or pending claims are eligible for payout")
        
        # Prepare recipient information based on gateway
        recipient_info = {"upi_id": req.recipient_identifier}
        if gateway == "razorpay":
            recipient_info = {
                "account_number": req.recipient_identifier,
                "ifsc": "SBIN0001234"  # Sample IFSC
            }
        elif gateway == "stripe":
            recipient_info = {
                "token": req.recipient_identifier
            }
        
        # Process payout using instant payout system
        payout_result = ips.process_claim_payout(
            claim_id=req.claim_id,
            amount=req.amount,
            gateway=gateway,
            recipient_info=recipient_info
        )

        payout_result["owner_id"] = claim_owner_id
        payout_result["processed_by"] = user_id
        payout_result["recipient_identifier"] = req.recipient_identifier

        payout_status = ips.payout_system._normalize_status(payout_result.get("status"))
        if payout_status == "success":
            cm.update_claim_admin(req.claim_id, {
                "status": "paid_out",
                "admin_notes": f"Payout settled via {gateway}"
            })
        
        # Generate payout ID
        payout_id = f"PAYOUT{payout_result.get('rrn', 'XXX')}"
        
        return PayoutResponse(
            payout_id=payout_id,
            status=payout_status,
            amount=payout_result.get("amount"),
            gateway=ips.payout_system._normalize_gateway(payout_result.get("gateway")),
            transaction_details={
                "transaction_id": payout_result.get("transaction_id"),
                "rrn": payout_result.get("rrn"),
                "reference_number": payout_result.get("reference_number"),
                "processing_time": payout_result.get("processing_time"),
                "fee": payout_result.get("fee"),
                "net_amount": payout_result.get("net_amount"),
                "expected_completion": payout_result.get("expected_completion"),
                "error": payout_result.get("error"),
            },
            created_at=payout_result.get("timestamp"),
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in payout: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/payouts")
def get_user_payouts(user_id_and_role: tuple[str, str] = Depends(get_user_role)):
    """
    Get user's recent payouts via instant payout system
    """
    try:
        user_id, role = user_id_and_role
        ips.payout_system.refresh_transaction_statuses()

        # Sync settled payouts back to claim status.
        for txn in ips.payout_system.transactions.values():
            if ips.payout_system._normalize_status(txn.get("status")) != "success":
                continue
            claim_id = txn.get("claim_id")
            if not claim_id:
                continue
            claim = cm.get_claim_admin(claim_id)
            if claim and claim.get("status") != "paid_out":
                cm.update_claim_admin(claim_id, {
                    "status": "paid_out",
                    "admin_notes": "Payout settled successfully"
                })

        analytics = ips.payout_system.get_payout_analytics()
        payouts = []
        for txn in ips.payout_system.transactions.values():
            owner_id = txn.get("owner_id")
            if role != "admin" and owner_id != user_id:
                continue
            rrn = txn.get("rrn")
            payout_id = f"PAYOUT{rrn}" if rrn else f"PAYOUT-{txn.get('transaction_id', 'UNKNOWN')}"
            payouts.append(
                {
                    "payout_id": payout_id,
                    "status": ips.payout_system._normalize_status(txn.get("status")) or "unknown",
                    "amount": float(txn.get("amount", 0) or 0),
                    "gateway": ips.payout_system._normalize_gateway(txn.get("gateway")) or "unknown",
                    "created_at": txn.get("timestamp") or datetime.now().isoformat(),
                    "claim_id": txn.get("claim_id"),
                    "transaction_id": txn.get("transaction_id"),
                    "owner_id": owner_id,
                }
            )

        payouts.sort(key=lambda p: p.get("created_at", ""), reverse=True)
        return {
            "analytics": analytics,
            "payouts": payouts,
            "total": len(payouts),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"Error fetching payouts: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# INTELLIGENT DASHBOARD ENDPOINTS
# ============================================

@app.get("/api/dashboard/worker-analytics")
def get_worker_dashboard_analytics(user_id: str = Depends(require_user_id)):
    """
    Worker Dashboard Analytics
    - Total earnings protected
    - Active weekly coverage
    - Pending payouts
    - Claim status breakdown
    """
    try:
        # Get worker's policies
        policies = pm.list_policies(user_id)
        
        # Get worker's claims
        claims = cm.get_claims_by_user(user_id)
        
        # Calculate analytics
        total_premium = sum(p.get("weekly_premium", 0) for p in policies)
        active_policies = len([p for p in policies if p.get("active", False)])
        
        # Earnings protected = weekly premium * number of active policies * weeks covered
        earnings_protected = total_premium * 52  # Annual protection
        
        claims_by_status = {
            "pending": len([c for c in claims if c.get("status") == "pending"]),
            "approved": len([c for c in claims if c.get("status") == "approved"]),
            "rejected": len([c for c in claims if c.get("status") == "rejected"]),
            "paid_out": len([c for c in claims if c.get("status") == "paid_out"]),
        }
        
        total_claim_amount = sum(
            c.get("claim_amount", 0)
            for c in claims
            if c.get("status") in ["approved", "paid_out"]
        )
        
        return {
            "earnings_protected": round(earnings_protected, 2),
            "active_policies": active_policies,
            "weekly_coverage": round(total_premium, 2),
            "claims": claims_by_status,
            "total_approved_amount": round(total_claim_amount, 2),
            "claim_count": len(claims),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"Error fetching worker analytics: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dashboard/admin-analytics")
def get_admin_dashboard_analytics(admin_id: str = Depends(require_admin)):
    """
    Admin/Insurer Dashboard Analytics with Predictive Intelligence
    - Loss ratios by claim type
    - High-risk patterns
    - Predictive analytics for next week's weather/disruptions
    - Fraud detection metrics
    """
    try:
        # Get all claims
        all_claims = cm.get_all_claims()
        all_policies = pm.get_all_policies()
        payout_transactions = list(ips.payout_system.transactions.values())
        
        # Calculate loss ratio from real policy premiums and payout transactions.
        approved_claim_amount = sum(c.get("claim_amount", 0) for c in all_claims if c.get("status") in ["approved", "paid_out"])
        active_policies = [p for p in all_policies if p.get("active", True)]
        total_policies = len(active_policies)
        total_premium = sum(float(p.get("weekly_premium", 0) or 0) for p in active_policies)

        # Prefer payout transaction ledger for paid amount; fallback to approved claim sum.
        total_paid_from_transactions = sum(float(t.get("amount", 0) or 0) for t in payout_transactions if str(t.get("status", "")).lower() in ["success", "processing", "pending"])
        effective_payout_amount = total_paid_from_transactions if total_paid_from_transactions > 0 else approved_claim_amount
        
        loss_ratio = effective_payout_amount / total_premium if total_premium > 0 else 0
        
        # Claim type breakdown
        claim_types = {}
        for claim in all_claims:
            title = claim.get("title", "Unknown")
            if title not in claim_types:
                claim_types[title] = {"count": 0, "amount": 0}
            claim_types[title]["count"] += 1
            claim_types[title]["amount"] += claim.get("claim_amount", 0)
        
        # Predictive analytics based on live public weather forecast data (Open-Meteo).
        geo_points = []
        for c in all_claims:
            try:
                lat = c.get("latitude")
                lon = c.get("longitude")
                if lat is None or lon is None:
                    continue
                geo_points.append((float(lat), float(lon)))
            except Exception:
                continue

        if geo_points:
            forecast_lat = sum(p[0] for p in geo_points) / len(geo_points)
            forecast_lon = sum(p[1] for p in geo_points) / len(geo_points)
            forecast_source = "open-meteo-claims-centroid"
        else:
            forecast_lat = float(os.getenv("FORECAST_LAT", "12.9716"))
            forecast_lon = float(os.getenv("FORECAST_LON", "77.5946"))
            forecast_source = "open-meteo-configured-default"

        weather_url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={forecast_lat}&longitude={forecast_lon}"
            "&daily=precipitation_sum,temperature_2m_max"
            "&forecast_days=7&timezone=auto"
        )

        try:
            req = Request(weather_url, headers={"User-Agent": "secure-gig-guardian/1.0"})
            with urlopen(req, timeout=8) as resp:
                weather_payload = json.loads(resp.read().decode("utf-8"))

            daily = weather_payload.get("daily", {})
            precip_values = daily.get("precipitation_sum", []) or []
            max_temp_values = daily.get("temperature_2m_max", []) or []

            rainy_days = len([v for v in precip_values if float(v) >= 10.0])
            severe_rain_days = len([v for v in precip_values if float(v) >= 40.0])
            heat_days = len([v for v in max_temp_values if float(v) >= 36.0])
            avg_precip = (sum(float(v) for v in precip_values) / len(precip_values)) if precip_values else 0.0
            max_precip = max((float(v) for v in precip_values), default=0.0)
            max_temp = max((float(v) for v in max_temp_values), default=0.0)

            # Weighted disruption likelihood from forecast signals.
            disruption_likelihood = min(
                0.95,
                0.15
                + (rainy_days / 7.0) * 0.35
                + (severe_rain_days / 7.0) * 0.30
                + (heat_days / 7.0) * 0.20,
            )

            predicted_claims = round(total_policies * disruption_likelihood * 0.28)
            if total_policies > 0 and disruption_likelihood > 0:
                predicted_claims = max(1, predicted_claims)
            else:
                predicted_claims = max(0, predicted_claims)
            avg_approved_claim = approved_claim_amount / max(1, len([c for c in all_claims if c.get("status") in ["approved", "paid_out"]]))
            estimated_claim_value = max(1200.0, avg_approved_claim)
            predicted_loss = round(predicted_claims * estimated_claim_value)

            risk_factors = []
            if severe_rain_days > 0:
                risk_factors.append(f"Severe rainfall expected on {severe_rain_days} day(s), peak {max_precip:.1f} mm/day")
            elif rainy_days > 0:
                risk_factors.append(f"Rain forecast on {rainy_days} day(s), average {avg_precip:.1f} mm/day")
            if heat_days > 0:
                risk_factors.append(f"Heat stress risk on {heat_days} day(s), peak {max_temp:.1f} C")
            if not risk_factors:
                risk_factors.append("No major weather disruption signals detected for the next 7 days")

            next_week_prediction = {
                "high_disruption_likelihood": round(disruption_likelihood, 4),
                "predicted_claims": predicted_claims,
                "predicted_loss": predicted_loss,
                "risk_factors": risk_factors,
                "exposure_active_policies": total_policies,
                "forecast_source": forecast_source,
                "forecast_location": {
                    "lat": round(forecast_lat, 4),
                    "lon": round(forecast_lon, 4),
                },
            }
        except Exception:
            # Fallback to claims-history-based estimate when weather API is unavailable.
            recent_pending_ratio = len([c for c in all_claims if c.get("status") == "pending"]) / max(1, len(all_claims))
            disruption_likelihood = min(0.9, 0.2 + recent_pending_ratio * 0.7)
            predicted_claims = round(total_policies * disruption_likelihood * 0.25)
            if total_policies > 0 and disruption_likelihood > 0:
                predicted_claims = max(1, predicted_claims)
            else:
                predicted_claims = max(0, predicted_claims)
            predicted_loss = round(predicted_claims * max(1200.0, approved_claim_amount / max(1, len(all_claims))))
            next_week_prediction = {
                "high_disruption_likelihood": round(disruption_likelihood, 4),
                "predicted_claims": predicted_claims,
                "predicted_loss": predicted_loss,
                "risk_factors": [
                    "Live weather forecast unavailable; using recent claims trend signals"
                ],
                "exposure_active_policies": total_policies,
                "forecast_source": "claims-fallback",
                "forecast_location": {
                    "lat": round(forecast_lat, 4),
                    "lon": round(forecast_lon, 4),
                },
            }
        
        # Fraud statistics
        pending_claims = [c for c in all_claims if c.get("status") == "pending"]
        high_risk_count = 0
        for claim in pending_claims:
            fraud_check = afd.analyze_claim_for_fraud({
                "claim_id": claim.get("id"),
                "worker_id": claim.get("owner_id"),
                "amount": claim.get("claim_amount", 0),
                "claim_date": claim.get("created_at", "").split("T")[0],
            })
            if fraud_check["final_risk_score"] > 0.5:
                high_risk_count += 1
        
        return {
            "loss_ratio": round(loss_ratio, 4),
            "loss_ratio_percentage": round(loss_ratio * 100, 2),
            "metrics": {
                "total_claims": len(all_claims),
                "approved_claims": len([c for c in all_claims if c.get("status") in ["approved", "paid_out"]]),
                "pending_claims": len(pending_claims),
                "rejected_claims": len([c for c in all_claims if c.get("status") == "rejected"]),
                "total_premium_pool": round(total_premium, 2),
                "total_approved_payout": round(effective_payout_amount, 2),
                "total_active_policies": total_policies,
            },
            "claim_breakdown": claim_types,
            "predictive_analytics": next_week_prediction,
            "fraud_metrics": {
                "pending_high_risk": high_risk_count,
                "pending_total": len(pending_claims),
                "high_risk_percentage": round(high_risk_count / len(pending_claims) * 100, 1) if pending_claims else 0,
            },
            "data_source": {
                "policies": "live",
                "claims": "live",
                "payouts": "live-in-memory-ledger",
                "weather": "live-open-meteo",
            },
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"Error fetching admin analytics: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        print(f"Error fetching payouts: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/payouts/analytics")
def get_payout_analytics():
    """
    Get overall payout system analytics (admin endpoint)
    """
    try:
        analytics = ips.payout_system.get_payout_analytics()
        return analytics
    except Exception as e:
        print(f"Error fetching payout analytics: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/fraud-advanced")
def run_advanced_fraud_scan(limit: int = 50, user_id: str = Depends(require_user_id)):
    """
    Admin endpoint to run an advanced fraud scan across recent claims.
    Returns a summary of flagged claims and counts.
    """
    try:
        # Fetch recent claims for the user (or all if admin privileges in future)
        recent_claims = cm.list_claims(user_id)[:limit]
        flagged = []
        for c in recent_claims:
            result = afd.analyze_claim_for_fraud({
                "claim_id": c.get("id"),
                "worker_id": user_id,
                "amount": c.get("claim_amount", 0),
                "claim_date": c.get("created_at", "").split("T")[0],
            })
            risk_score = float(result.get("final_risk_score", 0.0))
            if risk_score >= 0.5:
                flagged.append({
                    "claim_id": c.get("id"),
                    "risk_score": risk_score,
                    "flags": result.get("flags", []),
                    "reason": result.get("reason", ""),
                })

        return {
            "scanned": len(recent_claims),
            "flagged_count": len(flagged),
            "flagged": flagged,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        print(f"Error in advanced fraud scan: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/payout-sim")
def run_payout_simulation(max_count: int = 10, amount: Optional[float] = None, admin_id: str = Depends(require_admin)):
    """
    Admin/test endpoint to simulate multiple instant payouts for demo/scale testing.
    Creates simulated payouts for approved worker claims.
    """
    try:
        claims = [c for c in cm.get_all_claims() if c.get("status") == "approved"][:max_count]
        results = []
        for c in claims:
            try:
                if ips.payout_system.has_active_or_successful_payout(c.get("id")):
                    results.append({"claim_id": c.get("id"), "skipped": "Payout already exists for this claim"})
                    continue

                worker_id = c.get("owner_id")
                if not worker_id:
                    results.append({"claim_id": c.get("id"), "error": "Missing worker owner_id"})
                    continue

                gateway_candidates = ["upi", "razorpay", "stripe"]
                gateway = gateway_candidates[abs(hash(c.get("id", ""))) % len(gateway_candidates)]
                payout_amount = float(amount) if amount is not None else float(c.get("claim_amount", 0) or 0)
                if payout_amount <= 0:
                    results.append({"claim_id": c.get("id"), "error": "Invalid claim amount for payout"})
                    continue

                if gateway == "upi":
                    recipient_info = {"upi_id": f"worker_{worker_id[-6:]}@gigpay"}
                elif gateway == "razorpay":
                    account_seed = ''.join(ch for ch in worker_id if ch.isalnum())
                    account_number = ''.join(str((ord(ch) % 10)) for ch in account_seed)[:12].ljust(12, '7')
                    recipient_info = {"account_number": account_number, "ifsc": "SBIN0001234"}
                else:
                    token_seed = ''.join(ch for ch in worker_id if ch.isalnum())[-8:]
                    recipient_info = {"token": f"tok_{token_seed or 'worker'}"}

                payout = ips.process_claim_payout(
                    claim_id=c.get("id"),
                    amount=payout_amount,
                    gateway=gateway,
                    recipient_info=recipient_info,
                )

                payout["owner_id"] = worker_id
                payout["processed_by"] = admin_id

                payout_status = ips.payout_system._normalize_status(payout.get("status"))
                if payout_status == "success":
                    cm.update_claim_admin(c.get("id"), {
                        "status": "paid_out",
                        "admin_notes": f"Simulated payout settled via {gateway} by {admin_id}"
                    })

                results.append({
                    "claim_id": c.get("id"),
                    "worker_id": worker_id,
                    "gateway": gateway,
                    "payout": payout,
                })
            except Exception as inner:
                results.append({"claim_id": c.get("id"), "error": str(inner)})

        return {
            "simulated": len(results),
            "processed_by": admin_id,
            "results": results,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        print(f"Error running payout simulation: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# ADMIN POLICY MANAGEMENT - Admins Creating Policies for Workers
# ============================================================

@app.post("/api/admin/policies/{worker_id}", response_model=PolicyResponse)
def create_policy_for_worker(worker_id: str, policy: PolicyCreate, admin_id: str = Depends(require_admin)):
    """
    Admin-only endpoint to create a policy for a specific worker.
    This allows insurers/admins to enroll workers in insurance policies.
    """
    try:
        if not worker_id or not worker_id.strip():
            raise HTTPException(status_code=400, detail="worker_id is required")
        
        # Create policy with worker_id as owner
        policy_data = policy.dict()
        created_policy = pm.create_policy(policy_data, worker_id)
        
        # Log admin action
        print(f"Admin {admin_id} created policy {created_policy.get('id')} for worker {worker_id}")
        
        return created_policy
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Error creating policy for worker: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/policies/worker/{worker_id}")
def get_worker_policies_admin(worker_id: str, admin_id: str = Depends(require_admin)):
    """
    Admin endpoint to view all policies for a specific worker.
    """
    try:
        policies = pm.list_policies(worker_id)
        return {
            "worker_id": worker_id,
            "policies": policies,
            "total": len(policies),
            "active": len([p for p in policies if p.get("active")]),
        }
    except Exception as e:
        print(f"Error fetching worker policies: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# ADMIN WORKER MANAGEMENT - View All Workers & Their Policies/Claims
# ============================================================

@app.get("/api/admin/workers")
def get_all_workers(admin_id: str = Depends(require_admin)):
    """
    Admin endpoint to get all workers with their policies and claims summary.
    Returns a list of workers with policy count, claim status breakdown, and risk indicators.
    """
    try:
        all_claims = cm.get_all_claims()
        all_policies = pm.get_all_policies()

        workers_dict = {}

        # Seed workers from policies first so workers with policies but no claims still appear.
        for policy in all_policies:
            worker_id = policy.get("owner_id")
            if not worker_id:
                continue
            if worker_id not in workers_dict:
                workers_dict[worker_id] = {
                    "worker_id": worker_id,
                    "name": policy.get("worker_name") or f"Worker {worker_id[:8]}",
                    "policies": [],
                    "claims": {
                        "total": 0,
                        "pending": 0,
                        "approved": 0,
                        "rejected": 0,
                        "paid_out": 0,
                    },
                    "claim_amount": {
                        "total": 0,
                        "pending": 0,
                        "approved": 0,
                        "rejected": 0,
                    },
                    "high_risk_flags": [],
                    "created_at": policy.get("created_at", ""),
                    "last_activity": policy.get("updated_at") or policy.get("created_at", ""),
                }

            workers_dict[worker_id]["policies"].append({
                "id": str(policy.get("id", "")),
                "policy_number": policy.get("policy_number"),
                "coverage_type": policy.get("coverage_type"),
                "weekly_premium": policy.get("weekly_premium"),
                "active": policy.get("active", False),
            })

        # Merge in claims and risk profile.
        for claim in all_claims:
            worker_id = claim.get("owner_id")
            if not worker_id:
                continue

            if worker_id not in workers_dict:
                workers_dict[worker_id] = {
                    "worker_id": worker_id,
                    "name": claim.get("worker_name") or f"Worker {worker_id[:8]}",
                    "policies": [],
                    "claims": {
                        "total": 0,
                        "pending": 0,
                        "approved": 0,
                        "rejected": 0,
                        "paid_out": 0,
                    },
                    "claim_amount": {
                        "total": 0,
                        "pending": 0,
                        "approved": 0,
                        "rejected": 0,
                    },
                    "high_risk_flags": [],
                    "created_at": claim.get("created_at", ""),
                    "last_activity": claim.get("updated_at") or claim.get("created_at", ""),
                }

            status = claim.get("status", "pending")
            workers_dict[worker_id]["claims"]["total"] += 1
            workers_dict[worker_id]["claims"][status] = workers_dict[worker_id]["claims"].get(status, 0) + 1
            workers_dict[worker_id]["claim_amount"]["total"] += claim.get("claim_amount", 0)
            if status in workers_dict[worker_id]["claim_amount"]:
                workers_dict[worker_id]["claim_amount"][status] += claim.get("claim_amount", 0)

            workers_dict[worker_id]["last_activity"] = max(
                workers_dict[worker_id].get("last_activity") or "",
                claim.get("updated_at") or claim.get("created_at") or "",
            )

            fraud_check = afd.analyze_claim_for_fraud({
                "claim_id": claim.get("id"),
                "worker_id": worker_id,
                "amount": claim.get("claim_amount", 0),
                "claim_date": claim.get("created_at", "").split("T")[0],
            })
            if fraud_check["final_risk_score"] > 0.5:
                workers_dict[worker_id]["high_risk_flags"].append({
                    "claim_id": claim.get("id"),
                    "risk_score": fraud_check["final_risk_score"],
                    "reason": fraud_check.get("flagged_reason", "High fraud risk"),
                })
        
        # Sort workers by pending claims count (descending) - show most pending first
        workers_list = sorted(
            workers_dict.values(),
            key=lambda w: w["claims"]["pending"],
            reverse=True
        )
        
        return {
            "total_workers": len(workers_list),
            "workers": workers_list,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        print(f"Error fetching workers: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/workers/{worker_id}")
def get_worker_details(worker_id: str, admin_id: str = Depends(require_admin)):
    """
    Admin endpoint to get detailed information about a specific worker.
    Returns all their policies and claims with fraud analysis.
    """
    try:
        # Get all claims for this worker
        worker_claims = cm.get_claims_by_user(worker_id)
        worker_policies = pm.list_policies(worker_id)
        worker_payouts = [
            txn for txn in ips.payout_system.transactions.values()
            if txn.get("owner_id") == worker_id
        ]
        worker_payouts.sort(key=lambda p: p.get("timestamp", ""), reverse=True)
        
        # Build detailed claims with fraud analysis
        detailed_claims = []
        for claim in worker_claims:
            fraud_check = afd.analyze_claim_for_fraud({
                "claim_id": claim.get("id"),
                "worker_id": worker_id,
                "amount": claim.get("claim_amount", 0),
                "claim_date": claim.get("created_at", "").split("T")[0],
            })
            
            detailed_claims.append({
                "id": claim.get("id"),
                "policy_id": claim.get("policy_id"),
                "claim_number": claim.get("claim_number"),
                "title": claim.get("title"),
                "description": claim.get("description"),
                "claim_amount": claim.get("claim_amount"),
                "status": claim.get("status"),
                "created_at": claim.get("created_at"),
                "admin_notes": claim.get("admin_notes"),
                "fraud_analysis": {
                    "risk_score": fraud_check.get("final_risk_score", 0),
                    "is_high_risk": fraud_check.get("final_risk_score", 0) > 0.5,
                    "reason": fraud_check.get("flagged_reason", ""),
                    "flags": fraud_check.get("flagged_reasons", []),
                }
            })
        
        # Summary statistics
        claims_by_status = {
            "total": len(worker_claims),
            "pending": len([c for c in worker_claims if c.get("status") == "pending"]),
            "approved": len([c for c in worker_claims if c.get("status") == "approved"]),
            "rejected": len([c for c in worker_claims if c.get("status") == "rejected"]),
            "paid_out": len([c for c in worker_claims if c.get("status") == "paid_out"]),
        }
        
        total_claim_amount = sum(c.get("claim_amount", 0) for c in worker_claims)
        approved_amount = sum(c.get("claim_amount", 0) for c in worker_claims if c.get("status") in ["approved", "paid_out"])
        pending_amount = sum(c.get("claim_amount", 0) for c in worker_claims if c.get("status") == "pending")
        payout_success = [p for p in worker_payouts if ips.payout_system._normalize_status(p.get("status")) == "success"]
        payout_processing = [p for p in worker_payouts if ips.payout_system._normalize_status(p.get("status")) in ["pending", "processing"]]

        worker_name = None
        if worker_claims:
            worker_name = worker_claims[0].get("worker_name")
        if not worker_name and worker_policies:
            worker_name = worker_policies[0].get("worker_name")

        recent_payouts = []
        for p in worker_payouts[:8]:
            rrn = p.get("rrn")
            payout_id = f"PAYOUT{rrn}" if rrn else f"PAYOUT-{p.get('transaction_id', 'UNKNOWN')}"
            recent_payouts.append({
                "payout_id": payout_id,
                "status": ips.payout_system._normalize_status(p.get("status")) or "unknown",
                "gateway": ips.payout_system._normalize_gateway(p.get("gateway")) or "unknown",
                "amount": float(p.get("amount", 0) or 0),
                "created_at": p.get("timestamp"),
                "claim_id": p.get("claim_id"),
            })

        created_candidates = [
            c.get("created_at") for c in worker_claims if c.get("created_at")
        ] + [
            p.get("created_at") for p in worker_policies if p.get("created_at")
        ] + [
            p.get("timestamp") for p in worker_payouts if p.get("timestamp")
        ]
        activity_candidates = [
            c.get("updated_at") or c.get("created_at") for c in worker_claims if (c.get("updated_at") or c.get("created_at"))
        ] + [
            p.get("updated_at") or p.get("created_at") for p in worker_policies if (p.get("updated_at") or p.get("created_at"))
        ] + [
            p.get("timestamp") for p in worker_payouts if p.get("timestamp")
        ]
        created_at = min(created_candidates) if created_candidates else None
        last_activity = max(activity_candidates) if activity_candidates else None
        
        return {
            "worker_id": worker_id,
            "worker_name": worker_name or f"Worker {worker_id[:8]}",
            "created_at": created_at,
            "last_activity": last_activity,
            "policies": worker_policies,
            "policy_count": len(worker_policies),
            "active_policies": len([p for p in worker_policies if p.get("active")]),
            "claims": detailed_claims,
            "claims_summary": claims_by_status,
            "claim_amounts": {
                "total": total_claim_amount,
                "approved": approved_amount,
                "pending": pending_amount,
            },
            "high_risk_claims": len([c for c in detailed_claims if c["fraud_analysis"]["is_high_risk"]]),
            "payouts_summary": {
                "total": len(worker_payouts),
                "success": len(payout_success),
                "in_flight": len(payout_processing),
                "total_paid": round(sum(float(p.get("amount", 0) or 0) for p in payout_success), 2),
            },
            "recent_payouts": recent_payouts,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        print(f"Error fetching worker details: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# Catch-all route for SPA routing. This serves built assets when requested
# directly and falls back to index.html for client-side routes like /dashboard.
@app.head("/")
async def head_root():
    index_path = os.path.join("dist", "index.html")
    if os.path.isfile(index_path):
        return Response(status_code=200)
    raise HTTPException(status_code=404, detail="Frontend build not found")


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found")

    requested = os.path.join("dist", full_path)
    if full_path and os.path.isfile(requested):
        return FileResponse(requested)

    index_path = os.path.join("dist", "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)

    raise HTTPException(status_code=404, detail="Frontend build not found")
