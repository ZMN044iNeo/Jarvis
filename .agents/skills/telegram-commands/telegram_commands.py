#!/usr/bin/env python3
"""
Telegram Command Parser for 3D Printing Assistant (Kestrel)

Parses incoming Telegram messages (slash commands or natural language)
and routes them to the appropriate Moonraker API action or analysis skill.

Usage:
    python3 telegram_commands.py "message text"
    echo "message text" | python3 telegram_commands.py

Output: JSON object with parsed command, action, and parameters.
"""

import sys
import json
import re
import argparse
from typing import Dict, Any, Optional

COMMANDS = {
    "status": {
        "aliases": ["/status", "status", "printer status", "how's the print", "how is the print", "printer state"],
        "action": "status", "description": "Get full printer status"
    },
    "info": {
        "aliases": ["/info", "server info", "moonraker info"],
        "action": "info", "description": "Get Moonraker server + printer info"
    },
    "temps": {
        "aliases": ["/temp", "/temps", "temperature", "temperatures", "what temp", "hotend temp", "bed temp"],
        "action": "status", "description": "Get current temperatures", "filter": "temperatures"
    },
    "progress": {
        "aliases": ["/progress", "how far", "how much left", "how much time", "eta", "when will it finish", "how long"],
        "action": "status", "description": "Get print progress + ETA", "filter": "print_progress"
    },
    "webcams": {
        "aliases": ["/webcams", "cameras", "webcam", "cam stream"],
        "action": "webcams", "description": "List available webcam streams"
    },
    "jobs": {
        "aliases": ["/jobs", "history", "print history", "job history"],
        "action": "jobs", "description": "Get recent print job history"
    },
    "files": {
        "aliases": ["/files", "list files", "gcodes", "gcode files", "what files"],
        "action": "files", "description": "List Gcode files on printer"
    },
    "start": {
        "aliases": ["/start", "start print", "print ", "begin print"],
        "action": "start", "description": "Start printing a Gcode file",
        "requires_param": True, "param_name": "filename"
    },
    "pause": {
        "aliases": ["/pause", "pause print", "pause", "hold", "hold print"],
        "action": "pause", "description": "Pause current print"
    },
    "resume": {
        "aliases": ["/resume", "resume print", "continue print", "resume"],
        "action": "resume", "description": "Resume paused print"
    },
    "cancel": {
        "aliases": ["/cancel", "cancel print", "abort print", "stop print", "cancel"],
        "action": "cancel", "description": "Cancel current print"
    },
    "estop": {
        "aliases": ["/estop", "emergency stop", "kill", "stop everything", "e stop", "estop"],
        "action": "estop", "description": "Emergency stop"
    },
    "home": {
        "aliases": ["/home", "home all", "g28"],
        "action": "send_gcode", "description": "Home all axes", "gcode": "G28"
    },
    "home_x": {
        "aliases": ["/home x", "home x axis", "home x"],
        "action": "send_gcode", "description": "Home X axis", "gcode": "G28 X"
    },
    "home_y": {
        "aliases": ["/home y", "home y axis", "home y"],
        "action": "send_gcode", "description": "Home Y axis", "gcode": "G28 Y"
    },
    "home_z": {
        "aliases": ["/home z", "home z axis", "home z"],
        "action": "send_gcode", "description": "Home Z axis", "gcode": "G28 Z"
    },
    "firmware_restart": {
        "aliases": ["/restart", "firmware restart", "restart firmware"],
        "action": "send_gcode", "description": "Restart Klipper firmware", "gcode": "FIRMWARE_RESTART"
    },
    "heat": {
        "aliases": ["/heat", "preheat", "set hotend", "set extruder", "heat hotend", "heat extruder"],
        "action": "send_gcode", "description": "Set extruder temperature",
        "requires_param": True, "param_name": "temperature", "gcode_template": "M104 S{param}"
    },
    "bed": {
        "aliases": ["/bed", "heat bed", "set bed", "bed temp"],
        "action": "send_gcode", "description": "Set bed temperature",
        "requires_param": True, "param_name": "temperature", "gcode_template": "M140 S{param}"
    },
    "cool": {
        "aliases": ["/cool", "cooldown", "cool down", "turn off heaters"],
        "action": "send_gcode", "description": "Turn off all heaters", "gcode": "M104 S0\nM140 S0"
    },
    "preheat_pla": {
        "aliases": ["/preheat pla", "preheat for pla", "preheat pla"],
        "action": "send_gcode", "description": "Preheat for PLA (200/60)", "gcode": "M104 S200\nM140 S60"
    },
    "preheat_petg": {
        "aliases": ["/preheat petg", "preheat for petg", "preheat petg"],
        "action": "send_gcode", "description": "Preheat for PETG (240/80)", "gcode": "M104 S240\nM140 S80"
    },
    "preheat_abs": {
        "aliases": ["/preheat abs", "preheat for abs", "preheat abs"],
        "action": "send_gcode", "description": "Preheat for ABS (250/100)", "gcode": "M104 S250\nM140 S100"
    },
    "gcode": {
        "aliases": ["/gcode", "send gcode", "send command", "run gcode"],
        "action": "send_gcode", "description": "Send raw Gcode to printer",
        "requires_param": True, "param_name": "gcode", "passthrough": True
    },
    "analyze": {
        "aliases": ["/analyze", "check gcode", "analyze gcode", "check file"],
        "action": "analyze_gcode", "description": "Analyze a Gcode file for issues",
        "requires_param": True, "param_name": "filepath"
    },
    "slicer": {
        "aliases": ["/slicer", "settings for", "slicer settings", "recommend settings"],
        "action": "slicer_guide", "description": "Get Elegoo Slicer settings for material",
        "requires_param": True, "param_name": "material"
    },
    "troubleshoot": {
        "aliases": ["/troubleshoot", "diagnose", "fix", "why is", "why does", "help with"],
        "action": "troubleshoot", "description": "Diagnose a print problem",
        "requires_param": True, "param_name": "issue"
    },
    "power": {
        "aliases": ["/power", "power devices", "power switch"],
        "action": "power", "description": "Control smart power devices"
    },
    "help": {
        "aliases": ["/help", "help", "commands", "what can you do"],
        "action": "help", "description": "Show available commands"
    },
}

