import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

import dateparser
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import settings
from app.db.mongo import db


# ── Helpers ────────────────────────────────────────────────────────────────────

async def get_calendar_service(user_id: str):
    """
    Fetch the user's stored OAuth credentials from MongoDB,
    refresh if expired, and return an authenticated Calendar API client.
    """
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        raise ValueError(f"User {user_id} not found")

    credentials = Credentials(
        token=user["access_token"],
        refresh_token=user["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=["https://www.googleapis.com/auth/calendar"],
    )

    if credentials.expired and credentials.refresh_token:
        # refresh is synchronous — run in thread to avoid blocking event loop
        await asyncio.to_thread(credentials.refresh, Request())
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {
                "access_token": credentials.token,
                "token_expiry": credentials.expiry.isoformat() if credentials.expiry else None,
            }},
        )

    # build() is synchronous — run in thread
    return await asyncio.to_thread(build, "calendar", "v3", credentials=credentials)


def parse_dt(text: str) -> Optional[datetime]:
    """Parse natural language or ISO datetime strings into timezone-aware datetime."""
    return dateparser.parse(text, settings={"RETURN_AS_TIMEZONE_AWARE": True})


def fmt_event(event: dict) -> str:
    """Format a calendar event dict into a readable string for the LLM."""
    start = event.get("start", {})
    end = event.get("end", {})
    attendees = event.get("attendees", [])
    attendee_str = ", ".join(a.get("email", "") for a in attendees) or "None"

    return (
        f"ID: {event.get('id', 'N/A')}\n"
        f"Title: {event.get('summary', 'No title')}\n"
        f"Start: {start.get('dateTime', start.get('date', 'Unknown'))}\n"
        f"End: {end.get('dateTime', end.get('date', 'Unknown'))}\n"
        f"Attendees: {attendee_str}\n"
        f"Description: {event.get('description', 'None')}"
    )


# ── Tool factory ───────────────────────────────────────────────────────────────

def build_calendar_tools(user_id: str) -> list:
    """
    Create all calendar tools as closures bound to user_id.
    This way the LLM never needs to pass user_id — it's captured automatically.
    """
    from langchain_core.tools import tool

    @tool
    async def list_events(start: str, end: str) -> str:
        """
        List calendar events between two dates.
        Args:
            start: Start date/time in natural language or ISO (e.g. 'today', 'tomorrow', '2024-01-15')
            end: End date/time in natural language or ISO (e.g. 'end of this week', '2024-01-20')
        """
        try:
            service = await get_calendar_service(user_id)

            start_dt = parse_dt(start) or datetime.now(timezone.utc)
            end_dt = parse_dt(end) or (start_dt + timedelta(days=1))

            result = await asyncio.to_thread(
                lambda: service.events().list(
                    calendarId="primary",
                    timeMin=start_dt.isoformat(),
                    timeMax=end_dt.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                ).execute()
            )

            events = result.get("items", [])
            if not events:
                return "No events found in this time range."

            return f"Found {len(events)} event(s):\n\n" + "\n---\n".join(fmt_event(e) for e in events)

        except Exception as e:
            return f"Error listing events: {str(e)}"

    @tool
    async def create_event(
        title: str,
        start: str,
        end: str,
        attendee_emails: str = "",
        description: str = "",
    ) -> str:
        """
        Create a new calendar event.
        Args:
            title: Event title
            start: Start date/time (e.g. 'tomorrow at 3pm')
            end: End date/time (e.g. 'tomorrow at 4pm')
            attendee_emails: Comma-separated attendee emails (optional)
            description: Event description (optional)
        """
        try:
            service = await get_calendar_service(user_id)

            start_dt = parse_dt(start)
            end_dt = parse_dt(end)

            if not start_dt or not end_dt:
                return "Could not parse the dates provided. Please be more specific."

            body: dict = {
                "summary": title,
                "description": description,
                "start": {"dateTime": start_dt.isoformat()},
                "end": {"dateTime": end_dt.isoformat()},
            }

            if attendee_emails:
                emails = [e.strip() for e in attendee_emails.split(",") if e.strip()]
                body["attendees"] = [{"email": email} for email in emails]

            created = await asyncio.to_thread(
                lambda: service.events().insert(
                    calendarId="primary",
                    body=body,
                    sendUpdates="all",
                ).execute()
            )

            return f"Event created successfully!\n{fmt_event(created)}"

        except Exception as e:
            return f"Error creating event: {str(e)}"

    @tool
    async def update_event(
        event_id: str,
        title: str = "",
        start: str = "",
        end: str = "",
        description: str = "",
    ) -> str:
        """
        Update an existing calendar event. Only provide the fields you want to change.
        Args:
            event_id: Event ID from list_events
            title: New title (optional)
            start: New start time (optional)
            end: New end time (optional)
            description: New description (optional)
        """
        try:
            service = await get_calendar_service(user_id)

            event = await asyncio.to_thread(
                lambda: service.events().get(calendarId="primary", eventId=event_id).execute()
            )

            if title:
                event["summary"] = title
            if description:
                event["description"] = description
            if start:
                start_dt = parse_dt(start)
                if start_dt:
                    event["start"] = {"dateTime": start_dt.isoformat()}
            if end:
                end_dt = parse_dt(end)
                if end_dt:
                    event["end"] = {"dateTime": end_dt.isoformat()}

            updated = await asyncio.to_thread(
                lambda: service.events().update(
                    calendarId="primary",
                    eventId=event_id,
                    body=event,
                ).execute()
            )

            return f"Event updated successfully!\n{fmt_event(updated)}"

        except Exception as e:
            return f"Error updating event: {str(e)}"

    @tool
    async def delete_event(event_id: str) -> str:
        """
        Delete a calendar event permanently.
        Args:
            event_id: Event ID from list_events
        """
        try:
            service = await get_calendar_service(user_id)

            await asyncio.to_thread(
                lambda: service.events().delete(calendarId="primary", eventId=event_id).execute()
            )

            return f"Event {event_id} deleted successfully."

        except Exception as e:
            return f"Error deleting event: {str(e)}"

    @tool
    async def check_freebusy(emails: str, start: str, end: str) -> str:
        """
        Check free/busy availability for one or more people.
        Only returns busy/free — never exposes event details.
        Args:
            emails: Comma-separated email addresses
            start: Start of time window to check
            end: End of time window to check
        """
        try:
            service = await get_calendar_service(user_id)

            start_dt = parse_dt(start) or datetime.now(timezone.utc)
            end_dt = parse_dt(end) or (start_dt + timedelta(hours=2))

            email_list = [e.strip() for e in emails.split(",") if e.strip()]

            result = await asyncio.to_thread(
                lambda: service.freebusy().query(body={
                    "timeMin": start_dt.isoformat(),
                    "timeMax": end_dt.isoformat(),
                    "items": [{"id": email} for email in email_list],
                }).execute()
            )

            output = []
            for email, data in result.get("calendars", {}).items():
                busy = data.get("busy", [])
                if busy:
                    slots = ", ".join(f"{s['start']} → {s['end']}" for s in busy)
                    output.append(f"{email}: BUSY during {slots}")
                else:
                    output.append(f"{email}: FREE during this period")

            return "\n".join(output) or "No availability data found."

        except Exception as e:
            return f"Error checking availability: {str(e)}"

    return [list_events, create_event, update_event, delete_event, check_freebusy]