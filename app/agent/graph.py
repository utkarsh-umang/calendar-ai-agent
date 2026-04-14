from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langfuse.callback import CallbackHandler
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from app.agent.context import load_user_context
from app.agent.conversation import load_history, save_turn
from app.agent.tools.calendar import build_calendar_tools
from app.agent.tools.memory import build_memory_tools
from app.config import settings


# ── State ──────────────────────────────────────────────────────────────────────
# AgentState is the object that flows through every node in the graph.
# `messages` uses add_messages reducer — new messages are appended, not replaced.

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str
    session_id: str
    tool_call_count: int  # tracks iterations to prevent infinite loops


# ── System prompt ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an intelligent AI calendar assistant. You help users manage \
their Google Calendar through natural conversation.

You can:
- List, create, update, and delete calendar events
- Check availability for meetings
- Remember user preferences and constraints using memory tools
- Resolve contact names to email addresses from known contacts

{user_context}

RULES:
1. Always apply hard rules without exception. If the user says never before 10am, never suggest 9am.
2. When the user states a new preference or constraint, immediately save it with the memory tools.
3. When a message contains both a person's name and their email address, you MUST call \
save_contact BEFORE doing anything else — even before creating an event.
4. When creating events, use known contact emails automatically — don't ask for them again.
5. After completing an action, confirm what you did clearly and concisely.
6. If you cannot complete something, explain why and suggest an alternative.
7. MULTI-USER SCHEDULING: When the user explicitly names attendees or provides email addresses, \
follow these steps IN ORDER — do not skip any:
   Step 1: If a new name+email pair appears in the message, call save_contact first.
   Step 2: Call check_freebusy for every named attendee to verify they are available.
   Step 3: Only then call create_event, using the confirmed availability.
   - If someone is busy, tell the user who is unavailable and suggest the next available slot.
   - If the user insists on a time even after seeing a conflict, respect their decision and create it anyway.
   - If no specific attendees are mentioned (e.g. "team sync", "standup"), skip steps 1–2 and create the event immediately.

ERROR HANDLING AND SELF-CORRECTION:
- If a tool returns an error starting with "Error:", read it carefully before retrying.
- "Event not found" → call list_events first to find the correct event ID, then retry.
- "Could not parse the dates" → reformat the date more explicitly and retry.
- "Authentication error" or "Permission denied" → stop and inform the user, do not retry.
- "temporarily unavailable" → inform the user the service is down and to try again shortly.
- Never retry the exact same failed call more than once without changing something.
"""

# Maximum tool call iterations per request — prevents infinite loops
MAX_TOOL_ITERATIONS = 10


# ── Graph factory ──────────────────────────────────────────────────────────────

async def create_agent_graph(user_id: str):
    """
    Build a compiled LangGraph agent for a specific user.
    Called once per chat request — tools are fresh closures bound to user_id.
    """

    # load user context to inject into system prompt
    user_context = await load_user_context(user_id)

    # build all tools bound to this user
    all_tools = build_calendar_tools(user_id) + build_memory_tools(user_id)

    # LLM with tools declared — gpt-4o-mini is fast and cheap, good for this
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=settings.OPENAI_API_KEY,
    ).bind_tools(all_tools)

    # ── Node definitions ───────────────────────────────────────────────────────

    async def agent_node(state: AgentState) -> dict:
        """
        Core reasoning node.
        Prepends the system prompt (with user context) to messages,
        calls the LLM, and returns the response to be appended to state.
        """
        system_msg = SystemMessage(
            content=SYSTEM_PROMPT.format(user_context=user_context)
        )
        response = await llm.ainvoke([system_msg] + state["messages"])
        return {"messages": [response]}

    def should_continue(state: AgentState) -> str:
        """
        Routing function — the conditional edge.
        If the LLM's last message contains tool_calls, go to tools.
        Otherwise we're done — go to END.
        """
        last = state["messages"][-1]
        # hard stop — prevents infinite tool call loops
        if state.get("tool_call_count", 0) >= MAX_TOOL_ITERATIONS:
            return "end"
        
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return "end"

    async def tools_node_with_count(state: AgentState) -> dict:
        """
        Wraps the built-in ToolNode to increment the iteration counter.
        This is how we track how many tool calls have happened.
        """
        tool_node = ToolNode(all_tools)
        result = await tool_node.ainvoke(state)
        return {
            **result,
            "tool_call_count": state.get("tool_call_count", 0) + 1,
        }

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node_with_count)

    graph.set_entry_point("agent")

    # after agent: either call tools or end
    graph.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", "end": END},
    )

    # after tools: always go back to agent to process the result
    graph.add_edge("tools", "agent")

    return graph.compile()


# ── Public interface ───────────────────────────────────────────────────────────

async def run_agent(user_id: str, session_id: str, message: str) -> str:
    """
    Run the agent for a single user message.
    Loads history, runs the graph, saves the turn, returns the response.
    """

    # Langfuse traces every LLM call and tool execution
    langfuse_handler = CallbackHandler(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
        host=settings.LANGFUSE_BASE_URL,
        session_id=session_id,
        user_id=user_id,
    )

    graph = await create_agent_graph(user_id)

    # load previous turns so the agent has full context
    history = await load_history(user_id, session_id)

    result = await graph.ainvoke(
        {
            "messages": history + [HumanMessage(content=message)],
            "user_id": user_id,
            "session_id": session_id,
            "tool_call_count": 0,
        },
        config={"callbacks": [langfuse_handler]},
    )

    response_text = result["messages"][-1].content

    # persist this turn for future context
    await save_turn(user_id, session_id, message, response_text)

    return response_text