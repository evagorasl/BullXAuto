/**
 * BullX Automation Dashboard
 * Main application script
 */

document.addEventListener('DOMContentLoaded', () => {
    // Check if API is running
    checkApiHealth();

    // Setup event listeners
    setupEventListeners();

    // Check for stored API key
    const storedApiKey = localStorage.getItem('bullx_api_key');
    if (storedApiKey) {
        document.getElementById('api-key').value = storedApiKey;
        handleLogin();
    }
});

/**
 * Check if the API is running
 */
async function checkApiHealth() {
    try {
        const health = await api.checkHealth();
        console.log('API health check:', health);
    } catch (error) {
        showMessage('login-message', 'API server is not running. Please start the server first.', 'error');
    }
}

/**
 * Setup all event listeners
 */
function setupEventListeners() {
    // Login button
    document.getElementById('login-btn').addEventListener('click', handleLogin);
    
    // API key input (enter key)
    document.getElementById('api-key').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            handleLogin();
        }
    });
    
    // Logout button
    document.getElementById('logout-btn').addEventListener('click', handleLogout);
    
    // Search button
    document.getElementById('search-btn').addEventListener('click', handleSearch);
    
    // Strategy button
    document.getElementById('strategy-btn').addEventListener('click', handleStrategy);
    
    // Refresh orders button
    document.getElementById('refresh-orders-btn').addEventListener('click', loadOrders);
    
    // Refresh coins button
    document.getElementById('refresh-coins-btn').addEventListener('click', loadCoins);
    
    // Advanced options toggle
    document.getElementById('advanced-toggle').addEventListener('change', (e) => {
        const advancedOptions = document.getElementById('advanced-options');
        if (e.target.checked) {
            advancedOptions.classList.remove('hidden');
        } else {
            advancedOptions.classList.add('hidden');
        }
    });
    
    // Modal close button
    document.querySelector('.close').addEventListener('click', () => {
        document.getElementById('orders-modal').style.display = 'none';
    });
    
    // Close modal when clicking outside
    window.addEventListener('click', (e) => {
        const modal = document.getElementById('orders-modal');
        if (e.target === modal) {
            modal.style.display = 'none';
        }
    });
}

/**
 * Handle login button click
 */
async function handleLogin() {
    const apiKeyInput = document.getElementById('api-key');
    const apiKey = apiKeyInput.value.trim();
    
    if (!apiKey) {
        showMessage('login-message', 'Please enter your API key', 'error');
        return;
    }
    
    if (!apiKey.startsWith('bullx_')) {
        showMessage('login-message', 'Invalid API key format. API keys should start with "bullx_"', 'error');
        return;
    }
    
    try {
        // Set the API key
        api.setApiKey(apiKey);
        
        // Get profile information
        const profile = await api.getProfile();
        
        // Store API key in local storage
        localStorage.setItem('bullx_api_key', apiKey);
        
        // Show profile info
        document.getElementById('profile-name').textContent = `Profile: ${profile.name}`;
        document.getElementById('profile-info').classList.remove('hidden');
        
        // Hide login section and show dashboard
        document.getElementById('login-section').classList.add('hidden');
        document.getElementById('dashboard').classList.remove('hidden');
        
        // Load initial data
        loadOrders();
        loadCoins();
        
        // Show success message
        showMessage('login-message', 'Login successful!', 'success');
        
        // Attempt to login to BullX (if not already logged in)
        if (!profile.is_logged_in) {
            try {
                await api.login();
                console.log('BullX login successful');
            } catch (loginError) {
                console.error('BullX login error:', loginError);
                // We don't show this error to the user as it's not critical
            }
        }
    } catch (error) {
        showMessage('login-message', `Authentication failed: ${error.message}`, 'error');
        api.clearApiKey();
    }
}

/**
 * Handle logout button click
 */
function handleLogout() {
    // Clear API key
    api.clearApiKey();
    localStorage.removeItem('bullx_api_key');
    
    // Hide dashboard and show login section
    document.getElementById('dashboard').classList.add('hidden');
    document.getElementById('login-section').classList.remove('hidden');
    document.getElementById('profile-info').classList.add('hidden');
    
    // Clear API key input
    document.getElementById('api-key').value = '';
    
    // Clear any messages
    document.getElementById('login-message').textContent = '';
    document.getElementById('login-message').className = 'message';
}

/**
 * Handle search button click
 */
