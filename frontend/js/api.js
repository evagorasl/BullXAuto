/**
 * BullX Automation API Client
 * Handles all API requests to the backend
 */

class BullXAPI {
    constructor() {
        this.baseUrl = window.location.origin;
        this.apiKey = null;
    }

    /**
     * Set the API key for authentication
     * @param {string} apiKey - The API key
     */
    setApiKey(apiKey) {
        this.apiKey = apiKey;
    }

    /**
     * Clear the API key (logout)
     */
    clearApiKey() {
        this.apiKey = null;
    }

    /**
     * Get the authorization headers for API requests
     * @returns {Object} - Headers object
     */
    getHeaders() {
        const headers = {
            'Content-Type': 'application/json'
        };

        if (this.apiKey) {
            headers['Authorization'] = `Bearer ${this.apiKey}`;
        }

        return headers;
    }

    /**
     * Make a request to the API
     * @param {string} method - HTTP method (GET, POST, etc.)
     * @param {string} endpoint - API endpoint
     * @param {Object} data - Request data (for POST, PUT, etc.)
     * @returns {Promise} - Promise that resolves to the response data
     */
    async request(method, endpoint, data = null) {
        const url = `${this.baseUrl}${endpoint}`;
        const options = {
            method: method,
            headers: this.getHeaders()
        };

        if (data && (method === 'POST' || method === 'PUT')) {
            options.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(url, options);
            const responseData = await response.json();

            if (!response.ok) {
                throw new Error(responseData.detail || 'API request failed');
            }

            return responseData;
        } catch (error) {
            console.error('API request error:', error);
            throw error;
        }
    }

    /**
     * Check if the API is healthy
     * @returns {Promise} - Promise that resolves to the health status
     */
    async checkHealth() {
        return this.request('GET', '/health');
    }

    /**
     * Get the current profile information
     * @returns {Promise} - Promise that resolves to the profile data
     */
    async getProfile() {
        return this.request('GET', '/api/v1/profile');
    }

    /**
     * Login with the current API key
     * @returns {Promise} - Promise that resolves to the login result
     */
    async login() {
        return this.request('POST', '/api/v1/login');
    }

    /**
     * Search for a token address
     * @param {string} address - Token address to search for
     * @returns {Promise} - Promise that resolves to the search result
     */
    async searchAddress(address) {
        return this.request('POST', '/api/v1/search', { address });
    }

    /**
     * Execute a trading strategy
     * @param {Object} strategyData - Strategy data
     * @returns {Promise} - Promise that resolves to the strategy execution result
     */
    async executeStrategy(strategyData) {
        return this.request('POST', '/api/v1/strategy', strategyData);
    }

    /**
     * Get all active orders for the current profile
     * @returns {Promise} - Promise that resolves to the orders data
     */
    async getOrders() {
        return this.request('GET', '/api/v1/orders');
    }

    /**
     * Get all coins in the database
     * @returns {Promise} - Promise that resolves to the coins data
     */
    async getCoins() {
        return this.request('GET', '/api/v1/coins');
    }

    /**
     * Get a specific coin by address
     * @param {string} address - Coin address
     * @returns {Promise} - Promise that resolves to the coin data
     */
    async getCoin(address) {
        return this.request('GET', `/api/v1/coins/${address}`);
    }

    /**
     * Get all orders for a specific coin
     * @param {string} address - Coin address
     * @param {string} status - Filter by order status (optional)
     * @returns {Promise} - Promise that resolves to the coin orders data
     */
    async getCoinOrders(address, status = null) {
        let endpoint = `/api/v1/coins/${address}/orders`;
        if (status) {
            endpoint += `?status=${status}`;
        }
        return this.request('GET', endpoint);
    }

    /**
     * Close the Chrome driver for the current profile
     * @returns {Promise} - Promise that resolves to the close result
     */
    async closeDriver() {
        return this.request('POST', '/api/v1/close-driver');
    }

    /**
     * Get bracket information
     * @returns {Promise} - Promise that resolves to the bracket info
     */
    async getBrackets() {
        return this.request('GET', '/api/v1/brackets');
    }

