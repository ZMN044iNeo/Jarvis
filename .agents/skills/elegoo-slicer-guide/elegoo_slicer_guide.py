#!/usr/bin/env python3
"""
Elegoo Slicer Guide & Recommendations Generator
------------------------------------------------
Provides comprehensive 3D printing slicer settings recommendations tailored for
Elegoo Slicer (Cura / Orca engine based) and Elegoo FDM/Resin printers.

Supports materials: PLA, PETG, ABS, TPU, ASA, PC, Nylon (PA), PLA+, Silk PLA, Wood PLA, CF-composites.
Supports quality targets: draft, standard, high, ultra.
Supports printer types: FDM, Resin.
Supports nozzle sizes: 0.2mm, 0.4mm, 0.6mm, 0.8mm.
Supports issue-based targeted troubleshooting adjustments (stringing, warping, adhesion, etc.).

Usage via CLI:
    python3 .agents/skills/elegoo-slicer-guide/elegoo_slicer_guide.py --material PLA --quality standard
    python3 .agents/skills/elegoo-slicer-guide/elegoo_slicer_guide.py --material PETG --quality high --issue stringing --nozzle-size 0.4
    python3 .agents/skills/elegoo-slicer-guide/elegoo_slicer_guide.py --json '{"material": "ABS", "quality": "draft", "issue": "warping"}'

Usage via stdin:
    echo '{"material": "TPU", "quality": "standard"}' | python3 .agents/skills/elegoo-slicer-guide/elegoo_slicer_guide.py
"""

import argparse
import json
import os
import select
import sys
from typing import Any, Dict, List, Optional, Tuple, Union


# ==============================================================================
# Material Profiles Database
# ==============================================================================

