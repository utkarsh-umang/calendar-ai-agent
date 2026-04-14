# Calendar AI Agent

A stateful, multi-user AI executive assistant that manages Google Calendar through natural conversation. Built with LangGraph, FastAPI, MongoDB, and Langfuse.

---

## Capabilities

| Objective | What's built |
|---|---|
| Calendar operations | List, create, update, delete events via natural language |
| Multi-user scheduling | Checks freebusy availability before booking; sends Google Calendar invites |
| Stateful architecture | Google OAuth per user; persistent sessions and memory in MongoDB |
| Long-term memory | Remembers hard constraints, soft preferences, and contacts across sessions |
| Rule adherence | Agent never violates stored rules — they're injected into every system prompt |
| Observability | Every LLM call and tool execution traced in Langfuse with full span detail |
| Error handling | Exponential backoff on transient errors; LLM self-correction on permanent ones |
| Automated evaluation | 11 test cases across 5 categories; three scoring strategies; scored report |

---

## Quick start

**Prerequisites:** Docker, Docker Compose, a Google Cloud project with Calendar API enabled, an OpenAI API key, a Langfuse project.

```bash
git clone <repo>
cd calendar-agent
cp .env.example .env
# fill in your credentials in .env
docker-compose up --build
```

Open `http://localhost:9000`, log in with Google, start chatting.

**Run the eval suite:**
```bash
docker-compose exec app python eval/run_eval.py
```

---

## Project structure

```
app/
  agent/
    graph.py          → LangGraph ReAct agent, run_agent() entry point
    context.py        → loads user profile into system prompt
    conversation.py   → saves/loads chat history from MongoDB
    tools/
      calendar.py     → 5 Google Calendar API tools with retry logic
      memory.py       → 3 memory tools (constraint, preference, contact)
  routes/
    auth.py           → Google OAuth flow (/auth/login, /auth/callback)
    chat.py           → POST /chat, GET /chat/history
  models.py           → Pydantic models for all MongoDB documents and API boundaries
  db/mongo.py         → async MongoDB connection
  static/index.html   → login page + chat UI
eval/
  cases.py            → 11 test case definitions
  runner.py           → test orchestration + Langfuse trace fetching
  scorers.py          → tool_called, llm_judge, state_check scorers
  report.py           → generates EVALUATION.md
  run_eval.py         → entry point
```

---

## Architecture overview

### Agent design

The agent is a LangGraph ReAct loop — two nodes, one conditional edge:

```
User message
      ↓
[agent node] — LLM reasons with system prompt + full message history
      ↓ tool_calls present?
     yes → [tools node] — executes tool, appends result to messages
      ↑_______________|
      ↓ no tool calls
    END → response returned
```

The LLM sees the full message list on every pass through the agent node. Tool results are appended as messages, so the LLM always has complete context of what it did and what came back before deciding the next step. A `MAX_TOOL_ITERATIONS` guard stops the loop at 10 iterations to prevent runaway execution.

### Memory and context layer

Memory is split into three distinct layers with different lifetimes:

**1. In-context (short-term)**
Raw conversation history loaded from MongoDB at the start of each request and passed directly into the graph. The agent sees the last 20 turns. This handles multi-turn references ("move that meeting we just created") but has a context window ceiling.

**2. Persistent profile (long-term)**
Structured facts extracted from conversation and stored permanently in MongoDB per user:

```
profiles collection:
  constraints  → hard rules, never violated ("never before 10am")
  preferences  → soft rules, applied when possible ("prefer 30 min meetings")

contacts collection:
  contacts     → name → email mappings ("Alex → alex@company.com")
```

The agent has three dedicated tools for writing to this layer: `save_constraint`, `save_preference`, `save_contact`. The system prompt instructs the agent to call these immediately when the user states something worth remembering.

**3. Context injection**
Before every LLM call, `context.py` reads the user's full profile and contacts from MongoDB and formats them into the system prompt:

```
HARD RULES — never violate these:
  - never schedule before 10am

KNOWN CONTACTS:
  - Alex → alex@company.com

CURRENT DATE/TIME: Tuesday, April 14, 2026 2:30 PM
```

This means the agent applies rules without being reminded — they're already in every prompt.

