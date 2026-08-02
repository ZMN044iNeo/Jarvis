#!/usr/bin/env python3
"""
Gcode Analysis Tool & Skill for 3D Printing
Analyzes Gcode files from OrcaSlicer, PrusaSlicer, Cura, Elegoo Slicer, SuperSlicer, BambuStudio, etc.
Outputs a structured JSON report detailing safety, settings, issues, warnings, recommendations, and metrics.
"""

import sys
import os
import json
import re
import math
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional, Set


class GCodeAnalyzer:
    def __init__(
        self,
        filament_diameter: float = 1.75,
        filament_density: Optional[float] = None,
        nozzle_diameter: float = 0.4,
    ):
        self.user_filament_diameter = filament_diameter
        self.user_filament_density = filament_density
        self.nozzle_diameter = nozzle_diameter

        # Metadata & Dialects
        self.lines_count = 0
        self.slicer_detected = "Unknown"
        self.slicer_version = ""
        self.firmware_dialect = "Standard RepRap / Marlin"
        self.firmware_confidence = "low"
        self.firmware_indicators: Set[str] = set()

        # Modes & Units
        self.positioning_mode = "G90"  # G90 (absolute) or G91 (relative)
        self.extrusion_mode = "M82"  # M82 (absolute) or M83 (relative)
        self.units = "mm (G21)"  # G21 or G20

        # Current state
        self.curr_x: Optional[float] = None
        self.curr_y: Optional[float] = None
        self.curr_z: Optional[float] = None
        self.curr_e: float = 0.0
        self.last_abs_e: float = 0.0
        self.curr_feedrate: Optional[float] = None  # mm/min
        self.curr_tool: int = 0

        # Bounding box
        self.min_x = float("inf")
        self.max_x = float("-inf")
        self.min_y = float("inf")
        self.max_y = float("-inf")
        self.min_z = float("inf")
        self.max_z = float("-inf")

        # Heaters and Temperatures
        self.extruder_target_temp = 0.0
        self.bed_target_temp = 0.0
        self.extruder_temps_seen: List[Dict[str, Any]] = []
        self.bed_temps_seen: List[Dict[str, Any]] = []
        self.wait_extruder_lines: List[int] = []
        self.wait_bed_lines: List[int] = []
        self.heating_order: List[Dict[str, Any]] = []

        # Fans
        self.curr_fan_speed = 0.0  # 0 to 100%
        self.fan_on_first_layer = False
        self.max_fan_speed_pct = 0.0

        # Start / End sequence tracking
        self.homing_lines: List[int] = []
        self.bed_leveling_lines: List[int] = []
        self.first_extrusion_line: Optional[int] = None
        self.last_extrusion_line: Optional[int] = None
        self.has_prime_line = False
        self.has_end_heater_off = False
        self.has_end_bed_off = False
        self.has_end_fan_off = False
        self.has_end_motor_off = False

        # Retractions & Speeds
        self.total_extrusion_length = 0.0  # mm
        self.retraction_count = 0
        self.retraction_distances: List[float] = []
        self.retraction_speeds: List[float] = []  # mm/s
        self.uses_firmware_retraction = False

        self.print_speeds: List[float] = []  # mm/s
        self.travel_speeds: List[float] = []  # mm/s
        self.first_layer_speeds: List[float] = []  # mm/s
        self.acceleration_commands: List[str] = []

        # Layer analysis
        self.current_layer = 0
        self.layer_heights: List[float] = []
        self.layer_z_map: Dict[int, float] = {}
        self.layer_start_lines: Dict[int, int] = {}
        self.layer_extrusion_counts: Dict[int, int] = {}
        self.last_z_with_extrusion: Optional[float] = None

        # Flow Rate & Volumetric
        self.flow_modifiers: List[Dict[str, Any]] = []
        self.max_volumetric_flow = 0.0  # mm3/s

        # Time estimation
        self.m73_times: List[float] = []
        self.slicer_estimated_time_sec: Optional[float] = None
        self.kinematic_time_sec = 0.0
        self.filament_type_detected = "PLA"
        self.filament_diameter_detected: Optional[float] = None

        # Absolute E check
        self.max_abs_e_seen = 0.0
        self.g92_resets_count = 0

        # Issues, Warnings, Recommendations
        self.issues: List[Dict[str, Any]] = []
        self.warnings: List[str] = []
        self.recommendations: List[str] = []

    def parse_line(self, raw_line: str) -> Tuple[Optional[str], Dict[str, Any], str]:
        comment = ""
        line_code = raw_line

        if ";" in raw_line:
            parts = raw_line.split(";", 1)
            line_code = parts[0]
            comment = parts[1].strip()

        line_code = line_code.strip()
        if not line_code:
            return None, {}, comment

        tokens = line_code.split()
        cmd = tokens[0].upper()
        params: Dict[str, Any] = {}

        for token in tokens[1:]:
            if "=" in token:
                k, v = token.split("=", 1)
                try:
                    params[k.upper()] = float(v)
                except ValueError:
                    params[k.upper()] = v
            else:
                m = re.match(r"^([A-Za-z]+)([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)$", token)
                if m:
                    key = m.group(1).upper()
                    val_str = m.group(2)
                    try:
                        params[key] = float(val_str)
                    except ValueError:
                        params[key] = val_str
                else:
                    m_letter = re.match(r"^([A-Za-z]+)$", token)
                    if m_letter:
                        params[m_letter.group(1).upper()] = True
                    else:
                        params[token.upper()] = True

        return cmd, params, comment

    def inspect_comment(self, comment: str, line_num: int):
        if not comment:
            return

        c_lower = comment.lower()

        # Slicer Detection
        if "orcaslicer" in c_lower or "orca slicer" in c_lower:
            self.slicer_detected = "OrcaSlicer"
            m = re.search(r"OrcaSlicer\s+v?([0-9\.]+)", comment, re.IGNORECASE)
            if m:
                self.slicer_version = m.group(1)
        elif "prusaslicer" in c_lower or "prusa slicer" in c_lower:
            self.slicer_detected = "PrusaSlicer"
            m = re.search(r"PrusaSlicer\s+v?([0-9\.]+)", comment, re.IGNORECASE)
            if m:
                self.slicer_version = m.group(1)
        elif "superslicer" in c_lower or "super slicer" in c_lower:
            self.slicer_detected = "SuperSlicer"
            m = re.search(r"SuperSlicer\s+v?([0-9\.]+)", comment, re.IGNORECASE)
            if m:
                self.slicer_version = m.group(1)
        elif "cura_steamengine" in c_lower or "generated with cura" in c_lower:
            self.slicer_detected = "Cura"
            m = re.search(r"Cura_SteamEngine\s+([0-9\.]+)", comment, re.IGNORECASE)
            if m:
                self.slicer_version = m.group(1)
        elif "elegoo" in c_lower:
            self.slicer_detected = "Elegoo Slicer"
        elif "bambustudio" in c_lower or "bambu studio" in c_lower:
            self.slicer_detected = "BambuStudio"
        elif "simplify3d" in c_lower:
            self.slicer_detected = "Simplify3D"
        elif "ideamaker" in c_lower:
            self.slicer_detected = "ideaMaker"

        # Metadata extraction
        # Filament type
        m_fil = re.search(r"filament_type\s*=\s*([A-Za-z0-9_\-\+]+)", comment, re.IGNORECASE)
        if not m_fil:
            m_fil = re.search(r"FILAMENT_TYPE:\s*([A-Za-z0-9_\-\+]+)", comment, re.IGNORECASE)
        if m_fil:
            self.filament_type_detected = m_fil.group(1).upper()

        # Filament diameter
        m_dia = re.search(r"filament_diameter\s*=\s*([0-9\.]+)", comment, re.IGNORECASE)
        if m_dia:
            try:
                self.filament_diameter_detected = float(m_dia.group(1))
            except ValueError:
                pass

        # Time estimation from comments
        m_time_p = re.search(r"estimated printing time.*=\s*(?:(\d+)h\s*)?(?:(\d+)m\s*)?(?:(\d+)s)?", comment, re.IGNORECASE)
        if m_time_p and any(m_time_p.groups()):
            h = int(m_time_p.group(1) or 0)
            m = int(m_time_p.group(2) or 0)
            s = int(m_time_p.group(3) or 0)
            sec = h * 3600 + m * 60 + s
            if sec > 0:
                self.slicer_estimated_time_sec = sec

        # Cura format: ;TIME:3600
        m_cura_time = re.search(r"^TIME:(\d+)$", comment)
        if m_cura_time:
            self.slicer_estimated_time_sec = float(m_cura_time.group(1))

        # Layer markers
        m_layer = re.search(r"^(?:LAYER|layer)[:\s]+(\d+)", comment, re.IGNORECASE)
        if m_layer:
            new_layer = int(m_layer.group(1))
            self.current_layer = new_layer
            self.layer_start_lines[new_layer] = line_num

    def process_command(self, cmd: str, params: Dict[str, Any], comment: str, line_num: int):
        # Firmware signature detection
        if cmd in ("BED_MESH_CALIBRATE", "BED_MESH_PROFILE", "SET_VELOCITY_LIMIT", "SET_HEATER_TEMPERATURE", "SAVE_GCODE_STATE", "RESTORE_GCODE_STATE"):
            self.firmware_indicators.add(cmd)
            self.firmware_dialect = "Klipper"
            self.firmware_confidence = "high"

        elif cmd in ("M420", "M900", "M500", "M501", "M503", "M201", "M203", "M204", "M205"):
            if self.firmware_dialect != "Klipper":
                self.firmware_indicators.add(cmd)
                self.firmware_dialect = "Marlin"
                self.firmware_confidence = "medium"

        elif cmd in ("M566", "M558", "M563", "M581", "M582", "M584"):
            self.firmware_indicators.add(cmd)
            self.firmware_dialect = "RepRapFirmware"
            self.firmware_confidence = "high"

        # Units
        if cmd == "G20":
            self.units = "inches (G20)"
        elif cmd == "G21":
            self.units = "mm (G21)"

        # Positioning Mode
        elif cmd == "G90":
            self.positioning_mode = "G90"
        elif cmd == "G91":
            self.positioning_mode = "G91"

        # Extrusion Mode
        elif cmd == "M82":
            self.extrusion_mode = "M82"
        elif cmd == "M83":
            self.extrusion_mode = "M83"

        # G92 E reset
        elif cmd == "G92":
            if "E" in params:
                self.curr_e = float(params["E"])
                self.g92_resets_count += 1
            if "X" in params:
                self.curr_x = float(params["X"])
            if "Y" in params:
                self.curr_y = float(params["Y"])
            if "Z" in params:
                self.curr_z = float(params["Z"])

        # Tool change
        elif cmd.startswith("T") and len(cmd) > 1 and cmd[1:].isdigit():
            self.curr_tool = int(cmd[1:])

        # Homing
        elif cmd == "G28":
            self.homing_lines.append(line_num)

        # Bed Leveling
        elif cmd in ("G29", "BED_MESH_CALIBRATE") or (cmd == "M420" and "S" in params and params["S"] > 0) or (cmd == "BED_MESH_PROFILE" and "LOAD" in params):
            self.bed_leveling_lines.append(line_num)

        # Firmware Retraction
        elif cmd in ("G10", "G11", "M207", "M208"):
            self.uses_firmware_retraction = True
            if cmd == "M207":
                if "S" in params:
                    self.retraction_distances.append(float(params["S"]))
                if "F" in params:
                    self.retraction_speeds.append(float(params["F"]) / 60.0)

        # Temperatures
        elif cmd in ("M104", "M109", "SET_HEATER_TEMPERATURE"):
            target_temp = None
            if "S" in params:
                target_temp = float(params["S"])
            elif "TARGET" in params:
                target_temp = float(params["TARGET"])

            if target_temp is not None:
                self.extruder_target_temp = target_temp
                self.extruder_temps_seen.append({"line": line_num, "temp": target_temp, "layer": self.current_layer})
                self.heating_order.append({"type": "nozzle", "line": line_num, "temp": target_temp})

            if cmd == "M109":
                self.wait_extruder_lines.append(line_num)

        elif cmd in ("M140", "M190"):
            target_temp = None
            if "S" in params:
                target_temp = float(params["S"])
            elif "TARGET" in params:
                target_temp = float(params["TARGET"])

            if target_temp is not None:
                self.bed_target_temp = target_temp
                self.bed_temps_seen.append({"line": line_num, "temp": target_temp, "layer": self.current_layer})
                self.heating_order.append({"type": "bed", "line": line_num, "temp": target_temp})

            if cmd == "M190":
                self.wait_bed_lines.append(line_num)

        # Fan control
        elif cmd == "M106":
            speed_val = 255.0
            if "S" in params:
                try:
                    speed_val = float(params["S"])
                except ValueError:
                    speed_val = 255.0

            if 0.0 < speed_val <= 1.0 and not isinstance(params.get("S"), int):
                speed_pct = speed_val * 100.0
            else:
                speed_pct = (speed_val / 255.0) * 100.0

            speed_pct = min(100.0, max(0.0, speed_pct))
            self.curr_fan_speed = speed_pct
            self.max_fan_speed_pct = max(self.max_fan_speed_pct, speed_pct)

            if speed_pct > 0 and self.current_layer <= 1:
                self.fan_on_first_layer = True

        elif cmd == "M107":
            self.curr_fan_speed = 0.0

        # Flow Rate Modifier
        elif cmd == "M221":
            if "S" in params:
                flow_pct = float(params["S"])
                self.flow_modifiers.append({"line": line_num, "percent": flow_pct})

        # Acceleration
        elif cmd in ("M201", "M204", "M205", "SET_VELOCITY_LIMIT"):
            raw_accel = f"{cmd} " + " ".join(f"{k}{v}" for k, v in params.items())
            self.acceleration_commands.append(raw_accel)

        # Time remaining M73
        elif cmd == "M73":
            if "R" in params:
                self.m73_times.append(float(params["R"]) * 60.0)

        # Movement commands G0, G1, G2, G3
        elif cmd in ("G0", "G1", "G2", "G3"):
            new_x = float(params["X"]) if "X" in params else self.curr_x
            new_y = float(params["Y"]) if "Y" in params else self.curr_y
            new_z = float(params["Z"]) if "Z" in params else self.curr_z
            feedrate = float(params["F"]) if "F" in params else self.curr_feedrate

            if feedrate is not None:
                self.curr_feedrate = feedrate

            feedrate_mm_s = (self.curr_feedrate / 60.0) if self.curr_feedrate else 30.0

            # Delta E calculation
            delta_e = 0.0
            if "E" in params:
                val_e = float(params["E"])
                if self.extrusion_mode == "M83":
                    delta_e = val_e
                    self.curr_e += delta_e
                else:  # M82 absolute
                    delta_e = val_e - self.curr_e
                    self.curr_e = val_e

                if self.curr_e > self.max_abs_e_seen:
                    self.max_abs_e_seen = self.curr_e

            # Calculate movement distance
            dx = (new_x - self.curr_x) if (new_x is not None and self.curr_x is not None) else 0.0
            dy = (new_y - self.curr_y) if (new_y is not None and self.curr_y is not None) else 0.0
            dz = (new_z - self.curr_z) if (new_z is not None and self.curr_z is not None) else 0.0
            dist = math.sqrt(dx * dx + dy * dy + dz * dz)

            # Kinematic time estimation approximation
            if dist > 0 and feedrate_mm_s > 0:
                self.kinematic_time_sec += dist / feedrate_mm_s

            # Update bounding box if extruding or moving
            if new_x is not None:
                self.curr_x = new_x
                if delta_e > 0:
                    self.min_x = min(self.min_x, new_x)
                    self.max_x = max(self.max_x, new_x)
            if new_y is not None:
                self.curr_y = new_y
                if delta_e > 0:
                    self.min_y = min(self.min_y, new_y)
                    self.max_y = max(self.max_y, new_y)
            if new_z is not None:
                self.curr_z = new_z
                if delta_e > 0:
                    self.min_z = min(self.min_z, new_z)
                    self.max_z = max(self.max_z, new_z)

            # Process Extrusion vs Travel vs Retraction
            if delta_e > 0:
                if self.first_extrusion_line is None:
                    self.first_extrusion_line = line_num
                self.last_extrusion_line = line_num

                self.total_extrusion_length += delta_e
                self.print_speeds.append(feedrate_mm_s)

                if self.current_layer <= 1:
                    self.first_layer_speeds.append(feedrate_mm_s)

                # Track Z height / layer change
                if new_z is not None and new_z != self.last_z_with_extrusion:
                    if self.last_z_with_extrusion is not None and new_z > self.last_z_with_extrusion:
                        if self.current_layer not in self.layer_z_map:
                            self.layer_z_map[self.current_layer] = new_z
                            if self.current_layer > 0:
                                prev_z = self.layer_z_map.get(self.current_layer - 1, 0.0)
                                h = round(new_z - prev_z, 4)
                                if h > 0:
                                    self.layer_heights.append(h)
                    self.last_z_with_extrusion = new_z

                self.layer_extrusion_counts[self.current_layer] = self.layer_extrusion_counts.get(self.current_layer, 0) + 1

                # Volumetric flow rate calculation Q = (A_fil * delta_e) / time
                if dist > 0 and feedrate_mm_s > 0:
                    move_time = dist / feedrate_mm_s
                    fil_dia = self.filament_diameter_detected or self.user_filament_diameter
                    fil_area = math.pi * ((fil_dia / 2.0) ** 2)
                    vol_mm3 = fil_area * delta_e
                    flow_rate = vol_mm3 / move_time if move_time > 0 else 0.0
                    if flow_rate < 100.0:
                        self.max_volumetric_flow = max(self.max_volumetric_flow, flow_rate)

                # Prime line check heuristic
                if self.lines_count < 200 and not self.has_prime_line:
                    if self.curr_z is not None and self.curr_z <= 0.4 and dist > 20.0 and delta_e > 1.0:
                        self.has_prime_line = True

            elif delta_e < 0:
                # Retraction
                self.retraction_count += 1
                ret_dist = abs(delta_e)
                self.retraction_distances.append(ret_dist)
                if feedrate_mm_s > 0:
                    self.retraction_speeds.append(feedrate_mm_s)

            else:
                # Travel move
                if dist > 0 and feedrate_mm_s > 0:
                    self.travel_speeds.append(feedrate_mm_s)

    def analyze_stream(self, stream):
        for line in stream:
            self.lines_count += 1
            cmd, params, comment = self.parse_line(line)

            if comment:
                self.inspect_comment(comment, self.lines_count)

            if cmd:
                self.process_command(cmd, params, comment, self.lines_count)

            # Check end heaters/motors commands
            if cmd in ("M104", "SET_HEATER_TEMPERATURE") and (params.get("S") == 0 or params.get("TARGET") == 0):
                self.has_end_heater_off = True
            if cmd in ("M140", "SET_HEATER_TEMPERATURE") and (params.get("S") == 0 or params.get("TARGET") == 0):
                self.has_end_bed_off = True
            if cmd == "M107" or (cmd == "M106" and params.get("S") == 0):
                self.has_end_fan_off = True
            if cmd in ("M84", "M18"):
                self.has_end_motor_off = True

        self.evaluate_rules_and_generate_issues()

    def add_issue(
        self,
        issue_id: str,
        severity: str,
        category: str,
        description: str,
        recommendation: str,
        line_number: Optional[int] = None,
        snippet: Optional[str] = None,
    ):
        issue = {
            "id": issue_id,
            "severity": severity,
            "category": category,
            "description": description,
            "recommendation": recommendation,
        }
        if line_number is not None:
            issue["line_number"] = line_number
        if snippet:
            issue["gcode_snippet"] = snippet

        self.issues.append(issue)

        msg = f"[{severity.upper()}] ({category}) {description}"
        if line_number:
            msg += f" (line {line_number})"
        self.warnings.append(msg)
        if recommendation and recommendation not in self.recommendations:
            self.recommendations.append(recommendation)

    def evaluate_rules_and_generate_issues(self):
        # 1. Start Gcode - Homing check
        if not self.homing_lines:
            self.add_issue(
                issue_id="MISSING_HOMING",
                severity="critical",
                category="Start Gcode",
                description="No homing command (G28) was detected in the file.",
                recommendation="Add G28 homing to your start Gcode before any movement or print commands.",
            )

        # Unsafe G28 after bed mesh check
        if self.homing_lines and self.bed_leveling_lines:
            last_homing = max(self.homing_lines)
            first_leveling = min(self.bed_leveling_lines)
            if last_homing > first_leveling and self.firmware_dialect in ("Marlin", "Standard RepRap / Marlin"):
                self.add_issue(
                    issue_id="UNSAFE_G28_AFTER_MESH",
                    severity="warning",
                    category="Start Gcode",
                    description=f"G28 (homing) at line {last_homing} is called AFTER bed leveling/mesh loading (line {first_leveling}). On Marlin firmware, G28 clears the active bed mesh.",
                    recommendation="Ensure G28 homing occurs BEFORE loading or creating the bed mesh (M420 S1 or G29).",
                    line_number=last_homing,
                    snippet="G28",
                )

        # Bed Leveling check
        if not self.bed_leveling_lines:
            self.add_issue(
                issue_id="MISSING_BED_LEVELING",
                severity="info",
                category="Start Gcode",
                description="No explicit bed leveling command (G29, M420 S1, or BED_MESH_CALIBRATE) was detected.",
                recommendation="If your printer has an ABL probe, add BED_MESH_CALIBRATE (Klipper) or M420 S1 (Marlin) to start Gcode.",
            )

        # Wait for heating before extrusion
        if self.first_extrusion_line is not None:
            if not self.wait_extruder_lines:
                self.add_issue(
                    issue_id="MISSING_EXTRUDER_WAIT_TEMP",
                    severity="warning",
                    category="Temperature",
                    description="No M109 wait command for extruder temperature was found before printing started.",
                    recommendation="Use M109 S[temp] to ensure the hotend reaches printing temperature before extruding.",
                    line_number=self.first_extrusion_line,
                )
            elif min(self.wait_extruder_lines) > self.first_extrusion_line:
                self.add_issue(
                    issue_id="EXTRUDING_BEFORE_HOTEND_READY",
                    severity="critical",
                    category="Temperature",
                    description=f"Extrusion begins at line {self.first_extrusion_line} before temperature wait command (M109) at line {min(self.wait_extruder_lines)}.",
                    recommendation="Move M109 temperature wait command before the first extrusion move.",
                    line_number=self.first_extrusion_line,
                )

        # Prime line check
        if not self.has_prime_line and self.total_extrusion_length > 0:
            self.add_issue(
                issue_id="MISSING_PRIME_LINE",
                severity="info",
                category="Start Gcode",
                description="No purge/prime line was detected before main object extrusion.",
                recommendation="Include a purge line in your start Gcode to prime nozzle pressure and clean stray filament before printing.",
            )

        # End Gcode completeness
        if not self.has_end_heater_off:
            self.add_issue(
                issue_id="HOTEND_LEFT_ON_AT_END",
                severity="critical",
                category="End Gcode",
                description="The Gcode file ends without turning off the hotend heater (M104 S0 / SET_HEATER_TEMPERATURE TARGET=0).",
                recommendation="Add 'M104 S0' to your end Gcode to prevent fire hazards and thermal runaway.",
            )

        if not self.has_end_bed_off and self.bed_target_temp > 0:
            self.add_issue(
                issue_id="BED_LEFT_ON_AT_END",
                severity="warning",
                category="End Gcode",
                description="The Gcode file ends without turning off the heated bed (M140 S0).",
                recommendation="Add 'M140 S0' to your end Gcode to disable the heated bed when printing completes.",
            )

        if not self.has_end_motor_off:
            self.add_issue(
                issue_id="MOTORS_NOT_DISABLED_AT_END",
                severity="info",
                category="End Gcode",
                description="No stepper motor disable command (M84 or M18) was detected in the end sequence.",
                recommendation="Add 'M84' to end Gcode to turn off stepper motors and allow free movement after printing.",
            )

        # Temperature Range checks
        if self.extruder_target_temp > 0:
            if self.extruder_target_temp < 170.0:
                self.add_issue(
                    issue_id="EXTRUDER_TEMP_VERY_LOW",
                    severity="warning",
                    category="Temperature",
                    description=f"Extruder temperature is set to {self.extruder_target_temp}°C, which is below standard printing range (<170°C). Cold extrusion risk!",
                    recommendation="Check slicer temperature settings. Common PLA printing temp is 190°C-220°C.",
                )
            elif self.extruder_target_temp > 285.0:
                self.add_issue(
                    issue_id="EXTRUDER_TEMP_HIGH",
                    severity="warning",
                    category="Temperature",
                    description=f"Extruder temperature is set to {self.extruder_target_temp}°C. Verify that your hotend has an all-metal break and proper thermistor rated for >285°C.",
                    recommendation="Ensure PTFE tube is not present in heatbreak at temperatures above 240°C.",
                )

        if self.bed_target_temp > 115.0:
            self.add_issue(
                issue_id="BED_TEMP_VERY_HIGH",
                severity="warning",
                category="Temperature",
                description=f"Bed target temperature is {self.bed_target_temp}°C, which exceeds typical safe limits (110°C).",
                recommendation="Reduce bed temperature unless using specialized engineering filaments like PEI/PEEK.",
            )

        # Heating order check
        nozzle_heat_lines = [h["line"] for h in self.heating_order if h["type"] == "nozzle"]
        bed_heat_lines = [h["line"] for h in self.heating_order if h["type"] == "bed"]
        if nozzle_heat_lines and bed_heat_lines:
            if min(nozzle_heat_lines) < min(bed_heat_lines):
                self.add_issue(
                    issue_id="NOZZLE_HEATING_BEFORE_BED",
                    severity="info",
                    category="Temperature",
                    description="Nozzle heating command appears before bed heating command. Because beds heat slowly, nozzle may sit hot for several minutes oozing filament.",
                    recommendation="Heat the bed first (M140/M190) before or alongside heating the nozzle (M104/M109).",
                )

        # Retraction Analysis
        if self.retraction_distances:
            max_ret_dist = max(self.retraction_distances)
            if max_ret_dist > 10.0:
                self.add_issue(
                    issue_id="EXTREME_RETRACTION_DISTANCE",
                    severity="warning",
                    category="Retraction",
                    description=f"Max retraction distance is {max_ret_dist:.1f}mm. Retractions above 10mm can pull molten plastic into cold zone causing heat creep clogs.",
                    recommendation="Reduce retraction distance (typically 0.5-2mm for direct drive, 3-6mm for bowden setups).",
                )

        if self.retraction_speeds:
            max_ret_speed = max(self.retraction_speeds)
            if max_ret_speed > 90.0:
                self.add_issue(
                    issue_id="FAST_RETRACTION_SPEED",
                    severity="warning",
                    category="Retraction",
                    description=f"Retraction speed is {max_ret_speed:.1f}mm/s. High retraction speeds can grind filament or slip extruder gears.",
                    recommendation="Keep retraction speeds between 25mm/s and 60mm/s.",
                )
            elif min(self.retraction_speeds) < 10.0:
                self.add_issue(
                    issue_id="SLOW_RETRACTION_SPEED",
                    severity="info",
                    category="Retraction",
                    description=f"Retraction speed is {min(self.retraction_speeds):.1f}mm/s, which may be too slow to prevent stringing.",
                    recommendation="Increase retraction speed to at least 25-35mm/s.",
                )

        # Speed Analysis
        if self.print_speeds:
            max_print_speed = max(self.print_speeds)
            if max_print_speed > 350.0:
                self.add_issue(
                    issue_id="VERY_HIGH_PRINT_SPEED",
                    severity="warning",
                    category="Speed",
                    description=f"Maximum print speed reaches {max_print_speed:.0f} mm/s. High speed requires high acceleration, tuned input shaping, and high flow hotend.",
                    recommendation="Verify stepper motor limits and input shaper tuning to prevent skipped steps.",
                )

        if self.first_layer_speeds and self.print_speeds:
            max_first_layer = max(self.first_layer_speeds)
            max_normal = max(self.print_speeds)
            if max_first_layer > 55.0 or (max_normal > 60.0 and max_first_layer > 0.6 * max_normal):
                self.add_issue(
                    issue_id="FAST_FIRST_LAYER_SPEED",
                    severity="warning",
                    category="Speed",
                    description=f"First layer speed reaches {max_first_layer:.0f} mm/s ({max_first_layer/max_normal*100:.0f}% of max speed). Printing layer 1 too fast risks bed detachment.",
                    recommendation="Set first layer print speed to 20-35 mm/s for optimal bed adhesion.",
                )

        if self.travel_speeds and self.print_speeds:
            if max(self.travel_speeds) < max(self.print_speeds):
                self.add_issue(
                    issue_id="TRAVEL_SLOWER_THAN_PRINT",
                    severity="info",
                    category="Speed",
                    description="Maximum travel speed is slower than maximum print speed. Slower travel moves increase total print time and stringing risk.",
                    recommendation="Set travel speeds higher than print speeds (e.g., 150-300 mm/s).",
                )

        # Layer Height Analysis
        if self.min_z != float("inf"):
            first_layer_h = self.min_z
            if first_layer_h < 0.08:
                self.add_issue(
                    issue_id="FIRST_LAYER_TOO_THIN",
                    severity="warning",
                    category="Layer Height",
                    description=f"First layer Z height is {first_layer_h:.3f}mm. Extremely thin initial layer risks nozzle scratching bed surface and extruder clogging.",
                    recommendation="Increase first layer height to at least 0.16mm - 0.28mm.",
                )
            elif first_layer_h > 0.36:
                self.add_issue(
                    issue_id="FIRST_LAYER_TOO_THICK",
                    severity="warning",
                    category="Layer Height",
                    description=f"First layer height is {first_layer_h:.2f}mm. Thick initial layer with standard 0.4mm nozzle reduces extrusion squish and bed adhesion.",
                    recommendation="Use first layer height between 0.20mm and 0.28mm for 0.4mm nozzle.",
                )

        # Units check
        if "G20" in self.units:
            self.add_issue(
                issue_id="IMPERIAL_UNITS_G20",
                severity="warning",
                category="Units",
                description="G20 command detected (Inches). Most 3D printers and firmware operate in metric (G21 millimeters).",
                recommendation="Configure your slicer to export Gcode in metric units (G21).",
            )

        # Volumetric Flow Rate check
        if self.max_volumetric_flow > 18.0:
            self.add_issue(
                issue_id="HIGH_VOLUMETRIC_FLOW_RATE",
                severity="warning",
                category="Flow Rate",
                description=f"Calculated peak volumetric flow rate is {self.max_volumetric_flow:.1f} mm³/s, exceeding standard hotend capacity (~12-15 mm³/s).",
                recommendation="Reduce print speed or layer height, or upgrade to a high-flow nozzle/hotend (e.g. CHT, Volcano).",
            )

        # Flow multiplier M221
        for mod in self.flow_modifiers:
            pct = mod["percent"]
            if pct < 80.0 or pct > 120.0:
                self.add_issue(
                    issue_id="EXTREME_FLOW_MULTIPLIER",
                    severity="warning",
                    category="Flow Rate",
                    description=f"Flow rate multiplier (M221) is set to {pct:.0f}% at line {mod['line']}.",
                    recommendation="Calibrate extruder rotation distance / e-steps instead of using extreme flow rate overrides.",
                    line_number=mod["line"],
                )

        # Fan on first layer
        if self.fan_on_first_layer:
            self.add_issue(
                issue_id="FAN_ON_FIRST_LAYER",
                severity="warning",
                category="Cooling",
                description="Part cooling fan is turned on during layer 0 or 1. Cooling early layers causes thermal shrinkage, warping, and poor bed adhesion.",
                recommendation="Disable part cooling fan for the first 1-3 layers in slicer cooling settings.",
            )

        # Large absolute E coordinate check
        if self.extrusion_mode == "M82" and self.max_abs_e_seen > 10000.0 and self.g92_resets_count == 0:
            self.add_issue(
                issue_id="LARGE_ABSOLUTE_E_VALUE",
                severity="info",
                category="Extrusion Mode",
                description=f"Absolute E coordinate reached {self.max_abs_e_seen:.1f}mm without any G92 E0 resets. Large E values can cause floating point precision errors in 32-bit firmware.",
                recommendation="Switch to relative extrusion mode (M83) or enable relative E in slicer settings.",
            )

    def generate_report(self, file_name: str = "input.gcode") -> Dict[str, Any]:
        # Calculate filament usage
        fil_dia = self.filament_diameter_detected or self.user_filament_diameter
        fil_radius_cm = (fil_dia / 10.0) / 2.0
        fil_area_cm2 = math.pi * (fil_radius_cm ** 2)

        total_length_cm = self.total_extrusion_length / 10.0
        volume_cm3 = fil_area_cm2 * total_length_cm

        densities = {
            "PLA": 1.24,
            "PETG": 1.27,
            "ABS": 1.04,
            "ASA": 1.07,
            "TPU": 1.21,
            "PC": 1.20,
            "PA": 1.14,
            "CF": 1.28,
        }
        density = self.user_filament_density or densities.get(self.filament_type_detected, 1.24)
        weight_g = volume_cm3 * density

        # Calculate print time estimation
        estimated_sec = 0.0
        time_source = "Kinematic approximation"
        if self.slicer_estimated_time_sec is not None:
            estimated_sec = self.slicer_estimated_time_sec
            time_source = "Slicer metadata"
        elif self.m73_times:
            estimated_sec = max(self.m73_times)
            time_source = "M73 commands"
        else:
            estimated_sec = self.kinematic_time_sec * 1.12

        hrs = int(estimated_sec // 3600)
        mins = int((estimated_sec % 3600) // 60)
        secs = int(estimated_sec % 60)
        formatted_time = f"{hrs}h {mins:02d}m {secs:02d}s" if hrs > 0 else f"{mins}m {secs:02d}s"

        has_bounds = self.min_x != float("inf")
        bounds = {
            "min_x": round(self.min_x, 2) if has_bounds else 0.0,
            "max_x": round(self.max_x, 2) if has_bounds else 0.0,
            "min_y": round(self.min_y, 2) if has_bounds else 0.0,
            "max_y": round(self.max_y, 2) if has_bounds else 0.0,
            "min_z": round(self.min_z, 2) if has_bounds else 0.0,
            "max_z": round(self.max_z, 2) if has_bounds else 0.0,
            "bounding_box_mm": {
                "width_x": round(self.max_x - self.min_x, 2) if has_bounds else 0.0,
                "depth_y": round(self.max_y - self.min_y, 2) if has_bounds else 0.0,
                "height_z": round(self.max_z - self.min_z, 2) if has_bounds else 0.0,
            },
        }

        critical_cnt = sum(1 for i in self.issues if i["severity"] == "critical")
        warning_cnt = sum(1 for i in self.issues if i["severity"] == "warning")
        info_cnt = sum(1 for i in self.issues if i["severity"] == "info")

        avg_layer_h = round(sum(self.layer_heights) / len(self.layer_heights), 4) if self.layer_heights else 0.2
        min_layer_h = round(min(self.layer_heights), 4) if self.layer_heights else (bounds["min_z"] if has_bounds else 0.2)
        max_layer_h = round(max(self.layer_heights), 4) if self.layer_heights else (bounds["min_z"] if has_bounds else 0.2)

        avg_print_speed = round(sum(self.print_speeds) / len(self.print_speeds), 1) if self.print_speeds else 0.0
        max_print_speed = round(max(self.print_speeds), 1) if self.print_speeds else 0.0
        max_travel_speed = round(max(self.travel_speeds), 1) if self.travel_speeds else 0.0
        first_layer_speed = round(sum(self.first_layer_speeds) / len(self.first_layer_speeds), 1) if self.first_layer_speeds else 0.0

        avg_ret_dist = round(sum(self.retraction_distances) / len(self.retraction_distances), 2) if self.retraction_distances else 0.0
        max_ret_dist = round(max(self.retraction_distances), 2) if self.retraction_distances else 0.0
        avg_ret_speed = round(sum(self.retraction_speeds) / len(self.retraction_speeds), 1) if self.retraction_speeds else 0.0

        report = {
            "summary": {
                "file_name": file_name,
                "total_lines": self.lines_count,
                "slicer_detected": f"{self.slicer_detected} {self.slicer_version}".strip(),
                "firmware_dialect": self.firmware_dialect,
                "estimated_print_time": {
                    "seconds": round(estimated_sec, 1),
                    "formatted": formatted_time,
                    "source": time_source,
                },
                "filament_usage": {
                    "length_mm": round(self.total_extrusion_length, 1),
                    "length_m": round(self.total_extrusion_length / 1000.0, 2),
                    "volume_cm3": round(volume_cm3, 2),
                    "weight_g": round(weight_g, 2),
                    "filament_type": self.filament_type_detected,
                    "filament_diameter_mm": fil_dia,
                    "density_g_cm3": density,
                },
                "dimensions": bounds,
                "layer_count": max(self.current_layer + 1, len(self.layer_z_map)),
                "temperatures": {
                    "extruder_target_c": self.extruder_target_temp,
                    "bed_target_c": self.bed_target_temp,
                },
                "speeds_mm_s": {
                    "max_print_speed": max_print_speed,
                    "avg_print_speed": avg_print_speed,
                    "max_travel_speed": max_travel_speed,
                    "first_layer_speed": first_layer_speed,
                },
                "layer_heights_mm": {
                    "first_layer": bounds["min_z"],
                    "min_layer": min_layer_h,
                    "max_layer": max_layer_h,
                    "avg_layer": avg_layer_h,
                },
                "issue_counts": {
                    "critical": critical_cnt,
                    "warning": warning_cnt,
                    "info": info_cnt,
                    "total": len(self.issues),
                },
            },
            "issues": self.issues,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
            "analysis_details": {
                "start_end_gcode": {
                    "has_homing": len(self.homing_lines) > 0,
                    "has_bed_leveling": len(self.bed_leveling_lines) > 0,
                    "has_extruder_heating": self.extruder_target_temp > 0,
                    "has_bed_heating": self.bed_target_temp > 0,
                    "has_wait_for_temp": len(self.wait_extruder_lines) > 0,
                    "has_prime_line": self.has_prime_line,
                    "has_end_heater_off": self.has_end_heater_off,
                    "has_end_bed_off": self.has_end_bed_off,
                    "has_end_fan_off": self.has_end_fan_off,
                    "has_end_motor_off": self.has_end_motor_off,
                },
                "temperature_analysis": {
                    "extruder_targets_c": sorted(list(set(t["temp"] for t in self.extruder_temps_seen))),
                    "bed_targets_c": sorted(list(set(t["temp"] for t in self.bed_temps_seen))),
                    "heating_events": len(self.heating_order),
                },
                "retraction_analysis": {
                    "retraction_count": self.retraction_count,
                    "uses_firmware_retraction": self.uses_firmware_retraction,
                    "avg_distance_mm": avg_ret_dist,
                    "max_distance_mm": max_ret_dist,
                    "avg_speed_mm_s": avg_ret_speed,
                },
                "speed_and_acceleration": {
                    "max_print_speed_mm_s": max_print_speed,
                    "max_travel_speed_mm_s": max_travel_speed,
                    "first_layer_speed_mm_s": first_layer_speed,
                    "acceleration_commands": self.acceleration_commands,
                },
                "flow_and_cooling": {
                    "max_volumetric_flow_mm3_s": round(self.max_volumetric_flow, 2),
                    "max_fan_speed_pct": round(self.max_fan_speed_pct, 1),
                    "fan_on_first_layer": self.fan_on_first_layer,
                    "flow_rate_modifiers": self.flow_modifiers,
                },
                "positioning_and_units": {
                    "units": self.units,
                    "positioning_mode": self.positioning_mode,
                    "extrusion_mode": self.extrusion_mode,
                    "g92_e_resets": self.g92_resets_count,
                },
                "firmware_dialect": {
                    "detected": self.firmware_dialect,
                    "confidence": self.firmware_confidence,
                    "indicators": sorted(list(self.firmware_indicators)),
                },
            },
        }

        return report


def main():
    parser = argparse.ArgumentParser(
        description="Comprehensive 3D Printing Gcode Analysis Tool & Skill"
    )
    parser.add_argument(
        "filepath",
        nargs="?",
        default="-",
        help="Path to Gcode file or '-' for stdin (default: stdin)",
    )
    parser.add_argument(
        "--filament-diameter",
        type=float,
        default=1.75,
        help="Filament diameter in mm (default: 1.75)",
    )
    parser.add_argument(
        "--filament-density",
        type=float,
        default=None,
        help="Filament density in g/cm3 (default: auto-detected based on filament type or 1.24 for PLA)",
    )
    parser.add_argument(
        "--nozzle-diameter",
        type=float,
        default=0.4,
        help="Nozzle diameter in mm (default: 0.4)",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Output only summary and issue counts",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Output compact single-line JSON",
    )

    args = parser.parse_args()

    analyzer = GCodeAnalyzer(
        filament_diameter=args.filament_diameter,
        filament_density=args.filament_density,
        nozzle_diameter=args.nozzle_diameter,
    )

    file_name = "stdin"

    if args.filepath == "-" or not args.filepath:
        if sys.stdin.isatty():
            print("Error: No input Gcode provided via file path or stdin.", file=sys.stderr)
            sys.exit(1)
        analyzer.analyze_stream(sys.stdin)
    else:
        file_path = Path(args.filepath)
        if not file_path.exists():
            print(f"Error: File not found: {args.filepath}", file=sys.stderr)
            sys.exit(1)
        file_name = file_path.name
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                analyzer.analyze_stream(f)
        except Exception as e:
            print(f"Error reading file {args.filepath}: {e}", file=sys.stderr)
            sys.exit(1)

    report = analyzer.generate_report(file_name=file_name)

    if args.summary_only:
        report = {
            "summary": report["summary"],
            "issue_counts": report["summary"]["issue_counts"],
            "warnings": report["warnings"],
            "recommendations": report["recommendations"],
        }

    indent = None if args.compact else 2
    print(json.dumps(report, indent=indent, ensure_ascii=False))


if __name__ == "__main__":
    main()
