# Hardware Setup

## System Overview

```
Raspberry Pi (3.3V logic)
    │
    │ USB serial (/dev/ttyACM0, 115200 baud)
    │
Teensy 3.1 (custom board, level shifter)
    │ powered via USB hub
    │
    ├── DATA_PIN 14 ──→ 5V level-shifted ──→ WS2801 data line
    ├── CLOCK_PIN 2 ──→ 5V level-shifted ──→ WS2801 clock line
    │
WS2801 LED strips (parallel, 32x18 = 576 LEDs)
    │
    └── powered by 5V DC power supply
```

## Components

### Raspberry Pi
- Runs Aurora software (Python, async)
- Sends RGB frame data over USB serial at 115200 baud
- Frame format: raw RGB bytes (capped at 254) + 0xFF delimiter byte
- Snake pattern applied in software before sending (alternate rows reversed)
- Gamma correction applied in software (default gamma 2.5)

### Teensy 3.1 (Custom Board)
- Mounted on a custom PCB that level-shifts 3.3V data/clock signals to 5V for the WS2801 strips
- Powered via USB hub (separate from the Pi's USB connection for serial)
- Runs `firmware/AuroraLEDs.ino` firmware using FastLED library
- WS2801 mode: `FastLED.addLeds<WS2801, DATA_PIN, CLOCK_PIN, BRG, DATA_RATE_MHZ(4)>`
- Pin 2: CLOCK, Pin 14: DATA
- Pin 13: onboard LED (blinks during FPS output)
- Reads serial RGB data, writes to LEDs via FastLED, sends 0xFF delimiter to trigger `FastLED.show()`

### WS2801 LED Strips
- Addressable RGB strips with separate clock and data lines (unlike WS2812 which is single-wire)
- Color order: BRG
- Data rate: 4 MHz
- Arranged as 32 columns x 18 rows (576 total LEDs)
- Multiple strips wired in parallel, all sharing the same data + clock lines from the Teensy
- Each strip's power (5V + GND) connected directly to the DC power supply

### 5V DC Power Supply
- Large supply powering all WS2801 strips directly
- Power LED indicator present
- 576 LEDs at ~60mA max per LED = ~35A theoretical max draw

### USB Hub
- Powers the Teensy 3.1 via USB
- Separate from serial data connection

## Wiring Summary

| Signal | Source | Destination | Voltage |
|--------|--------|-------------|---------|
| Serial TX/RX | Raspberry Pi USB | Teensy USB | 3.3V (USB standard) |
| WS2801 Data | Teensy pin 14 → level shifter | LED strip data in | 5V |
| WS2801 Clock | Teensy pin 2 → level shifter | LED strip clock in | 5V |
| LED Power | DC power supply | All LED strips (parallel) | 5V |
| Teensy Power | USB hub | Teensy USB | 5V (USB) |

## Serial Protocol

1. Pi sends RGB bytes for each pixel (values 0-254, never 255)
2. After all 576x3 = 1728 bytes, Pi sends 0xFF (255) as frame delimiter
3. Teensy calls `FastLED.show()` on delimiter, resets pixel counter
4. If more bytes arrive than expected, Teensy logs overflow but continues