    /**
     * Get bracket configuration
     * @returns {Promise} - Promise that resolves to the bracket config
     */
    async getBracketConfig() {
        return this.request('GET', '/api/v1/bracket-config');
    }

    /**
     * Create multiple orders automatically using bracket configuration
     * @param {string} address - Token address
     * @param {number} strategyNumber - Strategy number
     * @param {string} orderType - Order type (BUY/SELL)
     * @param {number} totalAmount - Total investment amount
     * @returns {Promise} - Promise that resolves to the auto multi-order result
     */
    async createAutoMultiOrder(address, strategyNumber, orderType, totalAmount) {
        const params = new URLSearchParams({
            address,
            strategy_number: strategyNumber,
            order_type: orderType,
            total_amount: totalAmount
        });
        return this.request('POST', `/api/v1/auto-multi-order?${params}`);
    }

    /**
     * Preview bracket orders for a coin
     * @param {string} address - Token address
     * @param {number} totalAmount - Total investment amount
     * @returns {Promise} - Promise that resolves to the bracket order preview
     */
    async getBracketOrderPreview(address, totalAmount) {
        const params = new URLSearchParams({
            total_amount: totalAmount
        });
        return this.request('GET', `/api/v1/coins/${address}/bracket-orders?${params}`);
    }

    /**
     * Get orders summary grouped by coin and bracket
     * @returns {Promise} - Promise that resolves to the orders summary
     */
    async getOrdersSummary() {
        return this.request('GET', '/api/v1/orders-summary');
    }

    /**
     * Get next available bracket ID for a coin
     * @param {string} address - Token address
     * @returns {Promise} - Promise that resolves to the next bracket ID
     */
    async getNextBracketId(address) {
        return this.request('GET', `/api/v1/coins/${address}/next-bracket-id`);
    }

    /**
     * Execute bracket strategy for a coin (places all 4 bracket orders)
     * @param {string} address - Token address
     * @param {number} totalAmount - Total investment amount
     * @param {number} strategyNumber - Strategy number (optional, default: 1)
     * @returns {Promise} - Promise that resolves to the bracket strategy result
     */
    async executeBracketStrategy(address, totalAmount, bracket = null) {
        const params = new URLSearchParams({
            address,
            total_amount: totalAmount
        });
        if (bracket !== null) {
            params.set('bracket', bracket);
        }
        return this.request('POST', `/api/v1/bracket-strategy?${params}`);
    }

    /**
     * Replace a specific bracket order
     * @param {string} address - Token address
     * @param {number} bracketId - Bracket ID to replace (1-4)
     * @param {number} newAmount - New order amount
     * @param {number} strategyNumber - Strategy number (optional, default: 1)
     * @returns {Promise} - Promise that resolves to the replacement result
     */
    async replaceBracketOrder(address, bracketId, newAmount) {
        const params = new URLSearchParams({
            new_amount: newAmount
        });
        return this.request('POST', `/api/v1/bracket-order-replace/${address}/${bracketId}?${params}`);
    }

    /**
     * Preview bracket orders without placing them
     * @param {string} address - Token address
     * @param {number} totalAmount - Total investment amount
     * @returns {Promise} - Promise that resolves to the bracket preview
     */
    async getBracketPreview(address, totalAmount) {
        const params = new URLSearchParams({
            total_amount: totalAmount
        });
        return this.request('GET', `/api/v1/bracket-preview/${address}?${params}`);
    }

    /**
     * Get current market cap for a token
     * @param {string} address - Token address
     * @returns {Promise} - Promise that resolves to the market cap data
     */
    async getMarketCap(address) {
        return this.request('GET', `/api/v1/market-cap/${address}`);
    }

    /**
     * Clear coin data and/or orders from database
     * @param {string} address - Token address
     * @param {boolean} ordersOnly - If true, only clear orders. If false, clear coin and all its orders
     * @returns {Promise} - Promise that resolves to the clear result
     */
    async clearCoinData(address, ordersOnly = false) {
        const params = new URLSearchParams({
            clear_orders_only: ordersOnly
        });
        return this.request('DELETE', `/api/v1/coins/${address}?${params}`);
    }

