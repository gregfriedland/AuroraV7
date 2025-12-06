/**
 * Aurora Paint - WebSocket client and canvas drawing logic
 * Uses float buffer for smooth fading without quantization artifacts
 */

class AuroraPaint {
    constructor() {
        this.canvas = document.getElementById('paint-canvas');
        this.ctx = this.canvas.getContext('2d');
        this.ws = null;
        this.matrixWidth = 32;
        this.matrixHeight = 18;
        this.scale = 10;  // Display scale
        this.color = [255, 255, 255];
        this.radius = 1;
        this.isDrawing = false;
        this.lastPos = null;
        this.decayRate = 0;  // 0 = no decay
        this.lastFrameTime = 0;

        // Float buffer for smooth fading (stores RGB values at matrix resolution)
        this.floatBuffer = null;

        this.init();
    }

    init() {
        this.setupCanvas();
        this.setupControls();
        this.connect();
        this.startRenderLoop();
    }

    initFloatBuffer() {
        // Initialize float buffer with zeros (black)
        this.floatBuffer = new Float32Array(this.matrixWidth * this.matrixHeight * 3);
    }

    setupCanvas() {
        // Set canvas size based on matrix dimensions
        this.updateCanvasSize();

        // Fill with black
        this.ctx.fillStyle = '#000';
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        // Canvas events
        this.canvas.addEventListener('mousedown', (e) => this.handlePointerStart(e));
        this.canvas.addEventListener('mousemove', (e) => this.handlePointerMove(e));
        this.canvas.addEventListener('mouseup', () => this.handlePointerEnd());
        this.canvas.addEventListener('mouseleave', () => this.handlePointerEnd());

        // Touch events
        this.canvas.addEventListener('touchstart', (e) => {
            e.preventDefault();
            this.handlePointerStart(e.touches[0]);
        });
        this.canvas.addEventListener('touchmove', (e) => {
            e.preventDefault();
            this.handlePointerMove(e.touches[0]);
        });
        this.canvas.addEventListener('touchend', (e) => {
            e.preventDefault();
            this.handlePointerEnd();
        });

        // Resize handler
        window.addEventListener('resize', () => this.updateCanvasSize());
    }

    updateCanvasSize() {
        const container = document.getElementById('canvas-container');
        // Account for padding (3% on each side = 6% total)
        const maxWidth = container.clientWidth * 0.94;
        const maxHeight = container.clientHeight * 0.94;

        // Calculate scale to fit container while maintaining aspect ratio
        const scaleX = maxWidth / this.matrixWidth;
        const scaleY = maxHeight / this.matrixHeight;
        this.scale = Math.floor(Math.min(scaleX, scaleY));

        this.canvas.width = this.matrixWidth * this.scale;
        this.canvas.height = this.matrixHeight * this.scale;

        // Initialize or preserve float buffer
        if (!this.floatBuffer) {
            this.initFloatBuffer();
        }

        // Render buffer to canvas
        this.renderBufferToCanvas();
    }

    setupControls() {
        // Color picker
        const swatches = document.querySelectorAll('.color-swatch');
        swatches.forEach((swatch, index) => {
            if (index === 0) swatch.classList.add('selected');
            swatch.addEventListener('click', () => {
                swatches.forEach(s => s.classList.remove('selected'));
                swatch.classList.add('selected');
                this.color = swatch.dataset.color.split(',').map(Number);
                this.sendMessage({ type: 'set_color', color: this.color });
            });
        });

        // Brush size
        const brushSizeInput = document.getElementById('brush-size');
        const brushSizeLabel = document.getElementById('brush-size-label');
        brushSizeInput.addEventListener('input', () => {
            this.radius = parseInt(brushSizeInput.value);
            brushSizeLabel.textContent = this.radius;
            this.sendMessage({ type: 'set_radius', radius: this.radius });
        });

        // Decay rate
        const decayInput = document.getElementById('decay-rate');
        const decayLabel = document.getElementById('decay-label');
        decayInput.addEventListener('input', () => {
            const rate = parseFloat(decayInput.value) / 10;  // 0-10 range
            this.decayRate = rate;
            decayLabel.textContent = rate.toFixed(1);
            this.sendMessage({ type: 'set_decay', rate: rate });
        });

        // Clear button
        document.getElementById('clear-btn').addEventListener('click', () => {
            this.clearCanvas();
        });
    }

