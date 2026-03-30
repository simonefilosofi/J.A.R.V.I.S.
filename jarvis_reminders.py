#!/usr/bin/env python3
"""
JARVIS Reminders & Timer Tool
- add_reminder  → Reminders.app via AppleScript
- set_timer     → countdown timer, fires voice + macOS notification
- set_alarm     → alarm at a specific time, fires voice + macOS notification
"""

import json
import subprocess
import threading
import time
from datetime import datetime, timedelta

VOICE       = "Daniel"
VOICE_RATE  = 165

# ── Tool definitions for Groq function calling ────────────────
TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "add_reminder",
            "description": (
                "Add a reminder to macOS Reminders.app. Use this when the user asks to "
                "remember something, set a reminder, or add a to-do item, optionally with a due date/time."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Reminder title"
                    },
                    "due_date": {
                        "type": "string",
                        "description": "Due date in YYYY-MM-DD format (optional)"
                    },
                    "due_time": {
                        "type": "string",
                        "description": "Due time in HH:MM 24-hour format (optional, requires due_date)"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional notes"
                    },
                    "list_name": {
                        "type": "string",
                        "description": "Name of the Reminders list. Defaults to the first available list."
                    }
                },
                "required": ["title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_timer",
            "description": (
                "Start a countdown timer. JARVIS will alert you with a voice notification and "
                "a macOS notification banner when the timer expires. Use this when the user says "
                "'remind me in X minutes', 'set a timer for X minutes', etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "minutes": {
                        "type": "number",
                        "description": "Duration in minutes (decimals allowed, e.g. 1.5 = 90 seconds)"
                    },
                    "label": {
                        "type": "string",
                        "description": "Optional label describing what the timer is for"
                    }
                },
                "required": ["minutes"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_alarm",
            "description": (
                "Set an alarm for a specific time of day. JARVIS will alert you vocally and with "
                "a notification at that time. If the time has already passed today, sets it for tomorrow."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "hour": {
                        "type": "integer",
                        "description": "Hour in 24-hour format (0-23)"
                    },
                    "minute": {
                        "type": "integer",
                        "description": "Minute (0-59)"
                    },
                    "label": {
                        "type": "string",
                        "description": "Optional label for the alarm"
                    }
                },
                "required": ["hour", "minute"]
            }
        }
    }
]


# ── Helpers ───────────────────────────────────────────────────

def _notify(title: str, message: str, subtitle: str = "J.A.R.V.I.S."):
    """Fire a macOS notification banner."""
    script = (
        f'display notification "{message}" '
        f'with title "{title}" subtitle "{subtitle}"'
    )
    subprocess.run(["osascript", "-e", script], capture_output=True)


def _speak(text: str):
    """Speak text via macOS TTS (non-blocking)."""
    subprocess.Popen(["say", "-v", VOICE, "-r", str(VOICE_RATE), text])


def _date_block(var: str, dt: datetime) -> str:
    """Locale-independent AppleScript date block (day set to 1 first to avoid rollover)."""
    return (
        f"set {var} to current date\n"
        f"        set day of {var} to 1\n"
        f"        set year of {var} to {dt.year}\n"
        f"        set month of {var} to {dt.month}\n"
        f"        set day of {var} to {dt.day}\n"
        f"        set hours of {var} to {dt.hour}\n"
        f"        set minutes of {var} to {dt.minute}\n"
        f"        set seconds of {var} to 0"
    )


# ── Tool implementations ──────────────────────────────────────

