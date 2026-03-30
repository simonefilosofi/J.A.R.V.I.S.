#!/usr/bin/env python3
"""
JARVIS System Control Tool
- set_volume     → volume output (0-100) + mute/unmute via AppleScript
- set_brightness → relative brightness via macOS key codes
- set_focus      → toggle Focus / Do Not Disturb via ControlCenter menu bar
"""

import json
import subprocess

TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "set_volume",
            "description": (
                "Set the system output volume or mute/unmute. "
                "Use when the user says 'volume', 'alza', 'abbassa', 'mute', 'silenzio', etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {
                        "type": "string",
                        "description": "Volume level from 0 to 100 as a number. Omit if just muting/unmuting."
                    },
                    "mute": {
                        "type": "string",
                        "description": "Pass 'true' to mute, 'false' to unmute. Omit if setting a specific level."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_brightness",
            "description": (
                "Increase or decrease screen brightness. "
                "Use when the user says 'luminosità', 'schermo più chiaro/scuro', 'brightness', etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "description": "'up' to increase brightness, 'down' to decrease brightness."
                    },
                    "steps": {
                        "type": "string",
                        "description": "Number of steps to change (1-16) as a number. Default is 4."
                    }
                },
                "required": ["direction"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_focus",
            "description": (
                "Enable or disable macOS Focus mode (Do Not Disturb). "
                "Use when the user says 'non disturbare', 'focus', 'do not disturb', "
                "'attiva/disattiva focus', 'non voglio essere disturbato', etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "enable": {
                        "type": "string",
                        "description": "Pass 'true' to enable Focus mode, 'false' to disable it."
                    }
                },
                "required": ["enable"]
            }
        }
    }
]


# ── Volume ────────────────────────────────────────────────────

def set_volume(level: int = None, mute: bool = None) -> dict:
    if mute is True:
        script = "set volume with output muted"
    elif mute is False:
        script = "set volume without output muted"
    elif level is not None:
        level = max(0, min(100, int(level)))
        script = f"set volume output volume {level}"
    else:
        return {"ok": False, "error": "Provide either a level (0-100) or mute (true/false)."}

    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        return {"ok": False, "error": result.stderr.strip()}

    if mute is True:
        return {"ok": True, "message": "Volume muted."}
    if mute is False:
        return {"ok": True, "message": "Volume unmuted."}
    return {"ok": True, "message": f"Volume set to {level}%."}


# ── Brightness ────────────────────────────────────────────────
# key code 144 = brightness up, 145 = brightness down (macOS built-in)

def set_brightness(direction: str, steps: int = 4) -> dict:
    direction = direction.strip().lower()
    if direction not in ("up", "down"):
        return {"ok": False, "error": "Direction must be 'up' or 'down'."}

    steps = max(1, min(16, int(steps)))
    key_code = 144 if direction == "up" else 145

    script = f"""
tell application "System Events"
    repeat {steps} times
        key code {key_code}
    end repeat
end tell
"""
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        return {"ok": False, "error": result.stderr.strip()}

    word = "increased" if direction == "up" else "decreased"
    return {"ok": True, "message": f"Brightness {word} by {steps} step{'s' if steps > 1 else ''}."}


# ── Focus / Do Not Disturb ────────────────────────────────────

def set_focus(enable: bool) -> dict:
    """
    Toggle Focus / Do Not Disturb via the 'JARVIS Focus On/Off' shortcuts.
    If the shortcuts are not set up, returns a setup instruction message.
    """
    shortcut_name = "JARVIS Focus On" if enable else "JARVIS Focus Off"
    result = subprocess.run(
        ["shortcuts", "run", shortcut_name],
        capture_output=True, text=True, timeout=10
    )
    if result.returncode == 0:
        state = "enabled" if enable else "disabled"
        return {"ok": True, "message": f"Focus mode {state}."}
    err = result.stderr.strip()
    if "Couldn't find shortcut" in err or "not found" in err.lower():
        return {
            "ok": False,
            "error": (
                f"Shortcut '{shortcut_name}' not found. "
                "Open Shortcuts.app, add an action 'Set Focus Mode' "
                f"(On={enable}), and name it '{shortcut_name}'."
            )
        }
    return {"ok": False, "error": err or "Unknown error running shortcut."}


# ── Dispatcher ────────────────────────────────────────────────

def dispatch_tool_call(tool_name: str, arguments) -> str:
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except Exception:
            return "Error: could not parse tool arguments."

    if tool_name == "set_volume":
        raw_level = arguments.get("level")
        level = int(float(raw_level)) if raw_level is not None else None
        raw_mute = arguments.get("mute")
        mute = None if raw_mute is None else str(raw_mute).lower() not in ("false", "0", "no")
        result = set_volume(level=level, mute=mute)
    elif tool_name == "set_brightness":
        result = set_brightness(
            direction=arguments.get("direction", "up"),
            steps=int(float(arguments.get("steps", 4))),
        )
    elif tool_name == "set_focus":
        raw = arguments.get("enable", "true")
        enable = str(raw).lower() not in ("false", "0", "no", "off")
        result = set_focus(enable=enable)
    else:
        return f"Unknown tool: {tool_name}"

    return result["message"] if result["ok"] else f"Error: {result['error']}"
