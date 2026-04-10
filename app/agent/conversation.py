from langchain_core.messages import AIMessage, HumanMessage

from app.db.mongo import db


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

    messages = doc.get("messages", [])[-limit:]
    result = []
    for msg in messages:
        if msg["role"] == "human":
            result.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "ai":
            result.append(AIMessage(content=msg["content"]))
    return result


async def save_turn(user_id: str, session_id: str, human_msg: str, ai_msg: str):
    """
    Persist one conversation turn (user message + agent response) to MongoDB.
    Called after every successful agent response.
    """
    await db.conversations.update_one(
        {"user_id": user_id, "session_id": session_id},
        {
            "$push": {
                "messages": {
                    "$each": [
                        {"role": "human", "content": human_msg},
                        {"role": "ai", "content": ai_msg},
                    ]
                }
            },
            "$setOnInsert": {"user_id": user_id, "session_id": session_id},
        },
        upsert=True,
    )