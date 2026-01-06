/**
 * Terminal module for termweave
 * Handles xterm.js and WebSocket communication
 */

class TerminalManager {
    constructor(container) {
        this.container = container;
        this.terminal = null;
        this.fitAddon = null;
        this.webLinksAddon = null;
        this.ws = null;
        this.sessionId = null;
        this.onDisconnect = null;
    }

    /**
     * Connect to a terminal session
     * @param {string} sessionId
     * @param {string} token - JWT access token
     * @returns {Promise<void>}
     */
    async connect(sessionId, token) {
        this.sessionId = sessionId;

        // Initialize xterm.js
        this.terminal = new Terminal({
            cursorBlink: true,
            cursorStyle: 'block',
            fontSize: 14,
            fontFamily: 'Menlo, Monaco, "Courier New", monospace',
            theme: {
                background: '#1a1a2e',
                foreground: '#eee',
                cursor: '#e94560',
                cursorAccent: '#1a1a2e',
                selection: 'rgba(233, 69, 96, 0.3)',
            },
            scrollback: 10000,
            allowProposedApi: true,
        });

        // Add addons
        this.fitAddon = new FitAddon.FitAddon();
        this.terminal.loadAddon(this.fitAddon);

        this.webLinksAddon = new WebLinksAddon.WebLinksAddon();
        this.terminal.loadAddon(this.webLinksAddon);

        // Open terminal in container
        this.terminal.open(this.container);
        this.fitAddon.fit();

        // Build WebSocket URL
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/terminal/${sessionId}?token=${encodeURIComponent(token)}`;

        // Connect WebSocket
        return new Promise((resolve, reject) => {
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this._sendResize();
                resolve();
            };

            this.ws.onclose = (event) => {
                console.log('WebSocket closed:', event.code, event.reason);
                if (this.onDisconnect) {
                    this.onDisconnect(event.reason || 'Connection closed');
                }
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                reject(new Error('WebSocket connection failed'));
            };

            this.ws.onmessage = (event) => {
                this._handleMessage(event);
            };

            // Handle terminal input
            this.terminal.onData((data) => {
                this._sendInput(data);
            });

            // Handle window resize
            window.addEventListener('resize', () => {
                this._handleResize();
            });

            // Also handle orientation change for mobile
            window.addEventListener('orientationchange', () => {
                setTimeout(() => this._handleResize(), 100);
            });
        });
    }

    /**
     * Disconnect from the terminal
     */
    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }

        if (this.terminal) {
            this.terminal.dispose();
            this.terminal = null;
        }

        this.container.innerHTML = '';
    }

    /**
     * Handle incoming WebSocket message
     * @param {MessageEvent} event
     */
    _handleMessage(event) {
        if (event.data instanceof Blob) {
            // Binary data - terminal output
            event.data.arrayBuffer().then((buffer) => {
                const text = new TextDecoder().decode(buffer);
                this.terminal.write(text);
            });
        } else if (typeof event.data === 'string') {
            // JSON control message
            try {
                const data = JSON.parse(event.data);
                this._handleControlMessage(data);
            } catch (e) {
                // Raw text output
                this.terminal.write(event.data);
            }
        }
    }

    /**
     * Handle control message from server
     * @param {Object} data
     */
    _handleControlMessage(data) {
        switch (data.type) {
            case 'pong':
                // Heartbeat response
                break;
            case 'error':
                console.error('Server error:', data.message);
                this.terminal.write(`\r\n\x1b[31mError: ${data.message}\x1b[0m\r\n`);
                break;
            case 'closed':
                console.log('Session closed:', data.reason);
                if (this.onDisconnect) {
                    this.onDisconnect(data.reason);
                }
                break;
        }
    }

    /**
     * Send input to the server
     * @param {string} data
     */
    _sendInput(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            // Send as base64-encoded JSON
            const encoded = btoa(unescape(encodeURIComponent(data)));
            this.ws.send(JSON.stringify({
                type: 'input',
                data: encoded,
            }));
        }
    }

    /**
     * Send resize message to server
     */
    _sendResize() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN && this.terminal) {
            this.ws.send(JSON.stringify({
                type: 'resize',
                cols: this.terminal.cols,
                rows: this.terminal.rows,
            }));
        }
    }

    /**
     * Handle window resize
     */
    _handleResize() {
        if (this.fitAddon && this.terminal) {
            this.fitAddon.fit();
            this._sendResize();
        }
    }

    /**
     * Focus the terminal
     */
    focus() {
        if (this.terminal) {
            this.terminal.focus();
        }
    }
}

// Export for use in app.js
window.TerminalManager = TerminalManager;