async function handleSearch() {
    const addressInput = document.getElementById('token-address');
    const address = addressInput.value.trim();
    
    if (!address) {
        showMessage('search-result', 'Please enter a token address', 'error');
        return;
    }
    
    try {
        // Show loading message
        const searchResultElement = document.getElementById('search-result');
        searchResultElement.classList.remove('hidden');
        searchResultElement.innerHTML = '<h3>Search Result</h3><div>Searching...</div>';
        
        // Search for the address
        const searchResponse = await api.searchAddress(address);
        
        // If search is successful, get the coin data
        let html = '';
        if (searchResponse.success) {
            // Get coin info from the database
            const coinInfo = await api.getCoin(address);
            
            // Display the result
            html = `
                <h3>Search Result</h3>
                <div class="result-content">
                    <p><strong>Address:</strong> ${coinInfo.address}</p>
                    <p><strong>URL:</strong> <a href="${coinInfo.url}" target="_blank">${coinInfo.url}</a></p>
            `;
            
            if (coinInfo.name) {
                html += `<p><strong>Name:</strong> ${coinInfo.name}</p>`;
            }
            
            if (coinInfo.market_cap) {
                html += `<p><strong>Market Cap:</strong> $${formatNumber(coinInfo.market_cap)}</p>`;
            }
            
            if (coinInfo.current_price) {
                html += `<p><strong>Current Price:</strong> $${coinInfo.current_price}</p>`;
            }
            
            if (coinInfo.last_updated) {
                html += `<p><strong>Last Updated:</strong> ${formatDate(coinInfo.last_updated)}</p>`;
            }
        } else {
            // If search failed, show a message
            html = `
                <h3>Search Result</h3>
                <div class="result-content">
                    <p>No information found for address: ${address}</p>
                </div>
            `;
        }
        
        html += '</div>';
        searchResultElement.innerHTML = html;
    } catch (error) {
        showMessage('search-result', `Search failed: ${error.message}`, 'error');
    }
}

/**
 * Handle strategy button click
 */
async function handleStrategy() {
    const address = document.getElementById('strategy-address').value.trim();
    const strategyNumber = parseInt(document.getElementById('strategy-number').value);
    const orderType = document.getElementById('order-type').value;
    
    if (!address) {
        showMessage('strategy-result', 'Please enter a token address', 'error');
        return;
    }
    
    // Get advanced options if enabled
    const advancedToggle = document.getElementById('advanced-toggle');
    let entryPrice = null;
    let takeProfit = null;
    let stopLoss = null;
    
    if (advancedToggle.checked) {
        const entryPriceInput = document.getElementById('entry-price').value.trim();
        const takeProfitInput = document.getElementById('take-profit').value.trim();
        const stopLossInput = document.getElementById('stop-loss').value.trim();
        
        if (entryPriceInput) entryPrice = parseFloat(entryPriceInput);
        if (takeProfitInput) takeProfit = parseFloat(takeProfitInput);
        if (stopLossInput) stopLoss = parseFloat(stopLossInput);
    }
    
    // Prepare strategy data
    const strategyData = {
        strategy_number: strategyNumber,
        address: address,
        order_type: orderType
    };
    
    // Add optional parameters if provided
    if (entryPrice !== null) strategyData.entry_price = entryPrice;
    if (takeProfit !== null) strategyData.take_profit = takeProfit;
    if (stopLoss !== null) strategyData.stop_loss = stopLoss;
    
    try {
        // Show loading message
        const strategyResult = document.getElementById('strategy-result');
        strategyResult.classList.remove('hidden');
        strategyResult.innerHTML = '<h3>Strategy Result</h3><div>Executing strategy...</div>';
        
        // Execute the strategy
        const result = await api.executeStrategy(strategyData);
        
        // Display the result
        let html = `
            <h3>Strategy Result</h3>
            <div class="result-content">
                <p><strong>Strategy:</strong> ${result.strategy_number}</p>
                <p><strong>Address:</strong> ${result.address}</p>
                <p><strong>Order Type:</strong> ${result.order_type}</p>
                <p><strong>Entry Price:</strong> ${result.entry_price}</p>
                <p><strong>Take Profit:</strong> ${result.take_profit}</p>
                <p><strong>Stop Loss:</strong> ${result.stop_loss}</p>
            </div>
        `;
        
        strategyResult.innerHTML = html;
        
        // Refresh orders
        loadOrders();
    } catch (error) {
        showMessage('strategy-result', `Strategy execution failed: ${error.message}`, 'error');
    }
}

/**
 * Load active orders
 */
async function loadOrders() {
    try {
        const orders = await api.getOrders();
        const ordersBody = document.getElementById('orders-body');
        const noOrdersMessage = document.getElementById('no-orders-message');
        
        if (orders.length === 0) {
            ordersBody.innerHTML = '';
            noOrdersMessage.style.display = 'block';
            return;
        }
        
        noOrdersMessage.style.display = 'none';
        
        // Clear existing rows
        ordersBody.innerHTML = '';
        
        // Add new rows
        orders.forEach(order => {
            const row = document.createElement('tr');
            
            row.innerHTML = `
                <td>${order.id}</td>
                <td>${truncateAddress(order.coin_id)}</td>
                <td>${order.strategy_number}</td>
                <td>${order.order_type}</td>
                <td>${order.entry_price}</td>
                <td>${order.take_profit}</td>
                <td>${order.stop_loss}</td>
                <td><span class="status-badge ${order.status.toLowerCase()}">${order.status}</span></td>
                <td>${formatDate(order.created_at)}</td>
            `;
            
            ordersBody.appendChild(row);
        });
    } catch (error) {
        console.error('Error loading orders:', error);
        showMessage('no-orders-message', `Error loading orders: ${error.message}`, 'error');
    }
}

