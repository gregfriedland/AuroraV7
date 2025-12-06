# AuroraV7

LED matrix control software for Raspberry Pi with support for various visual patterns and remote operation.

## Architecture

The project consists of two binaries:

- **AuroraMatrix** - Server that runs on the Raspberry Pi with the LED matrix connected. Receives frames over gRPC and displays them on the matrix.
- **AuroraPatternGen** - Client that generates visual patterns and sends them to AuroraMatrix. Can run on the Pi or remotely.

## Supported Platforms

- **Raspberry Pi 5** - Uses libcamera via GStreamer for camera input
- **Raspberry Pi 4 and earlier** - Uses raspicam for camera input
- **Linux/macOS** - For development with ComputerScreen matrix output (OpenCV window)

## Prerequisites

### Ubuntu/Debian (Raspberry Pi or Linux)

Run the dependency installation script:

```bash
sudo ./install/install-deps.sh
```

This installs cmake, build-essential, OpenCV, gRPC, Protocol Buffers, nlohmann/json, and GStreamer.

### rpi-rgb-led-matrix Library (Raspberry Pi only)

```bash
# Clone the library
cd ~/src
mkdir -p ~/src
git clone https://github.com/hzeller/rpi-rgb-led-matrix.git

# Build
cd rpi-rgb-led-matrix
make -j4

# Install headers and library
sudo cp lib/librgbmatrix.* /usr/local/lib/
sudo cp -r include/* /usr/local/include/
sudo ldconfig
```

### json.hpp Header

Download the nlohmann/json single-header library:

```bash
curl -sL https://github.com/nlohmann/json/releases/download/v3.11.3/json.hpp \
    -o src/cpp/json.hpp
```

## Building

```bash
# Clone the repository
git clone https://github.com/gregfriedland/AuroraV7.git
cd AuroraV7

# Create build directory
mkdir -p build
cd build

# Configure and build
cmake ..
make -j4
```

### Build Output

On Raspberry Pi with rpi-rgb-led-matrix installed:
- `AuroraMatrix` - LED matrix server
- `AuroraPatternGen` - Pattern generator client

On non-ARM systems or without rpi-rgb-led-matrix:
- `AuroraPatternGen` only (can connect to remote AuroraMatrix)

## Configuration

Create a JSON configuration file (see `config/` directory for examples):

```json
{
    "width": 192,
    "height": 96,
    "matrix": "HzellerRpi",
    "networkPort": 50051,
    "fps": 30,
    "gamma": 2.2
}
```

### Matrix Types

- `HzellerRpi` - rpi-rgb-led-matrix (Raspberry Pi with LED panels)
- `Serial` - Serial-connected LED matrix
- `ComputerScreen` - OpenCV window display (for development)
- `Remote` - Connect to a remote AuroraMatrix server
- `Noop` - No display output (for testing)

## Running

### On Raspberry Pi (with LED matrix)

```bash
# Run the matrix server (requires root for GPIO access)
sudo ./build/AuroraMatrix config/your-config.json

# In another terminal, run the pattern generator
./build/AuroraPatternGen config/your-config.json
```

### Remote Operation

Run AuroraMatrix on the Pi, then run AuroraPatternGen on another machine with a Remote matrix configuration:

```json
{
    "matrix": "Remote",
    "remote": {
        "host": "aurora.local",
        "port": 50051
    }
}
```

## Camera Support

### Raspberry Pi 5

Uses libcamera via GStreamer pipeline. Make sure you have:
- `gstreamer1.0-libcamera` package installed
- Camera enabled in raspi-config

### Raspberry Pi 4 and earlier

Uses raspicam library. Install from source:

```bash
git clone https://github.com/cedricve/raspicam.git
cd raspicam
mkdir build && cd build
cmake ..
make -j4
sudo make install
```

## Systemd Service

To run AuroraMatrix as a system service:

```bash
# Create service file
sudo tee /etc/systemd/system/aurorav7.service << EOF
[Unit]
Description=AuroraV7 LED Matrix Driver
After=network.target

[Service]
ExecStart=/home/debian/AuroraV7/build/AuroraMatrix /home/debian/AuroraV7/config/your-config.json
Type=simple
WorkingDirectory=/home/debian/AuroraV7/build
Nice=-20
User=root
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable aurorav7
sudo systemctl start aurorav7

# View logs
sudo journalctl -u aurorav7 -f
```

## Dependencies

- [rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix) - LED matrix driver
- [raspicam](https://github.com/cedricve/raspicam) - Raspberry Pi camera library (Pi 4 and earlier)
- [OpenCV](https://opencv.org/) - Computer vision library
- [gRPC](https://grpc.io/) - Remote procedure call framework
- [nlohmann/json](https://github.com/nlohmann/json) - JSON for Modern C++