MATERIAL_PROFILES: Dict[str, Dict[str, Any]] = {
    "PLA": {
        "full_name": "Polylactic Acid (PLA / PLA+)",
        "aliases": ["pla", "pla+", "pla_plus", "silk_pla", "wood_pla", "pla_cf"],
        "ease_of_use": "Beginner (Very Easy)",
        "enclosure_required": False,
        "filament_drying_required": False,
        "drying_recommendation": "Not strictly necessary unless exposed to high humidity. If brittle, dry at 45-50°C for 4 hours.",
        "bed_preparation": "Clean PEI sheet with 90%+ Isopropyl Alcohol (IPA). Standard glass or textured PEI plate.",
        "notes": "Easiest material to print. Excellent detail, low shrinkage, minimal warping. Needs active cooling fan.",
        "base_temps": {
            "extruder": 205,
            "extruder_min": 190,
            "extruder_max": 220,
            "bed": 60,
            "bed_min": 50,
            "bed_max": 65,
        },
        "cooling": {
            "enable": True,
            "fan_speed_percent": 100,
            "min_fan_speed": 100,
            "max_fan_speed": 100,
            "initial_layer_fan": 0,
            "regular_fan_at_layer": 2,
            "aux_fan_speed": 50,
        },
        "flow_rate": 100.0,
        "retraction_distance_direct": 0.8,
        "retraction_distance_bowden": 5.0,
        "retraction_speed": 40,
        "speed_factor": 1.0,
        "z_offset_adj": 0.0,
        "default_adhesion": "skirt",
    },
    "PETG": {
        "full_name": "Polyethylene Terephthalate Glycol (PETG)",
        "aliases": ["petg", "petg_cf", "pet"],
        "ease_of_use": "Intermediate",
        "enclosure_required": False,
        "filament_drying_required": True,
        "drying_recommendation": "Recommended before printing: 60-65°C for 4-6 hours in filament dryer.",
        "bed_preparation": "Clean PEI sheet with IPA. Use glue stick or hairspray on smooth PEI/glass as a release agent to prevent glass chipping.",
        "notes": "Strong, impact & chemical resistant. Prone to stringing and nozzle buildup. Likes slightly less squish on first layer.",
        "base_temps": {
            "extruder": 240,
            "extruder_min": 230,
            "extruder_max": 250,
            "bed": 75,
            "bed_min": 70,
            "bed_max": 85,
        },
        "cooling": {
            "enable": True,
            "fan_speed_percent": 40,
            "min_fan_speed": 30,
            "max_fan_speed": 60,
            "initial_layer_fan": 0,
            "regular_fan_at_layer": 3,
            "aux_fan_speed": 0,
        },
        "flow_rate": 98.0,
        "retraction_distance_direct": 1.0,
        "retraction_distance_bowden": 6.0,
        "retraction_speed": 35,
        "speed_factor": 0.8,
        "z_offset_adj": 0.03,  # PETG likes slight gap to prevent nozzle sticking
        "default_adhesion": "brim",
    },
    "ABS": {
        "full_name": "Acrylonitrile Butadiene Styrene (ABS)",
        "aliases": ["abs", "abs_plus"],
        "ease_of_use": "Advanced",
        "enclosure_required": True,
        "filament_drying_required": True,
        "drying_recommendation": "Dry at 65-70°C for 4-6 hours if stored in open air.",
        "bed_preparation": "Textured PEI plate or glue stick/ABS juice on smooth surface. Enclosure ambient temp 40-50°C.",
        "notes": "High heat resistance & toughness. Prone to severe warping and corner lifting without enclosure and draft protection.",
        "base_temps": {
            "extruder": 245,
            "extruder_min": 235,
            "extruder_max": 260,
            "bed": 100,
            "bed_min": 95,
            "bed_max": 110,
        },
        "cooling": {
            "enable": False,  # Off or very minimal
            "fan_speed_percent": 0,
            "min_fan_speed": 0,
            "max_fan_speed": 20,
            "initial_layer_fan": 0,
            "regular_fan_at_layer": 4,
            "aux_fan_speed": 0,
        },
        "flow_rate": 100.0,
        "retraction_distance_direct": 0.8,
        "retraction_distance_bowden": 4.5,
        "retraction_speed": 40,
        "speed_factor": 0.9,
        "z_offset_adj": -0.01,
        "default_adhesion": "brim",
    },
    "TPU": {
        "full_name": "Thermoplastic Polyurethane (TPU / Flexible 95A/85A)",
        "aliases": ["tpu", "tpe", "flexible"],
        "ease_of_use": "Intermediate to Advanced",
        "enclosure_required": False,
        "filament_drying_required": True,
        "drying_recommendation": "Highly moisture sensitive! Dry at 50-55°C for 6-8 hours before printing.",
        "bed_preparation": "Textured PEI plate or blue painter's tape / glue stick on glass as release agent.",
        "notes": "Flexible elastomer. Must print SLOWLY (15-35 mm/s). Direct drive strongly recommended. Minimal/zero retraction.",
        "base_temps": {
            "extruder": 225,
            "extruder_min": 210,
            "extruder_max": 240,
            "bed": 50,
            "bed_min": 40,
            "bed_max": 60,
        },
        "cooling": {
            "enable": True,
            "fan_speed_percent": 80,
            "min_fan_speed": 50,
            "max_fan_speed": 100,
            "initial_layer_fan": 0,
            "regular_fan_at_layer": 2,
            "aux_fan_speed": 0,
        },
        "flow_rate": 103.0,
        "retraction_distance_direct": 0.5,  # Very short or 0 to prevent jamming
        "retraction_distance_bowden": 0.0,  # Turn off retraction on Bowden TPU
        "retraction_speed": 20,
        "speed_factor": 0.35,  # Much slower
        "z_offset_adj": 0.02,
        "default_adhesion": "skirt",
    },
    "ASA": {
        "full_name": "Acrylonitrile Styrene Acrylate (ASA)",
        "aliases": ["asa"],
        "ease_of_use": "Advanced",
        "enclosure_required": True,
        "filament_drying_required": True,
        "drying_recommendation": "Dry at 65-70°C for 4-6 hours.",
        "bed_preparation": "Textured PEI or glue stick. Enclosure recommended to prevent layer delamination.",
        "notes": "UV-resistant alternative to ABS. High strength and weather resistance. Warps easily without enclosure.",
        "base_temps": {
            "extruder": 250,
            "extruder_min": 240,
            "extruder_max": 265,
            "bed": 100,
            "bed_min": 90,
            "bed_max": 110,
        },
        "cooling": {
            "enable": False,
            "fan_speed_percent": 10,
            "min_fan_speed": 0,
            "max_fan_speed": 20,
            "initial_layer_fan": 0,
            "regular_fan_at_layer": 4,
            "aux_fan_speed": 0,
        },
        "flow_rate": 100.0,
        "retraction_distance_direct": 0.8,
        "retraction_distance_bowden": 4.5,
        "retraction_speed": 40,
        "speed_factor": 0.9,
        "z_offset_adj": -0.01,
        "default_adhesion": "brim",
    },
    "PC": {
        "full_name": "Polycarbonate (PC / PC-ABS)",
        "aliases": ["pc", "polycarbonate", "pc_abs"],
        "ease_of_use": "Expert",
        "enclosure_required": True,
        "filament_drying_required": True,
        "drying_recommendation": "Extremely hydroscopic! Dry at 75-80°C for 8-10 hours.",
        "bed_preparation": "Enclosure mandatory (50-70°C ambient). Glue stick or specialized bed adhesive on PEI.",
        "notes": "Extremely high strength and heat resistance (110°C+). Very high printing temperature, high tendency to warp.",
        "base_temps": {
            "extruder": 275,
            "extruder_min": 260,
            "extruder_max": 295,
            "bed": 110,
            "bed_min": 100,
            "bed_max": 120,
        },
        "cooling": {
            "enable": False,
            "fan_speed_percent": 0,
            "min_fan_speed": 0,
            "max_fan_speed": 10,
            "initial_layer_fan": 0,
            "regular_fan_at_layer": 5,
            "aux_fan_speed": 0,
        },
        "flow_rate": 100.0,
        "retraction_distance_direct": 1.0,
        "retraction_distance_bowden": 5.0,
        "retraction_speed": 35,
        "speed_factor": 0.7,
        "z_offset_adj": 0.0,
        "default_adhesion": "brim",
    },
    "Nylon": {
        "full_name": "Nylon (Polyamide / PA6 / PA12 / PA-CF)",
        "aliases": ["nylon", "pa", "pa6", "pa12", "pa_cf", "pa12_cf"],
        "ease_of_use": "Expert",
        "enclosure_required": True,
        "filament_drying_required": True,
        "drying_recommendation": "CRITICAL: Must dry at 75-80°C for 8-12 hours and print directly from a dry box!",
        "bed_preparation": "Garolite (FR4) sheet or heavy PVA glue stick on PEI/glass.",
        "notes": "Exceptional mechanical strength, toughness, and fatigue resistance. Absorbs moisture within hours of exposure.",
        "base_temps": {
            "extruder": 265,
            "extruder_min": 250,
            "extruder_max": 285,
            "bed": 85,
            "bed_min": 75,
            "bed_max": 100,
        },
        "cooling": {
            "enable": False,
            "fan_speed_percent": 0,
            "min_fan_speed": 0,
            "max_fan_speed": 15,
            "initial_layer_fan": 0,
            "regular_fan_at_layer": 4,
            "aux_fan_speed": 0,
        },
        "flow_rate": 98.0,
        "retraction_distance_direct": 1.0,
        "retraction_distance_bowden": 5.0,
        "retraction_speed": 35,
        "speed_factor": 0.7,
        "z_offset_adj": 0.0,
        "default_adhesion": "raft",
    },
}