/**
 * Load coins from the database
 */
async function loadCoins() {
    try {
        const coins = await api.getCoins();
        const coinsBody = document.getElementById('coins-body');
        const noCoinsMessage = document.getElementById('no-coins-message');
        
        if (coins.length === 0) {
            coinsBody.innerHTML = '';
            noCoinsMessage.style.display = 'block';
            return;
        }
        
        noCoinsMessage.style.display = 'none';
        
        // Clear existing rows
        coinsBody.innerHTML = '';
        
        // Add new rows
        coins.forEach(coin => {
            const row = document.createElement('tr');
            
            row.innerHTML = `
                <td>${coin.id}</td>
                <td>${coin.name || 'Unknown'}</td>
                <td>${truncateAddress(coin.address)}</td>
                <td>${coin.market_cap ? '$' + formatNumber(coin.market_cap) : 'N/A'}</td>
                <td>${coin.current_price ? '$' + coin.current_price : 'N/A'}</td>
                <td>${formatDate(coin.last_updated)}</td>
                <td>
                    <button class="btn btn-secondary btn-sm view-orders" data-address="${coin.address}" data-name="${coin.name || coin.address}">
                        View Orders
                    </button>
                </td>
            `;
            
            coinsBody.appendChild(row);
        });
        
        // Add event listeners to view orders buttons
        document.querySelectorAll('.view-orders').forEach(button => {
            button.addEventListener('click', async (e) => {
                const address = e.target.getAttribute('data-address');
                const name = e.target.getAttribute('data-name');
                await showCoinOrders(address, name);
            });
        });
    } catch (error) {
        console.error('Error loading coins:', error);
        showMessage('no-coins-message', `Error loading coins: ${error.message}`, 'error');
    }
}

/**
 * Show orders for a specific coin in a modal
 * @param {string} address - Coin address
 * @param {string} name - Coin name
 */
async function showCoinOrders(address, name) {
    try {
        const orders = await api.getCoinOrders(address);
        const modalOrdersBody = document.getElementById('modal-orders-body');
        const modalNoOrders = document.getElementById('modal-no-orders');
        const modalCoinName = document.getElementById('modal-coin-name');
        
        // Set coin name in modal title
        modalCoinName.textContent = name;
        
        if (orders.length === 0) {
            modalOrdersBody.innerHTML = '';
            modalNoOrders.style.display = 'block';
        } else {
            modalNoOrders.style.display = 'none';
            
            // Clear existing rows
            modalOrdersBody.innerHTML = '';
            
            // Add new rows
            orders.forEach(order => {
                const row = document.createElement('tr');
                
                row.innerHTML = `
                    <td>${order.id}</td>
                    <td>${order.strategy_number}</td>
                    <td>${order.order_type}</td>
                    <td>${order.entry_price}</td>
                    <td>${order.take_profit}</td>
                    <td>${order.stop_loss}</td>
                    <td><span class="status-badge ${order.status.toLowerCase()}">${order.status}</span></td>
                    <td>${formatDate(order.created_at)}</td>
                `;
                
                modalOrdersBody.appendChild(row);
            });
        }
        
        // Show the modal
        document.getElementById('orders-modal').style.display = 'block';
    } catch (error) {
        console.error('Error loading coin orders:', error);
        alert(`Error loading orders for ${name}: ${error.message}`);
    }
}

/**
 * Show a message in a message container
 * @param {string} elementId - ID of the message container
 * @param {string} message - Message to display
 * @param {string} type - Message type (success, error, info, warning)
 */
function showMessage(elementId, message, type = 'info') {
    const messageElement = document.getElementById(elementId);
    messageElement.textContent = message;
    messageElement.className = `message ${type}`;
    messageElement.classList.remove('hidden');
}

/**
 * Format a date string
 * @param {string} dateString - ISO date string
 * @returns {string} - Formatted date string
 */
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString();
}

/**
 * Format a number with commas
 * @param {number} number - Number to format
 * @returns {string} - Formatted number string
 */
function formatNumber(number) {
    return number.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

/**
 * Truncate an address for display
 * @param {string} address - Address to truncate
 * @returns {string} - Truncated address
 */
function truncateAddress(address) {
    if (!address) return 'N/A';
    if (address.length <= 16) return address;
    return `${address.substring(0, 8)}...${address.substring(address.length - 8)}`;
}