### Why upfront injection rather than a retrieval tool

For this MVP, user profiles are small (< 20 rules, < 50 contacts) so injecting everything upfront costs roughly 200–500 tokens and keeps the implementation simple. In production with hundreds of contacts and years of inferred preferences, the right approach is semantic retrieval — embedding the user's message and fetching only relevant context from a vector store. This is documented as a known production improvement.

### Multi-user architecture

Each user gets isolated state in MongoDB: their own `users`, `profiles`, `contacts`, and `conversations` documents keyed by `user_id`. OAuth tokens are stored per user and refreshed automatically on expiry.

For multi-user scheduling, the agent calls `check_freebusy` against the Google Calendar freebusy API before creating any event with attendees. This endpoint returns only busy/free slots — never event titles or details — preserving privacy. The agent only creates the event after confirming availability, or if the user explicitly overrides a conflict.

---

## Evaluation strategy

### Overview

The eval suite runs 11 test cases against a real agent instance using your actual Google Calendar. A temporary test user is created using your authenticated tokens so Calendar API calls work end to end. DB state is reset between tests to prevent bleed.

### Scoring methods

**tool_called** — deterministic. Verifies the expected tool was invoked by inspecting Langfuse trace spans after the run. Used for baseline calendar operations where the correct behavior maps directly to a tool call.

**llm_judge** — GPT-4o-mini reads the agent's response and evaluates it against a plain-English success criterion. Returns PASS or FAIL with a one-sentence reason. Used for nuanced behaviors like rule adherence, self-correction, and graceful error handling where deterministic checks are insufficient.

**state_check** — queries MongoDB directly after the agent runs to verify the correct data was persisted. Used for memory saving tests where the proof is in the database, not the response.

### Test categories and coverage

| Category | Cases | What's tested |
|---|---|---|
| baseline | TC1–TC4 | List, create, delete, availability check |
| memory | TC5–TC7 | Rule adherence, constraint saving, contact resolution |
| edge_case | TC8 | Ambiguous request handling |
| error_handling | TC9–TC10 | 404 self-correction, unparseable date |
| multi_user | TC11 | Freebusy check before scheduling |

---

## Error handling

Calendar tool errors are classified into three categories:

**Retryable (429, 5xx)** — exponential backoff, up to 3 attempts (1s → 2s → 4s). These are transient failures where retrying makes sense.

**Permanent with self-correction (404)** — returns a rich error message: "Event not found — use list_events first to get the correct ID." The LLM reads this and changes its approach rather than retrying the same failed call.

**Permanent, stop (401, 403)** — auth and permission errors are surfaced directly to the user. No retry attempted.

The system prompt includes explicit self-correction instructions so the LLM knows what to do for each error type.

---

## Trade-offs

### Model choice: gpt-4o-mini

Chose `gpt-4o-mini` over `gpt-4o` for two reasons: latency and cost. Calendar operations are tool-heavy — the LLM's job is mostly routing to the right tool with the right parameters, not complex reasoning. `gpt-4o-mini` handles this well at roughly 10x lower cost and ~40% lower latency. For a production system handling hundreds of users, this matters.

The tradeoff is occasional failures on nuanced rule adherence — `gpt-4o` would be more reliable for complex multi-constraint scheduling. The right production approach is tiered: use `gpt-4o-mini` for simple operations and escalate to `gpt-4o` when the request involves multiple constraints or conflict resolution.

### Conversation history: raw messages vs summarisation

We store and reload raw conversation history (last 20 turns). This is simple and works well for sessions under ~50 turns. The production gap is summarisation — periodically compressing older turns into a short summary and discarding the raw messages. Without this, long-lived sessions eventually hit context limits and get expensive. Implementing summarisation as a background job on sessions older than 7 days would close this gap.

### Context injection vs semantic retrieval

User profile is injected into every system prompt upfront. Simple, fast, correct for small profiles. Doesn't scale to large profiles — a user with 200 contacts and 3 years of inferred preferences would add thousands of tokens to every request. Production fix: embed the user's message, retrieve only relevant profile entries from a vector store (Pinecone or Qdrant), inject the top-k results. Tools like Mem0 implement this pattern well.

### Multi-user OAuth

