#!/usr/bin/env python3
"""
Klipper Troubleshooting Assistant Skill
Analyzes Klipper logs, error strings, and print quality issues to provide detailed 
diagnoses, actionable fix recommendations, relevant configuration parameters, 
and Moonraker/Fluidd/Mainsail troubleshooting steps.
"""

import sys
import os
import re
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple


# ==============================================================================
# KLIPPER ERROR & ISSUE DATABASE
# ==============================================================================

KNOWLEDGE_BASE: List[Dict[str, Any]] = [
    # --------------------------------------------------------------------------
    # 1. MCU COMMUNICATION & TIMING ERRORS
    # --------------------------------------------------------------------------
    {
        "id": "mcu_timer_too_close",
        "title": "MCU Timer Too Close / Rescheduled Timer in Past",
        "category": "firmware",
        "severity": "critical",
        "patterns": [
            r"MCU '?.+?'? shutdown: Timer too close",
            r"\bRescheduled timer in the past\b",
            r"\bTimer too close\b"
        ],
        "diagnosis": (
            "The Klipper host software (Raspberry Pi/Linux host) sent an instruction to the MCU "
            "with an execution timestamp that was already in the past or too close to the current time "
            "for the MCU to process. This usually happens when the host CPU experiences a latency spike, "
            "system load overload, USB serial buffer delay, or microstepping rates exceed host/MCU bandwidth."
        ),
        "fixes": [
            "Disable resource-heavy host background tasks (e.g., webcam streaming at high frame rates, timelapses, database backups).",
            "Check Raspberry Pi CPU temperature and throttling status using `vcgencmd get_throttled` (look for under-voltage or thermal throttling).",
            "Avoid using USB hubs; connect MCU directly to host USB ports with a high-quality shielded USB cable.",
            "Reduce microsteps on high-speed axes (e.g., from 64 or 128 down to 16 with interpolation enabled).",
            "Decrease max_velocity or max_accel in printer.cfg if using high-resolution step settings."
        ],
        "config_parameters": [
            "[printer] max_velocity",
            "[printer] max_accel",
            "[stepper_x] microsteps",
            "[stepper_y] microsteps"
        ],
        "moonraker_fluidd_steps": [
            "Check Moonraker System Information tab in Mainsail/Fluidd for CPU and RAM load spikes.",
            "Inspect Fluidd/Mainsail system status for power throttling warnings.",
            "Lower webcam stream resolution and frame rate in Mainsail/Fluidd settings."
        ]
    },
    {
        "id": "mcu_lost_communication",
        "title": "Lost Communication with MCU / MCU Timeout",
        "category": "connectivity",
        "severity": "critical",
        "patterns": [
            r"Lost communication with MCU '?.+?'?",
            r"MCU '?.+?'? shutdown: Timeout",
            r"\bCommunication timeout with MCU\b",
            r"\bTimeout with MCU\b",
            r"\bLost communication with MCU\b"
        ],
        "diagnosis": (
            "The Klipper host lost USB/Serial/CANbus communication with one or more MCU boards. "
            "Causes include faulty USB cable, loose connectors, power fluctuations, ground loops, "
            "CANbus termination resistor misconfigurations, or electrostatic discharge (ESD)."
        ),
        "fixes": [
            "Inspect USB cable and connections between host and mainboard. Replace cable with a short, double-shielded USB cable with ferrite core.",
            "Ensure stable power supply to host (Raspberry Pi original power adapter strongly recommended).",
            "Check CANbus wiring, termination resistors (120 ohm at both ends of the bus), and CAN bus bitrate (typically 500000 or 1000000).",
            "Verify `/dev/serial/by-id/` or CAN bus UUID mapping in printer.cfg.",
            "Check for potential static electricity discharges from vacuum dust collection or ungrounded frame."
        ],
        "config_parameters": [
            "[mcu] serial",
            "[mcu] canbus_uuid",
            "[mcu] baud"
        ],
        "moonraker_fluidd_steps": [
            "Run `ls /dev/serial/by-id/*` or `ip -s link show can0` via SSH or Fluidd terminal.",
            "Restart Moonraker and Klipper services via Mainsail/Fluidd UI power menu.",
            "Review Moonraker log (`moonraker.log`) for USB disconnection events."
        ]
    },
    {
        "id": "mcu_crc_serial_error",
        "title": "MCU Serial CRC & Corrupted Packet Errors",
        "category": "connectivity",
        "severity": "error",
        "patterns": [
            r"\bCRC error\b",
            r"\bBytes read corrupted\b",
            r"mcu '?.+?'? serial error",
            r"\bSerial connection closed\b"
        ],
        "diagnosis": (
            "Data packets transmitted over serial/USB between host and MCU were corrupted during transmission. "
            "Indicates electrical noise, loose connection, improper baud rate, cable degradation, or EMI from stepper motor wiring."
        ),
        "fixes": [
            "Reroute USB/serial cables away from high-voltage stepper motor and bed heater cables.",
            "Check serial connections and solder joints on custom control boards.",
            "Replace USB cable with high-quality shielded data cable.",
            "Ensure mainboard ground is properly connected to printer frame and PSU ground."
        ],
        "config_parameters": [
            "[mcu] baud",
            "[mcu] restart_method"
        ],
        "moonraker_fluidd_steps": [
            "Check `klippy.log` stats section for increasing `bytes_invalid` counters.",
            "Ensure host system power remains stable during print start routines."
        ]
    },

    # --------------------------------------------------------------------------
    # 2. THERMISTOR & HEATER ERRORS
    # --------------------------------------------------------------------------
    {
        "id": "adc_out_of_range",
        "title": "ADC Out of Range (Thermistor Open / Short Circuit)",
        "category": "thermal",
        "severity": "critical",
        "patterns": [
            r"MCU '?.+?'? shutdown: ADC out of range",
            r"\bADC out of range\b",
            r"\bThermistor reading out of range\b",
            r"\bTHROWN_OPEN\b",
            r"\bSHORT_TO_GND\b"
        ],
        "diagnosis": (
            "The micro-controller read an analog-to-digital converter (ADC) voltage outside the configured "
            "`min_temp` or `max_temp` limits. A reading below `min_temp` usually indicates an OPEN circuit "
            "(broken wire, unplugged thermistor), while a reading above `max_temp` (or negative extreme) indicates a SHORT circuit (screws crushed thermistor wire)."
        ),
        "fixes": [
            "Inspect thermistor wiring at heater block and control board for breaks or pinches.",
            "If reading shows negative value (e.g. -14°C), check for loose plug or broken wire (Open circuit).",
            "If reading shows extremely high value (e.g. 300°C+ at room temp), check for short circuit across thermistor pins or heater block retaining screw.",
            "Verify sensor_type setting in printer.cfg matches actual thermistor hardware (e.g., ATC Semitec 104GT-2, PT1000, NTC 100K beta 3950).",
            "Check pullup resistance setting if using custom board/daughterboard (default is usually 4700 ohms)."
        ],
        "config_parameters": [
            "[extruder] sensor_type",
            "[extruder] min_temp",
            "[extruder] max_temp",
            "[extruder] pullup_resistor",
            "[heater_bed] sensor_type",
            "[heater_bed] min_temp",
            "[heater_bed] max_temp"
        ],
        "moonraker_fluidd_steps": [
            "Observe temperature graphs in Fluidd/Mainsail interface to see if temperature spikes up or drops to min/max prior to shutdown.",
            "Test thermistor by gently wiggling printhead cables while monitoring temperature graph in Fluidd."
        ]
    },
    {
        "id": "thermal_runaway_not_heating",
        "title": "Heater Extruder / Heater Bed Not Heating at Expected Rate",
        "category": "thermal",
        "severity": "critical",
        "patterns": [
            r"Heater .* not heating at expected rate",
            r"\bThermal runaway\b",
            r"Heater .* timeout",
            r"Temperature .* exceeds max_temp",
            r"Temperature .* below min_temp"
        ],
        "diagnosis": (
            "Klipper detected that the heater is receiving power but temperature is not increasing fast enough, "
            "or heat is dropping unexpectedly during operation. Klipper triggers shutdown to prevent fire or hardware damage. "
            "Common causes: bad PID tuning, cooling fan blowing directly on heater block/nozzle, insufficient heater cartridge wattage, loose thermistor, or blown MOSFET."
        ),
        "fixes": [
            "Perform PID calibration: run `PID_CALIBRATE HEATER=extruder TARGET=220` or `PID_CALIBRATE HEATER=heater_bed TARGET=60` and save configuration with `SAVE_CONFIG`.",
            "Verify silicone boot is installed on printhead heater block to insulate against part cooling fan air.",
            "Ensure part cooling fan is not pointing directly at heater block or thermistor.",
            "Check heater cartridge wiring and screw terminals on mainboard for loose connections or burn marks.",
            "Check power supply voltage output under load."
        ],
        "config_parameters": [
            "[extruder] control",
            "[extruder] pid_Kp",
            "[extruder] pid_Ki",
            "[extruder] pid_Kd",
            "[verify_heater extruder] check_gain_time",
            "[verify_heater extruder] heating_gain"
        ],
        "moonraker_fluidd_steps": [
            "Run PID Tune macro directly from Mainsail/Fluidd UI macros section.",
            "Monitor thermal response curve in Fluidd/Mainsail temperature chart during heating cycles."
        ]
    },

    # --------------------------------------------------------------------------
    # 3. STEPPER & DRIVER (TMC) ERRORS
    # --------------------------------------------------------------------------
    {
        "id": "tmc_driver_error",
        "title": "TMC Stepper Driver Error (DRV_STATUS / GSTAT / Short)",
        "category": "firmware",
        "severity": "critical",
        "patterns": [
            r"TMC '?.+?'? reports error: DRV_STATUS",
            r"TMC '?.+?'? reports error: GSTAT",
            r"\bDRV_STATUS\b",
            r"\bGSTAT\b",
            r"Driver .* error",
            r"\bSHORT_TO_GROUND\b",
            r"\bOVERTEMPERATURE\b",
            r"\bTMC driver error\b",
            r"stepper_.* driver error"
        ],
        "diagnosis": (
            "Trinamic driver reported an internal fault via UART/SPI communication. "
            "Triggers include short circuit in motor coils or motor cable, driver overheating, "
            "excessive motor current, supply voltage drop, or motor cable disconnect while powered."
        ),
        "fixes": [
            "Check motor cables and connector crimps for shorts or disconnections.",
            "Ensure stepper driver heatsinks are installed and cooling fan is blowing active airflow over stepper drivers.",
            "Reduce motor current (`run_current`) in driver configuration block.",
            "Verify stepper motor wiring sequence (A1, A2, B1, B2 pairs) matches board schematic.",
            "Check power supply voltage (12V/24V) into motor power terminals."
        ],
        "config_parameters": [
            "[tmc2209 stepper_x] run_current",
            "[tmc2209 stepper_x] hold_current",
            "[tmc2209 stepper_x] stealthchop_threshold",
            "[tmc2209 stepper_x] driver_SGTHRS"
        ],
        "moonraker_fluidd_steps": [
            "Execute `DUMP_TMC STEPPER=stepper_x` command in Fluidd/Mainsail console to inspect registers.",
            "Review driver register flags (e.g. otpw, ot, s2ga, s2gb) in console output."
        ]
    },
    {
        "id": "stepper_too_fast_move_out_of_range",
        "title": "Stepper Too Fast / Move Exceeds Maximum Position / Unable to Move",
        "category": "gcode",
        "severity": "error",
        "patterns": [
            r"Stepper '?.+?'? too fast",
            r"Requested speed exceeds max_velocity",
            r"Move exceeds maximum position",
            r"Move out of range",
            r"Move out of bounds",
            r"\bUnable to move\b"
        ],
        "diagnosis": (
            "G-code requested a move that requires step rates beyond Klipper's step frequency limits "
            "or exceeds configured axis physical bounds (position_max / position_min)."
        ),
        "fixes": [
            "Check slicer G-code travel speed or initial purge / start macro coordinates.",
            "Verify `position_max` and `position_min` settings in printer.cfg for affected axis.",
            "Ensure step distance and microstep configuration match physical hardware gear ratio and pulley teeth count.",
            "Check slicer build volume dimensions match Klipper configuration."
        ],
        "config_parameters": [
            "[stepper_x] position_max",
            "[stepper_x] position_min",
            "[printer] max_velocity",
            "[printer] max_z_velocity"
        ],
        "moonraker_fluidd_steps": [
            "Check target coordinates in Gcode Preview / Toolpath viewer in Fluidd/Mainsail.",
            "Inspect recent Gcode command line output prior to crash in console history."
        ]
    },
    {
        "id": "step_compression_error",
        "title": "Step Compression Error / Steppers Out of Sync",
        "category": "firmware",
        "severity": "error",
        "patterns": [
            r"\bStep compression error\b",
            r"\bSteppers out of sync\b",
            r"Internal error in stepcompress"
        ],
        "diagnosis": (
            "Klipper's host stepcompress algorithm encountered queue overload or corrupted step queue timing data. "
            "Often caused by heavy host CPU overload or invalid microstepping / step distance settings."
        ),
        "fixes": [
            "Lower host system load; stop non-essential services.",
            "Verify microsteps on all axes are reasonable (16 or 32 microsteps recommended).",
            "Update Klipper to latest version on host."
        ],
        "config_parameters": [
            "[stepper_x] microsteps",
            "[stepper_y] microsteps"
        ],
        "moonraker_fluidd_steps": [
            "Use Fluidd/Mainsail System Update Manager to update Klipper software."
        ]
    },

    # --------------------------------------------------------------------------
    # 4. PROBE & BLTOUCH ERRORS
    # --------------------------------------------------------------------------
    {
        "id": "probe_triggered_prior_to_movement",
        "title": "Probe Triggered Prior to Movement / Probe State Error",
        "category": "mechanical",
        "severity": "error",
        "patterns": [
            r"Probe triggered prior to movement",
            r"Probe state invalid",
            r"Probe already triggered",
            r"Probe triggered prior to move"
        ],
        "diagnosis": (
            "Klipper attempted to initiate a probing sequence (G28 Z or BED_MESH_CALIBRATE), "
            "but the probe signal was already in a HIGH/TRIGGERED state before moving down. "
            "Common causes: optical/inductive probe miswiring, reversed pin pullup (^), BLTouch pin stuck/bent, or nozzle pressing bed."
        ),
        "fixes": [
            "Test probe pin state with `QUERY_PROBE` command in console while probe is free.",
            "Invert probe pin logic in `printer.cfg` (add or remove `^` or `!` before pin name e.g., `pin: ^PC2`).",
            "Check BLTouch pin physically for bends or dust obstructing deployment.",
            "Inspect wiring for broken probe signal pin or loose ground connection."
        ],
        "config_parameters": [
            "[probe] pin",
            "[bltouch] sensor_pin",
            "[bltouch] control_pin",
            "[probe] z_offset"
        ],
        "moonraker_fluidd_steps": [
            "Run `QUERY_PROBE` in Fluidd console when manually triggered vs free to verify logic.",
            "Use BLTouch control macros in Fluidd UI (Pin Down, Self Test, Reset) to check BLTouch mechanical operation."
        ]
    },
    {
        "id": "bltouch_failed_to_verify_state",
        "title": "BLTouch Failed to Verify Sensor State / Deploy Failure",
        "category": "mechanical",
        "severity": "error",
        "patterns": [
            r"Failed to verify BLTouch probe state",
            r"\bBLTouch error\b",
            r"\bBLTouch failed to deploy\b",
            r"\bBLTouch failed to stow\b",
            r"\bProbe failed to trigger\b",
            r"\bNo probe triggered\b"
        ],
        "diagnosis": (
            "The BLTouch probe failed to switch to expected logic state after sending deploy or stow control pulse. "
            "Often caused by magnetic interference, bent push-pin, loose control wire, low 5V supply voltage, or incorrect control_pin configuration."
        ),
        "fixes": [
            "Check BLTouch push-pin for bends; straighten or replace with spare pin.",
            "Adjust top grub screw on BLTouch to reset internal magnet tension.",
            "Verify stable 5V power rail on control board.",
            "Ensure `pin_move_time` and `stow_on_each_sample` parameters are properly set in `[bltouch]` section."
        ],
        "config_parameters": [
            "[bltouch] sensor_pin",
            "[bltouch] control_pin",
            "[bltouch] pin_move_time",
            "[bltouch] stow_on_each_sample",
            "[bltouch] probe_with_touch_mode"
        ],
        "moonraker_fluidd_steps": [
            "Trigger `BLTOUCH_DEBUG COMMAND=pin_down` and `BLTOUCH_DEBUG COMMAND=pin_up` in Fluidd console to test servo motor response."
        ]
    },
    {
        "id": "probe_samples_deviance_tolerance",
        "title": "Probe Samples Deviance Exceeds Tolerance",
        "category": "mechanical",
        "severity": "warning",
        "patterns": [
            r"Probe samples deviance exceeds tolerance",
            r"Probe sample deviance",
            r"Probe tolerance exceeded"
        ],
        "diagnosis": (
            "During multi-sample probing, the difference between minimum and maximum probe Z values "
            "exceeded configured `samples_tolerance`. Caused by mechanical backlash, loose gantry, frame wobble, "
            "electrical noise on probe wire, or dirty print bed."
        ),
        "fixes": [
            "Tighten Z axis lead screws, eccentric nuts, and belt tension on gantry.",
            "Increase `samples_tolerance` slightly (e.g. from 0.005 to 0.015 mm) if using standard mechanical probe.",
            "Set `samples_result: median` or increase `samples: 3` in `[probe]` config.",
            "Lower probe speed (`speed: 3.0` or `5.0`)."
        ],
        "config_parameters": [
            "[probe] samples",
            "[probe] samples_tolerance",
            "[probe] samples_tolerance_retries",
            "[probe] samples_result",
            "[probe] speed"
        ],
        "moonraker_fluidd_steps": [
            "Run `PROBE_ACCURACY` command in Fluidd/Mainsail console to evaluate standard deviation across 10 probes."
        ]
    },

    # --------------------------------------------------------------------------
    # 5. ENDSTOP ERRORS
    # --------------------------------------------------------------------------
    {
        "id": "endstop_still_triggered_after_retract",
        "title": "Endstop Still Triggered After Retract / Failed to Trigger",
        "category": "mechanical",
        "severity": "error",
        "patterns": [
            r"Endstop '?.+?'? still triggered after retract",
            r"Endstop '?.+?'? failed to trigger",
            r"\bEndstop not responding\b"
        ],
        "diagnosis": (
            "During homing sequence (G28), the axis hit the endstop switch and performed retract move, "
            "but the endstop pin remained in TRIGGERED state, or the endstop never closed upon movement. "
            "Caused by sticky endstop switch mechanism, incorrect inversion flag (`!`), or homing retract distance too short."
        ),
        "fixes": [
            "Test endstop states using `QUERY_ENDSTOPS` command in console.",
            "Increase `homing_retract_dist` (e.g. from 2mm to 5mm) in `[stepper_x/y/z]` config.",
            "Inspect physical endstop switch for stickiness or misaligned bump stop tab.",
            "Check endstop pin inversion logic (`!` in pin definition)."
        ],
        "config_parameters": [
            "[stepper_x] endstop_pin",
            "[stepper_x] homing_retract_dist",
            "[stepper_x] homing_speed",
            "[stepper_x] homing_positive_dir"
        ],
        "moonraker_fluidd_steps": [
            "Run `QUERY_ENDSTOPS` in Mainsail/Fluidd console while manually pressing vs releasing endstop button."
        ]
    },

    # --------------------------------------------------------------------------
    # 6. Z-HOP, Z-OFFSET & BED MESH ERRORS
    # --------------------------------------------------------------------------
    {
        "id": "must_home_axis_first",
        "title": "Must Home Axis First",
        "category": "gcode",
        "severity": "error",
        "patterns": [
            r"\bMust home axis first\b",
            r"\bPrinter is not homed\b",
            r"Axis .* not homed"
        ],
        "diagnosis": (
            "A movement command (G0/G1/G2/G3) or bed meshing/probing command was issued while "
            "one or more kinematic axes lacked homing positional reference."
        ),
        "fixes": [
            "Add `G28` (Home All Axes) command in slicer Start G-code before any movement commands or bed mesh loading.",
            "Verify custom start macros (e.g., `START_PRINT`) check homing status with `{% if \"xyz\" not in printer.toolhead.homed_axes %} G28 {% endif %}`."
        ],
        "config_parameters": [
            "[homing_override]",
            "[safe_z_home]",
            "[gcode_macro START_PRINT]"
        ],
        "moonraker_fluidd_steps": [
            "Click 'Home All' button in Fluidd/Mainsail control panel prior to running manual movement commands."
        ]
    },
    {
        "id": "z_hop_z_offset_issues",
        "title": "Z-Hop Out of Range / Z-Offset Out of Bounds",
        "category": "configuration",
        "severity": "error",
        "patterns": [
            r"Move out of range on Z",
            r"\bZ-hop out of range\b",
            r"\bZ offset out of bounds\b",
            r"\bProbe offset invalid\b"
        ],
        "diagnosis": (
            "A Z-hop command, retargeting move, or bed mesh offset move exceeded the physical `position_max` or `position_min` boundaries configured for the Z axis."
        ),
        "fixes": [
            "Ensure `position_max` in `[stepper_z]` allows sufficient headroom for Z-hop at top print heights.",
            "Check slicer Z-hop setting (typically 0.2mm - 0.4mm).",
            "Verify `z_offset` in `[probe]` or `[bltouch]` is positive and within realistic physical distance (e.g. 0.5mm - 3.5mm)."
        ],
        "config_parameters": [
            "[stepper_z] position_max",
            "[stepper_z] position_min",
            "[probe] z_offset"
        ],
        "moonraker_fluidd_steps": [
            "Recalibrate probe Z-offset using Fluidd/Mainsail Z-offset calibration wizard."
        ]
    },
    {
        "id": "bed_mesh_probe_out_of_bounds",
        "title": "Bed Mesh Probe Out of Bounds / Invalid Parameter",
        "category": "configuration",
        "severity": "error",
        "patterns": [
            r"Bed mesh probe out of bounds",
            r"Bed mesh invalid parameter",
            r"Mesh profile not found",
            r"Points out of range"
        ],
        "diagnosis": (
            "Bed mesh configuration specifies grid boundaries (`mesh_min`, `mesh_max`) that cause the probe "
            "(offset from print nozzle via `x_offset`, `y_offset`) to move outside physical axis travel limits (`position_min`, `position_max`)."
        ),
        "fixes": [
            "Calculate valid probe boundary: `mesh_min_x = position_min_x + x_offset` (or safety margin). Ensure `mesh_max_x + x_offset <= position_max_x`.",
            "Account for nozzle-to-probe offset: if probe offset is `x_offset: -40, y_offset: -10`, mesh_max must be at least 40mm inside right edge of physical travel.",
            "Check `BED_MESH_CALIBRATE` profile parameters or dynamic adaptive mesh parameters."
        ],
        "config_parameters": [
            "[bed_mesh] mesh_min",
            "[bed_mesh] mesh_max",
            "[bed_mesh] probe_count",
            "[probe] x_offset",
            "[probe] y_offset"
        ],
        "moonraker_fluidd_steps": [
            "Inspect Bed Mesh tab in Fluidd/Mainsail to visualize generated height map."
        ]
    },

    # --------------------------------------------------------------------------
    # 7. CONFIGURATION & PIN PARSING ERRORS
    # --------------------------------------------------------------------------
    {
        "id": "config_parsing_missing_option",
        "title": "Config Option Missing / Unknown Section / Invalid Pin",
        "category": "configuration",
        "severity": "critical",
        "patterns": [
            r"Option '.*' in section '.*' must be specified",
            r"Missing required config option",
            r"Unknown config section",
            r"Section '.*' is not valid",
            r"Invalid pin description",
            r"Pin '.*' reserved",
            r"Pin '.*' is not a valid hardware pin",
            r"Pin '.*' already configured"
        ],
        "diagnosis": (
            "Klipper failed to parse `printer.cfg` or included configuration files due to a missing mandatory option, "
            "typo in section header, duplicate pin allocation, or invalid hardware pin alias."
        ),
        "fixes": [
            "Check syntax line indicated in `klippy.log` error block.",
            "Ensure no two components share the exact same output pin without sharing definition (e.g. multi-pin configuration).",
            "Verify hardware board pinout aliases file (e.g., `board_pins.cfg` or sample config for your MCU).",
            "Ensure correct section naming (e.g. `[tmc2209 stepper_x]` requires `stepper_x` suffix)."
        ],
        "config_parameters": [
            "[board_pins]",
            "[mcu]"
        ],
        "moonraker_fluidd_steps": [
            "Open Configuration Editor in Mainsail/Fluidd UI to locate syntax red highlights."
        ]
    },

    # --------------------------------------------------------------------------
    # 8. PRINT QUALITY & MECHANICAL ISSUES (NOT JUST LOG ERRORS)
    # --------------------------------------------------------------------------
    {
        "id": "quality_stringing_oozing",
        "title": "Stringing and Oozing",
        "category": "slicing",
        "severity": "warning",
        "patterns": [
            r"\bstringing\b",
            r"\boozing\b",
            r"\bcobwebs\b",
            r"\bhairy prints\b",
            r"\bwhispers of plastic\b"
        ],
        "diagnosis": (
            "Melted filament drips or strings out of nozzle during non-printing travel moves. "
            "Caused by insufficient retraction distance/speed, excessive printing temperature, high nozzle pressure, "
            "or wet filament absorbing ambient moisture."
        ),
        "fixes": [
            "Tune retraction distance (Direct Drive: 0.5 - 1.5mm; Bowden: 2.0 - 6.0mm) and retraction speed (30 - 50 mm/s).",
            "Perform a Temperature Tower test to find lowest temperature with good layer adhesion.",
            "Enable Pressure Advance in Klipper (`tuning_tower VARIABLE=pressure_advance`) to reduce nozzle pressure during deceleration.",
            "Dry filament in a dedicated filament dryer (especially PETG, TPU, Nylon, ABS)."
        ],
        "config_parameters": [
            "[extruder] pressure_advance",
            "[extruder] pressure_advance_smooth_time",
            "[firmware_retraction] retract_length",
            "[firmware_retraction] retract_speed"
        ],
        "moonraker_fluidd_steps": [
            "Set and adjust Pressure Advance dynamically during print via Fluidd console: `SET_PRESSURE_ADVANCE ADVANCE=0.04`."
        ]
    },
    {
        "id": "quality_warping_bed_adhesion",
        "title": "Warping and Bed Adhesion Failure",
        "category": "thermal",
        "severity": "warning",
        "patterns": [
            r"\bwarping\b",
            r"\bbed adhesion\b",
            r"\blifting corners\b",
            r"\bprint coming off bed\b",
            r"\bdetaching from bed\b"
        ],
        "diagnosis": (
            "Print bottom corners pull away from build plate due to thermal shrinkage stress as upper layers cool. "
            "Caused by improper first layer Z-offset, low bed temperature, drafty room environment, dirty build plate, or disabled bed mesh."
        ),
        "fixes": [
            "Clean build plate thoroughly with warm water and dish soap, followed by 99% Isopropyl Alcohol (IPA).",
            "Tune Z-offset using Klipper `Z_ENDSTOP_CALIBRATE` or `PROBE_CALIBRATE` so first layer line is slightly squished.",
            "Increase heated bed temperature by 5 - 10°C for first layer.",
            "Turn off part cooling fan for first 3-5 layers.",
            "Use draft shield or printer enclosure when printing ABS/ASA/PC filaments."
        ],
        "config_parameters": [
            "[stepper_z] position_endstop",
            "[probe] z_offset",
            "[bed_mesh] zero_reference_position",
            "[heater_bed] target"
        ],
        "moonraker_fluidd_steps": [
            "Use Mainsail/Fluidd Z-offset controls (+0.01 / -0.01mm) during first layer printing to fine-tune squish."
        ]
    },
    {
        "id": "quality_layer_shifting",
        "title": "Layer Shifting / Axis Slip",
        "category": "mechanical",
        "severity": "error",
        "patterns": [
            r"\blayer shift(?:ing)?\b",
            r"\bshifted layer\b",
            r"\baxis slip\b",
            r"\bstepper skipping\b"
        ],
        "diagnosis": (
            "Extruder head or print bed skips steps along X/Y axis mid-print, causing horizontal misalignment of subsequent layers. "
            "Caused by loose timing belts/pulleys, mechanical collision with curled print edges, stepper driver overheating, or excessively high acceleration."
        ),
        "fixes": [
            "Tighten timing belts (aim for ~110Hz frequency over 150mm span on belt tension app). Ensure pulley grub screws are tight on motor D-shaft.",
            "Inspect stepper motor drivers for overheating; ensure electrical fan is blowing air on MCU board.",
            "Increase TMC driver `run_current` slightly if set too low, or check if motor gets scalding hot.",
            "Reduce acceleration (`max_accel`) in `printer.cfg` or slicer settings.",
            "Enable Z-hop (0.2 - 0.4mm) in slicer to avoid colliding with curled overhang edges."
        ],
        "config_parameters": [
            "[printer] max_accel",
            "[printer] max_accel_to_decel",
            "[tmc2209 stepper_x] run_current",
            "[tmc2209 stepper_y] run_current"
        ],
        "moonraker_fluidd_steps": [
            "Adjust acceleration limit dynamically via console: `SET_VELOCITY_LIMIT ACCEL=3000`."
        ]
    },
    {
        "id": "quality_under_over_extrusion",
        "title": "Under-Extrusion or Over-Extrusion",
        "category": "mechanical",
        "severity": "warning",
        "patterns": [
            r"\bunder-?extrusion\b",
            r"\bover-?extrusion\b",
            r"\bgaps in layers\b",
            r"\bstarved extrusion\b",
            r"\bdimensional accuracy\b"
        ],
        "diagnosis": (
            "The hotend extrudes too little or too much filament relative to expected volume calculated by slicer. "
            "Under-extrusion causes gaps and weak layer bonds; over-extrusion causes blobby walls, dimensional inaccuracy, and nozzle scraping."
        ),
        "fixes": [
            "Calibrate Extruder Rotation Distance (e-steps in Klipper): mark 100mm filament, extrude 100mm (`G1 E100 F60`), measure actual movement, and recalculate `rotation_distance`.",
            "Verify filament diameter setting in slicer matches physical filament (measure with calipers e.g. 1.75mm vs 2.85mm).",
            "Adjust Extrusion Multiplier / Flow Rate in slicer (typically 0.92 - 1.05).",
            "Check extruder drive gear tension thumb screw for slipping or grinding."
        ],
        "config_parameters": [
            "[extruder] rotation_distance",
            "[extruder] microsteps",
            "[extruder] noozle_diameter",
            "[extruder] filament_diameter"
        ],
        "moonraker_fluidd_steps": [
            "Use Extrude/Retract panel in Mainsail/Fluidd UI to perform precise 100mm extrusion calibration tests."
        ]
    },
    {
        "id": "quality_clogging_heat_creeping",
        "title": "Hotend Clogging, Heat Creep, and Filament Grinding",
        "category": "thermal",
        "severity": "error",
        "patterns": [
            r"\bclogging\b",
            r"\bnozzle clog\b",
            r"\bheat creep\b",
            r"\bfilament grinding\b",
            r"\bextruder slipping\b",
            r"\bchewed filament\b",
            r"\bjammed hotend\b"
        ],
        "diagnosis": (
            "Filament stops advancing through heatbreak or nozzle tip. "
            "Heat creep occurs when heat travels upward from heater block into cool side heatbreak due to inadequate heatsink cooling fan, causing filament to swell and jam in PTFE tube/heatbreak."
        ),
        "fixes": [
            "Check hotend heatsink cooling fan (always-on fan) is spinning at 100% full speed whenever hotend temperature > 50°C.",
            "Perform a Cold Pull (Atomic Pull) cleaning procedure using Nylon or PLA filament to clear debris from nozzle.",
            "Avoid excessive retraction distance on all-metal hotends (keep < 1.5mm for direct drive).",
            "Ensure PTFE tube is cut flush and seated firmly against nozzle back inside heatbreak."
        ],
        "config_parameters": [
            "[heater_fan hotend_fan] heater",
            "[heater_fan hotend_fan] heater_temp",
            "[heater_fan hotend_fan] fan_speed",
            "[extruder] min_extrude_temp"
        ],
        "moonraker_fluidd_steps": [
            "Verify `[heater_fan hotend_fan]` status in Fluidd dashboard to ensure RPM/PWM power triggers above 50°C."
        ]
    },
    {
        "id": "quality_ghosting_ringing",
        "title": "Ghosting / Ringing / Input Shaper Tuning",
        "category": "mechanical",
        "severity": "info",
        "patterns": [
            r"\bghosting\b",
            r"\bringing\b",
            r"\brippling\b",
            r"\bechoing\b",
            r"\bvibration artifacts\b"
        ],
        "diagnosis": (
            "Repeating ripples or shadow lines trailing after sharp corners or high-acceleration direction changes. "
            "Caused by mechanical resonance, belt flex, high print acceleration, or uncalibrated resonance frequencies."
        ),
        "fixes": [
            "Calibrate Klipper Input Shaper feature using ADXL345 accelerometer (`ACCELEROMETER_QUERY`, `TEST_RESONANCES AXIS=X/Y`) or manual ringing frequency measurement.",
            "Mount printer on a heavy concrete paver with foam dampening pad underneath.",
            "Tighten frame fasteners, linear rails, and belt mounts to eliminate mechanical play.",
            "Reduce outer wall printing speed and corner square corner velocity."
        ],
        "config_parameters": [
            "[input_shaper] shaper_type_x",
            "[input_shaper] shaper_freq_x",
            "[input_shaper] shaper_type_y",
            "[input_shaper] shaper_freq_y",
            "[printer] square_corner_velocity"
        ],
        "moonraker_fluidd_steps": [
            "Run resonance graph generation scripts or view generated PNG resonance plots in Mainsail/Fluidd file browser."
        ]
    },
    {
        "id": "quality_z_seam_blobs",
        "title": "Z-Seam Artifacts, Blobs, and Zits",
        "category": "slicing",
        "severity": "info",
        "patterns": [
            r"\bz-?seam\b",
            r"\bzipper\b",
            r"\bseam blobs\b",
            r"\bblobbing\b",
            r"\bzits\b",
            r"\bretraction blobs\b"
        ],
        "diagnosis": (
            "Visible bumps, dots, or scars along wall surfaces where each print layer starts and ends. "
            "Caused by uncalibrated pressure advance, excessive extra prime volume after retraction, or coasting issues."
        ),
        "fixes": [
            "Align Z-seam in slicer (e.g. 'Aligned', 'Sharpest Corner', or 'Back').",
            "Fine-tune Pressure Advance in Klipper to eliminate pressure lag at start/end of loops.",
            "Ensure 'Extra Length on Restart' in slicer retraction settings is set to 0.0mm.",
            "Enable Wipe while retracting in slicer settings."
        ],
        "config_parameters": [
            "[extruder] pressure_advance",
            "[extruder] pressure_advance_smooth_time"
        ],
        "moonraker_fluidd_steps": [
            "Tune Pressure Advance value live during print via Fluidd console to inspect seam smoothness."
        ]
    },
    {
        "id": "quality_elephant_foot",
        "title": "Elephant Foot / First Layer Flare",
        "category": "mechanical",
        "severity": "info",
        "patterns": [
            r"\belephants? foot\b",
            r"\bfirst layer flare\b",
            r"\bsquished first layer\b",
            r"\bbottom layer bulge\b"
        ],
        "diagnosis": (
            "The initial bottom layers bulge outwards wider than nominal wall dimensions. "
            "Caused by excessive nozzle squish (Z-offset too low), bed temperature set too high, or heavy bed weight causing Z lead screw back-lash."
        ),
        "fixes": [
            "Slightly raise Z-offset (+0.02 - +0.05mm).",
            "Enable Initial Layer Horizontal Expansion compensation in slicer (e.g. -0.15mm).",
            "Lower bed temperature by 5°C after first layer completes.",
            "Ensure Z axis mechanical lead screw moves freely without binding."
        ],
        "config_parameters": [
            "[probe] z_offset",
            "[stepper_z] position_endstop"
        ],
        "moonraker_fluidd_steps": [
            "Adjust live Z-offset during print via Fluidd / Mainsail UI."
        ]
    },
    {
        "id": "quality_pillowing",
        "title": "Pillowing and Top Surface Holes",
        "category": "slicing",
        "severity": "info",
        "patterns": [
            r"\bpillow(?:ing)?\b",
            r"\btop layer holes\b",
            r"\btop surface gaps\b",
            r"\brough top layer\b"
        ],
        "diagnosis": (
            "Bumps, blisters, or small pinholes appearing on top flat solid layers. "
            "Occurs when top layers sag into infill spaces due to inadequate top solid layers count, insufficient infill density, or weak part cooling fan."
        ),
        "fixes": [
            "Increase number of top solid layers in slicer (at least 4-6 layers).",
            "Increase infill density (minimum 15-20%) or change infill pattern to Grid/Gyroid.",
            "Increase top layer part cooling fan speed to 100%."
        ],
        "config_parameters": [
            "[fan] pin",
            "[fan] max_power"
        ],
        "moonraker_fluidd_steps": [
            "Check print cooling fan slider in Fluidd/Mainsail dashboard to confirm fan operates at full speed."
        ]
    }
]