# ==============================================================================
# Quality Profile Definitions
# ==============================================================================

QUALITY_PROFILES: Dict[str, Dict[str, Any]] = {
    "draft": {
        "layer_height_ratio": 0.70,  # multiplier of nozzle size (e.g. 0.28mm for 0.4 nozzle)
        "wall_count": 2,
        "top_layers": 3,
        "bottom_layers": 3,
        "infill_density": 10,
        "base_speed_fdm": 80,  # mm/s base
        "description": "Fast print speed, visible layer lines, suitable for rapid prototyping and functional test fits.",
    },
    "standard": {
        "layer_height_ratio": 0.50,  # 0.20mm for 0.4 nozzle
        "wall_count": 3,
        "top_layers": 4,
        "bottom_layers": 4,
        "infill_density": 15,
        "base_speed_fdm": 60,  # mm/s base
        "description": "Balanced speed and visual surface finish. Best general-purpose setting.",
    },
    "high": {
        "layer_height_ratio": 0.30,  # 0.12mm for 0.4 nozzle
        "wall_count": 4,
        "top_layers": 5,
        "bottom_layers": 5,
        "infill_density": 20,
        "base_speed_fdm": 45,  # mm/s base
        "description": "Smooth surface finish, crisp details, ideal for display models or tight tolerances.",
    },
    "ultra": {
        "layer_height_ratio": 0.20,  # 0.08mm for 0.4 nozzle
        "wall_count": 4,
        "top_layers": 6,
        "bottom_layers": 6,
        "infill_density": 25,
        "base_speed_fdm": 35,  # mm/s base
        "description": "Maximum vertical resolution and detail. Longest print times, almost invisible layer lines.",
    },
}


# ==============================================================================
# Printer Profiles & Defaults
# ==============================================================================

PRINTER_MODELS: Dict[str, Dict[str, Any]] = {
    "neptune_4": {
        "name": "Elegoo Neptune 4 / 4 Pro / 4 Plus / 4 Max",
        "type": "FDM",
        "extruder_type": "Direct Drive (Dual-Gear)",
        "firmware": "Klipper",
        "max_speed_mm_s": 250,
        "default_acceleration": 3000,
        "travel_acceleration": 5000,
        "aux_fan_available": True,
    },
    "neptune_3": {
        "name": "Elegoo Neptune 3 / 3 Pro / 3 Plus / 3 Max",
        "type": "FDM",
        "extruder_type": "Direct Drive (Dual-Gear)",
        "firmware": "Marlin",
        "max_speed_mm_s": 120,
        "default_acceleration": 1500,
        "travel_acceleration": 2500,
        "aux_fan_available": False,
    },
    "mars_saturn": {
        "name": "Elegoo Mars / Saturn Series (Resin MSLA)",
        "type": "Resin",
        "firmware": "Chitu/Elegoo Resin OS",
    },
}


# ==============================================================================
# Helper Functions
# ==============================================================================

def normalize_material_name(raw_material: str) -> str:
    """Normalize input material string to standard profile key."""
    clean = raw_material.strip().upper().replace("-", "_").replace(" ", "_")
    
    for key, prof in MATERIAL_PROFILES.items():
        if clean == key:
            return key
        if raw_material.strip().lower() in [a.lower() for a in prof.get("aliases", [])]:
            return key

    # Partial match fallback
    if "PLA" in clean:
        return "PLA"
    if "PETG" in clean or "PET" in clean:
        return "PETG"
    if "ABS" in clean:
        return "ABS"
    if "TPU" in clean or "FLEX" in clean:
        return "TPU"
    if "ASA" in clean:
        return "ASA"
    if "PC" in clean or "POLYCARB" in clean:
        return "PC"
    if "NYLON" in clean or "PA" in clean:
        return "Nylon"

    return "PLA"  # Default fallback


def normalize_quality(raw_quality: Optional[str]) -> str:
    """Normalize quality target string."""
    if not raw_quality:
        return "standard"
    clean = raw_quality.strip().lower()
    if clean in QUALITY_PROFILES:
        return clean
    if "draft" in clean or "fast" in clean or "low" in clean:
        return "draft"
    if "high" in clean or "fine" in clean:
        return "high"
    if "ultra" in clean or "best" in clean or "detail" in clean:
        return "ultra"
    return "standard"


def normalize_printer_type(raw_type: Optional[str], raw_model: Optional[str] = None) -> str:
    """Determine if printer is FDM or Resin."""
    if raw_type:
        clean_t = raw_type.strip().lower()
        if "resin" in clean_t or "msla" in clean_t or "lcd" in clean_t:
            return "Resin"
        if "fdm" in clean_t or "fff" in clean_t:
            return "FDM"

    if raw_model:
        clean_m = raw_model.strip().lower()
        if "mars" in clean_m or "saturn" in clean_m or "jupiter" in clean_m:
            return "Resin"

    return "FDM"