    startRenderLoop() {
        const render = (timestamp) => {
            if (this.lastFrameTime === 0) {
                this.lastFrameTime = timestamp;
            }

            const deltaTime = (timestamp - this.lastFrameTime) / 1000;  // Convert to seconds
            this.lastFrameTime = timestamp;

            // Apply fade to float buffer if decay rate > 0
            if (this.decayRate > 0 && this.floatBuffer) {
                // Calculate decay multiplier
                // decayRate of 1 = slow fade, 10 = fast fade
                // Using exponential decay: value *= e^(-rate * dt)
                const decayMultiplier = Math.exp(-this.decayRate * deltaTime * 2.0);

                // Apply decay to all pixels in float buffer
                for (let i = 0; i < this.floatBuffer.length; i++) {
                    this.floatBuffer[i] *= decayMultiplier;
                }
            }

            // Render float buffer to canvas
            this.renderBufferToCanvas();

            // Send canvas frame to server at ~20fps
            this.frameSendCounter = (this.frameSendCounter || 0) + 1;
            if (this.frameSendCounter >= 3) {  // Every 3rd frame (~20fps from 60fps)
                this.frameSendCounter = 0;
                this.sendCanvasFrame();
            }

            requestAnimationFrame(render);
        };

        requestAnimationFrame(render);
    }

    renderBufferToCanvas() {
        if (!this.floatBuffer) return;

        // Create ImageData at canvas resolution
        const imageData = this.ctx.createImageData(this.canvas.width, this.canvas.height);
        const data = imageData.data;

        // Render each matrix pixel as a scaled block
        for (let my = 0; my < this.matrixHeight; my++) {
            for (let mx = 0; mx < this.matrixWidth; mx++) {
                const bufIdx = (my * this.matrixWidth + mx) * 3;
                const r = Math.round(Math.min(255, Math.max(0, this.floatBuffer[bufIdx])));
                const g = Math.round(Math.min(255, Math.max(0, this.floatBuffer[bufIdx + 1])));
                const b = Math.round(Math.min(255, Math.max(0, this.floatBuffer[bufIdx + 2])));

                // Fill the scaled block
                for (let sy = 0; sy < this.scale; sy++) {
                    for (let sx = 0; sx < this.scale; sx++) {
                        const canvasX = mx * this.scale + sx;
                        const canvasY = my * this.scale + sy;
                        const canvasIdx = (canvasY * this.canvas.width + canvasX) * 4;
                        data[canvasIdx] = r;
                        data[canvasIdx + 1] = g;
                        data[canvasIdx + 2] = b;
                        data[canvasIdx + 3] = 255;  // Alpha
                    }
                }
            }
        }

        this.ctx.putImageData(imageData, 0, 0);
    }

    sendCanvasFrame() {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN || !this.floatBuffer) return;

        // Convert float buffer to uint8 for sending
        const frameData = new Uint8Array(this.matrixWidth * this.matrixHeight * 3);

        for (let i = 0; i < this.floatBuffer.length; i++) {
            frameData[i] = Math.round(Math.min(255, Math.max(0, this.floatBuffer[i])));
        }

