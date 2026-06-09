# LED Panel Back Brackets

This folder generates two parametric 3D-printable back brackets:

- `cross_bracket`: a plus-shaped bracket for four-panel intersections.
- `column_bracket`: a tall vertical strap for panel seams.

The dimensions come from `bracket_config.example.yaml`. Copy that file, enter
real caliper measurements for your panels, then generate STL and STEP files.

## Install

CadQuery is only needed for the hardware generator, not for Aurora runtime:

```bash
uv pip install cadquery pyyaml
```

## Validate Config

```bash
python hardware/brackets/generate_brackets.py \
  --config hardware/brackets/bracket_config.example.yaml \
  --validate-only
```

## Generate Models

```bash
python hardware/brackets/generate_brackets.py \
  --config hardware/brackets/bracket_config.example.yaml \
  --out hardware/brackets/out
```

This writes:

```text
hardware/brackets/out/cross_bracket.stl
hardware/brackets/out/cross_bracket.step
hardware/brackets/out/column_bracket.stl
hardware/brackets/out/column_bracket.step
```

Use `--only cross` or `--only column` to generate one model.

## Measurements To Update

- Panel outer width and height.
- Gap between neighboring panels in the intended frame.
- Offset from panel edge to each screw hole used by the bracket.
- Screw clearance diameter.
- Screw head or washer diameter.
- Maximum bracket thickness that clears HUB75 ribbons, power plugs, and rear
  electronics.

## Print Iteration

Print one cheap fit test first:

- Use low infill or reduced thickness.
- Confirm holes line up without forcing the panels.
- Confirm screw heads, washers, ribbons, and power wires clear the bracket.
- Confirm the bracket sits flat and does not hit raised components.

Final print starting point:

- PETG, ASA, or ABS.
- 4+ perimeters.
- 35-50% infill.
- Print flat on the panel-facing side.