Currently supports full OAuth for any number of users. Freebusy checking works for any Google Calendar user by email — the other user doesn't need to be registered in our system. The missing piece is explicit consent — in production, users should be able to control whether others can check their availability, similar to Google Calendar's sharing settings.

### LangGraph vs a simpler loop

LangGraph adds some complexity over a manual while loop. The benefit is clean state management via `AgentState`, built-in support for conditional edges, and easy extensibility — adding a new node (like a summarisation step) is a matter of adding a node and an edge rather than rewriting control flow. For a production system that will grow, this is the right call.

---

## Environment variables

```
GOOGLE_CLIENT_ID        → from Google Cloud Console
GOOGLE_CLIENT_SECRET    → from Google Cloud Console
SECRET_KEY              → any random string for JWT signing
REDIRECT_URI            → http://localhost:9000/auth/callback
MONGODB_URL             → mongodb://mongo:27017
OPENAI_API_KEY          → from OpenAI
LANGFUSE_PUBLIC_KEY     → from Langfuse project settings
LANGFUSE_SECRET_KEY     → from Langfuse project settings
LANGFUSE_HOST           → https://cloud.langfuse.com
```

---

## Production improvements

### Memory and learning

- **Self-learning preference extraction** — the agent currently saves preferences only when the user explicitly states them. Implicit patterns (e.g. always books 30-minute 1:1s, never schedules back-to-back meetings) go undetected. The fix is a background cron job that runs periodically per active user, takes their last ~50 conversation messages, and passes them to a reasoning LLM with a structured prompt asking it to identify recurring behavioural patterns not already in the profile. The output is a JSON list of inferred preferences with a confidence score. High-confidence results are written to a separate `inferred_preferences` field in MongoDB (distinct from explicitly stated `preferences`, so the agent can apply them with appropriate softness). The job tracks a `last_analysed_at` timestamp per user to avoid reprocessing the same history on every run, and diffs inferred results against the existing profile before writing to prevent duplicates.

- **Conversation summarisation** — long sessions will eventually hit context limits. A background job that compresses older turns into a rolling summary would close this gap.

- **Semantic profile retrieval** — upfront context injection doesn't scale to large user profiles. The production fix is to embed the user's message and retrieve only relevant profile entries from a vector store.

### Evaluation and prompt quality

- **Automated prompt optimisation** — the eval pipeline currently measures failures but doesn't act on them. In production, a scheduled job would collect all eval failures from the Langfuse logs, group them by failure pattern, and send them to a reasoning LLM. That LLM would analyse why the current prompt version is causing each failure class, then produce a candidate revised prompt. The revised prompt would be pushed back into Langfuse as a new prompt version, and the eval suite would run automatically against it to confirm improvement before the version is promoted. This closes the loop between evaluation and the system prompt, turning the eval pipeline into a continuous improvement engine rather than a one-shot report.

- **Tool call count validation** — the current `tool_called` scorer only checks whether the expected tool was invoked, not whether the agent called the right number of tools. A scorer that asserts an exact tool call sequence (e.g. `check_freebusy` then `create_event`, nothing more) would catch over-calling and under-calling bugs that the current eval misses.

### Reliability and scaling

- **Rate limiting** — two layers are missing. At the application layer, `slowapi` middleware on the `/chat` endpoint would cap requests per user (e.g. 10/minute), preventing abuse before the agent even starts. At the LLM layer, routing OpenAI calls through a [LiteLLM](https://github.com/BerriAI/litellm) proxy would add per-user TPM/RPM caps, hard budget limits, and automatic fallback to a secondary model if the primary is rate-limited or unavailable.

- **Token refresh edge cases** — mid-conversation token expiry is handled but not tested under load.

- **Availability consent model** — users should control who can check their freebusy, similar to Google Calendar's sharing settings.

### Observability

- **Application-level logging** — Langfuse covers LLM-layer observability (traces, token costs, tool calls) but not business-level telemetry. A dedicated logging module writing structured events (user activity, tool error rates, latencies) to a `logs` MongoDB collection, paired with a dashboard (Metabase or Grafana), would give full platform visibility. Langfuse trace IDs can be cross-referenced in every log document so both systems stay linked.
