/**
 * Aurora - WebSocket client for LED matrix control
 * Supports Paint mode (finger painting) and Pattern mode (server-generated patterns)
 */

class AuroraApp {
    constructor() {
        this.canvas = document.getElementById('paint-canvas');
        this.ctx = this.canvas.getContext('2d');
        this.ws = null;
        this.matrixWidth = 32;
        this.matrixHeight = 18;
        this.scale = 10;
        this.color = [255, 255, 255];
        this.radius = 1;
        this.isDrawing = false;
        this.lastPos = null;
        this.decayRate = 0;
        this.lastFrameTime = 0;

        // Mode: "paint" or "pattern"
        this.mode = "paint";

        // Available drawers
        this.drawers = [];
        this.activeDrawer = null;

        // Float buffer for smooth fading
        this.floatBuffer = null;

        this.init();
    }

    init() {
        this.setupCanvas();
        this.setupControls();
        this.setupModeToggle();
        this.connect();
        this.startRenderLoop();
    }

    initFloatBuffer() {
        this.floatBuffer = new Float32Array(this.matrixWidth * this.matrixHeight * 3);
    }

    setupCanvas() {
        this.updateCanvasSize();
        this.ctx.fillStyle = '#000';
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        // Mouse events
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

        window.addEventListener('resize', () => this.updateCanvasSize());
    }

    updateCanvasSize() {
        const container = document.getElementById('canvas-container');
        const maxWidth = container.clientWidth * 0.94;
        const maxHeight = container.clientHeight * 0.94;

        const scaleX = maxWidth / this.matrixWidth;
        const scaleY = maxHeight / this.matrixHeight;
        this.scale = Math.floor(Math.min(scaleX, scaleY));

        this.canvas.width = this.matrixWidth * this.scale;
        this.canvas.height = this.matrixHeight * this.scale;

        if (!this.floatBuffer) {
            this.initFloatBuffer();
        }

        this.renderBufferToCanvas();
    }

    setupModeToggle() {
        const paintBtn = document.getElementById('mode-paint');
        const patternBtn = document.getElementById('mode-pattern');

        paintBtn.addEventListener('click', () => this.setMode('paint'));
        patternBtn.addEventListener('click', () => this.setMode('pattern'));
    }

