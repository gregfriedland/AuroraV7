# ADR 0002: HUB75 LED Panel Wall, Controller, and Power Supply

**Status:** Proposed  
**Date:** 2026-06-06

## Context

Aurora currently targets a small WS2801 strip matrix driven through a Teensy serial bridge. A larger wall is being evaluated using indoor RGB HUB75 LED modules from the vendor listing described as:

- P2 indoor full-color LED display module
- 256 mm x 128 mm module size
- 128 x 64 pixels per module
- Chipset: ICN6373C driver + ICN32019 row scan
- 1/32 scan
- 5 V LED module power domain
- Maximum power consumption: 880 W/m²
- Average power consumption: 352 W/m²
- Indoor or semi-outdoor use

The planning configuration is 30 modules arranged 5 wide x 6 high. The price assumption for budgeting is $20 per panel, even though the pasted vendor text includes lower list prices for adjacent module variants. This ADR treats $20/panel as the more conservative landed-cost estimate.

## Decision

Build around a 30-panel HUB75 wall (5 wide x 6 high) and initially drive it from the existing Raspberry Pi 5 using the hzeller `rpi-rgb-led-matrix` adapter path.

Use four Mean Well LRS-350-5 5 V / 60 A power supplies for max-white electrical sizing. Three supplies is the strict minimum but leaves only ~7 A headroom; four provides comfortable derating.

Keep Colorlight or NovaStar sender/receiver hardware as the fallback path if direct Raspberry Pi HUB75 driving cannot meet refresh, color-depth, flicker, or CPU isolation requirements.

## Panel Geometry

Each panel:

- Physical size: 256 mm x 128 mm
- Physical size: 10.08 in x 5.04 in
- Physical size: 0.84 ft x 0.42 ft
- Resolution: 128 x 64 pixels
- Area: 0.032768 m²

30 panels in the chosen 5 wide x 6 high layout:

- Physical size: 1280 mm x 768 mm
- Physical size: 50.39 in x 30.24 in
- Physical size: 4.20 ft x 2.52 ft
- Resolution: 640 x 384 pixels
- Pixel count: 245,760 pixels
- Area: 0.98304 m²
- Area: 10.58 ft²

Alternative 30-panel layouts:

| Layout (W x H) | Physical Size | Resolution |
| --- | --- | --- |
| 5 x 6 (chosen) | 4.20 ft x 2.52 ft | 640 x 384 |
| 6 x 5 | 5.04 ft x 2.10 ft | 768 x 320 |
| 10 x 3 | 8.40 ft x 1.26 ft | 1280 x 192 |

## Power Budget

Maximum per-panel power:

```text
0.256 m x 0.128 m = 0.032768 m²
880 W/m² x 0.032768 m² = 28.84 W
28.84 W / 5 V = 5.77 A
```

Maximum 30-panel power:

```text
28.84 W x 30 = 865.1 W
865.1 W / 5 V = 173.0 A
```

Average 30-panel power, using the vendor's 352 W/m² average figure:

```text
352 W/m² x 0.98304 m² = 346.0 W
346.0 W / 5 V = 69.2 A
```

Selected supply:

- Mean Well LRS-350-5
- 5 V, 60 A, 300 W
- Planning price: approximately $36.51 each
- Link: https://www.trcelectronics.com/products/mean-well-lrs-350-5

Required quantity:

```text
173.0 A / 60 A = 2.88 supplies
```

Use four supplies (three is the strict minimum with only ~7 A headroom):

- Total rated output: 5 V, 240 A, 1200 W
- Supply cost: 4 x $36.51 = $146.04
- Headroom over maximum estimate: 240 A - 173.0 A = 67.0 A

Power distribution must be split into supply zones. Do not route the full wall current through one connector, one small wire bundle, or one panel input chain. Each supply zone should have appropriately sized 5 V and ground distribution, branch fusing, and short panel power injection runs.

## Controller Options

### Option A: Raspberry Pi 5 + hzeller HUB75 Adapter

Use the existing Raspberry Pi 5 and the hzeller `rpi-rgb-led-matrix` adapter board:

- Adapter docs: https://github.com/hzeller/rpi-rgb-led-matrix/tree/master/adapter
- Library: https://github.com/hzeller/rpi-rgb-led-matrix
- Best fit for custom programmed patterns generated directly by Aurora
- Lowest hardware cost because the Pi 5 is already available
- Avoids a separate LED video sender/receiver stack

Likely starting geometry for the 5 x 6 wall:

```text
--led-cols=128
--led-rows=64
--led-chain=10
--led-parallel=3
```

That maps to three parallel HUB75 chains with 10 panels per chain. The physical 5 x 6 wall will need explicit chain mapping or serpentine mapping so each 10-panel chain covers two physical rows of five panels.

Driving HUB75 panels is not CPU-free. The display refresh process continuously scans rows and PWM bitplanes. On Raspberry Pi 5, the hzeller library supports RP1/RIO-related modes that can reduce CPU impact, but controller load still needs to be measured with the final geometry, brightness, PWM bit depth, and refresh target.

### Option B: Raspberry Pi 5 HDMI + Colorlight

Render Aurora patterns fullscreen on the Raspberry Pi HDMI output and use Colorlight hardware for LED-wall scanning.

