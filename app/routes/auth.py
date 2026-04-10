import datetime
import httpx
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse
from google_auth_oauthlib.flow import Flow
from jose import jwt, JWTError

from app.config import settings
from app.db.mongo import db

router = APIRouter()

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/calendar",
]


def create_flow() -> Flow:
    return Flow.from_client_config(
        {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.REDIRECT_URI],
            }
        },
        scopes=SCOPES,
        redirect_uri=settings.REDIRECT_URI,
    )


@router.get("/login")
async def login():
    flow = create_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return RedirectResponse(auth_url)


@router.get("/callback")
async def callback(request: Request):
    code = request.query_params.get("code")
    if not code:
        return JSONResponse({"error": "No code returned from Google"}, status_code=400)

    flow = create_flow()
    flow.fetch_token(code=code)
    credentials = flow.credentials

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {credentials.token}"},
        )
    user_data = resp.json()

    user_doc = {
        "user_id": user_data["id"],
        "email": user_data["email"],
        "name": user_data["name"],
        "picture": user_data.get("picture", ""),
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_expiry": credentials.expiry.isoformat() if credentials.expiry else None,
    }

    await db.users.update_one(
        {"user_id": user_data["id"]},
        {"$set": user_doc},
        upsert=True,
    )

    # also initialise empty profile and contacts if first login
    await db.profiles.update_one(
        {"user_id": user_data["id"]},
        {"$setOnInsert": {"user_id": user_data["id"], "preferences": [], "constraints": []}},
        upsert=True,
    )
    await db.contacts.update_one(
        {"user_id": user_data["id"]},
        {"$setOnInsert": {"user_id": user_data["id"], "contacts": []}},
        upsert=True,
    )

    session_token = jwt.encode(
        {
            "user_id": user_data["id"],
            "email": user_data["email"],
            "name": user_data["name"],
            "picture": user_data.get("picture", ""),
            "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7),
        },
        settings.SECRET_KEY,
        algorithm="HS256",
    )

    response = RedirectResponse(url="/")
    response.set_cookie("session", session_token, httponly=True, max_age=604800)
    return response


@router.get("/me")
async def me(request: Request):
    session = request.cookies.get("session")
    if not session:
        return JSONResponse({"authenticated": False})
    try:
        payload = jwt.decode(session, settings.SECRET_KEY, algorithms=["HS256"])
        return JSONResponse({
            "authenticated": True,
            "user_id": payload["user_id"],
            "email": payload["email"],
            "name": payload["name"],
            "picture": payload.get("picture", ""),
        })
    except JWTError:
        return JSONResponse({"authenticated": False})


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/")
    response.delete_cookie("session")
    return response