    setMode(mode) {
        this.mode = mode;

        // Update UI
        document.getElementById('mode-paint').classList.toggle('active', mode === 'paint');
        document.getElementById('mode-pattern').classList.toggle('active', mode === 'pattern');

        document.getElementById('canvas-container').classList.toggle('hidden', mode === 'pattern');
        document.getElementById('pattern-info').classList.toggle('hidden', mode === 'paint');

        document.getElementById('paint-controls').classList.toggle('hidden', mode === 'pattern');
        document.getElementById('pattern-controls').classList.toggle('hidden', mode === 'paint');

        // Notify server
        this.sendMessage({ type: 'set_mode', mode: mode });
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
            });
        });

        // Brush size
        const brushSizeInput = document.getElementById('brush-size');
        const brushSizeLabel = document.getElementById('brush-size-label');
        brushSizeInput.addEventListener('input', () => {
            this.radius = parseInt(brushSizeInput.value);
            brushSizeLabel.textContent = this.radius;
        });

        // Decay rate
        const decayInput = document.getElementById('decay-rate');
        const decayLabel = document.getElementById('decay-label');
        decayInput.addEventListener('input', () => {
            const rate = parseFloat(decayInput.value) / 10;
            this.decayRate = rate;
            decayLabel.textContent = rate.toFixed(1);
        });

        // Clear button
        document.getElementById('clear-btn').addEventListener('click', () => {
            this.clearCanvas();
        });

        // Drawer select
        document.getElementById('drawer-select').addEventListener('change', (e) => {
            const drawerName = e.target.value;
            if (drawerName) {
                this.sendMessage({ type: 'set_drawer', drawer: drawerName });
            }
        });

        // Randomize button
        document.getElementById('randomize-btn').addEventListener('click', () => {
            this.sendMessage({ type: 'randomize_drawer' });
        });

        // Palette slider
        const paletteSlider = document.getElementById('palette-slider');
        const paletteLabel = document.getElementById('palette-label');
        paletteSlider.addEventListener('input', () => {
            const index = parseInt(paletteSlider.value);
            paletteLabel.textContent = index;
            this.sendMessage({ type: 'set_palette', index: index });
        });
    }

    updatePaletteSlider(index, count) {
        const slider = document.getElementById('palette-slider');
        const label = document.getElementById('palette-label');
        if (count !== undefined) {
            slider.max = count - 1;
        }
        slider.value = index;
        label.textContent = index;
    }

    populateDrawerSelect(drawers) {
        const select = document.getElementById('drawer-select');
        select.innerHTML = '<option value="">-- Select Pattern --</option>';

        drawers.forEach(drawer => {
            const option = document.createElement('option');
            option.value = drawer.name;
            option.textContent = drawer.name;
            select.appendChild(option);
        });

        this.drawers = drawers;
    }

    updateDrawerSettings(settings) {
        const container = document.getElementById('drawer-settings');
        container.innerHTML = '';

        for (const [key, info] of Object.entries(settings)) {
            const group = document.createElement('div');
            group.className = 'control-group';

            const label = document.createElement('label');
            const labelSpan = document.createElement('span');
            labelSpan.id = `setting-${key}-label`;
            labelSpan.textContent = info.value;
            label.textContent = `${key}: `;
            label.appendChild(labelSpan);

            const input = document.createElement('input');
            input.type = 'range';
            input.min = info.min;
            input.max = info.max;
            input.value = info.value;
            input.dataset.setting = key;

            input.addEventListener('input', () => {
                labelSpan.textContent = input.value;
                this.sendMessage({
                    type: 'set_drawer_settings',
                    settings: { [key]: parseInt(input.value) }
                });
            });

            group.appendChild(label);
            group.appendChild(input);
            container.appendChild(group);
        }
    }

    startRenderLoop() {
        const render = (timestamp) => {
            if (this.lastFrameTime === 0) {
                this.lastFrameTime = timestamp;
            }

            const deltaTime = (timestamp - this.lastFrameTime) / 1000;
            this.lastFrameTime = timestamp;

            // Only process in paint mode
            if (this.mode === 'paint') {
                // Apply fade to float buffer if decay rate > 0
                if (this.decayRate > 0 && this.floatBuffer) {
                    const decayMultiplier = Math.exp(-this.decayRate * deltaTime * 0.2);
                    for (let i = 0; i < this.floatBuffer.length; i++) {
                        this.floatBuffer[i] *= decayMultiplier;
                    }
                }

                // Render float buffer to canvas
                this.renderBufferToCanvas();

                // Send canvas frame to server at ~20fps
                this.frameSendCounter = (this.frameSendCounter || 0) + 1;
                if (this.frameSendCounter >= 3) {
                    this.frameSendCounter = 0;
                    this.sendCanvasFrame();
                }
            }

            requestAnimationFrame(render);
        };

        requestAnimationFrame(render);
    }

    renderBufferToCanvas() {
        if (!this.floatBuffer) return;

        const imageData = this.ctx.createImageData(this.canvas.width, this.canvas.height);
        const data = imageData.data;

        for (let my = 0; my < this.matrixHeight; my++) {
            for (let mx = 0; mx < this.matrixWidth; mx++) {
                const bufIdx = (my * this.matrixWidth + mx) * 3;
                const r = Math.round(Math.min(255, Math.max(0, this.floatBuffer[bufIdx])));
                const g = Math.round(Math.min(255, Math.max(0, this.floatBuffer[bufIdx + 1])));
                const b = Math.round(Math.min(255, Math.max(0, this.floatBuffer[bufIdx + 2])));

                for (let sy = 0; sy < this.scale; sy++) {
                    for (let sx = 0; sx < this.scale; sx++) {
                        const canvasX = mx * this.scale + sx;
                        const canvasY = my * this.scale + sy;
                        const canvasIdx = (canvasY * this.canvas.width + canvasX) * 4;
                        data[canvasIdx] = r;
                        data[canvasIdx + 1] = g;
                        data[canvasIdx + 2] = b;
                        data[canvasIdx + 3] = 255;
                    }
                }
            }
        }

        this.ctx.putImageData(imageData, 0, 0);
    }

    sendCanvasFrame() {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN || !this.floatBuffer) return;
        if (this.mode !== 'paint') return;

        const frameData = new Uint8Array(this.matrixWidth * this.matrixHeight * 3);

        for (let i = 0; i < this.floatBuffer.length; i++) {
            frameData[i] = Math.round(Math.min(255, Math.max(0, this.floatBuffer[i])));
        }

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

                // Handle initial mode and drawers
                if (msg.mode) {
                    this.mode = msg.mode;
                    this.setMode(msg.mode);
                }
                if (msg.drawers) {
                    this.populateDrawerSelect(msg.drawers);
                }
                if (msg.active_drawer) {
                    document.getElementById('drawer-select').value = msg.active_drawer;
                    document.getElementById('current-pattern-name').textContent = msg.active_drawer;
                    // Find drawer settings
                    const drawer = msg.drawers?.find(d => d.name === msg.active_drawer);
                    if (drawer) {
                        this.updateDrawerSettings(drawer.settings);
                    }
                }
                if (msg.palette_index !== undefined) {
                    this.updatePaletteSlider(msg.palette_index, msg.palette_count);
                }
                break;

            case 'status':
                document.getElementById('fps-display').textContent = `FPS: ${msg.fps}`;
                if (msg.drawer) {
                    document.getElementById('current-pattern-name').textContent = msg.drawer;
                }
                break;

            case 'mode_changed':
                this.mode = msg.mode;
                document.getElementById('mode-paint').classList.toggle('active', msg.mode === 'paint');
                document.getElementById('mode-pattern').classList.toggle('active', msg.mode === 'pattern');
                break;

            case 'drawer_changed':
                document.getElementById('drawer-select').value = msg.drawer;
                document.getElementById('current-pattern-name').textContent = msg.drawer;
                if (msg.settings) {
                    this.updateDrawerSettings(msg.settings);
                }
                if (msg.palette_index !== undefined) {
                    this.updatePaletteSlider(msg.palette_index);
                }
                break;

            case 'auto_rotated':
                document.getElementById('drawer-select').value = msg.drawer;
                document.getElementById('current-pattern-name').textContent = msg.drawer;
                if (msg.settings) {
                    this.updateDrawerSettings(msg.settings);
                }
                if (msg.palette_index !== undefined) {
                    this.updatePaletteSlider(msg.palette_index);
                }
                break;

            case 'drawers_list':
                this.populateDrawerSelect(msg.drawers);
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
        if (this.mode !== 'paint') return;
        this.isDrawing = true;
        const pos = this.getCanvasPos(event);
        this.lastPos = pos;
        this.drawPointToBuffer(pos.x, pos.y);
    }

    handlePointerMove(event) {
        if (!this.isDrawing || this.mode !== 'paint') return;
        const pos = this.getCanvasPos(event);
        if (this.lastPos) {
            this.drawLineToBuffer(this.lastPos.x, this.lastPos.y, pos.x, pos.y);
        }
        this.lastPos = pos;
    }

    handlePointerEnd() {
        this.isDrawing = false;
        this.lastPos = null;
    }

    drawPointToBuffer(x, y) {
        if (!this.floatBuffer) return;

        const cx = x * this.matrixWidth;
        const cy = y * this.matrixHeight;

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

    drawLineToBuffer(x1, y1, x2, y2) {
        if (!this.floatBuffer) return;

        const mx1 = x1 * this.matrixWidth;
        const my1 = y1 * this.matrixHeight;
        const mx2 = x2 * this.matrixWidth;
        const my2 = y2 * this.matrixHeight;

        const dx = mx2 - mx1;
        const dy = my2 - my1;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const steps = Math.max(1, Math.ceil(dist * 2));

        for (let i = 0; i <= steps; i++) {
            const t = i / steps;
            const cx = mx1 + dx * t;
            const cy = my1 + dy * t;

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
    window.auroraApp = new AuroraApp();
});
