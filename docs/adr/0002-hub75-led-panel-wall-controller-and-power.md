# ADR 0002: HUB75 LED Panel Wall, Controller, and Power Supply

**Status:** Proposed  
**Date:** 2026-06-06

## Context

Aurora currently targets a small WS2801 strip matrix driven through a Teensy serial bridge. A larger wall is being evaluated using indoor RGB HUB75 LED modules from the vendor listing described as:

- P2 indoor full-color LED display module
- 256 mm x 128 mm module size
- 128 x 64 pixels per module
- 1/32 scan
- 5 V LED module power domain
- Maximum power consumption: 880 W/m²
- Average power consumption: 352 W/m²
- Indoor or semi-outdoor use

The planning configuration is 36 modules. The price assumption for budgeting is $20 per panel, even though the pasted vendor text includes lower list prices for adjacent module variants. This ADR treats $20/panel as the more conservative landed-cost estimate.

## Decision

Build around a 36-panel HUB75 wall and initially drive it from the existing Raspberry Pi 5 using the hzeller `rpi-rgb-led-matrix` adapter path.

Use four Mean Well LRS-350-5 5 V / 60 A power supplies for max-white electrical sizing. One supply is insufficient for 36 panels.

Keep Colorlight or NovaStar sender/receiver hardware as the fallback path if direct Raspberry Pi HUB75 driving cannot meet refresh, color-depth, flicker, or CPU isolation requirements.

## Panel Geometry

Each panel:

- Physical size: 256 mm x 128 mm
- Physical size: 10.08 in x 5.04 in
- Physical size: 0.84 ft x 0.42 ft
- Resolution: 128 x 64 pixels
- Area: 0.032768 m²

36 panels in a 6 x 6 layout:

- Physical size: 1536 mm x 768 mm
- Physical size: 60.47 in x 30.24 in
- Physical size: 5.04 ft x 2.52 ft
- Resolution: 768 x 384 pixels
- Pixel count: 294,912 pixels
- Area: 1.179648 m²
- Area: 12.70 ft²

Alternative 36-panel layouts:

| Layout | Physical Size | Resolution |
| --- | --- | --- |
| 6 x 6 | 5.04 ft x 2.52 ft | 768 x 384 |
| 9 x 4 | 7.56 ft x 1.68 ft | 1152 x 256 |
| 12 x 3 | 10.08 ft x 1.26 ft | 1536 x 192 |

## Power Budget

Maximum per-panel power:

```text
0.256 m x 0.128 m = 0.032768 m²
880 W/m² x 0.032768 m² = 28.84 W
28.84 W / 5 V = 5.77 A
```

Maximum 36-panel power:

```text
28.84 W x 36 = 1038 W
1038 W / 5 V = 207.7 A
```

Average 36-panel power, using the vendor's 352 W/m² average figure:

```text
352 W/m² x 1.179648 m² = 415.2 W
415.2 W / 5 V = 83.0 A
```

Selected supply:

- Mean Well LRS-350-5
- 5 V, 60 A, 300 W
- Planning price: approximately $36.51 each
- Link: https://www.trcelectronics.com/products/mean-well-lrs-350-5

Required quantity:

```text
207.7 A / 60 A = 3.46 supplies
```

Use four supplies:

- Total rated output: 5 V, 240 A, 1200 W
- Supply cost: 4 x $36.51 = $146.04
- Headroom over maximum estimate: 240 A - 207.7 A = 32.3 A

Power distribution must be split into supply zones. Do not route the full wall current through one connector, one small wire bundle, or one panel input chain. Each supply zone should have appropriately sized 5 V and ground distribution, branch fusing, and short panel power injection runs.

## Controller Options

### Option A: Raspberry Pi 5 + hzeller HUB75 Adapter

Use the existing Raspberry Pi 5 and the hzeller `rpi-rgb-led-matrix` adapter board:

- Adapter docs: https://github.com/hzeller/rpi-rgb-led-matrix/tree/master/adapter
- Library: https://github.com/hzeller/rpi-rgb-led-matrix
- Best fit for custom programmed patterns generated directly by Aurora
- Lowest hardware cost because the Pi 5 is already available
- Avoids a separate LED video sender/receiver stack

Likely starting geometry for a 6 x 6 wall:

```text
--led-cols=128
--led-rows=64
--led-chain=12
--led-parallel=3
```

