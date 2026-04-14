from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr


# ── Shared config ──────────────────────────────────────────────────────────────
# extra="ignore" so MongoDB's _id field never causes validation errors

class MongoModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


# ── Profile models ─────────────────────────────────────────────────────────────

class ProfileRule(MongoModel):
    rule: str
    source: Literal["explicit", "inferred"] = "explicit"


class UserProfile(MongoModel):
    user_id: str
    constraints: list[ProfileRule] = []
    preferences: list[ProfileRule] = []


# ── Contact models ─────────────────────────────────────────────────────────────

class Contact(MongoModel):
    name: str
    email: EmailStr


class ContactsDoc(MongoModel):
    user_id: str
    contacts: list[Contact] = []


# ── Conversation models ────────────────────────────────────────────────────────

class ConversationMessage(MongoModel):
    role: Literal["human", "ai"]
    content: str


class ConversationDoc(MongoModel):
    user_id: str
    session_id: str
    messages: list[ConversationMessage] = []


# ── User / auth models ─────────────────────────────────────────────────────────

class UserDoc(MongoModel):
    user_id: str
    email: EmailStr
    name: str
    picture: str = ""
    access_token: str
    refresh_token: str | None = None
    token_expiry: str | None = None


class SessionPayload(MongoModel):
    user_id: str
    email: EmailStr
    name: str
    picture: str = ""


# ── API request / response models ─────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    response: str
    session_id: str
