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

        // Mode: "paint", "pattern", or "code"
        this.mode = "paint";

        // Available drawers
        this.drawers = [];
        this.activeDrawer = null;

        // Float buffer for smooth fading
        this.floatBuffer = null;

        // Stroke history for undo/redo
        this.undoStack = [];       // Array of Float32Array snapshots
        this.redoStack = [];       // Array of Float32Array snapshots
        this.maxUndoLevels = 50;
        this.currentStroke = null;  // Tracks in-progress stroke metadata
        this.strokeHistory = [];    // Completed stroke metadata (color, radius, path)

        this.init();
    }

    init() {
        this.setupCanvas();
        this.setupPreviewCanvas();
        this.setupControls();
        this.setupModeToggle();
        this.setupKeyboardShortcuts();
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

        // Skip if container is hidden (0 dimensions)
        if (maxWidth <= 0 || maxHeight <= 0) return;

        const scaleX = maxWidth / this.matrixWidth;
        const scaleY = maxHeight / this.matrixHeight;
        this.scale = Math.max(1, Math.floor(Math.min(scaleX, scaleY)));

        this.canvas.width = this.matrixWidth * this.scale;
        this.canvas.height = this.matrixHeight * this.scale;

        if (!this.floatBuffer) {
            this.initFloatBuffer();
        }

        this.renderBufferToCanvas();
    }

    setupModeToggle() {
        document.getElementById('mode-paint').addEventListener('click', () => this.setMode('paint'));
        document.getElementById('mode-pattern').addEventListener('click', () => this.setMode('pattern'));
        document.getElementById('mode-code').addEventListener('click', () => this.setMode('code'));
    }

    setMode(mode, fromServer = false) {
        this.mode = mode;

        // Update mode toggle buttons
        document.getElementById('mode-paint').classList.toggle('active', mode === 'paint');
        document.getElementById('mode-pattern').classList.toggle('active', mode === 'pattern');
        document.getElementById('mode-code').classList.toggle('active', mode === 'code');

        // Show/hide main content areas
        const showPreview = mode === 'pattern' || mode === 'code';
        document.getElementById('canvas-container').classList.toggle('hidden', mode !== 'paint');
        document.getElementById('content-area').classList.toggle('hidden', !showPreview);
        document.getElementById('content-area').classList.toggle('code-layout', mode === 'code');
        document.getElementById('code-container').classList.toggle('hidden', mode !== 'code');

        // Show/hide control sections
        document.getElementById('paint-controls').classList.toggle('hidden', mode !== 'paint');
        document.getElementById('pattern-controls').classList.toggle('hidden', mode !== 'pattern');
        document.getElementById('code-controls').classList.toggle('hidden', mode !== 'code');

        // Recalculate canvas size when switching to paint mode
        if (mode === 'paint') {
            requestAnimationFrame(() => this.updateCanvasSize());
        }

        // Refresh CodeMirror when code tab becomes visible
        if (mode === 'code') {
            if (!this.codeTemplateLoaded) {
                this.sendMessage({ type: 'get_code_template' });
            }
            requestAnimationFrame(() => this.codeMirror.refresh());
        }

        // Notify server — but skip if this was triggered by server to avoid feedback loop
        if (!fromServer) {
            const serverMode = mode === 'code' ? 'pattern' : mode;
            this.sendMessage({ type: 'set_mode', mode: serverMode });
        }
    }

    setupControls() {
        // Color picker
        const swatches = document.querySelectorAll('.color-swatch');
        swatches.forEach((swatch, index) => {
            if (index === 1) swatch.classList.add('selected');  // default to white
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

        // Undo/Redo buttons
        document.getElementById('undo-btn').addEventListener('click', () => {
            this.undo();
        });
        document.getElementById('redo-btn').addEventListener('click', () => {
            this.redo();
        });
        this.updateUndoRedoButtons();

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

        // Code editor (CodeMirror)
        this.codeTemplateLoaded = false;
        this.codeMirror = CodeMirror.fromTextArea(document.getElementById('code-editor'), {
            mode: 'python',
            theme: 'material-darker',
            lineNumbers: true,
            indentUnit: 4,
            tabSize: 4,
            indentWithTabs: false,
            lineWrapping: false,
            extraKeys: {
                'Cmd-Enter': () => this.submitCode(),
                'Ctrl-Enter': () => this.submitCode(),
            },
        });

        // Run button
        document.getElementById('run-code-btn').addEventListener('click', () => {
            this.submitCode();
        });

        // Stop button
        document.getElementById('stop-code-btn').addEventListener('click', () => {
            this.stopCode();
        });

        // Code palette slider
        const codePaletteSlider = document.getElementById('code-palette-slider');
        const codePaletteLabel = document.getElementById('code-palette-label');
        codePaletteSlider.addEventListener('input', () => {
            const index = parseInt(codePaletteSlider.value);
            codePaletteLabel.textContent = index;
            this.sendMessage({ type: 'set_palette', index: index });
        });
    }

    updatePaletteSlider(index, count) {
        console.log('updatePaletteSlider called:', index, count);
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

        // Draw pixel grid lines
        if (this.scale >= 4) {
            this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
            this.ctx.lineWidth = 1;
            this.ctx.beginPath();
            for (let x = 0; x <= this.matrixWidth; x++) {
                const px = x * this.scale + 0.5;
                this.ctx.moveTo(px, 0);
                this.ctx.lineTo(px, this.canvas.height);
            }
            for (let y = 0; y <= this.matrixHeight; y++) {
                const py = y * this.scale + 0.5;
                this.ctx.moveTo(0, py);
                this.ctx.lineTo(this.canvas.width, py);
            }
            this.ctx.stroke();
        }
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

        this.ws.binaryType = 'arraybuffer';
        this.ws.onmessage = (event) => {
            if (event.data instanceof ArrayBuffer) {
                this.handlePreviewFrame(event.data);
            } else {
                this.handleMessage(JSON.parse(event.data));
            }
        };
    }

    handleMessage(msg) {
        console.log('Received message:', msg);
        switch (msg.type) {
            case 'config':
                this.matrixWidth = msg.width;
                this.matrixHeight = msg.height;
                this.initFloatBuffer();
                this.updateCanvasSize();
                this.updatePreviewCanvasSize();
                document.getElementById('matrix-info').textContent =
                    `Matrix: ${msg.width}x${msg.height}`;

                // Handle initial mode and drawers
                if (msg.mode) {
                    this.setMode(msg.mode, true);
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
                // Server only knows paint/pattern — don't override if we're in code mode
                if (this.mode !== 'code') {
                    this.setMode(msg.mode, true);
                }
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

            case 'code_result':
                this.handleCodeResult(msg);
                break;

            case 'code_template':
                this.handleCodeTemplate(msg);
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
        const x = (event.clientX - rect.left) / rect.width;
        const y = (event.clientY - rect.top) / rect.height;
        return { x: Math.max(0, Math.min(1, x)), y: Math.max(0, Math.min(1, y)) };
    }

    handlePointerStart(event) {
        if (this.mode !== 'paint') return;
        this.isDrawing = true;
        const pos = this.getCanvasPos(event);
        this.lastPos = pos;

        // Save buffer snapshot for undo before the stroke begins
        this.pushUndoSnapshot();

        // Begin tracking stroke metadata
        this.currentStroke = {
            color: [...this.color],
            radius: this.radius,
            points: [{ x: pos.x, y: pos.y }]
        };

        this.drawPointToBuffer(pos.x, pos.y);
    }

    handlePointerMove(event) {
        if (!this.isDrawing || this.mode !== 'paint') return;
        const pos = this.getCanvasPos(event);
        if (this.lastPos) {
            this.drawLineToBuffer(this.lastPos.x, this.lastPos.y, pos.x, pos.y);
        }
        this.lastPos = pos;

        // Track stroke path
        if (this.currentStroke) {
            this.currentStroke.points.push({ x: pos.x, y: pos.y });
        }
    }

    handlePointerEnd() {
        if (this.isDrawing && this.currentStroke) {
            // Save completed stroke metadata
            this.strokeHistory.push(this.currentStroke);
            this.currentStroke = null;

            // New stroke clears redo stack
            this.redoStack = [];
            this.updateUndoRedoButtons();
        }
        this.isDrawing = false;
        this.lastPos = null;
    }

    setPixel(mx, my) {
        if (mx < 0 || mx >= this.matrixWidth || my < 0 || my >= this.matrixHeight) return;
        const idx = (my * this.matrixWidth + mx) * 3;
        this.floatBuffer[idx] = this.color[0];
        this.floatBuffer[idx + 1] = this.color[1];
        this.floatBuffer[idx + 2] = this.color[2];
    }

    drawPointToBuffer(x, y) {
        if (!this.floatBuffer) return;

        const cx = x * this.matrixWidth;
        const cy = y * this.matrixHeight;

        if (this.radius <= 1) {
            // Single pixel: just the pixel under the cursor
            this.setPixel(Math.floor(cx), Math.floor(cy));
        } else {
            const effectiveRadius = this.radius - 0.5;
            for (let my = 0; my < this.matrixHeight; my++) {
                for (let mx = 0; mx < this.matrixWidth; mx++) {
                    const dx = mx + 0.5 - cx;
                    const dy = my + 0.5 - cy;
                    const dist = Math.sqrt(dx * dx + dy * dy);

                    if (dist <= effectiveRadius) {
                        this.setPixel(mx, my);
                    }
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

            if (this.radius <= 1) {
                this.setPixel(Math.floor(cx), Math.floor(cy));
            } else {
                const effectiveRadius = this.radius - 0.5;
                for (let my = 0; my < this.matrixHeight; my++) {
                    for (let mx = 0; mx < this.matrixWidth; mx++) {
                        const pdx = mx + 0.5 - cx;
                        const pdy = my + 0.5 - cy;
                        const pdist = Math.sqrt(pdx * pdx + pdy * pdy);

                        if (pdist <= effectiveRadius) {
                            this.setPixel(mx, my);
                        }
                    }
                }
            }
        }
    }

    clearCanvas() {
        if (this.floatBuffer) {
            // Save snapshot so clear is undoable
            this.pushUndoSnapshot();
            this.redoStack = [];

            this.floatBuffer.fill(0);
        }
        this.renderBufferToCanvas();
        this.sendMessage({ type: 'clear_canvas' });
        this.updateUndoRedoButtons();
    }

    // --- Undo/Redo ---

    pushUndoSnapshot() {
        if (!this.floatBuffer) return;
        this.undoStack.push(new Float32Array(this.floatBuffer));
        if (this.undoStack.length > this.maxUndoLevels) {
            this.undoStack.shift();
        }
    }

    undo() {
        if (this.undoStack.length === 0 || !this.floatBuffer) return;

        // Save current state to redo stack
        this.redoStack.push(new Float32Array(this.floatBuffer));

        // Restore previous state
        const snapshot = this.undoStack.pop();
        this.floatBuffer.set(snapshot);
        this.renderBufferToCanvas();
        this.sendCanvasFrame();
        this.updateUndoRedoButtons();
    }

    redo() {
        if (this.redoStack.length === 0 || !this.floatBuffer) return;

        // Save current state to undo stack
        this.undoStack.push(new Float32Array(this.floatBuffer));

        // Restore redo state
        const snapshot = this.redoStack.pop();
        this.floatBuffer.set(snapshot);
        this.renderBufferToCanvas();
        this.sendCanvasFrame();
        this.updateUndoRedoButtons();
    }

    updateUndoRedoButtons() {
        const undoBtn = document.getElementById('undo-btn');
        const redoBtn = document.getElementById('redo-btn');
        if (undoBtn) undoBtn.disabled = this.undoStack.length === 0;
        if (redoBtn) redoBtn.disabled = this.redoStack.length === 0;
    }

    // --- Preview Canvas ---

    setupPreviewCanvas() {
        this.previewCanvas = document.getElementById('preview-canvas');
        this.previewCtx = this.previewCanvas.getContext('2d');
        this.updatePreviewCanvasSize();
    }

    updatePreviewCanvasSize() {
        // Scale preview to a reasonable size while maintaining aspect ratio
        const previewScale = 8;
        this.previewCanvas.width = this.matrixWidth * previewScale;
        this.previewCanvas.height = this.matrixHeight * previewScale;
        this.previewScale = previewScale;
    }

    handlePreviewFrame(buffer) {
        if (!this.previewCtx) return;

        const data = new Uint8Array(buffer);
        const expectedSize = this.matrixWidth * this.matrixHeight * 3;
        if (data.length !== expectedSize) return;

        const scale = this.previewScale;
        const imageData = this.previewCtx.createImageData(
            this.previewCanvas.width, this.previewCanvas.height
        );
        const pixels = imageData.data;

        for (let my = 0; my < this.matrixHeight; my++) {
            for (let mx = 0; mx < this.matrixWidth; mx++) {
                const srcIdx = (my * this.matrixWidth + mx) * 3;
                const r = data[srcIdx];
                const g = data[srcIdx + 1];
                const b = data[srcIdx + 2];

                for (let sy = 0; sy < scale; sy++) {
                    for (let sx = 0; sx < scale; sx++) {
                        const cx = mx * scale + sx;
                        const cy = my * scale + sy;
                        const dstIdx = (cy * this.previewCanvas.width + cx) * 4;
                        pixels[dstIdx] = r;
                        pixels[dstIdx + 1] = g;
                        pixels[dstIdx + 2] = b;
                        pixels[dstIdx + 3] = 255;
                    }
                }
            }
        }

        this.previewCtx.putImageData(imageData, 0, 0);
    }

    // --- Code Editor ---

    submitCode() {
        const code = this.codeMirror.getValue();
        if (!code.trim()) return;

        const errorEl = document.getElementById('code-error');
        errorEl.classList.add('hidden');
        errorEl.textContent = '';

        // Disable run button while submitting
        const runBtn = document.getElementById('run-code-btn');
        runBtn.disabled = true;
        runBtn.textContent = '... Running';

        this.sendMessage({ type: 'submit_code', code: code });
    }

    handleCodeResult(msg) {
        const runBtn = document.getElementById('run-code-btn');
        const stopBtn = document.getElementById('stop-code-btn');
        runBtn.disabled = false;
        runBtn.textContent = '\u25B6 Run';

        const errorEl = document.getElementById('code-error');
        if (msg.success) {
            errorEl.classList.add('hidden');
            stopBtn.disabled = false;
            // Brief green flash on run button
            runBtn.style.background = '#0a7e35';
            setTimeout(() => { runBtn.style.background = ''; }, 600);
        } else {
            errorEl.textContent = msg.error;
            errorEl.classList.remove('hidden');
        }
    }

    stopCode() {
        this.sendMessage({ type: 'stop_code' });
        const stopBtn = document.getElementById('stop-code-btn');
        stopBtn.disabled = true;
    }

    handleCodeTemplate(msg) {
        if (!this.codeTemplateLoaded && this.codeMirror.getValue() === '') {
            this.codeMirror.setValue(msg.code);
            this.codeTemplateLoaded = true;
        }
    }

    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            if (this.mode !== 'paint') return;

            const isCtrlOrCmd = e.ctrlKey || e.metaKey;
            if (isCtrlOrCmd && e.key === 'z' && !e.shiftKey) {
                e.preventDefault();
                this.undo();
            } else if (isCtrlOrCmd && e.key === 'z' && e.shiftKey) {
                e.preventDefault();
                this.redo();
            } else if (isCtrlOrCmd && e.key === 'y') {
                e.preventDefault();
                this.redo();
            }
        });
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.auroraApp = new AuroraApp();
});
