# Telegram Printer Commands — 3D Printing Assistant

This skill defines the command vocabulary for controlling your 3D printer via Telegram. When a Telegram message is received, Kestrel parses it and routes it to the appropriate Moonraker API action or analysis skill.

## Command Reference

### Status & Monitoring
| Command | Aliases | Action |
|---------|---------|--------|
| `/status` | `status`, `printer status`, `how's the print` | Get full printer status (temps, progress, position) |
| `/info` | `info`, `server info` | Get Moonraker server + printer info |
| `/temp` | `temps`, `temperature` | Get current temperatures |
| `/progress` | `how far`, `how much left` | Get print progress + ETA |
| `/webcams` | `cameras`, `webcam` | List available webcam streams |
| `/jobs` | `history`, `print history` | Get recent print job history |
| `/files` | `list files`, `gcodes` | List available Gcode files on printer |

### Print Control
| Command | Aliases | Action |
|---------|---------|--------|
| `/start <filename>` | `print <filename>`, `start print` | Start printing a Gcode file |
| `/pause` | `pause print`, `hold` | Pause current print |
| `/resume` | `resume print`, `continue` | Resume paused print |
| `/cancel` | `cancel print`, `abort` | Cancel current print |
| `/estop` | `emergency stop`, `kill` | Emergency stop (M112) |
| `/restart` | `firmware restart` | Send FIRMWARE_RESTART |
| `/home` | `home all`, `G28` | Home all axes (G28) |

### Temperature Control
| Command | Aliases | Action |
|---------|---------|--------|
| `/heat <temp>` | `preheat <temp>`, `set hotend <temp>` | Set extruder target temperature |
| `/bed <temp>` | `heat bed <temp>`, `set bed <temp>` | Set bed target temperature |
| `/cool` | `cooldown`, `cool down` | Turn off all heaters (M104 S0, M140 S0) |
| `/preheat pla` | `preheat for pla` | Preheat for PLA (200/60) |
| `/preheat petg` | `preheat for petg` | Preheat for PETG (240/80) |
| `/preheat abs` | `preheat for abs` | Preheat for ABS (250/100) |

### Gcode & Slicer
| Command | Aliases | Action |
|---------|---------|--------|
| `/gcode <command>` | `send <command>` | Send raw Gcode to printer |
| `/analyze <filepath>` | `check gcode` | Analyze a Gcode file for issues |
| `/slicer <material>` | `settings for <material>` | Get Elegoo Slicer settings for material |
| `/troubleshoot <issue>` | `diagnose <issue>`, `fix <issue>` | Diagnose a print problem |

### Power Management
| Command | Aliases | Action |
|---------|---------|--------|
| `/power` | `power devices` | List smart power devices |
| `/power <device> on` | `turn on <device>` | Turn on a power device |
| `/power <device> off` | `turn off <device>` | Turn off a power device |

### Help
| Command | Aliases | Action |
|---------|---------|--------|
| `/help` | `help`, `commands` | Show available commands |

## Natural Language Processing

Kestrel also understands natural language commands. Examples:
- "What's the status of my printer?" → `/status`
- "Pause the print" → `/pause`
- "How much filament have I used on this print?" → `/status` (extract filament_used)
- "Preheat to 210 for the hotend and 60 for the bed" → `/heat 210` + `/bed 60`
- "Check my Gcode file for issues" → `/analyze`
- "Why is my print stringing?" → `/troubleshoot stringing`
- "What settings should I use for PETG?" → `/slicer PETG`
- "Stop everything!" → `/estop`
- "What time will my print finish?" → `/progress` (calculate ETA)

## Response Format

Responses are formatted for Telegram:
- Short, scannable text
- Emoji indicators: 🔥 (heating), ✅ (complete), ⏸️ (paused), 🖨️ (printing), ⚠️ (warning), 🛑 (error)
- Temperature shown as `🌡️ Extruder: 210/210°C | Bed: 60/60°C`
- Progress shown as `📊 45% — ~2h 15m remaining`
- File lists shown as numbered list with sizes
- Error messages include root cause + fix steps