        // Send as binary
        this.ws.send(frameData.buffer);
    }

    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        this.updateStatus('Connecting...', '');
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            this.updateStatus('Connected', 'connected');
        };

        this.ws.onclose = () => {
            this.updateStatus('Disconnected', 'error');
            // Reconnect after 2 seconds
            setTimeout(() => this.connect(), 2000);
        };

        this.ws.onerror = () => {
            this.updateStatus('Error', 'error');
        };

        this.ws.onmessage = (event) => {
            this.handleMessage(JSON.parse(event.data));
        };
    }

    handleMessage(msg) {
        switch (msg.type) {
            case 'config':
                this.matrixWidth = msg.width;
                this.matrixHeight = msg.height;
                this.initFloatBuffer();
                this.updateCanvasSize();
                document.getElementById('matrix-info').textContent =
                    `Matrix: ${msg.width}x${msg.height}`;
                break;

            case 'status':
                document.getElementById('fps-display').textContent =
                    `FPS: ${msg.fps}`;
                break;
        }
    }

    sendMessage(msg) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(msg));
        }
    }

    updateStatus(text, className) {
        const status = document.getElementById('status');
        status.textContent = text;
        status.className = 'status ' + className;
    }

    getCanvasPos(event) {
        const rect = this.canvas.getBoundingClientRect();
        const x = (event.clientX - rect.left) / this.canvas.width;
        const y = (event.clientY - rect.top) / this.canvas.height;
        return { x: Math.max(0, Math.min(1, x)), y: Math.max(0, Math.min(1, y)) };
    }

    handlePointerStart(event) {
        this.isDrawing = true;
        const pos = this.getCanvasPos(event);
        this.lastPos = pos;

        // Draw to float buffer
        this.drawPointToBuffer(pos.x, pos.y);

        // Send to server
        this.sendMessage({
            type: 'touch_start',
            x: pos.x,
            y: pos.y,
            color: this.color,
            radius: this.radius
        });
    }

    handlePointerMove(event) {
        if (!this.isDrawing) return;

        const pos = this.getCanvasPos(event);

        // Draw to float buffer
        if (this.lastPos) {
            this.drawLineToBuffer(this.lastPos.x, this.lastPos.y, pos.x, pos.y);
        }
        this.lastPos = pos;

        // Send to server
        this.sendMessage({
            type: 'touch_move',
            x: pos.x,
            y: pos.y
        });
    }

    handlePointerEnd() {
        if (!this.isDrawing) return;
        this.isDrawing = false;
        this.lastPos = null;

        this.sendMessage({ type: 'touch_end' });
    }

    // Draw a filled circle to the float buffer at matrix resolution
    drawPointToBuffer(x, y) {
        if (!this.floatBuffer) return;

        const cx = x * this.matrixWidth;
        const cy = y * this.matrixHeight;

        // Draw filled circle
        for (let my = 0; my < this.matrixHeight; my++) {
            for (let mx = 0; mx < this.matrixWidth; mx++) {
                const dx = mx + 0.5 - cx;
                const dy = my + 0.5 - cy;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist <= this.radius) {
                    const idx = (my * this.matrixWidth + mx) * 3;
                    this.floatBuffer[idx] = this.color[0];
                    this.floatBuffer[idx + 1] = this.color[1];
                    this.floatBuffer[idx + 2] = this.color[2];
                }
            }
        }
    }

    // Draw a line to the float buffer using Bresenham-style interpolation
    drawLineToBuffer(x1, y1, x2, y2) {
        if (!this.floatBuffer) return;

        // Convert to matrix coordinates
        const mx1 = x1 * this.matrixWidth;
        const my1 = y1 * this.matrixHeight;
        const mx2 = x2 * this.matrixWidth;
        const my2 = y2 * this.matrixHeight;

        // Calculate distance and step count
        const dx = mx2 - mx1;
        const dy = my2 - my1;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const steps = Math.max(1, Math.ceil(dist * 2));  // 2 samples per pixel

        // Draw points along the line
        for (let i = 0; i <= steps; i++) {
            const t = i / steps;
            const cx = mx1 + dx * t;
            const cy = my1 + dy * t;

            // Draw filled circle at this point
            for (let my = 0; my < this.matrixHeight; my++) {
                for (let mx = 0; mx < this.matrixWidth; mx++) {
                    const pdx = mx + 0.5 - cx;
                    const pdy = my + 0.5 - cy;
                    const pdist = Math.sqrt(pdx * pdx + pdy * pdy);

                    if (pdist <= this.radius) {
                        const idx = (my * this.matrixWidth + mx) * 3;
                        this.floatBuffer[idx] = this.color[0];
                        this.floatBuffer[idx + 1] = this.color[1];
                        this.floatBuffer[idx + 2] = this.color[2];
                    }
                }
            }
        }
    }

    clearCanvas() {
        if (this.floatBuffer) {
            this.floatBuffer.fill(0);
        }
        this.renderBufferToCanvas();
        this.sendMessage({ type: 'clear_canvas' });
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.auroraPaint = new AuroraPaint();
});