# ==============================================================================
# Troubleshooting Engine
# ==============================================================================

def analyze_issue(
    issue_raw: str,
    material_key: str,
    printer_type: str,
    nozzle_size: float
) -> Dict[str, Any]:
    """Provide targeted overrides and actionable troubleshooting steps for reported issue."""
    issue_clean = issue_raw.strip().lower().replace(" ", "_").replace("-", "_")
    overrides: List[Dict[str, Any]] = []
    action_steps: List[str] = []
    root_cause = ""

    if any(kw in issue_clean for kw in ["string", "ooz", "blob", "wisps"]):
        issue_name = "Stringing & Oozing"
        root_cause = "Molten plastic leaking during non-printing travel moves due to insufficient retraction or excessive hotend temperature."
        overrides = [
            {"setting": "retraction_distance_mm", "adjustment": "+0.3 to +0.8 mm", "reason": "Pulls filament back further from nozzle melt zone"},
            {"setting": "retraction_speed_mm_s", "value": 45, "reason": "Faster retraction snaps molten thread cleanly"},
            {"setting": "extruder_temperature_c", "adjustment": "-5°C to -10°C", "reason": "Lowers molten plastic viscosity to reduce oozing"},
            {"setting": "combing_mode", "value": "Not in Outer Surface", "reason": "Keeps travel moves inside infill boundaries"},
            {"setting": "wipe_while_retracting", "value": True, "reason": "Wipes nozzle tip against wall while retracting"},
        ]
        action_steps = [
            "Verify filament dry state: Wet PETG, TPU, and Nylon are the #1 cause of uncontrollable stringing.",
            "Perform a retraction calibration tower to find exact sweet spot.",
            "Lower hotend temperature by 5°C increments.",
            "Enable 'Avoid Printed Parts When Traveling' in Elegoo Slicer travel options."
        ]

    elif any(kw in issue_clean for kw in ["warp", "lift", "curl", "corner"]):
        issue_name = "Warping & Corner Lifting"
        root_cause = "Thermal contraction as extruded plastic cools and shrinks rapidly, pulling away from build plate."
        overrides = [
            {"setting": "adhesion_type", "value": "brim", "reason": "Increases first layer contact area with build plate"},
            {"setting": "brim_width_mm", "value": 8.0, "reason": "Provides mechanical anchor for outer corners"},
            {"setting": "bed_temperature_c", "adjustment": "+5°C", "reason": "Keeps bottom layers above glass transition temperature longer"},
            {"setting": "initial_layer_fan_speed_percent", "value": 0, "reason": "Prevents premature cooling of initial layers"},
            {"setting": "fan_regular_speed_at_layer", "value": 4, "reason": "Delays full fan cooling until 4th layer"},
        ]
        action_steps = [
            "Wash PEI build plate thoroughly with warm water and dish soap (Dawn) to remove skin oils, then rinse with 90%+ IPA.",
            "Eliminate room drafts: AC vents, fans, or open windows cause rapid uneven cooling.",
            "For ABS/ASA/PC: An enclosure is strictly required to keep ambient air temperature at 40-50°C.",
            "Ensure nozzle Z-offset is correctly adjusted to provide adequate first-layer squish."
        ]

    elif any(kw in issue_clean for kw in ["adhesion", "stick", "first_layer", "peel"]):
        issue_name = "Poor Bed Adhesion / First Layer Not Sticking"
        root_cause = "Incorrect Z-offset distance, dirty build surface, or improper initial layer print speed and temperature."
        overrides = [
            {"setting": "initial_layer_speed_mm_s", "value": 15, "reason": "Gives molten plastic maximum time to bond to build plate"},
            {"setting": "initial_layer_line_width_percent", "value": 130, "reason": "Extrudes wider plastic bead for superior surface area contact"},
            {"setting": "initial_layer_extruder_temp_c", "adjustment": "+5°C", "reason": "Higher initial temperature improves molten polymer wetting"},
            {"setting": "initial_layer_bed_temp_c", "adjustment": "+5°C", "reason": "Enhances bed heat transfer to first layer"},
            {"setting": "adhesion_type", "value": "brim", "reason": "Adds outer stability border"},
        ]
        action_steps = [
            "Re-level bed (tramming) using standard paper gauge or feeler gauge at 4 corners.",
            "Adjust Z-offset: Lower Z height in 0.02mm increments until lines squeeze together without gaps or rough ridges.",
            "Clean build plate with IPA or PVA glue stick depending on surface type.",
            "Disable initial layer fan completely for the first 2-3 layers."
        ]

    elif any(kw in issue_clean for kw in ["elephant", "squish", "foot"]):
        issue_name = "Elephant's Foot (First Layer Bulge)"
        root_cause = "Excessive first layer squish, overly hot bed temperature, or weight of upper layers compressing molten bottom layer."
        overrides = [
            {"setting": "initial_layer_horizontal_expansion_mm", "value": -0.15, "reason": "Compensates mathematically for first layer flare"},
            {"setting": "z_offset_recommendation", "adjustment": "+0.02mm higher", "reason": "Relieves excessive initial layer compression"},
            {"setting": "initial_layer_bed_temp_c", "adjustment": "-5°C after layer 1", "reason": "Prevents plastic at bottom from remaining semi-molten"},
        ]
        action_steps = [
            "Slightly raise Z-offset gap.",
            "Use Elegoo Slicer's 'Initial Layer Horizontal Expansion' setting set to -0.15mm.",
            "Ensure bed temp isn't set above glass transition point after layer 1."
        ]

    elif any(kw in issue_clean for kw in ["split", "layer_sep", "delaminat", "crack"]):
        issue_name = "Layer Separation & Delamination"
        root_cause = "Weak inter-layer bonding due to insufficient nozzle heat, excessive cooling fan, or high print speed."
        overrides = [
            {"setting": "extruder_temperature_c", "adjustment": "+5°C to +10°C", "reason": "Increases thermal fusion between adjacent layers"},
            {"setting": "fan_speed_percent", "adjustment": "-50%", "reason": "Reduces cooling so layer below stays hot enough to bond"},
            {"setting": "print_speed_mm_s", "adjustment": "-20%", "reason": "Increases heat transfer time per unit area"},
            {"setting": "wall_line_count", "adjustment": "+1 wall", "reason": "Adds structural perimeter strength"},
        ]
        action_steps = [
            "Increase hotend temperature closer to material maximum.",
            "Reduce or completely disable cooling fan (especially for ABS, ASA, PETG, Nylon).",
            "Use an enclosure to maintain ambient warmth.",
            "Check for dry filament—absorbed moisture severely degrades tensile layer strength."
        ]

    elif any(kw in issue_clean for kw in ["under_extru", "gap", "hole", "thin"]):
        issue_name = "Under-Extrusion"
        root_cause = "Less filament extruded than commanded, caused by clogged nozzle, low temperature, slipping extruder gears, or incorrect flow."
        overrides = [
            {"setting": "flow_rate_percent", "adjustment": "+3% to +5%", "reason": "Increases volume of extruded plastic"},
            {"setting": "extruder_temperature_c", "adjustment": "+5°C to +10°C", "reason": "Reduces backpressure in hotend melt zone"},
            {"setting": "print_speed_mm_s", "adjustment": "-20%", "reason": "Allows extruder gear to push plastic without skipping"},
        ]
        action_steps = [
            "Perform cold pull or nozzle needle cleaning to clear partial hotend clog.",
            "Verify filament diameter (1.75mm) and check if extruder gear tension spring is tight.",
            "Calibrate Extruder E-steps in firmware.",
            "Check for heat creep in hotend heatsink."
        ]

    elif any(kw in issue_clean for kw in ["over_extru", "ridge", "rough_top"]):
        issue_name = "Over-Extrusion"
        root_cause = "Excess filament deposited, causing overflowing ridges, dimensional inaccuracy, and top surface rough spots."
        overrides = [
            {"setting": "flow_rate_percent", "value": 95.0, "reason": "Reduces total flow volume to prevent excess plastic buildup"},
            {"setting": "top_bottom_flow_percent", "value": 93.0, "reason": "Smooths out top solid layers"},
        ]
        action_steps = [
            "Calibrate Flow Rate / Extrusion Multiplier in slicer using a single-wall calibration cube.",
            "Calibrate E-steps in Klipper/Marlin.",
            "Ensure correct nozzle size setting selected in Elegoo Slicer (e.g. 0.4mm)."
        ]

    elif any(kw in issue_clean for kw in ["seam", "zit", "pimple", "rough"]):
        issue_name = "Z-Seam Visibility / Surface Zits"
        root_cause = "Start and end points of perimeter loops leaving visible blobs or marks along outer surface."
        overrides = [
            {"setting": "z_seam_alignment", "value": "User Specified", "reason": "Consolidates seam to non-visible location"},
            {"setting": "z_seam_position", "value": "Back / Sharpest Corner", "reason": "Hides seam along rear edge or inner vertex"},
            {"setting": "outer_wall_speed_mm_s", "value": 30, "reason": "Provides uniform pressure for clean perimeter finish"},
            {"setting": "coasting_enable", "value": True, "reason": "Stops extrusion just before end of path to utilize residual nozzle pressure"},
        ]
        action_steps = [
            "Set Z Seam Alignment to 'Sharpest Corner' and Seam Corner Preference to 'Hide Seam'.",
            "Enable Pressure Advance (Klipper) or Linear Advance (Marlin) to sharpen corner transitions.",
            "Dry filament to prevent steam pop zits on walls."
        ]

    elif any(kw in issue_clean for kw in ["bridge", "droop", "sag"]):
        issue_name = "Bridging & Sagging"
        root_cause = "Extruded plastic sagging across open gaps before cooling fan can solidify thread."
        overrides = [
            {"setting": "bridge_fan_speed_percent", "value": 100, "reason": "Instantly freezes plastic thread suspended in mid-air"},
            {"setting": "bridge_speed_mm_s", "value": 25, "reason": "Maintains proper tension on suspended plastic filament"},
            {"setting": "bridge_flow_percent", "value": 92.0, "reason": "Prevents heavy plastic bead from pulling bridge down"},
        ]
        action_steps = [
            "Ensure part cooling fan operates at 100% during bridging moves.",
            "Orient print in slicer to minimize maximum bridging span distance.",
            "Enable supports if gap distance exceeds 25-30mm."
        ]

    else:
        issue_name = f"Custom Issue: {issue_raw}"
        root_cause = "General printing anomaly reported."
        overrides = [
            {"setting": "print_speed_mm_s", "adjustment": "-15%", "reason": "Slower speed improves print fidelity"},
            {"setting": "extruder_temperature_c", "adjustment": "Verify within filament range", "reason": "Ensures proper viscosity"},
        ]
        action_steps = [
            "Check mechanical bed tramming, Z-offset height, and nozzle cleanliness.",
            "Ensure filament is dry and fed smoothly from spool holder."
        ]

    return {
        "issue_identified": issue_name,
        "root_cause": root_cause,
        "recommended_overrides": overrides,
        "actionable_troubleshooting_steps": action_steps,
    }


