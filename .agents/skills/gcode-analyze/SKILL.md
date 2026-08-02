# Gcode Analysis Skill

Analyzes Gcode files for issues, optimization opportunities, and print parameters. Compatible with Elegoo Slicer, Cura, PrusaSlicer, and OrcaSlicer output.

## Usage

```bash
# Analyze a file
python3 .agents/skills/gcode-analyze/gcode_analyze.py /path/to/file.gcode

# Analyze from stdin
cat file.gcode | python3 .agents/skills/gcode-analyze/gcode_analyze.py
```

## What It Detects

### Critical Issues
- Missing homing (G28) in start Gcode
- Hotend/bed left on at end of file (fire hazard)
- No units specified (G20/G21)
- No positioning mode specified (G90/G91)
- Conflicting Gcode commands

### Warnings
- Missing bed leveling commands (G29, BED_MESH_CALIBRATE)
- Unusual temperature settings
- Retraction not configured
- High print speeds for material type
- Missing fan commands

### Info
- Slicer detection (Elegoo, Cura, PrusaSlicer, OrcaSlicer)
- Estimated print time
- Filament usage estimation (length, volume, weight)
- Bounding box dimensions
- Layer height analysis
- Speed statistics (max, avg, first layer)

## Output Format

Returns JSON with:
- `summary`: Overview stats (lines, slicer, filament, dimensions, temps, speeds)
- `issues`: Array of issues sorted by severity (critical → info)
- Each issue includes: id, severity, category, description, recommendation
