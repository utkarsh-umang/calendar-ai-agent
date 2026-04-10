from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from jose import jwt, JWTError
from pydantic import BaseModel

from app.config import settings
from app.agent.graph import run_agent
from app.db.mongo import db

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


def get_user_from_cookie(request: Request) -> dict | None:
    session = request.cookies.get("session")
    if not session:
        return None
    try:
        return jwt.decode(session, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        return None


@router.post("/chat")
async def chat(request: Request, body: ChatRequest):
    user = get_user_from_cookie(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    try:
        response = await run_agent(
            user_id=user["user_id"],
            session_id=body.session_id,
            message=body.message,
        )
        return JSONResponse({"response": response, "session_id": body.session_id})

    except Exception as e:
        return JSONResponse({"error": f"Agent error: {str(e)}"}, status_code=500)


@router.get("/chat/history")
async def get_history(request: Request, session_id: str):
    user = get_user_from_cookie(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    doc = await db.conversations.find_one({
        "user_id": user["user_id"],
        "session_id": session_id,
    })

    messages = doc.get("messages", []) if doc else []
    return JSONResponse({"messages": messages})