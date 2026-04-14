from langchain_core.tools import tool

from app.db.mongo import db
from app.models.models import Contact, ProfileRule


def build_memory_tools(user_id: str) -> list:
    """
    Create memory tools bound to user_id via closure.
    These let the agent persist what it learns about the user.
    """

    @tool
    async def save_constraint(constraint: str) -> str:
        """
        Save a hard scheduling constraint — a rule that must never be broken.
        Use this when the user states firm rules like:
        'I never take meetings before 10am' or 'I don't work on Sundays'.
        Args:
            constraint: The rule to save (e.g. 'never schedule before 10am')
        """
        try:
            rule = ProfileRule(rule=constraint, source="explicit")
            await db.profiles.update_one(
                {"user_id": user_id},
                {"$addToSet": {"constraints": rule.model_dump()}},
                upsert=True,
            )
            return f"Constraint saved: '{constraint}'"
        except Exception as e:
            return f"Error saving constraint: {str(e)}"

    @tool
    async def save_preference(preference: str) -> str:
        """
        Save a soft scheduling preference — something to apply when possible but not a hard rule.
        Use this when the user mentions things like:
        'I prefer 30 minute meetings' or 'I like buffer time between calls'.
        Args:
            preference: The preference to save
        """
        try:
            rule = ProfileRule(rule=preference, source="explicit")
            await db.profiles.update_one(
                {"user_id": user_id},
                {"$addToSet": {"preferences": rule.model_dump()}},
                upsert=True,
            )
            return f"Preference saved: '{preference}'"
        except Exception as e:
            return f"Error saving preference: {str(e)}"

    @tool
    async def save_contact(name: str, email: str) -> str:
        """
        Save a contact's name and email address for future reference.
        Use this when the user tells you who someone is or provides their email.
        Args:
            name: Contact's name (e.g. 'Alex')
            email: Contact's email address
        """
        try:
            contact = Contact(name=name, email=email)
            # remove existing entry with same name to avoid duplicates
            await db.contacts.update_one(
                {"user_id": user_id},
                {"$pull": {"contacts": {"name": {"$regex": f"^{name}$", "$options": "i"}}}},
            )
            await db.contacts.update_one(
                {"user_id": user_id},
                {"$push": {"contacts": contact.model_dump()}},
                upsert=True,
            )
            return f"Contact saved: {contact.name} → {contact.email}"
        except Exception as e:
            return f"Error saving contact: {str(e)}"

    return [save_constraint, save_preference, save_contact]
