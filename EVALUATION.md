# Evaluation Report — Calendar Agent

**Date:** 2026-04-14 13:37

**Success Rate: 11/11 (100%)**


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
| TC9 | Agent self-corrects when given a nonexistent event ID | error_handling | llm_judge | ✅ PASS |
| TC10 | Agent handles completely unparseable date gracefully | error_handling | llm_judge | ✅ PASS |
| TC11 | Agent checks freebusy before scheduling with another user | multi_user | tool_called | ✅ PASS |

---

## Detailed Results

### TC1 — List events for a date range ✅ PASS

**Category:** baseline  
**Scorer:** tool_called

**User message:** `What's on my calendar tomorrow?`

**Agent response:**
> You have one event on your calendar for tomorrow:

- **Title:** Demo Meet
- **Start Time:** April 15, 2026, 1:00 PM (IST)
- **End Time:** April 15, 2026, 2:00 PM (IST) 

Let me know if you need any further assistance!

**Score reason:** PASS — 'list_events' was called

### TC2 — Create a new event ✅ PASS

**Category:** baseline  
**Scorer:** tool_called

**User message:** `Schedule a team sync tomorrow at 2pm for 1 hour`

**Agent response:**
> I have scheduled a team sync for tomorrow at 2 PM for 1 hour. If you need any further adjustments or details, just let me know!

**Score reason:** PASS — 'create_event' was called

### TC3 — Delete an event by name ✅ PASS

**Category:** baseline  
**Scorer:** tool_called

**User message:** `Cancel my team sync tomorrow`

**Agent response:**
> I have successfully canceled your team sync scheduled for tomorrow. If you need any further assistance, just let me know!

**Score reason:** PASS — 'delete_event' was called

### TC4 — Check availability ✅ PASS

**Category:** baseline  
**Scorer:** tool_called

**User message:** `Am I free tomorrow afternoon?`

**Agent response:**
> You have a "Demo Meet" scheduled tomorrow from 1:00 PM to 2:00 PM. Therefore, you are not free during that time. However, you are available before 1:00 PM and after 2:00 PM. Would you like to schedule something during those times?

**Score reason:** PASS — 'list_events' was called

### TC5 — Agent refuses to schedule before hard constraint time ✅ PASS

**Category:** memory  
**Scorer:** llm_judge

**User message:** `Schedule a meeting tomorrow at 8am`

**Agent response:**
> I cannot schedule meetings before 10am. Would you like to choose a different time?

**Score reason:** PASS: The agent correctly informs the user that it cannot schedule meetings before 10am and prompts for a different time.

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
> I have scheduled a 30-minute meeting with Alex for tomorrow at 3 PM. Here are the details:

- **Title:** Meeting with Alex
- **Start:** April 15, 2026, 3:00 PM
- **End:** April 15, 2026, 3:30 PM
- **Attendees:** Alex (alex@example.com)

Let me know if you need anything else!

**Score reason:** PASS: The agent correctly scheduled the meeting without asking the user for Alex's email address, indicating it already has the necessary contact information.

### TC8 — Agent handles ambiguous request gracefully ✅ PASS

**Category:** edge_case  
**Scorer:** llm_judge

**User message:** `Move my meeting`

**Agent response:**
> Could you please provide me with the details of the meeting you would like to move, including the current date and time, and the new date and time you have in mind?

**Score reason:** PASS: The agent response appropriately asks for clarification on the meeting details and the new date and time, aligning with the expected behavior.

### TC9 — Agent self-corrects when given a nonexistent event ID ✅ PASS

**Category:** error_handling  
**Scorer:** llm_judge

**User message:** `Update event with ID 'fake-nonexistent-id-999' to start at 5pm`

**Agent response:**
> The event with ID 'fake-nonexistent-id-999' does not exist. Here are the events I found for today:

1. **Meeting Call**
   - Start: 3:30 PM
   - End: 4:00 PM
   - Attendees: utk.umang@gmail.com, aditya@gmail.com

2. **Work Updates - Utkarsh Umang <> Aditya ...

**Score reason:** PASS: The agent clearly informs the user that the event ID does not exist and provides a list of today's events to help the user identify the correct one.

### TC10 — Agent handles completely unparseable date gracefully ✅ PASS

**Category:** error_handling  
**Scorer:** llm_judge

**User message:** `Schedule a meeting on blahblah at xyztime`

**Agent response:**
> It seems like the date and time for the meeting are not specified. Could you please provide the exact date and time for the meeting?

**Score reason:** PASS: The agent correctly identifies that the date and time are not specified and asks the user for clarification.

### TC11 — Agent checks freebusy before scheduling with another user ✅ PASS

**Category:** multi_user  
**Scorer:** tool_called

**User message:** `Schedule a 1 hour meeting with Kumar Utkarsh at utkarsh.utk123@gmail.com tomorrow at 3pm`

**Agent response:**
> I have scheduled a 1-hour meeting with Kumar Utkarsh for tomorrow at 3 PM. The details are as follows:

- **Title:** Meeting with Kumar Utkarsh
- **Start:** April 15, 2026, 3:00 PM
- **End:** April 15, 2026, 4:00 PM
- **Attendees:** Kumar Utkarsh (utkarsh.utk123@gmail.com)

If you need anything else...

**Score reason:** PASS — 'check_freebusy' was called


---

## Failure Analysis

All test cases passed.


---

## Methodology

Three scoring strategies were used:

- **tool_called** — verifies the agent invoked the correct Google Calendar API tool by inspecting Langfuse trace spans. Pass/fail is deterministic.
- **llm_judge** — uses GPT-4o-mini to evaluate whether the agent's natural language response meets the expected behavior criteria. Used for rule adherence and graceful handling cases where deterministic checks are insufficient.
- **state_check** — queries MongoDB directly after the agent runs to verify the correct data was persisted. Used for memory/preference saving tests.