PREHEAT_PRESETS = {
    "pla": {"hotend": 200, "bed": 60},
    "petg": {"hotend": 240, "bed": 80},
    "abs": {"hotend": 250, "bed": 100},
    "asa": {"hotend": 250, "bed": 100},
    "tpu": {"hotend": 220, "bed": 50},
    "pc": {"hotend": 275, "bed": 110},
    "nylon": {"hotend": 260, "bed": 90},
}

def parse_message(text: str) -> Dict[str, Any]:
    text = text.strip()
    text_lower = text.lower()

    for cmd_name, cmd_def in COMMANDS.items():
        for alias in cmd_def["aliases"]:
            if text_lower == alias.lower():
                return _build_command(cmd_name, cmd_def, text)

    for cmd_name, cmd_def in COMMANDS.items():
        for alias in sorted(cmd_def["aliases"], key=len, reverse=True):
            if text_lower.startswith(alias.lower()):
                param_text = text[len(alias):].strip()
                return _build_command(cmd_name, cmd_def, text, param_text)

    result = _parse_natural_language(text)
    if result:
        return result

    return {"action": "unknown", "original_message": text, "suggestion": "Type /help to see available commands"}


def _build_command(cmd_name: str, cmd_def: Dict, original: str, param_text: str = "") -> Dict[str, Any]:
    result = {
        "command": cmd_name,
        "action": cmd_def["action"],
        "description": cmd_def["description"],
        "original_message": original,
    }

    if cmd_def.get("gcode"):
        result["gcode"] = cmd_def["gcode"]
    elif cmd_def.get("gcode_template"):
        temp_match = re.search(r'(\d+)', param_text)
        if temp_match:
            result["gcode"] = cmd_def["gcode_template"].format(param=temp_match.group(1))
        else:
            result["error"] = f"Missing temperature parameter for {cmd_name}"
    elif cmd_def.get("passthrough"):
        result["gcode"] = param_text
    elif cmd_def.get("requires_param"):
        if param_text:
            result[cmd_def["param_name"]] = param_text
        else:
            result["error"] = f"Missing parameter: {cmd_def['param_name']}"
    elif cmd_def.get("filter"):
        result["filter"] = cmd_def["filter"]

    return result


