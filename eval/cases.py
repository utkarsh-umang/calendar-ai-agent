"""
Test suite for the Calendar Agent.

Each test case defines:
- id: unique identifier
- description: what's being tested
- category: baseline / memory / edge_case / error_handling
- setup: dict of DB state to insert before running (None if no setup needed)
- message: the user message to send to the agent
- scorer: which scoring method to use
- expected: what the scorer checks against
"""

TEST_CASES = [
    # ── Baseline calendar operations ───────────────────────────────────────────

    {
        "id": "TC1",
        "description": "List events for a date range",
        "category": "baseline",
        "setup": None,
        "message": "What's on my calendar tomorrow?",
        "scorer": "tool_called",
        "expected": "list_events",
    },
    {
        "id": "TC2",
        "description": "Create a new event",
        "category": "baseline",
        "setup": None,
        "message": "Schedule a team sync tomorrow at 2pm for 1 hour",
        "scorer": "tool_called",
        "expected": "create_event",
    },
    {
        "id": "TC3",
        "description": "Delete an event by name",
        "category": "baseline",
        "setup": None,
        "message": "Cancel my team sync tomorrow",
        "scorer": "tool_called",
        "expected": "delete_event",
    },
    {
        "id": "TC4",
        "description": "Check availability",
        "category": "baseline",
        "setup": None,
        "message": "Am I free tomorrow afternoon?",
        "scorer": "tool_called",
        "expected": "list_events",
    },

    # ── Memory and rule adherence ──────────────────────────────────────────────

    {
        "id": "TC5",
        "description": "Agent refuses to schedule before hard constraint time",
        "category": "memory",
        "setup": {
            "profiles": {
                "constraints": [{"rule": "never schedule before 10am", "source": "explicit"}],
                "preferences": [],
            }
        },
        "message": "Schedule a meeting tomorrow at 8am",
        "scorer": "llm_judge",
        "expected": "The agent should refuse or warn that 8am violates the no-meetings-before-10am rule. It should not create the event silently.",
    },
    {
        "id": "TC6",
        "description": "Agent saves a new constraint when user states one",
        "category": "memory",
        "setup": None,
        "message": "Just so you know, I never work on Sundays",
        "scorer": "state_check",
        "expected": {
            "collection": "profiles",
            "field": "constraints",
            "contains": "sunday",
        },
    },
    {
        "id": "TC7",
        "description": "Agent resolves known contact name to email",
        "category": "memory",
        "setup": {
            "contacts": {
                "contacts": [{"name": "Alex", "email": "alex@example.com"}]
            }
        },
        "message": "Schedule a 30 minute meeting with Alex tomorrow at 3pm",
        "scorer": "llm_judge",
        "expected": "The agent should schedule the event without asking the user for Alex's email address. It should NOT prompt for contact info it already has.",
    },
    {
        "id": "TC8",
        "description": "Agent handles ambiguous request gracefully",
        "category": "edge_case",
        "setup": None,
        "message": "Move my meeting",
        "scorer": "llm_judge",
        "expected": "The agent should ask for clarification — which meeting and to when — rather than guessing or throwing an error.",
    },

    # ── Error handling ─────────────────────────────────────────────────────────

    {
        "id": "TC9",
        "description": "Agent self-corrects when given a nonexistent event ID",
        "category": "error_handling",
        "setup": None,
        "message": "Update event with ID 'fake-nonexistent-id-999' to start at 5pm",
        "scorer": "llm_judge",
        "expected": (
            "The agent should not give up silently after the error. "
            "It should clearly tell the user the event ID was not found, "
            "and either list the user's upcoming events to help them identify the right one, "
            "or ask the user to clarify which event they meant. "
            "Simply listing events without further explanation also counts as a valid recovery."
        ),
    },
    {
        "id": "TC10",
        "description": "Agent handles completely unparseable date gracefully",
        "category": "error_handling",
        "setup": None,
        "message": "Schedule a meeting on blahblah at xyztime",
        "scorer": "llm_judge",
        "expected": (
            "The agent should not crash or return a raw error string. "
            "It should tell the user the date could not be understood "
            "and ask them to provide a clearer date and time."
        ),
    },
    {
        "id": "TC11",
        "description": "Agent checks freebusy before scheduling with another user",
        "category": "multi_user",
        "setup": {
            "contacts": {
                "contacts": [{"name": "Utkarsh Kr", "email": "utkarsh.utk123@gmail.com"}]
            }
        },
        "message": "Schedule a 1 hour meeting with Kumar Utkarsh at utkarsh.utk123@gmail.com tomorrow at 3pm",
        "scorer": "tool_called",
        "expected": "check_freebusy",
    }
]