# ==============================================================================
# KLIPPY LOG PARSER HELPERS
# ==============================================================================

def parse_klippy_log(log_content: str) -> Dict[str, Any]:
    """
    Parses full raw content of a klippy.log file and extracts key metadata,
    shutdown messages, tracebacks, recent G-code, and temperature statistics.
    """
    lines = log_content.splitlines()
    
    version_match = re.search(r"Git version:\s*['\"]?([^\n'\"]+)", log_content)
    klipper_version = version_match.group(1).strip() if version_match else "Unknown"

    mcu_matches = re.findall(r"MCU '(\w+)' config:.*mcu_type=([^\s]+)", log_content)
    mcus = [{"mcu_name": m[0], "mcu_type": m[1]} for m in mcu_matches]

    shutdown_patterns = [
        r"(MCU '.*?' shutdown: [^\n]+)",
        r"(Transition to shutdown state: [^\n]+)",
        r"(Unhandled exception [^\n]+)",
        r"(!! [^\n]+)",
        r"(Error: [^\n]+)"
    ]

    extracted_errors = []
    for pattern in shutdown_patterns:
        matches = re.findall(pattern, log_content)
        for m in matches:
            clean_err = m.strip()
            if clean_err not in extracted_errors:
                extracted_errors.append(clean_err)

    # Extract last tracebacks
    tracebacks = []
    tb_matches = re.findall(r"Traceback \(most recent call last\):\n(.*?)(?=\n\n|\n[A-Z]|\Z)", log_content, re.DOTALL)
    for tb in tb_matches[-3:]:  # last 3 tracebacks
        tracebacks.append(tb.strip())

    # Extract recent G-code commands executed
    gcode_commands = []
    gcode_matches = re.findall(r"gcode: (G\d+|M\d+|[A-Z_]+[^\n]*)", log_content)
    if gcode_matches:
        gcode_commands = gcode_matches[-10:]

    # Extract latest temperature stats snapshot
    temp_snapshot = {}
    stats_matches = re.findall(r"stats: [^\n]*", log_content)
    if stats_matches:
        last_stat = stats_matches[-1]
        heaters = re.findall(r"(\w+): target=(\d+(?:\.\d+)?) temp=(\d+(?:\.\d+)?)", last_stat)
        for name, target, temp in heaters:
            temp_snapshot[name] = {"target": float(target), "temp": float(temp)}

    return {
        "klipper_version": klipper_version,
        "mcus": mcus,
        "extracted_errors": extracted_errors,
        "recent_tracebacks": tracebacks,
        "last_gcode_commands": gcode_commands,
        "temperature_snapshot": temp_snapshot
    }


