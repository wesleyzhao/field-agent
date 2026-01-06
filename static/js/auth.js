/**
 * Auth module for field-agent
 * Handles passphrase authentication and JWT token management
 */

class AuthManager {
    constructor() {
        this.accessToken = null;
        this.refreshToken = null;
        this.expiresAt = null;

        // Try to restore from sessionStorage
        this._restore();
    }

    /**
     * Check if user is authenticated
     * @returns {boolean}
     */
    isAuthenticated() {
        if (!this.accessToken) {
            return false;
        }

        // Check if token is expired (with 30s buffer)
        if (this.expiresAt && Date.now() > this.expiresAt - 30000) {
            return false;
        }

        return true;
    }

    /**
     * Get the current access token
     * @returns {string|null}
     */
    getAccessToken() {
        return this.accessToken;
    }

    /**
     * Login with passphrase
     * @param {string} passphrase
     * @returns {Promise<boolean>}
     */
    async login(passphrase) {
        try {
            const response = await fetch('/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ passphrase }),
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Login failed');
            }

            const data = await response.json();
            this._setTokens(data);
            return true;
        } catch (error) {
            console.error('Login error:', error);
            throw error;
        }
    }

    /**
     * Refresh the access token using refresh token
     * @returns {Promise<boolean>}
     */
    async refreshAccessToken() {
        if (!this.refreshToken) {
            return false;
        }

        try {
            const response = await fetch('/auth/refresh', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ refresh_token: this.refreshToken }),
            });

            if (!response.ok) {
                this.logout();
                return false;
            }

            const data = await response.json();
            this._setTokens(data);
            return true;
        } catch (error) {
            console.error('Token refresh error:', error);
            this.logout();
            return false;
        }
    }

    /**
     * Logout and clear tokens
     */
    logout() {
        this.accessToken = null;
        this.refreshToken = null;
        this.expiresAt = null;
        sessionStorage.removeItem('field_agent_auth');
    }

    /**
     * Set tokens from login/refresh response
     * @param {Object} data
     */
    _setTokens(data) {
        this.accessToken = data.access_token;
        this.refreshToken = data.refresh_token;
        this.expiresAt = Date.now() + (data.expires_in * 1000);

        // Store in sessionStorage (cleared when tab closes)
        sessionStorage.setItem('field_agent_auth', JSON.stringify({
            accessToken: this.accessToken,
            refreshToken: this.refreshToken,
            expiresAt: this.expiresAt,
        }));
    }

    /**
     * Restore tokens from sessionStorage
     */
    _restore() {
        try {
            const stored = sessionStorage.getItem('field_agent_auth');
            if (stored) {
                const data = JSON.parse(stored);
                this.accessToken = data.accessToken;
                this.refreshToken = data.refreshToken;
                this.expiresAt = data.expiresAt;
            }
        } catch (error) {
            console.error('Failed to restore auth:', error);
        }
    }

    /**
     * Make an authenticated API request
     * @param {string} url
     * @param {Object} options
     * @returns {Promise<Response>}
     */
    async fetch(url, options = {}) {
        // Refresh token if needed
        if (this.expiresAt && Date.now() > this.expiresAt - 60000) {
            await this.refreshAccessToken();
        }

        if (!this.accessToken) {
            throw new Error('Not authenticated');
        }

        const headers = {
            ...options.headers,
            'Authorization': `Bearer ${this.accessToken}`,
        };

        return fetch(url, { ...options, headers });
    }
}

// Global instance
window.authManager = new AuthManager();