That maps to three parallel HUB75 chains with 12 panels per chain. The physical 6 x 6 wall will need explicit chain mapping or serpentine mapping so each 12-panel chain covers two physical rows.

Driving HUB75 panels is not CPU-free. The display refresh process continuously scans rows and PWM bitplanes. On Raspberry Pi 5, the hzeller library supports RP1/RIO-related modes that can reduce CPU impact, but controller load still needs to be measured with the final geometry, brightness, PWM bit depth, and refresh target.

### Option B: Raspberry Pi 5 HDMI + Colorlight

Render Aurora patterns fullscreen on the Raspberry Pi HDMI output and use Colorlight hardware for LED-wall scanning.

Example components:

- Colorlight X2 LED controller, approximately $235-$285
- Link: https://www.led-estore.com/ColorLight-X2-LED-display-controller
- Colorlight 5A-75B receiver card, approximately $10 each
- Link: https://leemanledscreen.com/product/colorlight-5a-75b-receiving-card-5a-75b-led-receiver-card/

For 294,912 pixels, plan on at least five receiver cards and often six for cleaner physical mapping.

This option moves timing-critical panel refresh off the Pi GPIO path. It is a better fit if the wall should behave like a conventional HDMI display. It adds cost, configuration complexity, and an extra rendering path.

### Option C: Raspberry Pi 5 HDMI + NovaStar

Render Aurora patterns fullscreen on the Raspberry Pi HDMI output and use NovaStar sender/receiver hardware.

Example components:

- NovaStar MSD300 sender, approximately $109
- NovaStar MRV328 receiver card, approximately $25-$39 each
- Link: https://novastarled.com/products/novastar-mrv328.html

For 294,912 pixels, plan on at least five receiver cards and often six for cleaner physical mapping.

This is the more conventional pro-video-wall architecture. It is likely more robust than direct GPIO driving, but it is less direct for Aurora's custom pixel pipeline and adds sender/receiver configuration work.

### Option D: Huidu Async Controller

Example component:

- Huidu HD-C15C Android LED controller, approximately $169
- Link: https://olympianled.com/product/huidu-hd-c15c-android-led-controller-with-10-hub75e-ports-wifi/

This is better for signage playlists, stored media, and app-managed content. It is a weaker fit for live custom generative patterns unless its API and refresh pipeline match Aurora's requirements.

## Cost Estimate for 36 Panels

| Item | Quantity | Unit Cost | Extended Cost |
| --- | ---: | ---: | ---: |
| 256 mm x 128 mm HUB75 RGB panels | 36 | $20.00 | $720.00 |
| Mean Well LRS-350-5 power supplies | 4 | $36.51 | $146.04 |
| HUB75 ribbon cables and panel power pigtails | 1 lot | $50-$120 | $50-$120 |
| DC distribution, fuses, busbars, terminals, wire | 1 lot | $50-$150 | $50-$150 |
| Basic backer/standoffs frame | 1 | $40-$100 | $40-$100 |
| 2020 aluminum extrusion frame | 1 | $70-$260 | $70-$260 |
| Commercial/custom LED cabinet frame | 1 | $150-$500+ | $150-$500+ |

Estimated totals:

| Build Path | Estimated Total |
| --- | ---: |
| Pi 5 + existing adapter + basic frame | $1,006-$1,236 |
| Pi 5 + existing adapter + 2020 extrusion frame | $1,036-$1,396 |
| Colorlight path + receivers + extrusion frame | $1,321-$1,741 |
| NovaStar path + receivers + extrusion frame | $1,270-$1,739 |

These totals exclude shipping, tax, import duties, spare panels, enclosure finishing, front diffusion, tools, and any replacement cables included with panel bundles.

## Consequences

- A 36-panel wall reaches 768 x 384 pixels in the preferred 6 x 6 layout, which is much larger than the current 32 x 18 WS2801 matrix.
- Maximum current is high enough that power distribution becomes a primary design constraint, not an accessory detail.
- The Raspberry Pi 5 direct-HUB75 path is the best initial choice for custom programmed patterns because it keeps Aurora in control of the pixel buffer.
- The Pi 5 path may consume measurable CPU for panel refresh and may require tuning PWM depth, refresh rate, GPIO slowdown, chain count, and mapping.
- Colorlight or NovaStar should be selected if direct GPIO driving produces unacceptable flicker, refresh limitations, color-depth compromises, or interference with Aurora's pattern generation workload.
