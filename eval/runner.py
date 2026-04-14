"""
Runner — sets up DB state, calls the agent, collects traces, scores results.
"""

import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient
from langfuse import Langfuse
from langfuse.api.core import ApiError as LangfuseApiError

from app.agent.graph import run_agent
from eval.scorers import score

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27037")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://us.cloud.langfuse.com")

mongo = AsyncIOMotorClient(MONGODB_URL)
db = mongo.calendar_agent


async def setup_test_user() -> str:
    """
    Create a test user in MongoDB using the real authenticated user's tokens.
    We reuse the first real user's tokens so Calendar API calls actually work.
    """
    real_user = await db.users.find_one({})
    if not real_user:
        raise RuntimeError(
            "No authenticated user found in DB. "
            "Please log in via the app at least once before running eval."
        )

    test_user_id = f"eval_test_{uuid.uuid4().hex[:8]}"

    await db.users.insert_one({
        "user_id": test_user_id,
        "email": real_user["email"],
        "name": f"Eval Test ({real_user['name']})",
        "access_token": real_user["access_token"],
        "refresh_token": real_user["refresh_token"],
        "token_expiry": real_user.get("token_expiry"),
    })

    return test_user_id


async def setup_db_state(user_id: str, setup: dict):
    """
    Insert test-specific DB state before running a test case.
    setup = { "profiles": {...}, "contacts": {...} }
    """
    if "profiles" in setup:
        await db.profiles.update_one(
            {"user_id": user_id},
            {"$set": {**setup["profiles"], "user_id": user_id}},
            upsert=True,
        )
    if "contacts" in setup:
        await db.contacts.update_one(
            {"user_id": user_id},
            {"$set": {**setup["contacts"], "user_id": user_id}},
            upsert=True,
        )


async def reset_db_state(user_id: str):
    """Reset profile and contacts between tests to avoid state bleed."""
    await db.profiles.update_one(
        {"user_id": user_id},
        {"$set": {"constraints": [], "preferences": []}},
        upsert=True,
    )
    await db.contacts.update_one(
        {"user_id": user_id},
        {"$set": {"contacts": []}},
        upsert=True,
    )


_RETRIABLE_STATUS_CODES = {429, 502, 503, 504}

_TOOL_NAMES = [
    "list_events", "create_event", "update_event",
    "delete_event", "check_freebusy",
    "save_constraint", "save_preference", "save_contact",
]


async def get_tools_called(
    user_id: str,
    session_id: str,
    *,
    max_attempts: int = 4,
    base_delay: float = 2.0,
) -> list[str]:
    """
    Fetch tool names called during a session from Langfuse traces.
    Returns list of tool names e.g. ['list_events', 'save_constraint']

    Retries with exponential backoff for two distinct reasons:
      1. Empty traces  — Langfuse hasn't indexed the data yet (propagation lag)
      2. HTTP 4xx/5xx — transient server errors (429, 502, 503, 504)
    Waits: 2s → 4s → 8s → 16s between attempts.
    """
    try:
        lf = Langfuse(
            public_key=LANGFUSE_PUBLIC_KEY,
            secret_key=LANGFUSE_SECRET_KEY,
            host=LANGFUSE_HOST,
        )
        lf.flush()

        delay = base_delay
        for attempt in range(1, max_attempts + 1):
            await asyncio.sleep(delay)

            try:
                traces = lf.client.trace.list(session_id=session_id).data
            except LangfuseApiError as e:
                if e.status_code in _RETRIABLE_STATUS_CODES and attempt < max_attempts:
                    print(f"    Langfuse {e.status_code}, retrying in {delay * 2:.0f}s... (attempt {attempt}/{max_attempts})")
                    delay *= 2
                    continue
                raise

            if not traces:
                if attempt < max_attempts:
                    delay *= 2
                    continue
                return []

            tools = []
            for trace in traces:
                try:
                    observations = lf.client.observations.get_many(trace_id=trace.id).data
                except LangfuseApiError as e:
                    if e.status_code in _RETRIABLE_STATUS_CODES and attempt < max_attempts:
                        print(f"    Langfuse {e.status_code} fetching observations, retrying in {delay * 2:.0f}s... (attempt {attempt}/{max_attempts})")
                        delay *= 2
                        tools = []
                        break
                    raise
                for obs in observations:
                    if obs.type == "SPAN" and obs.name:
                        name = obs.name.lower()
                        if any(t in name for t in _TOOL_NAMES):
                            tools.append(obs.name)
            else:
                return tools

    except Exception as e:
        print(f"    Warning: could not fetch Langfuse traces: {e}")
        return []

    return []


async def run_test(test_case: dict, user_id: str) -> dict:
    """Run a single test case and return the result."""
    session_id = f"eval_{test_case['id']}_{uuid.uuid4().hex[:6]}"

    print(f"\n{'─'*55}")
    print(f"  {test_case['id']} — {test_case['description']}")
    print(f"  Message: \"{test_case['message']}\"")

    # reset state between tests
    await reset_db_state(user_id)

    # apply any test-specific setup
    if test_case.get("setup"):
        await setup_db_state(user_id, test_case["setup"])

    # run the agent
    try:
        response = await run_agent(
            user_id=user_id,
            session_id=session_id,
            message=test_case["message"],
        )
        print(f"  Response: {response[:120]}{'...' if len(response) > 120 else ''}")
    except Exception as e:
        print(f"  ERROR: {e}")
        return {
            "id": test_case["id"],
            "description": test_case["description"],
            "category": test_case["category"],
            "score": 0,
            "reason": f"FAIL — agent threw exception: {str(e)}",
            "response": "",
        }

    tools_called = await get_tools_called(user_id, session_id)
    trace_data = {"tools_called": tools_called}

    test_score, reason = await score(test_case, response, user_id, trace_data)

    status = "✅ PASS" if test_score == 1 else "❌ FAIL"
    print(f"  {status} — {reason}")

    return {
        "id": test_case["id"],
        "description": test_case["description"],
        "category": test_case["category"],
        "scorer": test_case["scorer"],
        "message": test_case["message"],
        "response": response,
        "score": test_score,
        "reason": reason,
    }


async def cleanup_test_user(user_id: str):
    """Remove all test data after eval run."""
    await db.users.delete_one({"user_id": user_id})
    await db.profiles.delete_one({"user_id": user_id})
    await db.contacts.delete_one({"user_id": user_id})
    await db.conversations.delete_many({"user_id": user_id})


async def run_all(test_cases: list) -> list[dict]:
    """Run all test cases and return results."""
    print("\n" + "="*55)
    print("  CALENDAR AGENT — EVALUATION SUITE")
    print("="*55)

    user_id = await setup_test_user()
    print(f"\n  Test user: {user_id}")

    results = []
    for tc in test_cases:
        result = await run_test(tc, user_id)
        results.append(result)

    await cleanup_test_user(user_id)
    return results
