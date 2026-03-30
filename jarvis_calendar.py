#!/usr/bin/env python3
"""
JARVIS Calendar Tool — adds events to macOS Calendar.app via AppleScript.
Used by both jarvis_voice.py and jarvis_hud.py through Groq function calling.
"""

import json
import subprocess
from datetime import datetime, timedelta

# ── Tool definition for Groq function calling ─────────────────
TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "add_calendar_event",
        "description": (
            "Add an event to the user's macOS Calendar app. "
            "Use this whenever the user asks to add, schedule, create, or set a reminder/event on a specific date and time."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Event title / name"
                },
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format"
                },
                "start_time": {
                    "type": "string",
                    "description": "Start time in HH:MM 24-hour format"
                },
                "end_time": {
                    "type": "string",
                    "description": "End time in HH:MM 24-hour format. If not specified, defaults to 1 hour after start."
                },
                "notes": {
                    "type": "string",
                    "description": "Optional notes or description for the event"
                },
                "calendar_name": {
                    "type": "string",
                    "description": "Name of the calendar to add the event to (e.g. 'Casa', 'Lavoro'). If not specified, uses the first available calendar."
                }
            },
            "required": ["title", "date", "start_time"]
        }
    }
}


def add_calendar_event(title: str, date: str, start_time: str,
                       end_time: str = None, notes: str = "",
                       calendar_name: str = None) -> dict:
    """
    Create an event in the first writable macOS Calendar via AppleScript.
    Returns {"ok": True, "message": "..."} or {"ok": False, "error": "..."}.
    """
    try:
        start_dt = datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M")
        end_dt = (
            datetime.strptime(f"{date} {end_time}", "%Y-%m-%d %H:%M")
            if end_time
            else start_dt + timedelta(hours=1)
        )
    except ValueError as e:
        return {"ok": False, "error": f"Invalid date/time format: {e}"}

    safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
    safe_notes = notes.replace("\\", "\\\\").replace('"', '\\"') if notes else ""

    def date_block(var: str, dt: datetime) -> str:
        """Build locale-independent AppleScript date using numeric properties.
        Day is set to 1 before changing month to prevent rollover
        (e.g. March 31 + set month to April = April 31 → May 1)."""
        return (
            f"set {var} to current date\n"
            f"    set day of {var} to 1\n"
            f"    set year of {var} to {dt.year}\n"
            f"    set month of {var} to {dt.month}\n"
            f"    set day of {var} to {dt.day}\n"
            f"    set hours of {var} to {dt.hour}\n"
            f"    set minutes of {var} to {dt.minute}\n"
            f"    set seconds of {var} to 0"
        )

    notes_prop = f', description:"{safe_notes}"' if safe_notes else ""

    if calendar_name:
        safe_cal = calendar_name.replace("\\", "\\\\").replace('"', '\\"')
        cal_selector = f'calendar "{safe_cal}"'
    else:
        cal_selector = "first calendar whose writable is true"

    script = f"""
tell application "Calendar"
    set targetCal to {cal_selector}
    set calName to name of targetCal
    {date_block("startDate", start_dt)}
    {date_block("endDate", end_dt)}
    tell targetCal
        make new event with properties {{summary:"{safe_title}", start date:startDate, end date:endDate{notes_prop}}}
    end tell
    reload calendars
    return calName
end tell
"""
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=10
    )

    if result.returncode == 0:
        friendly_date = start_dt.strftime("%d %B %Y")
        friendly_time = start_dt.strftime("%H:%M")
        used_calendar = result.stdout.strip() or calendar_name or "Calendar"
        return {
            "ok": True,
            "message": f"Event '{title}' added on {friendly_date} at {friendly_time} in the '{used_calendar}' calendar."
        }
    else:
        err = result.stderr.strip() or result.stdout.strip() or "Unknown AppleScript error"
        return {"ok": False, "error": err}


def dispatch_tool_call(tool_name: str, arguments) -> str:
    """
    Execute a tool call returned by the Groq model.
    Returns a string result to feed back to the model.
    """
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except Exception:
            return "Error: could not parse tool arguments."

    if tool_name == "add_calendar_event":
        result = add_calendar_event(
            title=arguments.get("title", ""),
            date=arguments.get("date", ""),
            start_time=arguments.get("start_time", ""),
            end_time=arguments.get("end_time"),
            notes=arguments.get("notes", ""),
            calendar_name=arguments.get("calendar_name"),
        )
        return result["message"] if result["ok"] else f"Failed to add event: {result['error']}"

    return f"Unknown tool: {tool_name}"
