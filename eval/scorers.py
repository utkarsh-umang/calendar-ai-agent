"""
Three scoring strategies:

1. tool_called     — checks if the agent called the expected tool
                     works by scanning Langfuse traces for tool use
2. llm_judge       — asks GPT to score whether the response meets the criteria
3. state_check     — queries MongoDB directly to verify state was updated
"""

import os
from openai import AsyncOpenAI
from motor.motor_asyncio import AsyncIOMotorClient

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27037")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)
mongo = AsyncIOMotorClient(MONGODB_URL)
db = mongo.calendar_agent


async def score_tool_called(response: str, expected_tool: str, trace_data: dict) -> tuple[int, str]:
    """
    Check if the expected tool name appears in the agent's trace.
    trace_data contains the list of tool calls recorded during the run.
    """
    tools_called = trace_data.get("tools_called", [])

    if expected_tool in tools_called:
        return 1, f"PASS — '{expected_tool}' was called"
    else:
        return 0, f"FAIL — expected '{expected_tool}' but got tools: {tools_called or 'none'}"


async def score_llm_judge(
    message: str,
    response: str,
    expected_behavior: str,
) -> tuple[int, str]:
    """
    Ask GPT-4o-mini to judge whether the agent response meets the expected behavior.
    Returns 1 (pass) or 0 (fail) with reasoning.
    """
    prompt = f"""You are evaluating an AI calendar assistant's response.

User message: {message}

Agent response: {response}

Expected behavior: {expected_behavior}

Does the agent response meet the expected behavior? 
Reply with exactly one of:
PASS: <one sentence reason>
FAIL: <one sentence reason>"""

    result = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=100,
    )

    verdict = result.choices[0].message.content.strip()
    score = 1 if verdict.upper().startswith("PASS") else 0
    return score, verdict


async def score_state_check(
    user_id: str,
    expected: dict,
) -> tuple[int, str]:
    """
    Query MongoDB to verify the expected state was written correctly.
    expected = {
        "collection": "profiles",
        "field": "constraints",
        "contains": "sunday"   # substring match against any item's "rule" field
    }
    """
    collection = expected["collection"]
    field = expected["field"]
    substring = expected["contains"].lower()

    doc = await db[collection].find_one({"user_id": user_id})
    if not doc:
        return 0, f"FAIL — no document found in '{collection}' for user"

    items = doc.get(field, [])

    for item in items:
        rule = item.get("rule", "") if isinstance(item, dict) else str(item)
        if substring in rule.lower():
            return 1, f"PASS — found '{substring}' in {collection}.{field}"

    return 0, f"FAIL — '{substring}' not found in {collection}.{field}. Got: {items}"


async def score(test_case: dict, response: str, user_id: str, trace_data: dict) -> tuple[int, str]:
    """
    Route to the correct scorer based on test case config.
    Returns (score: 0|1, reason: str)
    """
    scorer = test_case["scorer"]

    if scorer == "tool_called":
        return await score_tool_called(response, test_case["expected"], trace_data)

    elif scorer == "llm_judge":
        return await score_llm_judge(
            test_case["message"],
            response,
            test_case["expected"],
        )

    elif scorer == "state_check":
        return await score_state_check(user_id, test_case["expected"])

    else:
        return 0, f"FAIL — unknown scorer: {scorer}"