    /**
     * Clear all coins and orders for the current profile
     * @returns {Promise} - Promise that resolves to the clear result
     */
    async clearAllData() {
        return this.request('DELETE', '/api/v1/clear-all-data');
    }

    // ---- Queue API Methods ----

    /**
     * Add a bracket strategy execution to the queue
     * @param {string} address - Token address
     * @param {number} totalAmount - Total investment amount
     * @param {number|null} bracket - Optional bracket override (1-5)
     * @param {number} priority - Queue priority (default: 0)
     * @returns {Promise}
     */
    async queueBracketStrategy(address, totalAmount, bracket = null, priority = 0) {
        const data = {
            address,
            total_amount: totalAmount,
            priority
        };
        if (bracket !== null) {
            data.bracket = bracket;
        }
        return this.request('POST', '/api/v1/queue/bracket-strategy', data);
    }

    /**
     * Get queue items
     * @param {string|null} status - Optional status filter
     * @returns {Promise}
     */
    async getQueue(status = null) {
        let endpoint = '/api/v1/queue';
        if (status) {
            endpoint += `?status=${status}`;
        }
        return this.request('GET', endpoint);
    }

    /**
     * Cancel a queued item
     * @param {number} itemId - Queue item ID
     * @returns {Promise}
     */
    async cancelQueueItem(itemId) {
        return this.request('DELETE', `/api/v1/queue/${itemId}`);
    }

    /**
     * Retry a failed queue item
     * @param {number} itemId - Queue item ID
     * @returns {Promise}
     */
    async retryQueueItem(itemId) {
        return this.request('POST', `/api/v1/queue/${itemId}/retry`);
    }

    /**
     * Clear completed/failed items from queue
     * @returns {Promise}
     */
    async clearCompletedQueue() {
        return this.request('DELETE', '/api/v1/queue');
    }

    // ---- Monitoring API Methods ----

    /**
     * Get unified monitoring status
     * @returns {Promise} - Promise that resolves to the monitoring status
     */
    async getMonitoringStatus() {
        return this.request('GET', '/api/v1/monitoring/status');
    }

    /**
     * Get recent log entries
     * @param {number} lines - Number of lines (default 50)
     * @param {string} level - Filter level: all, error, warning (default all)
     * @returns {Promise} - Promise that resolves to log entries
     */
    async getMonitoringLogs(lines = 50, level = 'all') {
        const params = new URLSearchParams({ lines, level });
        return this.request('GET', `/api/v1/monitoring/logs?${params}`);
    }

    /**
     * Clear today's log file
     * @returns {Promise} - Promise that resolves to the clear result
     */
    async clearMonitoringLogs() {
        return this.request('DELETE', '/api/v1/monitoring/logs');
    }

    // ---- Daily Report API Methods ----

    /**
     * Get list of available daily health reports
     * @param {number} limit - Maximum reports to return (default 30)
     * @returns {Promise}
     */
    async getHealthReports(limit = 30) {
        return this.request('GET', `/api/v1/monitoring/reports?limit=${limit}`);
    }

    /**
     * Get a specific daily health report by date
     * @param {string} dateStr - Date in YYYY-MM-DD format
     * @returns {Promise}
     */
    async getHealthReport(dateStr) {
        return this.request('GET', `/api/v1/monitoring/reports/${dateStr}`);
    }

    /**
     * Manually trigger health report generation
     * @param {string|null} dateStr - Optional date (YYYY-MM-DD), defaults to yesterday
     * @returns {Promise}
     */
    async generateHealthReport(dateStr = null) {
        let endpoint = '/api/v1/monitoring/reports/generate';
        if (dateStr) {
            endpoint += `?date_str=${dateStr}`;
        }
        return this.request('POST', endpoint);
    }
}

// Create a global API client instance
const api = new BullXAPI();
