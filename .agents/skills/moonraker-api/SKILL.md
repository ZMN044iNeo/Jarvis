# Moonraker API Skill

This skill integrates Superagent with **Moonraker**, the web API server for **Klipper 3D printers**. It provides a lightweight, zero-dependency Python client (`moonraker_api.py`) and command-line interface to monitor, control, and automate 3D printers connected via Moonraker.

---

## 📌 Features & Capabilities

- **Printer Monitoring**: Real-time status, extruder/bed temperatures, head position, and print progress.
- **Print Job Control**: Start, pause, resume, cancel, and emergency stop (`M112`).
- **Gcode Execution**: Send custom Gcode scripts directly to Klipper.
- **File Management**: List Gcode files, upload new `.gcode` models, download files, and automatically trigger prints upon upload.
- **Hardware & Peripherals**: Manage smart power switches/relays and list live webcam streams.
- **History & System Info**: Fetch print job history, system notifications, temperature presets, and Klipper/Moonraker server info.
- **Robust Error Handling**: Gracefully handles network timeouts, connection refused errors, and HTTP auth failures.

---

## ⚙️ Configuration & Environment Variables

The skill reads configuration from environment variables, which can also be overridden via command-line arguments:

| Variable | Required | Default | Description |
| :--- | :---: | :--- | :--- |
| `MOONRAKER_URL` | No | `http://localhost:7125` | Base URL of Moonraker API (e.g., `http://192.168.1.100:7125`) |
| `MOONRAKER_API_KEY` | No | *None* | Optional API Key if Moonraker authentication is enabled (`X-Api-Key` header) |

---

## 🛠️ Command-Line Usage

The skill can be executed directly from the terminal or sub-agent execution tools:

```bash
python3 .agents/skills/moonraker-api/moonraker_api.py [OPTIONS]
```

### CLI Arguments

| Argument | Description | Example |
| :--- | :--- | :--- |
| `--status` | Get full printer status (temps, position, progress, state) | `python3 moonraker_api.py --status` |
| `--info` | Get combined Moonraker server and printer info | `python3 moonraker_api.py --info` |
| `--send <gcode>` | Send Gcode command to printer | `python3 moonraker_api.py --send "G28"` |
| `--start <filename>` | Start printing a Gcode file | `python3 moonraker_api.py --start "bench3d.gcode"` |
| `--pause` | Pause current print job | `python3 moonraker_api.py --pause` |
| `--resume` | Resume paused print job | `python3 moonraker_api.py --resume` |
| `--cancel` | Cancel current print job | `python3 moonraker_api.py --cancel` |
| `--estop` | Trigger Emergency Stop (`M112`) | `python3 moonraker_api.py --estop` |
| `--files` | List Gcode files on server | `python3 moonraker_api.py --files` |
| `--upload <path>` | Upload a local `.gcode` file | `python3 moonraker_api.py --upload "./part.gcode"` |
| `--download <name>` | Download file from server | `python3 moonraker_api.py --download "part.gcode" --output "./part.gcode"` |
| `--webcams` | List configured webcam streams | `python3 moonraker_api.py --webcams` |
| `--power [dev act]` | List or control smart power devices | `python3 moonraker_api.py --power printer_switch on` |
| `--jobs` | Fetch print job history | `python3 moonraker_api.py --jobs` |
| `--notifications` | Fetch Moonraker announcements/notifications | `python3 moonraker_api.py --notifications` |
| `--presets` | Fetch pre-configured temperature presets | `python3 moonraker_api.py --presets` |
| `--url <url>` | Override `MOONRAKER_URL` | `python3 moonraker_api.py --url http://192.168.1.50:7125 --status` |
| `--api-key <key>` | Override `MOONRAKER_API_KEY` | `python3 moonraker_api.py --api-key "secret" --status` |
| `--timeout <sec>` | Set HTTP timeout in seconds (default: 10) | `python3 moonraker_api.py --timeout 5.0 --status` |

---

## 🐍 Python API Usage

The client module can be imported and used directly in Python scripts:

```python
from .agents.skills.moonraker_api.moonraker_api import MoonrakerAPI, MoonrakerError

# Initialize client
client = MoonrakerAPI(url="http://192.168.1.100:7125", api_key="OPTIONAL_KEY", timeout=10.0)

try:
    # Get consolidated status
    status = client.get_status()
    print(f"Printer State: {status['state']}")
    print(f"Extruder Temp: {status['temperatures']['extruder']['actual']}°C")

    # Send home command
    client.send_gcode("G28")

    # Start print
    client.start_print("voron_cube.gcode")

except MoonrakerError as err:
    print(f"Moonraker Error [{err.error_type}]: {err.message}")
```

### Supported API Endpoints Summary

| Feature | Method | Moonraker Endpoint | Python Method |
| :--- | :---: | :--- | :--- |
| Printer Info | `GET` | `/printer/info` | `client.get_printer_info()` |
| Objects Query | `GET` | `/printer/objects/query?heater_bed&extruder` | `client.query_printer_objects(...)` |
| Send Gcode | `POST` | `/printer/gcode/script` | `client.send_gcode(script)` |
| Job Stats | `GET` | `/printer/objects/query?print_stats` | `client.get_print_stats()` |
| Start Print | `POST` | `/printer/print/start?filename=<name>` | `client.start_print(filename)` |
| Pause Print | `POST` | `/printer/print/pause` | `client.pause_print()` |
| Resume Print | `POST` | `/printer/print/resume` | `client.resume_print()` |
| Cancel Print | `POST` | `/printer/print/cancel` | `client.cancel_print()` |
| Emergency Stop | `POST` | `/printer/emergency_stop` | `client.emergency_stop()` |
| File List | `GET` | `/server/files/list?root=gcodes` | `client.list_files(root)` |
| File Upload | `POST` | `/server/files/upload` | `client.upload_file(filepath)` |
| File Download | `GET` | `/server/files/gcodes/<filename>` | `client.download_file(filename)` |
| Server Info | `GET` | `/server/info` | `client.get_server_info()` |
| Webcams List | `GET` | `/server/webcams/list` | `client.list_webcams()` |
| Power Devices | `GET/POST`| `/machine/device_power/devices`, `/device` | `client.get_power_devices()`, `client.set_power_device(...)` |
| History / Jobs | `GET` | `/server/history/list` | `client.get_history()` |
| Notifications | `GET` | `/server/notifications` | `client.get_notifications()` |
| Temp Presets | `GET` | `/server/temperature_presets` | `client.get_temperature_presets()` |

---

## 📄 Response Formats

### Success Response Example (`--status`)

```json
{
  "success": true,
  "data": {
    "state": "ready",
    "state_message": "Printer is ready",
    "hostname": "voron-24",
    "temperatures": {
      "extruder": {
        "actual": 210.0,
        "target": 210.0,
        "power": 0.45
      },
      "heater_bed": {
        "actual": 60.0,
        "target": 60.0,
        "power": 0.30
      }
    },
    "position": {
      "x": 150.0,
      "y": 150.0,
      "z": 10.5,
      "e": 12.4
    },
    "print_progress": {
      "filename": "voron_bench.gcode",
      "state": "printing",
      "progress": 0.65,
      "print_duration": 1800.0,
      "total_duration": 1850.0,
      "filament_used": 2450.0,
      "message": ""
    }
  }
}
```

### Error Response Example (Connection Refused)

```json
{
  "success": false,
  "error": {
    "type": "ConnectionError",
    "message": "Failed to connect to Moonraker at http://192.168.1.100:7125: [Errno 111] Connection refused",
    "details": {
      "url": "http://192.168.1.100:7125/printer/info",
      "method": "GET",
      "reason": "[Errno 111] Connection refused"
    }
  }
}
```

---

## 💡 Assistant Integration Examples

### Prompt: *"Check how much time is left on my 3D print"*
1. Run `python3 .agents/skills/moonraker-api/moonraker_api.py --status`
2. Parse `print_progress.progress` and `print_duration` to calculate remaining time and format a clear status update.

### Prompt: *"Preheat my extruder to 200°C and bed to 60°C"*
1. Run `python3 .agents/skills/moonraker-api/moonraker_api.py --send "M104 S200\nM140 S60"`

### Prompt: *"Turn on the printer power plug and start printing calibration_cube.gcode"*
1. Run `python3 .agents/skills/moonraker-api/moonraker_api.py --power printer_plug on`
2. Run `python3 .agents/skills/moonraker-api/moonraker_api.py --start "calibration_cube.gcode"`