def _parse_natural_language(text: str) -> Optional[Dict[str, Any]]:
    text_lower = text.lower()

    if any(w in text_lower for w in ["stop everything", "kill it", "kill the print", "shut it down"]):
        return {"command": "estop", "action": "estop", "original_message": text}
    if any(w in text_lower for w in ["pause the print", "pause it", "hold on", "hold the print"]):
        return {"command": "pause", "action": "pause", "original_message": text}
    if any(w in text_lower for w in ["resume the print", "continue the print", "keep going", "resume it"]):
        return {"command": "resume", "action": "resume", "original_message": text}
    if any(w in text_lower for w in ["cancel the print", "cancel it", "abort the print"]):
        return {"command": "cancel", "action": "cancel", "original_message": text}
    if any(w in text_lower for w in ["what temp", "what's the temp", "whats the temp", "temperature"]):
        return {"command": "temps", "action": "status", "filter": "temperatures", "original_message": text}
    if any(w in text_lower for w in ["how far", "how much left", "how much time", "when will", "what time", "how long", "eta"]):
        return {"command": "progress", "action": "status", "filter": "print_progress", "original_message": text}

    for material, temps in PREHEAT_PRESETS.items():
        if f"preheat for {material}" in text_lower or f"preheat {material}" in text_lower:
            return {"command": f"preheat_{material}", "action": "send_gcode",
                    "gcode": f"M104 S{temps['hotend']}\nM140 S{temps['bed']}", "original_message": text}

    heat_match = re.search(r'(?:set|heat).*(?:hotend|extruder|nozzle).*(?:to\s*)?(\d+)', text_lower)
    if heat_match:
        return {"command": "heat", "action": "send_gcode", "gcode": f"M104 S{heat_match.group(1)}", "original_message": text}
    bed_match = re.search(r'(?:set|heat).*(?:bed).*(?:to\s*)?(\d+)', text_lower)
    if bed_match:
        return {"command": "bed", "action": "send_gcode", "gcode": f"M140 S{bed_match.group(1)}", "original_message": text}

    if any(w in text_lower for w in ["cool down", "cooldown", "turn off heaters", "turn off heat"]):
        return {"command": "cool", "action": "send_gcode", "gcode": "M104 S0\nM140 S0", "original_message": text}

    if "home" in text_lower and ("all" in text_lower or "axis" not in text_lower):
        return {"command": "home", "action": "send_gcode", "gcode": "G28", "original_message": text}
    if "home x" in text_lower:
        return {"command": "home_x", "action": "send_gcode", "gcode": "G28 X", "original_message": text}
    if "home y" in text_lower:
        return {"command": "home_y", "action": "send_gcode", "gcode": "G28 Y", "original_message": text}
    if "home z" in text_lower:
        return {"command": "home_z", "action": "send_gcode", "gcode": "G28 Z", "original_message": text}

    start_match = re.search(r'(?:start|print|begin).*(?:print(?:ing)?)?\s+(.+\.gcode)', text_lower)
    if start_match:
        return {"command": "start", "action": "start", "filename": start_match.group(1), "original_message": text}

    issue_keywords = [
        "stringing", "warping", "layer shift", "under extrusion", "over extrusion",
        "clog", "clogging", "heat creep", "ghosting", "ringing", "z seam",
        "elephant foot", "pillowing", "blobbing", "zits", "filament grinding",
        "poor adhesion", "not sticking", "lifting", "pitting", "warp"
    ]
    for keyword in issue_keywords:
        if keyword in text_lower and any(q in text_lower for q in ["why", "fix", "help", "how"]):
            return {"command": "troubleshoot", "action": "troubleshoot", "issue": keyword, "original_message": text}

    material_keywords = ["pla", "petg", "abs", "asa", "tpu", "pc", "nylon", "pva", "hips"]
    if "settings" in text_lower and any(m in text_lower for m in material_keywords):
        for m in material_keywords:
            if m in text_lower:
                return {"command": "slicer", "action": "slicer_guide", "material": m.upper(), "original_message": text}

    return None


def format_help() -> str:
    lines = [
        "🦅 Kestrel — 3D Printing Assistant",
        "",
        "Status & Monitoring:",
        "  /status     — Full printer status",
        "  /temp       — Current temperatures",
        "  /progress   — Print progress + ETA",
        "  /files      — List Gcode files",
        "  /jobs       — Print history",
        "  /webcams    — List cameras",
        "",
        "Print Control:",
        "  /start <f>  — Start print",
        "  /pause      — Pause print",
        "  /resume     — Resume print",
        "  /cancel     — Cancel print",
        "  /estop      — Emergency stop",
        "  /home       — Home all axes",
        "  /restart    — Firmware restart",
        "",
        "Temperature:",
        "  /heat <t>   — Set hotend temp",
        "  /bed <t>    — Set bed temp",
        "  /cool       — Turn off heaters",
        "  /preheat pla|petg|abs — Material presets",
        "",
        "Gcode & Analysis:",
        "  /gcode <c>  — Send raw Gcode",
        "  /analyze <f>— Analyze Gcode",
        "  /slicer <m> — Slicer settings",
        "  /troubleshoot <issue> — Diagnose problem",
        "",
        "Power:",
        "  /power              — List devices",
        "  /power <dev> on|off — Toggle device",
        "",
        "Natural language also works! Try: 'What's my printer status?' or 'Pause the print'",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Parse Telegram messages for 3D printer commands")
    parser.add_argument("message", nargs="?", help="Message text to parse")
    parser.add_argument("--help-text", action="store_true", help="Print formatted help text")
    args = parser.parse_args()

    if args.help_text:
        print(format_help())
        return

    if args.message:
        text = args.message
    else:
        text = sys.stdin.read().strip()

    if not text:
        print(json.dumps({"error": "No message provided"}))
        return

    result = parse_message(text)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
