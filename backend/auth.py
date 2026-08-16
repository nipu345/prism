from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from db import supabase

router = APIRouter()


class SignUpRequest(BaseModel):
    email: str
    password: str
    company_name: str


class LoginRequest(BaseModel):
    email: str
    password: str


def get_current_user(authorization: str = Header(...)):
    """Verify the bearer token and return the Supabase user, or raise a
    clean 401. supabase.auth.get_user raises on an invalid/expired token
    rather than returning something falsy, so that has to be caught here."""
    token = authorization.replace("Bearer ", "").strip()
    try:
        result = supabase.auth.get_user(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if not result or not result.user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return result.user


def get_current_user_and_company(user=Depends(get_current_user)):
    """Resolve the caller's company_id alongside their user record — used
    by every router that needs to scope data to the caller's company."""
    record = supabase.table("users").select("company_id").eq("id", user.id).execute()
    if not record.data:
        raise HTTPException(status_code=403, detail="No company associated with this account")
    return user, record.data[0]["company_id"]


@router.post("/signup")
def signup(data: SignUpRequest):
    try:
        auth_response = supabase.auth.sign_up({
            "email": data.email,
            "password": data.password
        })
        user = auth_response.user
        if not user:
            raise HTTPException(status_code=400, detail="Signup failed — check your email and password")

        company_response = supabase.table("companies").insert({
            "name": data.company_name
        }).execute()
        company_id = company_response.data[0]["id"]

        supabase.table("users").insert({
            "id": user.id,
            "company_id": company_id,
            "email": data.email,
            "role": "admin"
        }).execute()

        return {"message": "Account created successfully", "user": user.email}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login")
def login(data: LoginRequest):
    try:
        auth_response = supabase.auth.sign_in_with_password({
            "email": data.email,
            "password": data.password
        })
        return {
            "access_token": auth_response.session.access_token,
            "user": auth_response.user.email
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/logout")
def logout():
    try:
        supabase.auth.sign_out()
        return {"message": "Logged out successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
