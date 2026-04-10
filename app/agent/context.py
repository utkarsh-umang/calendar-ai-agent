from datetime import datetime

from app.db.mongo import db


async def load_user_context(user_id: str) -> str:
    """
    Load user profile, constraints, preferences and contacts from MongoDB.
    Returns a formatted string that gets injected into the system prompt
    so the agent knows the user's rules and contacts before it reasons.
    """
    profile = await db.profiles.find_one({"user_id": user_id}) or {}
    contacts_doc = await db.contacts.find_one({"user_id": user_id}) or {}

    constraints = profile.get("constraints", [])
    preferences = profile.get("preferences", [])
    contacts = contacts_doc.get("contacts", [])

    parts = []

    if constraints:
        rules = "\n".join(f"  - {c['rule']}" for c in constraints)
        parts.append(f"HARD RULES — never violate these:\n{rules}")

    if preferences:
        prefs = "\n".join(f"  - {p['rule']}" for p in preferences)
        parts.append(f"SOFT PREFERENCES — apply when possible:\n{prefs}")

    if contacts:
        contact_list = "\n".join(f"  - {c['name']} → {c['email']}" for c in contacts)
        parts.append(f"KNOWN CONTACTS:\n{contact_list}")

    now = datetime.now().strftime("%A, %B %d, %Y %I:%M %p")
    parts.append(f"CURRENT DATE/TIME: {now}")

    return "\n\n".join(parts)