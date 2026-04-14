# Evaluation Report — Calendar Agent

**Date:** 2026-04-14 12:42

**Success Rate: 8/8 (100%)**


---

## Results Summary

| ID | Description | Category | Scorer | Result |
|---|---|---|---|---|
| TC1 | List events for a date range | baseline | tool_called | ✅ PASS |
| TC2 | Create a new event | baseline | tool_called | ✅ PASS |
| TC3 | Delete an event by name | baseline | tool_called | ✅ PASS |
| TC4 | Check availability | baseline | tool_called | ✅ PASS |
| TC5 | Agent refuses to schedule before hard constraint time | memory | llm_judge | ✅ PASS |
| TC6 | Agent saves a new constraint when user states one | memory | state_check | ✅ PASS |
| TC7 | Agent resolves known contact name to email | memory | llm_judge | ✅ PASS |
| TC8 | Agent handles ambiguous request gracefully | edge_case | llm_judge | ✅ PASS |

---

## Detailed Results

### TC1 — List events for a date range ✅ PASS

**Category:** baseline  
**Scorer:** tool_called

**User message:** `What's on my calendar tomorrow?`

**Agent response:**
> You have no events scheduled for tomorrow, April 15, 2026.

**Score reason:** PASS — 'list_events' was called

### TC2 — Create a new event ✅ PASS

**Category:** baseline  
**Scorer:** tool_called

**User message:** `Schedule a team sync tomorrow at 2pm for 1 hour`

**Agent response:**
> I have scheduled a team sync for tomorrow at 2 PM for 1 hour. If you need to add attendees or make any changes, just let me know!

**Score reason:** PASS — 'create_event' was called

### TC3 — Delete an event by name ✅ PASS

**Category:** baseline  
**Scorer:** tool_called

**User message:** `Cancel my team sync tomorrow`

**Agent response:**
> I have successfully canceled your team sync scheduled for tomorrow. If you need anything else, just let me know!

**Score reason:** PASS — 'delete_event' was called

### TC4 — Check availability ✅ PASS

**Category:** baseline  
**Scorer:** tool_called

**User message:** `Am I free tomorrow afternoon?`

**Agent response:**
> You are free tomorrow afternoon! There are no events scheduled between 12 PM and 5 PM on April 15, 2026.

**Score reason:** PASS — 'list_events' was called

### TC5 — Agent refuses to schedule before hard constraint time ✅ PASS

**Category:** memory  
**Scorer:** llm_judge

**User message:** `Schedule a meeting tomorrow at 8am`

**Agent response:**
> I cannot schedule meetings before 10am. Would you like to schedule the meeting for 10am or later instead?

**Score reason:** PASS: The agent correctly identifies the scheduling conflict and offers an alternative time, adhering to the no-meetings-before-10am rule.

### TC6 — Agent saves a new constraint when user states one ✅ PASS

**Category:** memory  
**Scorer:** state_check

**User message:** `Just so you know, I never work on Sundays`

**Agent response:**
> I've saved your constraint: you never work on Sundays.

**Score reason:** PASS — found 'sunday' in profiles.constraints

### TC7 — Agent resolves known contact name to email ✅ PASS

**Category:** memory  
**Scorer:** llm_judge

**User message:** `Schedule a 30 minute meeting with Alex tomorrow at 3pm`

**Agent response:**
> I have scheduled a 30-minute meeting with Alex for tomorrow at 3 PM. If you need anything else, just let me know!

**Score reason:** PASS: The agent correctly scheduled the meeting without asking for Alex's email address or any additional contact information.

### TC8 — Agent handles ambiguous request gracefully ✅ PASS

**Category:** edge_case  
**Scorer:** llm_judge

**User message:** `Move my meeting`

**Agent response:**
> Could you please provide me with the details of the meeting you'd like to move, such as the title or the date and time? Additionally, let me know the new date and time you'd like to schedule it for.

**Score reason:** PASS: The agent response appropriately asks for clarification on which meeting to move and requests the new date and time, aligning with the expected behavior.


---

## Failure Analysis

All test cases passed.


---

## Methodology

Three scoring strategies were used:

- **tool_called** — verifies the agent invoked the correct Google Calendar API tool by inspecting Langfuse trace spans. Pass/fail is deterministic.
- **llm_judge** — uses GPT-4o-mini to evaluate whether the agent's natural language response meets the expected behavior criteria. Used for rule adherence and graceful handling cases where deterministic checks are insufficient.
- **state_check** — queries MongoDB directly after the agent runs to verify the correct data was persisted. Used for memory/preference saving tests.
