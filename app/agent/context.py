from datetime import datetime

from app.db.mongo import db
from app.models.models import ContactsDoc, UserProfile


async def load_user_context(user_id: str) -> str:
    """
    Load user profile, constraints, preferences and contacts from MongoDB.
    Returns a formatted string that gets injected into the system prompt
    so the agent knows the user's rules and contacts before it reasons.
    """
    raw_profile = await db.profiles.find_one({"user_id": user_id}) or {}
    raw_contacts = await db.contacts.find_one({"user_id": user_id}) or {}

    profile = UserProfile.model_validate({**raw_profile, "user_id": user_id})
    contacts_doc = ContactsDoc.model_validate({**raw_contacts, "user_id": user_id})

    parts = []

    if profile.constraints:
        rules = "\n".join(f"  - {c.rule}" for c in profile.constraints)
        parts.append(f"HARD RULES — never violate these:\n{rules}")

    if profile.preferences:
        prefs = "\n".join(f"  - {p.rule}" for p in profile.preferences)
        parts.append(f"SOFT PREFERENCES — apply when possible:\n{prefs}")

    if contacts_doc.contacts:
        contact_list = "\n".join(
            f"  - {c.name} → {c.email}" for c in contacts_doc.contacts
        )
        parts.append(f"KNOWN CONTACTS:\n{contact_list}")

    now = datetime.now().strftime("%A, %B %d, %Y %I:%M %p")
    parts.append(f"CURRENT DATE/TIME: {now}")

    return "\n\n".join(parts)
