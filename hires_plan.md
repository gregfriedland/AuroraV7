# 6x6 LED Wall Layout

## Physical Layout

Use 36 panels, each 64x32 pixels:

```text
6 panels wide x 6 panels tall
384 pixels wide x 192 pixels tall
```

Wire the wall as three identical horizontal bands. Each Raspberry Pi parallel
output/channel drives one 6x2 band, for 12 panels per channel.

Viewed from the LED/front side:

```text
Channel 1 / top band:
  P01 -> P02 -> P03 -> P04 -> P05 -> P06
                                      |
  P12 <- P11 <- P10 <- P09 <- P08 <- P07

Channel 2 / middle band:
  P01 -> P02 -> P03 -> P04 -> P05 -> P06
                                      |
  P12 <- P11 <- P10 <- P09 <- P08 <- P07

Channel 3 / bottom band:
  P01 -> P02 -> P03 -> P04 -> P05 -> P06
                                      |
  P12 <- P11 <- P10 <- P09 <- P08 <- P07
```

This uses a U-shaped chain per channel. Put the Pi/adapter near one side so all
three channels can start from the same side of their band.

## rpi-rgb-led-matrix Mapping

Use `U-mapper`. The library normally maps chained panels horizontally; `U-mapper`
folds each 12-panel chain into two 6-panel rows. With `parallel: 3`, the three
folded bands stack into one 384x192 canvas.

AuroraV7 config:

```yaml
matrix:
  width: 384
  height: 192
  output_driver: "rgbmatrix"
  fps: 35
  gamma: 1.0

  rgbmatrix:
    rows: 32
    cols: 64
    chain_length: 12
    parallel: 3
    hardware_mapping: "regular"
    gpio_slowdown: 2
    pixel_mapper_config: "U-mapper"
```

If the rendered image is rotated or mirrored relative to the physical wall,
append mappers in order, for example:

```yaml
pixel_mapper_config: "U-mapper;Rotate:180"
```

or:

```yaml
pixel_mapper_config: "U-mapper;Mirror:H"
```

## Power Plan

Use regulated 5V power supplies. Budget at 4A per 64x32 panel:

```text
36 panels x 4A = 144A at 5V
5V x 144A = 720W
```

Design for at least 144A total available current, with some headroom. Do not run
the whole wall through one small feed; inject power near the panels and tie all
power-supply grounds together.

### Option A: Three Supplies

Use one supply per 6x2 channel/band:

```text
12 panels per band x 4A = 48A per band
Recommended: 3 x 5V 60A supplies
Total capacity: 180A
```

Your existing 5V 40A supply is undersized for a full 12-panel band at the 4A
budget. With a 3-supply design, keep the 40A supply as a spare, for Pi/control
electronics, or for bench-testing a smaller subset of panels.

### Option B: Six Supplies

Use one supply per physical row of 6 panels:

```text
6 panels per row x 4A = 24A per row
Recommended: 6 x 5V 30A supplies
Total capacity: 180A
```

This is the cleaner match for the existing 40A supply: use the 40A supply for
one row, and add five 5V 30A supplies for the remaining rows. A 40A row supply
has comfortable headroom for a 24A row.

### Distribution Notes

- Fuse each supply output or each branch feeding a row/band.
- Use heavy enough wire for the branch current and keep high-current runs short.
- Inject 5V/GND into every panel or every 1-2 panels, not only at the start of a
  12-panel data chain.
- Tie all grounds together, including the Raspberry Pi/adapter ground.
- Adjust supply voltage at the terminals only as needed to keep panel inputs
  near 5V under load; do not exceed panel voltage limits.

### Fanless Low-Profile Supply Candidates

Good fits for the six-supply row plan:

```text
MEAN WELL RSP-150-5
5V, 30A, 150W
199 x 99 x 30 mm
Fanless / free-air convection
Use: one supply per 6-panel row
```

```text
MEAN WELL UHP-200-5
5V, 40A, 200W
194 x 55 x 26 mm
Fanless / convection
Use: one supply per 6-panel row, more compact with more headroom
```

The existing 5V 40A supply fits naturally as one row supply in this plan.
If buying new supplies, the UHP-200-5 class is the cleaner low-profile fanless
match for a 24A row load.

Possible fit for the three-supply band plan:

```text
MEAN WELL UHP-350-5
5V, 60A, 300W
220 x 62 x 31 mm
Fanless / slim low-profile
Use: one supply per 12-panel band
```

The three-supply plan runs each 60A supply near a 48A expected band load. That
is electrically reasonable but has less thermal margin than one supply per row.
For fanless operation, prefer the six-supply row plan unless enclosure space or
AC wiring strongly favors fewer supplies.

### Estimated Supply Cost

Reference prices checked against DigiKey in May 2026, before tax, shipping, and
any tariff charges:

```text
Six-row plan, using RSP-150-5:
  6 x $38.60 = $231.60
  Or, using the existing 40A supply for one row:
  5 x $38.60 = $193.00

Six-row plan, using UHP-200-5:
  6 x $54.90 = $329.40
  Or, using the existing 40A supply for one row:
  5 x $54.90 = $274.50

Three-band plan, using UHP-350-5:
  3 x $77.00 = $231.00
```

The cheapest clean fanless path is the RSP-150-5 row plan. The most compact
fanless row plan is UHP-200-5. The UHP-350-5 three-band plan has similar supply
cost to six RSP-150-5 units, but less thermal margin per supply.
