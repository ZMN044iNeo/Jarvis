# Elegoo Slicer Guide Skill

Provides comprehensive Elegoo Slicer settings recommendations based on material, quality target, and print issues. Covers Elegoo Slicer (Cura-based) settings for FDM printing.

## Usage

```bash
# Get settings for PLA at standard quality
python3 .agents/skills/elegoo-slicer-guide/elegoo_slicer_guide.py --material PLA --quality standard

# Get settings for PETG at high quality
python3 .agents/skills/elegoo-slicer-guide/elegoo_slicer_guide.py --material PETG --quality high

# Get settings for TPU with troubleshooting for stringing
python3 .agents/skills/elegoo-slicer-guide/elegoo_slicer_guide.py --material TPU --issue stringing

# Get settings with specific nozzle size
python3 .agents/skills/elegoo-slicer-guide/elegoo_slicer_guide.py --material ABS --nozzle 0.6
```

## CLI Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--material` | PLA, PETG, ABS, TPU, ASA, PC, Nylon, PVA, HIPS | PLA |
| `--quality` | draft, standard, high, ultra | standard |
| `--nozzle` | Nozzle size in mm (0.2, 0.4, 0.6, 0.8) | 0.4 |
| `--issue` | Print issue to optimize for (stringing, warping, adhesion, etc.) | None |
| `--printer` | Printer type (FDM) | FDM |

## Material Coverage

- **PLA**: 190-220°C, 50-65°C bed, easy print, full cooling
- **PETG**: 220-250°C, 70-90°C bed, stringing-prone, moderate cooling
- **ABS**: 230-260°C, 90-110°C bed, enclosure required, minimal cooling
- **TPU**: 210-230°C, 40-60°C bed, slow print, no retraction
- **ASA**: 240-260°C, 90-110°C bed, UV resistant, enclosure required
- **PC**: 260-300°C, 100-120°C bed, enclosure required, high temp
- **Nylon**: 240-270°C, 70-100°C bed, moisture sensitive, needs drying

## Output

Returns JSON with:
- `request_summary`: Input parameters
- `material_profile`: Material characteristics and notes
- `recommended_settings`: All slicer settings organized by category
  - Layer settings, wall/shell, infill, temperature/flow, speed, acceleration, cooling, retraction, support, bed adhesion, z-offset
- When `--issue` is specified, includes targeted adjustments
