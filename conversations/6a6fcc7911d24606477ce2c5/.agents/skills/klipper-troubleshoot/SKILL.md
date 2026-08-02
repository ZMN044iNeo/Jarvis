# Klipper Troubleshooting Assistant Skill

An expert 3D printing diagnostic tool for Klipper, Klippy logs, Moonraker, Mainsail, Fluidd, and general FDM print quality issues.

## Overview

The `klipper-troubleshoot` skill analyzes error strings, raw `klippy.log` files, or JSON error payloads to diagnose Klipper firmware crashes, micro-controller communication drops, thermistor failures, stepper driver trips, probe errors, and slicing/mechanical print quality defects.

Each matched issue returns a structured JSON report including:
- **Category**: `firmware`, `mechanical`, `thermal`, `slicing`, `gcode`, `connectivity`, `configuration`
- **Severity**: `critical`, `error`, `warning`, `info`
- **Detailed Diagnosis**: In-depth explanation of the root cause
- **Step-by-Step Fixes**: Actionable resolution steps
- **Relevant Config Parameters**: Specific sections and settings in `printer.cfg` to inspect or calibrate
- **Moonraker/Fluidd/Mainsail Steps**: Web UI diagnostic macros, commands, and console checks

---

## Usage

### 1. Analyze an Error String or Issue Description
```bash
python3 .agents/skills/klipper-troubleshoot/klipper_troubleshoot.py --error "MCU 'mcu' shutdown: ADC out of range"
```

### 2. Analyze a `klippy.log` File
```bash
python3 .agents/skills/klipper-troubleshoot/klipper_troubleshoot.py --logfile /path/to/klippy.log
```

### 3. Analyze JSON Error Object via Stdin
```bash
echo '{"error": "TMC stepper_x reports error: DRV_STATUS"}' | python3 .agents/skills/klipper-troubleshoot/klipper_troubleshoot.py
```

---

## CLI Options

| Flag | Short | Description |
| --- | --- | --- |
| `--error` | `-e` | Error message string or print quality problem description. |
| `--logfile` | `-f` | Path to a `klippy.log` file to parse and analyze. |
| `--json` | | Output formatted JSON response (default behavior). |

---

## Output Structure

The skill returns a JSON object with the following schema:

```json
{
  "status": "success",
  "input_type": "error_string | logfile | json_object | text_stream",
  "analyzed_source": "error argument | /path/to/klippy.log | stdin",
  "summary": {
    "total_matches_found": 1,
    "top_category": "thermal",
    "highest_severity": "critical"
  },
  "log_context": {
    "klipper_version": "v0.11.0",
    "mcus": [{"mcu_name": "mcu", "mcu_type": "stm32f446"}],
    "extracted_errors": ["MCU 'mcu' shutdown: ADC out of range"],
    "recent_tracebacks": [],
    "last_gcode_commands": ["G28", "BED_MESH_CALIBRATE"],
    "temperature_snapshot": {
      "heater_bed": {"target": 60.0, "temp": 59.8},
      "extruder": {"target": 210.0, "temp": 209.9}
    }
  },
  "matches": [
    {
      "id": "adc_out_of_range",
      "title": "ADC Out of Range (Thermistor Open / Short Circuit)",
      "category": "thermal",
      "severity": "critical",
      "match_confidence": "exact",
      "matched_pattern": "MCU '.*' shutdown: ADC out of range",
      "diagnosis": "The micro-controller read an analog-to-digital converter (ADC) voltage outside configured limits...",
      "step_by_step_fixes": [
        "Inspect thermistor wiring at heater block...",
        "If reading shows negative value, check for broken wire (Open circuit)..."
      ],
      "relevant_config_parameters": [
        "[extruder] sensor_type",
        "[extruder] min_temp",
        "[extruder] max_temp"
      ],
      "moonraker_fluidd_steps": [
        "Observe temperature graphs in Fluidd/Mainsail interface...",
        "Test thermistor by gently wiggling printhead cables..."
      ]
    }
  ],
  "general_recommendations": [
    "Always back up printer.cfg before making major parameter modifications.",
    "When changing configuration settings, execute RESTART or FIRMWARE_RESTART in Fluidd/Mainsail."
  ]
}
```

---

## Knowledge Base Coverage

### Klipper Runtime & Firmware Errors
1. **MCU Communication Errors**:
   - `Timer too close` / `Rescheduled timer in past`
   - `Lost communication with MCU` / `Timeout`
   - `CRC error` / `Bytes read corrupted`
2. **Thermistor & Heater Errors**:
   - `ADC out of range` / `THROWN_OPEN` / `SHORT_TO_GND`
   - `Heater not heating at expected rate`
   - Thermal runaway triggers
3. **Stepper & TMC Driver Errors**:
   - Trinamic errors (`DRV_STATUS`, `GSTAT`, `SHORT_TO_GROUND`, `OVERTEMPERATURE`)
   - `Stepper too fast` / `Unable to move`
   - Step compression errors
4. **Probe & BLTouch Errors**:
   - `Probe triggered prior to movement`
   - `Failed to verify BLTouch probe state`
   - Probe samples deviance tolerance exceeded
5. **Endstop Errors**:
   - `Endstop still triggered after retract`
   - `Endstop failed to trigger`
6. **Z-Hop, Z-Offset & Bed Mesh Errors**:
   - `Move out of range on Z`
   - `Bed mesh probe out of bounds`
7. **Config Parsing & Pin Errors**:
   - Missing required config options
   - Unknown config sections
   - Reserved or duplicate pin configurations
8. **Unsafe Speed & Movement**:
   - `Must home axis first`
   - Requested speed exceeds `max_velocity`

### Print Quality & Mechanical Defects
- **Stringing & Oozing**: Retraction, Pressure Advance, filament drying
- **Warping & Bed Adhesion**: Z-offset, bed temperature, clean build surface
- **Layer Shifting**: Belt tension, TMC motor current, driver cooling
- **Under / Over-Extrusion**: Rotation distance (E-steps), flow multiplier
- **Clogging & Heat Creep**: Heatsink cooling fan, cold pulls, PTFE seating
- **Ghosting & Ringing**: Input Shaper tuning, resonance testing
- **Z-Seam Artifacts**: Seam alignment, Pressure Advance calibration
- **Elephant Foot**: First layer squish, initial layer expansion compensation
- **Pillowing**: Top solid layers count, infill density, cooling fan
- **Blobbing & Zits**: Pressure Advance, retraction restarts
- **Filament Grinding**: Extruder tensioner gear, heatbreak blockages
