#!/usr/bin/env python3
"""Standalone LED test signal generator.

Sends known RGB patterns directly over serial to the Teensy,
bypassing the Aurora framework. Useful for hardware debugging.

Protocol: 576 pixels x 3 bytes (RGB, values 0-254) + 0xFF delimiter.
"""

import serial
import time
import sys
import argparse
import numpy as np

WIDTH = 32
HEIGHT = 18
NUM_PIXELS = WIDTH * HEIGHT  # 576
FRAME_BYTES = NUM_PIXELS * 3  # 1728
DELIMITER = b'\xff'


def make_frame(r: int, g: int, b: int) -> bytes:
    """Solid color frame. Values capped at 254 (255 = delimiter)."""
    r, g, b = min(r, 254), min(g, 254), min(b, 254)
    return bytes([r, g, b] * NUM_PIXELS) + DELIMITER


def make_single_pixel(index: int, r: int, g: int, b: int) -> bytes:
    """One pixel lit, rest black."""
    data = bytearray(FRAME_BYTES)
    offset = index * 3
    data[offset] = min(r, 254)
    data[offset + 1] = min(g, 254)
    data[offset + 2] = min(b, 254)
    return bytes(data) + DELIMITER


def make_gradient() -> bytes:
    """Horizontal red gradient (col 0=dark, col 31=bright)."""
    data = bytearray(FRAME_BYTES)
    for row in range(HEIGHT):
        for col in range(WIDTH):
            idx = (row * WIDTH + col) * 3
            val = min(int(col * 254 / 31), 254)
            data[idx] = val  # red
    return bytes(data) + DELIMITER


def make_row_bars() -> bytes:
    """Each row a different brightness of white. Row 0=dim, row 17=bright."""
    data = bytearray(FRAME_BYTES)
    for row in range(HEIGHT):
        val = min(int((row + 1) * 254 / HEIGHT), 254)
        for col in range(WIDTH):
            idx = (row * WIDTH + col) * 3
            data[idx] = val
            data[idx + 1] = val
            data[idx + 2] = val
    return bytes(data) + DELIMITER


def test_solid(port: serial.Serial, fps: float):
    """Cycle through solid R, G, B, white, holding each for 2 seconds."""
    colors = [
        ("RED",   254, 0, 0),
        ("GREEN", 0, 254, 0),
        ("BLUE",  0, 0, 254),
        ("WHITE", 254, 254, 254),
        ("BLACK", 0, 0, 0),
    ]
    delay = 1.0 / fps
    for name, r, g, b in colors:
        print(f"  {name} ({r},{g},{b}) -- holding 2s")
        frame = make_frame(r, g, b)
        end = time.time() + 2.0
        while time.time() < end:
            port.write(frame)
            time.sleep(delay)


def test_march(port: serial.Serial, fps: float):
    """Single white pixel marching through all 576 positions."""
    delay = 1.0 / fps
    print(f"  Marching pixel through {NUM_PIXELS} positions...")
    for i in range(NUM_PIXELS):
        frame = make_single_pixel(i, 254, 254, 254)
        port.write(frame)
        if i % WIDTH == 0:
            print(f"    row {i // WIDTH}")
        time.sleep(delay)


def test_first_pixel(port: serial.Serial, fps: float):
    """Blink first pixel red at 1 Hz -- easy to probe with voltmeter."""
    delay = 1.0 / fps
    print("  Blinking pixel 0 red at 1 Hz (Ctrl+C to stop)")
    try:
        while True:
            # On for 0.5s
            frame_on = make_single_pixel(0, 254, 0, 0)
            end = time.time() + 0.5
            while time.time() < end:
                port.write(frame_on)
                time.sleep(delay)
            # Off for 0.5s
            frame_off = make_frame(0, 0, 0)
            end = time.time() + 0.5
            while time.time() < end:
                port.write(frame_off)
                time.sleep(delay)
    except KeyboardInterrupt:
        pass


def test_static(port: serial.Serial, fps: float):
    """Send a single solid red frame repeatedly -- most predictable signal."""
    delay = 1.0 / fps
    frame = make_frame(254, 0, 0)
    print(f"  Sending solid red at {fps} FPS (Ctrl+C to stop)")
    print(f"  Frame: {FRAME_BYTES} RGB bytes + 0xFF = {FRAME_BYTES + 1} bytes")
    print(f"  Byte rate: {(FRAME_BYTES + 1) * fps:.0f} bytes/sec")
    try:
        count = 0
        while True:
            port.write(frame)
            count += 1
            if count % int(fps * 5) == 0:
                print(f"    {count} frames sent")
            time.sleep(delay)
    except KeyboardInterrupt:
        pass


TESTS = {
    "solid": ("Cycle R/G/B/white/black, 2s each", test_solid),
    "march": ("Single pixel marching through all positions", test_march),
    "blink": ("Blink pixel 0 at 1 Hz (voltmeter-friendly)", test_first_pixel),
    "static": ("Continuous solid red (most predictable signal)", test_static),
}


def main():
    parser = argparse.ArgumentParser(description="LED strip test signal generator")
    parser.add_argument("--port", default="/dev/ttyACM0", help="Serial port (default: /dev/ttyACM0)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--fps", type=float, default=10, help="Frames per second (default: 10)")
    parser.add_argument("test", nargs="?", default="solid",
                        choices=list(TESTS.keys()),
                        help="Test pattern to run")
    args = parser.parse_args()

    print(f"Opening {args.port} at {args.baud} baud...")
    try:
        port = serial.Serial(args.port, args.baud, timeout=1)
    except serial.SerialException as e:
        print(f"ERROR: Cannot open {args.port}: {e}")
        print("Is the Teensy connected? Check `ls /dev/ttyACM*`")
        sys.exit(1)

    time.sleep(0.5)  # let Teensy reset after serial open

    # Send black frame first to clear any residual state
    port.write(make_frame(0, 0, 0))
    time.sleep(0.1)

    desc, func = TESTS[args.test]
    print(f"Running: {args.test} -- {desc}")
    func(port, args.fps)

    # Black out on exit
    print("Blanking...")
    port.write(make_frame(0, 0, 0))
    time.sleep(0.1)
    port.close()
    print("Done.")


if __name__ == "__main__":
    main()