def add_reminder(title: str, due_date: str = None, due_time: str = None,
                 notes: str = "", list_name: str = None) -> dict:
    safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
    safe_notes = notes.replace("\\", "\\\\").replace('"', '\\"') if notes else ""

    if list_name:
        safe_list = list_name.replace("\\", "\\\\").replace('"', '\\"')
        list_selector = f'list "{safe_list}"'
    else:
        list_selector = "first list"

    due_block = ""
    friendly_due = ""
    if due_date:
        try:
            if due_time:
                dt = datetime.strptime(f"{due_date} {due_time}", "%Y-%m-%d %H:%M")
            else:
                dt = datetime.strptime(due_date, "%Y-%m-%d").replace(hour=9, minute=0)
            due_block = f"\n        {_date_block('dueDate', dt)}\n        set due date of newRem to dueDate"
            friendly_due = f" due {dt.strftime('%d %B %Y')} at {dt.strftime('%H:%M')}"
        except ValueError as e:
            return {"ok": False, "error": f"Invalid date/time: {e}"}

    notes_block = f'\n        set body of newRem to "{safe_notes}"' if safe_notes else ""

    script = f"""
tell application "Reminders"
    set targetList to {list_selector}
    tell targetList
        set newRem to make new reminder with properties {{name:"{safe_title}"}}
        {due_block}
        {notes_block}
        return name of newRem
    end tell
end tell
"""
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        used_list = list_name or "Promemoria"
        return {"ok": True, "message": f"Reminder '{title}' added{friendly_due} in '{used_list}'."}
    else:
        err = result.stderr.strip() or result.stdout.strip() or "Unknown error"
        return {"ok": False, "error": err}


def set_timer(minutes: float, label: str = "") -> dict:
    seconds = float(minutes) * 60
    if seconds <= 0:
        return {"ok": False, "error": "Duration must be positive."}

    display_label = label if label else f"{minutes}-minute timer"

    def _fire():
        time.sleep(seconds)
        msg = f"Timer complete. {label}" if label else f"Your {minutes}-minute timer is up."
        _notify("⏱ JARVIS Timer", display_label, "Time's up!")
        _speak(msg)

    threading.Thread(target=_fire, daemon=True).start()

    # Human-friendly duration string
    total_s = int(seconds)
    if total_s >= 3600:
        h, rem = divmod(total_s, 3600)
        m = rem // 60
        duration = f"{h}h {m}m" if m else f"{h}h"
    elif total_s >= 60:
        m, s = divmod(total_s, 60)
        duration = f"{m}m {s}s" if s else f"{m}m"
    else:
        duration = f"{total_s}s"

    msg = f"Timer set for {duration}"
    if label:
        msg += f" — {label}"
    msg += ". I'll alert you when it expires."
    return {"ok": True, "message": msg}


def set_alarm(hour: int, minute: int, label: str = "") -> dict:
    now = datetime.now()
    alarm_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if alarm_dt <= now:
        alarm_dt += timedelta(days=1)

    delay = (alarm_dt - datetime.now()).total_seconds()
    time_str = alarm_dt.strftime("%H:%M")
    display_label = label if label else f"Alarm at {time_str}"
    tomorrow = alarm_dt.date() != now.date()

    def _fire():
        time.sleep(delay)
        msg = f"Alarm. {label}" if label else f"It's {time_str}, Mr. Filosofi."
        _notify("⏰ JARVIS Alarm", display_label, f"It's {time_str}")
        _speak(msg)

    threading.Thread(target=_fire, daemon=True).start()

    suffix = " tomorrow" if tomorrow else ""
    msg = f"Alarm set for {time_str}{suffix}"
    if label:
        msg += f" — {label}"
    msg += "."
    return {"ok": True, "message": msg}


# ── Dispatcher ────────────────────────────────────────────────

def dispatch_tool_call(tool_name: str, arguments) -> str:
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except Exception:
            return "Error: could not parse tool arguments."

    if tool_name == "add_reminder":
        result = add_reminder(
            title=arguments.get("title", ""),
            due_date=arguments.get("due_date"),
            due_time=arguments.get("due_time"),
            notes=arguments.get("notes", ""),
            list_name=arguments.get("list_name"),
        )
    elif tool_name == "set_timer":
        result = set_timer(
            minutes=arguments.get("minutes", 1),
            label=arguments.get("label", ""),
        )
    elif tool_name == "set_alarm":
        result = set_alarm(
            hour=int(arguments.get("hour", 0)),
            minute=int(arguments.get("minute", 0)),
            label=arguments.get("label", ""),
        )
    else:
        return f"Unknown tool: {tool_name}"

    return result["message"] if result["ok"] else f"Error: {result['error']}"
