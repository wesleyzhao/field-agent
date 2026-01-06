/**
 * Main application for termweave
 */

class App {
    constructor() {
        this.auth = window.authManager;
        this.terminalManager = null;
        this.currentSessionId = null;

        // DOM elements
        this.loginView = document.getElementById('login-view');
        this.sessionsView = document.getElementById('sessions-view');
        this.terminalView = document.getElementById('terminal-view');

        this.loginForm = document.getElementById('login-form');
        this.loginError = document.getElementById('login-error');
        this.sessionsList = document.getElementById('sessions-list');
        this.sessionName = document.getElementById('session-name');
        this.terminalContainer = document.getElementById('terminal-container');

        this._bindEvents();
    }

    /**
     * Initialize the app
     */
    async init() {
        if (this.auth.isAuthenticated()) {
            this._showSessionsView();
            await this._loadSessions();
        } else {
            this._showLoginView();
        }
    }

    /**
     * Bind event handlers
     */
    _bindEvents() {
        // Login form
        this.loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            await this._handleLogin();
        });

        // Logout button
        document.getElementById('logout-btn').addEventListener('click', () => {
            this._handleLogout();
        });

        // Refresh button
        document.getElementById('refresh-btn').addEventListener('click', async () => {
            await this._loadSessions();
        });

        // New session button
        document.getElementById('new-session-btn').addEventListener('click', async () => {
            await this._createSession();
        });

        // Back from terminal
        document.getElementById('back-btn').addEventListener('click', () => {
            this._disconnectTerminal();
        });

        // Disconnect terminal
        document.getElementById('disconnect-btn').addEventListener('click', () => {
            this._disconnectTerminal();
        });
    }

    /**
     * Handle login form submission
     */
    async _handleLogin() {
        const passphrase = document.getElementById('passphrase').value;
        this.loginError.textContent = '';

        try {
            await this.auth.login(passphrase);
            this._showSessionsView();
            await this._loadSessions();
        } catch (error) {
            this.loginError.textContent = error.message;
        }
    }

    /**
     * Handle logout
     */
    _handleLogout() {
        this.auth.logout();
        this._disconnectTerminal();
        this._showLoginView();
        document.getElementById('passphrase').value = '';
    }

    /**
     * Load sessions list
     */
    async _loadSessions() {
        this.sessionsList.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

        try {
            const response = await fetch('/sessions', {
                headers: {
                    'Authorization': `Bearer ${this.auth.getAccessToken()}`,
                },
            });
            if (!response.ok) {
                if (response.status === 401) {
                    // Token expired, redirect to login
                    this._handleLogout();
                    return;
                }
                throw new Error('Failed to load sessions');
            }

            const data = await response.json();
            this._renderSessions(data.sessions);
        } catch (error) {
            console.error('Load sessions error:', error);
            this.sessionsList.innerHTML = `
                <div class="empty-state">
                    <p>Failed to load sessions</p>
                    <p style="font-size: 0.9rem">${error.message}</p>
                </div>
            `;
        }
    }

    /**
     * Render sessions list
     * @param {Array} sessions
     */
    _renderSessions(sessions) {
        if (sessions.length === 0) {
            this.sessionsList.innerHTML = `
                <div class="empty-state">
                    <p>No sessions yet</p>
                    <p style="font-size: 0.9rem">Create your first tmux session</p>
                </div>
            `;
            return;
        }

        this.sessionsList.innerHTML = sessions.map(session => `
            <div class="session-card" data-session-id="${session.id}">
                <div class="session-info">
                    <div class="session-name">${this._escapeHtml(session.name)}</div>
                    <div class="session-meta">
                        ${session.windows} window${session.windows !== 1 ? 's' : ''} &bull;
                        ${this._formatDate(session.created_at)}
                    </div>
                </div>
                <div class="session-status">
                    <span class="status-dot ${session.attached ? 'attached' : ''}"></span>
                </div>
                <div class="session-actions">
                    <button class="delete-btn" data-delete="${session.id}" title="Delete">&times;</button>
                </div>
            </div>
        `).join('');

        // Bind click events
        this.sessionsList.querySelectorAll('.session-card').forEach(card => {
            card.addEventListener('click', async (e) => {
                // Don't trigger if delete button was clicked
                if (e.target.closest('.delete-btn')) return;

                const sessionId = card.dataset.sessionId;
                await this._attachSession(sessionId);
            });
        });

        this.sessionsList.querySelectorAll('.delete-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const sessionId = btn.dataset.delete;
                if (confirm('Delete this session?')) {
                    await this._deleteSession(sessionId);
                }
            });
        });
    }

    /**
     * Create a new session
     */
    async _createSession() {
        try {
            const response = await fetch('/sessions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.auth.getAccessToken()}`,
                },
                body: JSON.stringify({}),
            });

            if (!response.ok) {
                if (response.status === 401) {
                    this._handleLogout();
                    return;
                }
                const error = await response.json();
                throw new Error(error.detail || 'Failed to create session');
            }

            const session = await response.json();
            await this._loadSessions();

            // Optionally attach to the new session
            await this._attachSession(session.id);
        } catch (error) {
            console.error('Create session error:', error);
            alert('Failed to create session: ' + error.message);
        }
    }

    /**
     * Delete a session
     * @param {string} sessionId
     */
    async _deleteSession(sessionId) {
        try {
            const response = await fetch(`/sessions/${sessionId}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${this.auth.getAccessToken()}`,
                },
            });

            if (response.status === 401) {
                this._handleLogout();
                return;
            }

            if (!response.ok && response.status !== 204) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to delete session');
            }

            await this._loadSessions();
        } catch (error) {
            console.error('Delete session error:', error);
            alert('Failed to delete session: ' + error.message);
        }
    }

    /**
     * Attach to a session
     * @param {string} sessionId
     */
    async _attachSession(sessionId) {
        this.currentSessionId = sessionId;

        // Get session name for header
        const sessions = Array.from(this.sessionsList.querySelectorAll('.session-card'));
        const sessionCard = sessions.find(s => s.dataset.sessionId === sessionId);
        const name = sessionCard?.querySelector('.session-name')?.textContent || sessionId;
        this.sessionName.textContent = name;

        // Show terminal view
        this._showTerminalView();

        // Create terminal manager
        this.terminalManager = new TerminalManager(this.terminalContainer);
        this.terminalManager.onDisconnect = (reason) => {
            console.log('Terminal disconnected:', reason);
            this._disconnectTerminal();
        };

        try {
            await this.terminalManager.connect(sessionId, this.auth.getAccessToken());
            this.terminalManager.focus();
        } catch (error) {
            console.error('Attach error:', error);
            alert('Failed to connect: ' + error.message);
            this._disconnectTerminal();
        }
    }

    /**
     * Disconnect from terminal and go back to sessions
     */
    _disconnectTerminal() {
        if (this.terminalManager) {
            this.terminalManager.disconnect();
            this.terminalManager = null;
        }
        this.currentSessionId = null;
        this._showSessionsView();
        this._loadSessions();
    }

    /**
     * Show login view
     */
    _showLoginView() {
        this.loginView.classList.remove('hidden');
        this.sessionsView.classList.add('hidden');
        this.terminalView.classList.add('hidden');
    }

    /**
     * Show sessions view
     */
    _showSessionsView() {
        this.loginView.classList.add('hidden');
        this.sessionsView.classList.remove('hidden');
        this.terminalView.classList.add('hidden');
    }

    /**
     * Show terminal view
     */
    _showTerminalView() {
        this.loginView.classList.add('hidden');
        this.sessionsView.classList.add('hidden');
        this.terminalView.classList.remove('hidden');
    }

    /**
     * Escape HTML for safe rendering
     * @param {string} str
     * @returns {string}
     */
    _escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    /**
     * Format date for display
     * @param {string} dateStr
     * @returns {string}
     */
    _formatDate(dateStr) {
        const date = new Date(dateStr);
        const now = new Date();
        const diff = now - date;

        if (diff < 60000) return 'Just now';
        if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
        return date.toLocaleDateString();
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const app = new App();
    app.init();
});