# ==============================================================================
# DIAGNOSTIC ENGINE & MATCHER
# ==============================================================================

def diagnose_input(input_text: str, log_analysis: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Matches the input text (or log extracted errors) against the Knowledge Base
    using regex pattern matching and semantic keyword scoring.
    """
    matched_results = []
    matched_ids = set()

    # If log analysis was run, prepend extracted errors to search corpus
    search_corpus = input_text
    if log_analysis and log_analysis.get("extracted_errors"):
        search_corpus = "\n".join(log_analysis["extracted_errors"]) + "\n" + input_text

    for item in KNOWLEDGE_BASE:
        confidence = None
        matched_pattern = None

        # 1. Exact / Regex pattern check
        for pattern in item["patterns"]:
            if re.search(pattern, search_corpus, re.IGNORECASE):
                confidence = "exact" if "mcu" in item["id"] or "adc" in item["id"] else "high"
                matched_pattern = pattern
                break

        # 2. Keyword fallback if no regex match
        if not confidence:
            title_words = [w.lower() for w in item["title"].split() if len(w) > 3]
            matches_count = sum(1 for w in title_words if w in search_corpus.lower())
            if len(title_words) > 0 and (matches_count / len(title_words)) >= 0.5:
                confidence = "medium"
                matched_pattern = f"Keyword match ratio: {matches_count}/{len(title_words)}"

        if confidence and item["id"] not in matched_ids:
            matched_ids.add(item["id"])
            matched_results.append({
                "id": item["id"],
                "title": item["title"],
                "category": item["category"],
                "severity": item["severity"],
                "match_confidence": confidence,
                "matched_pattern": matched_pattern,
                "diagnosis": item["diagnosis"],
                "step_by_step_fixes": item["fixes"],
                "relevant_config_parameters": item["config_parameters"],
                "moonraker_fluidd_steps": item["moonraker_fluidd_steps"]
            })

    # Sort results by severity: critical > error > warning > info
    severity_order = {"critical": 0, "error": 1, "warning": 2, "info": 3}
    matched_results.sort(key=lambda x: severity_order.get(x["severity"], 4))

    return matched_results


# ==============================================================================
# MAIN SCRIPT CLI ENTRY
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Klipper 3D Printer Troubleshooting & Diagnostic Skill"
    )
    parser.add_argument(
        "--error", "-e",
        type=str,
        help="Error message string or print quality problem description."
    )
    parser.add_argument(
        "--logfile", "-f",
        type=str,
        help="Path to a klippy.log file to analyze."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=True,
        help="Output results in JSON format (default: True)."
    )

    args, unknown = parser.parse_known_args()

    input_text = ""
    input_type = "string"
    analyzed_source = "CLI argument"
    log_analysis = None

    if args.logfile:
        input_type = "logfile"
        analyzed_source = args.logfile
        log_path = Path(args.logfile)
        if not log_path.exists():
            error_output = {
                "status": "error",
                "message": f"Log file not found at path: {args.logfile}"
            }
            print(json.dumps(error_output, indent=2))
            sys.exit(1)
        
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                log_content = f.read()
            log_analysis = parse_klippy_log(log_content)
            input_text = log_content
        except Exception as e:
            error_output = {
                "status": "error",
                "message": f"Failed to read log file: {str(e)}"
            }
            print(json.dumps(error_output, indent=2))
            sys.exit(1)

    elif args.error:
        input_type = "error_string"
        analyzed_source = "error argument"
        input_text = args.error

    else:
        # Check stdin if no explicit argument was given
        if not sys.stdin.isatty():
            stdin_data = sys.stdin.read().strip()
            if stdin_data:
                analyzed_source = "stdin"
                # Check if stdin is JSON
                if stdin_data.startswith("{") and stdin_data.endswith("}"):
                    try:
                        parsed_json = json.loads(stdin_data)
                        if "error" in parsed_json:
                            input_text = str(parsed_json["error"])
                            input_type = "json_object"
                        elif "message" in parsed_json:
                            input_text = str(parsed_json["message"])
                            input_type = "json_object"
                        else:
                            input_text = stdin_data
                            input_type = "json_object"
                    except json.JSONDecodeError:
                        input_text = stdin_data
                        input_type = "text_stream"
                else:
                    input_text = stdin_data
                    if "Git version:" in stdin_data or "stats:" in stdin_data:
                        input_type = "logfile_stream"
                        log_analysis = parse_klippy_log(stdin_data)
                    else:
                        input_type = "text_stream"

    if not input_text and not log_analysis:
        parser.print_help()
        sys.exit(1)

    diagnoses = diagnose_input(input_text, log_analysis)

    # General recommendations based on output
    general_recs = [
        "Always back up printer.cfg before making major parameter modifications.",
        "When changing configuration settings, execute RESTART or FIRMWARE_RESTART in Fluidd/Mainsail.",
        "Ensure host operating system packages and Klipper/Moonraker/Mainsail services are up to date."
    ]

    output_data = {
        "status": "success",
        "input_type": input_type,
        "analyzed_source": analyzed_source,
        "summary": {
            "total_matches_found": len(diagnoses),
            "top_category": diagnoses[0]["category"] if diagnoses else None,
            "highest_severity": diagnoses[0]["severity"] if diagnoses else None
        },
        "log_context": log_analysis,
        "matches": diagnoses,
        "general_recommendations": general_recs
    }

    print(json.dumps(output_data, indent=2))


if __name__ == "__main__":
    main()
