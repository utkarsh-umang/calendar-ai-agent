from langchain_core.messages import AIMessage, HumanMessage

from app.db.mongo import db
from app.models.models import ConversationMessage


async def load_history(user_id: str, session_id: str, limit: int = 20) -> list:
    """
    Load the last N messages from this session from MongoDB.
    Returns a list of LangChain HumanMessage / AIMessage objects
    ready to pass directly into the graph.
    """
    doc = await db.conversations.find_one(
        {"user_id": user_id, "session_id": session_id}
    )
    if not doc:
        return []

    raw_messages = doc.get("messages", [])[-limit:]
    result = []
    for raw in raw_messages:
        msg = ConversationMessage.model_validate(raw)
        if msg.role == "human":
            result.append(HumanMessage(content=msg.content))
        elif msg.role == "ai":
            result.append(AIMessage(content=msg.content))
    return result


async def save_turn(user_id: str, session_id: str, human_msg: str, ai_msg: str):
    """
    Persist one conversation turn (user message + agent response) to MongoDB.
    Called after every successful agent response.
    """
    human = ConversationMessage(role="human", content=human_msg)
    ai = ConversationMessage(role="ai", content=ai_msg)

    await db.conversations.update_one(
        {"user_id": user_id, "session_id": session_id},
        {
            "$push": {
                "messages": {
                    "$each": [human.model_dump(), ai.model_dump()],
                }
            },
            "$setOnInsert": {"user_id": user_id, "session_id": session_id},
        },
        upsert=True,
    )