# ==============================================================================
# Settings Generator
# ==============================================================================

def generate_recommendations(
    material_raw: str,
    quality_raw: Optional[str] = "standard",
    printer_type_raw: Optional[str] = "FDM",
    printer_model_raw: Optional[str] = None,
    nozzle_size: float = 0.4,
    issue_raw: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate full structured slicer settings recommendations."""
    
    mat_key = normalize_material_name(material_raw)
    mat_prof = MATERIAL_PROFILES[mat_key]
    qual_key = normalize_quality(quality_raw)
    qual_prof = QUALITY_PROFILES[qual_key]
    p_type = normalize_printer_type(printer_type_raw, printer_model_raw)

    # Determine printer profile details
    p_model_key = "neptune_4"
    if printer_model_raw:
        pm_clean = printer_model_raw.lower()
        if "3" in pm_clean:
            p_model_key = "neptune_3"
        elif "mars" in pm_clean or "saturn" in pm_clean:
            p_model_key = "mars_saturn"

    p_info = PRINTER_MODELS.get(p_model_key, PRINTER_MODELS["neptune_4"])

    # --------------------------------------------------------------------------
    # FDM Calculations
    # --------------------------------------------------------------------------
    
    # Layer height scaling based on nozzle size & quality profile
    layer_height = round(nozzle_size * qual_prof["layer_height_ratio"], 2)
    # Clamp layer height safety (max 75% of nozzle size, min 0.05mm)
    layer_height = max(0.05, min(layer_height, round(nozzle_size * 0.75, 2)))
    
    initial_layer_height = round(min(nozzle_size * 0.70, 0.28), 2)
    line_width = round(nozzle_size * 1.05, 2)
    outer_wall_line_width = round(nozzle_size * 1.0, 2)
    
    wall_count = qual_prof["wall_count"]
    wall_thickness = round(wall_count * line_width, 2)
    top_layers = qual_prof["top_layers"]
    bottom_layers = qual_prof["bottom_layers"]
    top_bottom_thickness = round(top_layers * layer_height, 2)

    # Infill density & pattern
    infill_density = qual_prof["infill_density"]
    infill_pattern = "gyroid" if mat_key in ["PETG", "TPU"] else "cubic"

    # Temperatures & Flow
    temps = mat_prof["base_temps"]
    extruder_temp = temps["extruder"]
    bed_temp = temps["bed"]
    initial_layer_extruder_temp = extruder_temp + 5
    initial_layer_bed_temp = bed_temp + 5
    flow_rate = mat_prof["flow_rate"]

    # Speed calculations based on quality, material factor, and printer
    base_speed = qual_prof["base_speed_fdm"]
    # If high-speed Neptune 4 printer
    if p_info.get("firmware") == "Klipper":
        base_speed = int(base_speed * 1.8)

    # Material speed factor adjustment (e.g. TPU prints much slower)
    effective_speed = max(18, int(base_speed * mat_prof["speed_factor"]))
    
    infill_speed = effective_speed
    outer_wall_speed = int(effective_speed * 0.5)
    inner_wall_speed = int(effective_speed * 0.75)
    initial_layer_speed = min(25, int(effective_speed * 0.35))
    travel_speed = p_info.get("max_speed_mm_s", 150)
    bridge_speed = min(30, int(effective_speed * 0.45))

    # Acceleration & Jerk
    print_accel = p_info.get("default_acceleration", 2000)
    travel_accel = p_info.get("travel_acceleration", 3500)
    if mat_key == "TPU":
        print_accel = 800
        travel_accel = 1500

    # Retraction
    is_direct_drive = "Direct" in p_info.get("extruder_type", "Direct Drive")
    if is_direct_drive:
        retraction_dist = mat_prof["retraction_distance_direct"]
    else:
        retraction_dist = mat_prof["retraction_distance_bowden"]

    # Z-Offset Recommendation
    base_z_adj = mat_prof["z_offset_adj"]
    if base_z_adj > 0:
        z_offset_note = f"Standard gap +{base_z_adj:.2f}mm (slightly looser squish to prevent nozzle drags/sticking)"
    elif base_z_adj < 0:
        z_offset_note = f"Standard gap {base_z_adj:.2f}mm (firm squish into bed texturing)"
    else:
        z_offset_note = "Standard paper test gauge gap (first layer lines smoothly touching without ridge buildup)"

    # Bed Adhesion
    adhesion_type = mat_prof["default_adhesion"]
    brim_width = 8.0 if adhesion_type == "brim" else 0.0

    # Cooling
    cooling_info = mat_prof["cooling"]

    # --------------------------------------------------------------------------
    # Build Structured Response
    # --------------------------------------------------------------------------

    response: Dict[str, Any] = {
        "request_summary": {
            "material": mat_key,
            "quality_target": qual_key,
            "printer_type": p_type,
            "printer_model": printer_model_raw or p_info["name"],
            "nozzle_size_mm": nozzle_size,
            "issue_specified": issue_raw or None,
        },
        "material_profile": {
            "full_name": mat_prof["full_name"],
            "ease_of_use": mat_prof["ease_of_use"],
            "enclosure_required": mat_prof["enclosure_required"],
            "filament_drying_required": mat_prof["filament_drying_required"],
            "drying_recommendation": mat_prof["drying_recommendation"],
            "bed_preparation": mat_prof["bed_preparation"],
            "characteristics_and_notes": mat_prof["notes"],
        },
    }

    if p_type == "FDM":
        response["recommended_settings"] = {
            "layer_settings": {
                "layer_height_mm": layer_height,
                "initial_layer_height_mm": initial_layer_height,
                "line_width_mm": line_width,
                "outer_wall_line_width_mm": outer_wall_line_width,
                "initial_layer_line_width_percent": 125,
            },
            "wall_and_shell_settings": {
                "wall_line_count": wall_count,
                "wall_thickness_mm": wall_thickness,
                "top_layers": top_layers,
                "bottom_layers": bottom_layers,
                "top_bottom_thickness_mm": top_bottom_thickness,
                "z_seam_alignment": "User Specified" if mat_key in ["PETG", "PLA"] else "Sharpest Corner",
                "z_seam_position": "Back",
                "seam_corner_preference": "Hide Seam",
            },
            "infill_settings": {
                "infill_density_percent": infill_density,
                "infill_pattern": infill_pattern,
                "infill_overlap_percent": 18,
            },
            "temperature_and_flow_settings": {
                "extruder_temperature_c": extruder_temp,
                "extruder_temp_range_c": f"{temps['extruder_min']}°C - {temps['extruder_max']}°C",
                "initial_layer_extruder_temp_c": initial_layer_extruder_temp,
                "bed_temperature_c": bed_temp,
                "bed_temp_range_c": f"{temps['bed_min']}°C - {temps['bed_max']}°C",
                "initial_layer_bed_temp_c": initial_layer_bed_temp,
                "flow_rate_percent": flow_rate,
                "initial_layer_flow_percent": 100.0 if mat_key != "TPU" else 105.0,
            },
            "speed_settings": {
                "print_speed_mm_s": effective_speed,
                "infill_speed_mm_s": infill_speed,
                "outer_wall_speed_mm_s": outer_wall_speed,
                "inner_wall_speed_mm_s": inner_wall_speed,
                "initial_layer_speed_mm_s": initial_layer_speed,
                "travel_speed_mm_s": travel_speed,
                "bridge_speed_mm_s": bridge_speed,
            },
            "acceleration_and_jerk_settings": {
                "enable_acceleration_control": True,
                "print_acceleration_mm_s2": print_accel,
                "travel_acceleration_mm_s2": travel_accel,
                "enable_jerk_control": False if p_info.get("firmware") == "Klipper" else True,
                "jerk_mm_s": 8 if p_info.get("firmware") == "Marlin" else "N/A (Klipper Square Corner Velocity 5.0)",
            },
            "cooling_and_fan_settings": {
                "enable_cooling": cooling_info["enable"],
                "fan_speed_percent": cooling_info["fan_speed_percent"],
                "min_fan_speed_percent": cooling_info["min_fan_speed"],
                "max_fan_speed_percent": cooling_info["max_fan_speed"],
                "initial_layer_fan_speed_percent": cooling_info["initial_layer_fan"],
                "fan_regular_speed_at_layer": cooling_info["regular_fan_at_layer"],
                "auxiliary_gantry_fan_percent": cooling_info["aux_fan_speed"] if p_info.get("aux_fan_available") else 0,
                "minimum_layer_time_s": 8,
            },
            "retraction_settings": {
                "enable_retraction": True if (mat_key != "TPU" or is_direct_drive) else False,
                "retraction_distance_mm": retraction_dist,
                "retraction_speed_mm_s": mat_prof["retraction_speed"],
                "retract_at_layer_change": True,
                "combing_mode": "Not in Outer Surface",
                "z_hop_when_retracted_mm": 0.2 if mat_key in ["PETG", "TPU"] else 0.0,
            },
            "support_settings": {
                "support_recommendation": "Enable only if overhang angles exceed threshold",
                "support_structure_type": "Tree (Slim)" if mat_key in ["PLA", "PETG"] else "Normal (Grid)",
                "support_placement": "Touching Buildplate",
                "support_overhang_angle_deg": 50 if mat_key in ["PLA", "PETG"] else 45,
                "support_density_percent": 12,
                "support_z_distance_mm": round(layer_height * 1.0, 2),
                "support_interface_enable": True,
            },
            "bed_adhesion_settings": {
                "adhesion_type": adhesion_type,
                "brim_width_mm": brim_width,
                "skirt_line_count": 3 if adhesion_type == "skirt" else 0,
                "z_offset_recommendation": z_offset_note,
            },
        }

    else:
        # Resin Profile
        response["recommended_settings"] = {
            "resin_exposure_settings": {
                "bottom_layer_count": 5,
                "bottom_exposure_time_s": 30.0,
                "normal_layer_exposure_time_s": 2.5,
                "light_off_delay_s": 0.5,
                "bottom_lift_distance_mm": 6.0,
                "bottom_lift_speed_mm_min": 60,
                "lifting_distance_mm": 5.0,
                "lifting_speed_mm_min": 80,
                "retract_speed_mm_min": 150,
                "anti_aliasing_level": "4x",
            },
            "resin_safety_and_handling": [
                "Always wear nitrile gloves, safety glasses, and organic vapor respirator mask.",
                "Ensure room temperature is between 20°C and 25°C for consistent curing.",
                "Wash prints thoroughly in 99% IPA using Elegoo Wash & Cure station before final UV post-curing."
            ],
        }

    # --------------------------------------------------------------------------
    # Targeted Issue Troubleshooting Adjustments
    # --------------------------------------------------------------------------
    if issue_raw:
        response["targeted_issue_adjustments"] = analyze_issue(
            issue_raw, mat_key, p_type, nozzle_size
        )

    # --------------------------------------------------------------------------
    # General Elegoo Slicer Best Practices
    # --------------------------------------------------------------------------
    response["elegoo_slicer_pro_tips"] = [
        "Use official Elegoo printer profiles in Elegoo Cura or OrcaSlicer as the baseline.",
        "Perform Bed Mesh Leveling (Aux Leveling + Auto Leveling) whenever nozzle or build sheet is changed.",
        "For Neptune 4 series running Klipper: Save configuration after setting Pressure Advance and Input Shaping in Fluid/Mainsail.",
        "Store sensitive filaments (PETG, TPU, ABS, Nylon) in sealed dry bags with desiccant or print directly from a heated filament dryer."
    ]

    return response


# ==============================================================================
# CLI and Stdin Parsing
# ==============================================================================

def parse_args_and_input() -> Dict[str, Any]:
    """Parse inputs from command line arguments, JSON string, or stdin."""
    
    parser = argparse.ArgumentParser(
        description="Elegoo Slicer Settings Guide & Profile Recommendations",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("-m", "--material", type=str, help="Filament/Resin material type (PLA, PETG, ABS, TPU, ASA, PC, Nylon)")
    parser.add_argument("-q", "--quality", type=str, help="Quality target (draft, standard, high, ultra)")
    parser.add_argument("-p", "--printer-type", "--printer_type", dest="printer_type", type=str, help="Printer technology (FDM or Resin)")
    parser.add_argument("--printer-model", "--printer_model", dest="printer_model", type=str, help="Printer model (e.g., Neptune 4 Pro, Neptune 3, Mars 4)")
    parser.add_argument("-i", "--issue", type=str, help="Printing issue experienced (stringing, warping, adhesion, elephant_foot, etc.)")
    parser.add_argument("-n", "--nozzle-size", "--nozzle_size", dest="nozzle_size", type=float, help="Nozzle diameter in mm (0.2, 0.4, 0.6, 0.8)")
    parser.add_argument("-j", "--json", type=str, help="JSON input string containing parameters")
    parser.add_argument("--stdin", action="store_true", help="Force reading input from stdin")

    args = parser.parse_args()

    # Dictionary to hold merged input values
    input_data: Dict[str, Any] = {}

    # 1. Read stdin if forced or if stdin has data ready (non-blocking select check)
    if args.stdin or (not sys.stdin.isatty()):
        try:
            # Non-blocking check for available stdin input
            rlist, _, _ = select.select([sys.stdin], [], [], 0.05)
            if rlist or args.stdin:
                stdin_content = sys.stdin.read().strip()
                if stdin_content:
                    parsed_stdin = json.loads(stdin_content)
                    if isinstance(parsed_stdin, dict):
                        input_data.update(parsed_stdin)
        except Exception:
            pass  # Fall back to CLI flags if stdin reading fails

    # 2. Read --json argument if provided
    if args.json:
        try:
            parsed_json = json.loads(args.json)
            if isinstance(parsed_json, dict):
                input_data.update(parsed_json)
        except json.JSONDecodeError as e:
            sys.stderr.write(f"Warning: Failed to parse --json argument: {e}\n")

    # 3. CLI flags take highest precedence if specified
    if args.material:
        input_data["material"] = args.material
    if args.quality:
        input_data["quality"] = args.quality
    if args.printer_type:
        input_data["printer_type"] = args.printer_type
    if args.printer_model:
        input_data["printer_model"] = args.printer_model
    if args.issue:
        input_data["issue"] = args.issue
    if args.nozzle_size is not None:
        input_data["nozzle_size"] = args.nozzle_size

    # Defaults
    material = str(input_data.get("material") or "PLA")
    quality = str(input_data.get("quality") or "standard")
    printer_type = str(input_data.get("printer_type") or "FDM")
    printer_model = input_data.get("printer_model")
    if printer_model is not None:
        printer_model = str(printer_model)
    issue = input_data.get("issue")
    if issue is not None:
        issue = str(issue)
    
    nozzle_size_val = input_data.get("nozzle_size") or input_data.get("nozzle_size_mm") or 0.4
    try:
        nozzle_size = float(nozzle_size_val)
    except (ValueError, TypeError):
        nozzle_size = 0.4

    return {
        "material": material,
        "quality": quality,
        "printer_type": printer_type,
        "printer_model": printer_model,
        "nozzle_size": nozzle_size,
        "issue": issue,
    }


# ==============================================================================
# Main Entry Point
# ==============================================================================

def main() -> None:
    inputs = parse_args_and_input()
    
    recommendations = generate_recommendations(
        material_raw=inputs["material"],
        quality_raw=inputs["quality"],
        printer_type_raw=inputs["printer_type"],
        printer_model_raw=inputs["printer_model"],
        nozzle_size=inputs["nozzle_size"],
        issue_raw=inputs["issue"],
    )

    print(json.dumps(recommendations, indent=2))


if __name__ == "__main__":
    main()