Example components:

- Colorlight X2 LED controller, approximately $235-$285
- Link: https://www.led-estore.com/ColorLight-X2-LED-display-controller
- Colorlight 5A-75B receiver card, approximately $10 each
- Link: https://leemanledscreen.com/product/colorlight-5a-75b-receiving-card-5a-75b-led-receiver-card/

For 245,760 pixels, plan on at least four receiver cards and often five for cleaner physical mapping.

This option moves timing-critical panel refresh off the Pi GPIO path. It is a better fit if the wall should behave like a conventional HDMI display. It adds cost, configuration complexity, and an extra rendering path.

### Option C: Raspberry Pi 5 HDMI + NovaStar

Render Aurora patterns fullscreen on the Raspberry Pi HDMI output and use NovaStar sender/receiver hardware.

Example components:

- NovaStar MSD300 sender, approximately $109
- NovaStar MRV328 receiver card, approximately $25-$39 each
- Link: https://novastarled.com/products/novastar-mrv328.html

For 245,760 pixels, plan on at least four receiver cards and often five for cleaner physical mapping.

This is the more conventional pro-video-wall architecture. It is likely more robust than direct GPIO driving, but it is less direct for Aurora's custom pixel pipeline and adds sender/receiver configuration work.

### Option D: Huidu Async Controller

Example component:

- Huidu HD-C15C Android LED controller, approximately $169
- Link: https://olympianled.com/product/huidu-hd-c15c-android-led-controller-with-10-hub75e-ports-wifi/

This is better for signage playlists, stored media, and app-managed content. It is a weaker fit for live custom generative patterns unless its API and refresh pipeline match Aurora's requirements.

## Mounting: Vertical Steel Strips

Build schematic: [30-panel-hub75-wall-schematic.svg](../hardware/30-panel-hub75-wall-schematic.svg)

Panels mount with magnetic screws (four per panel) landing on vertical mild-steel strips fastened to the backer. Strips run top-to-bottom along the panel-column edges so each strip serves the magnets of the two adjacent columns and they never overlap:

- Strip count: 6 total — left edge, 4 internal column seams, right edge
- Strip width: 2 in (50.8 mm), 1/16 in thick mild steel. Measured from the received module (P2-1515-128X64-32S-S2): the vertical-edge inserts sit ~7.5 mm in from the panel edge, at ~33 mm from the top and bottom edges. With Ø20 mm magnet feet, a seam strip must span ±17.5 mm = 35 mm minimum; 1.5 in (38 mm) leaves ~1.5 mm alignment tolerance, so use 2 in
- Strip length: panel array height 768 mm plus 25-40 mm bezel-margin overrun at each end (steel for magnetic bezel attachment) → cut to ~840 mm (33 in) each
- Panels also have inserts along their long edges at mid-span x positions; these are unused — vertical strips catch only the 4 vertical-edge inserts per panel

Total steel length:

```text
6 strips x 840 mm = 5040 mm = 5.04 m = 16.5 ft
```

Buy three 8 ft (2438 mm) lengths of flat stock; each yields two 840 mm strips, leaving ~30 in of offcut for bezel-magnet landing plates and mistakes.

## Cost Estimate for 30 Panels

| Item | Quantity | Unit Cost | Extended Cost |
| --- | ---: | ---: | ---: |
| 256 mm x 128 mm HUB75 RGB panels | 30 | $20.00 | $600.00 |
| Mean Well LRS-350-5 power supplies | 4 | $36.51 | $146.04 |
| HUB75 ribbon cables and panel power pigtails | 1 lot | $50-$120 | $50-$120 |
| DC distribution, fuses, busbars, terminals, wire | 1 lot | $50-$150 | $50-$150 |
| Basic backer/standoffs frame | 1 | $40-$100 | $40-$100 |
| 2020 aluminum extrusion frame | 1 | $70-$260 | $70-$260 |
| Commercial/custom LED cabinet frame | 1 | $150-$500+ | $150-$500+ |

Estimated totals:

| Build Path | Estimated Total |
| --- | ---: |
| Pi 5 + existing adapter + basic frame | $886-$1,116 |
| Pi 5 + existing adapter + 2020 extrusion frame | $916-$1,276 |
| Colorlight path + receivers + extrusion frame | $1,201-$1,621 |
| NovaStar path + receivers + extrusion frame | $1,150-$1,619 |

These totals exclude shipping, tax, import duties, spare panels, enclosure finishing, front diffusion, tools, and any replacement cables included with panel bundles.

## Consequences

- A 30-panel wall reaches 640 x 384 pixels in the chosen 5 x 6 layout, which is much larger than the current 32 x 18 WS2801 matrix.
- Maximum current is high enough that power distribution becomes a primary design constraint, not an accessory detail.
- The Raspberry Pi 5 direct-HUB75 path is the best initial choice for custom programmed patterns because it keeps Aurora in control of the pixel buffer.
- The Pi 5 path may consume measurable CPU for panel refresh and may require tuning PWM depth, refresh rate, GPIO slowdown, chain count, and mapping.
- Colorlight or NovaStar should be selected if direct GPIO driving produces unacceptable flicker, refresh limitations, color-depth compromises, or interference with Aurora's pattern generation workload.
