/**
 * Aurora Paint - WebSocket client and canvas drawing logic
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
        this.radius = 3;
        this.isDrawing = false;
        this.lastPos = null;

        this.init();
    }

    init() {
        this.setupCanvas();
        this.setupControls();
        this.connect();
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

        // Redraw
        this.ctx.fillStyle = '#000';
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
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
            decayLabel.textContent = rate.toFixed(1);
            this.sendMessage({ type: 'set_decay', rate: rate });
        });

        // Clear button
        document.getElementById('clear-btn').addEventListener('click', () => {
            this.clearCanvas();
        });
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

        // Draw locally
        this.drawPoint(pos.x, pos.y);

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

        // Draw locally
        if (this.lastPos) {
            this.drawLine(this.lastPos.x, this.lastPos.y, pos.x, pos.y);
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

    drawPoint(x, y) {
        const px = x * this.matrixWidth;
        const py = y * this.matrixHeight;

        this.ctx.fillStyle = `rgb(${this.color.join(',')})`;
        this.ctx.beginPath();
        this.ctx.arc(
            px * this.scale,
            py * this.scale,
            this.radius * this.scale,
            0,
            Math.PI * 2
        );
        this.ctx.fill();
    }

    drawLine(x1, y1, x2, y2) {
        const px1 = x1 * this.matrixWidth * this.scale;
        const py1 = y1 * this.matrixHeight * this.scale;
        const px2 = x2 * this.matrixWidth * this.scale;
        const py2 = y2 * this.matrixHeight * this.scale;

        this.ctx.strokeStyle = `rgb(${this.color.join(',')})`;
        this.ctx.lineWidth = this.radius * this.scale * 2;
        this.ctx.lineCap = 'round';
        this.ctx.beginPath();
        this.ctx.moveTo(px1, py1);
        this.ctx.lineTo(px2, py2);
        this.ctx.stroke();

        // Also draw end point
        this.drawPoint(x2, y2);
    }

    clearCanvas() {
        this.ctx.fillStyle = '#000';
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        this.sendMessage({ type: 'clear_canvas' });
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.auroraPaint = new AuroraPaint();
});
