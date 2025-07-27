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
    
    // Bracket strategy event listeners
    document.getElementById('get-market-cap-btn').addEventListener('click', handleGetMarketCap);
    document.getElementById('preview-bracket-btn').addEventListener('click', handlePreviewBracket);
    document.getElementById('execute-bracket-btn').addEventListener('click', handleExecuteBracket);
    
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
            // Get coin info from the search response or fetch it separately
            let coinInfo = searchResponse.coin_data;
            if (!coinInfo) {
                coinInfo = await api.getCoin(address);
            }
            
            console.log('Search response:', searchResponse);
            console.log('Coin info:', coinInfo);
            
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
            
            if (coinInfo.bracket) {
                const bracketInfo = getBracketDescription(coinInfo.bracket);
                html += `<p><strong>Bracket:</strong> ${coinInfo.bracket} (${bracketInfo})</p>`;
            } else if (coinInfo.market_cap) {
                // Calculate bracket if not assigned
                const bracket = calculateBracketFromMarketCap(coinInfo.market_cap);
                const bracketInfo = getBracketDescription(bracket);
                html += `<p><strong>Bracket:</strong> ${bracket} (${bracketInfo}) <em>- calculated</em></p>`;
            }
            
            if (coinInfo.current_price) {
                html += `<p><strong>Current Price:</strong> $${coinInfo.current_price}</p>`;
            }
            
            if (coinInfo.last_updated) {
                html += `<p><strong>Last Updated:</strong> ${formatDate(coinInfo.last_updated)}</p>`;
            }
            
            // Add bracket order preview if market cap is available
            if (coinInfo.market_cap && coinInfo.bracket) {
                html += `
                    <div class="bracket-preview">
                        <h4>Bracket Order Preview (for $1000 investment):</h4>
                        <div id="bracket-preview-${coinInfo.id}" class="loading">Loading bracket preview...</div>
                    </div>
                `;
                
                // Load bracket preview asynchronously
                loadBracketPreview(coinInfo.address, coinInfo.id, 1000);
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
        console.log('Coins data:', coins);
        
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
            console.log('Processing coin:', coin);
            const row = document.createElement('tr');
            
            const bracketDisplay = coin.bracket ? 
                `<span class="bracket-badge bracket-${coin.bracket}">${coin.bracket}</span>` : 
                'N/A';
            
            row.innerHTML = `
                <td>${coin.id}</td>
                <td>${coin.name || 'Unknown'}</td>
                <td>${truncateAddress(coin.address)}</td>
                <td>${coin.market_cap ? '$' + formatNumber(coin.market_cap) : 'N/A'}</td>
                <td>${bracketDisplay}</td>
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

/**
 * Get bracket description based on bracket number
 * @param {number} bracket - Bracket number (1-5)
 * @returns {string} - Bracket description
 */
function getBracketDescription(bracket) {
    const descriptions = {
        1: 'Micro Cap (20K - 120K)',
        2: 'Small Cap (200K - 1.2M)',
        3: 'Medium Cap (2M - 12M)',
        4: 'Large Cap (12M - 120M)',
        5: 'Mega Cap (120M - 1.2B)'
    };
    return descriptions[bracket] || 'Unknown';
}

/**
 * Calculate bracket from market cap (client-side calculation)
 * @param {number} marketCap - Market cap value
 * @returns {number} - Bracket number (1-5)
 */
function calculateBracketFromMarketCap(marketCap) {
    if (marketCap >= 20000 && marketCap <= 120000) {
        return 1;
    } else if (marketCap >= 200000 && marketCap <= 1200000) {
        return 2;
    } else if (marketCap >= 2000000 && marketCap <= 12000000) {
        return 3;
    } else if (marketCap > 12000000 && marketCap <= 120000000) {
        return 4;
    } else if (marketCap > 120000000 && marketCap <= 1200000000) {
        return 5;
    } else {
        // Default to bracket 1 for market caps outside defined ranges
        return 1;
    }
}

/**
 * Load bracket order preview for a coin
 * @param {string} address - Coin address
 * @param {number} coinId - Coin ID for element targeting
 * @param {number} totalAmount - Total investment amount
 */
async function loadBracketPreview(address, coinId, totalAmount) {
    try {
        const preview = await api.getBracketOrderPreview(address, totalAmount);
        const previewElement = document.getElementById(`bracket-preview-${coinId}`);
        
        if (preview.success) {
            let html = `
                <div class="bracket-preview-content">
                    <p><strong>Bracket ${preview.bracket}:</strong> ${preview.bracket_info.description}</p>
                    <div class="preview-orders">
            `;
            
            preview.preview_orders.forEach((order, index) => {
                html += `
                    <div class="preview-order">
                        <strong>Order ${order.bracket_id}:</strong>
                        Amount: $${order.amount.toFixed(2)} (${(order.trade_size_pct * 100).toFixed(1)}%) |
                        Entry: ${order.entry_price.toLocaleString()} |
                        TP: ${order.take_profit.toLocaleString()} (${(order.take_profit_pct * 100).toFixed(0)}%) |
                        SL: ${order.stop_loss.toLocaleString()}
                    </div>
                `;
            });
            
            html += `
                    </div>
                    <button class="btn btn-primary btn-sm" onclick="createAutoOrder('${address}', ${totalAmount})">
                        Create These Orders
                    </button>
                </div>
            `;
            
            previewElement.innerHTML = html;
        } else {
            previewElement.innerHTML = '<p>Unable to load bracket preview</p>';
        }
    } catch (error) {
        console.error('Error loading bracket preview:', error);
        const previewElement = document.getElementById(`bracket-preview-${coinId}`);
        previewElement.innerHTML = '<p>Error loading bracket preview</p>';
    }
}

/**
 * Create auto multi-order for a coin
 * @param {string} address - Coin address
 * @param {number} totalAmount - Total investment amount
 */
async function createAutoOrder(address, totalAmount) {
    try {
        const result = await api.createAutoMultiOrder(address, 1, 'BUY', totalAmount);
        
        if (result.success) {
            alert(`Successfully created ${result.total_orders_created} orders for $${totalAmount}`);
            // Refresh orders and coins
            loadOrders();
            loadCoins();
        } else {
            alert('Failed to create auto orders');
        }
    } catch (error) {
        console.error('Error creating auto order:', error);
        alert(`Error creating auto orders: ${error.message}`);
    }
}

/**
 * Handle get market cap button click
 */
async function handleGetMarketCap() {
    const address = document.getElementById('bracket-address').value.trim();
    
    if (!address) {
        showBracketMessage('Please enter a token address', 'error');
        return;
    }
    
    try {
        // Show loading state
        const button = document.getElementById('get-market-cap-btn');
        const originalText = button.textContent;
        button.innerHTML = '<span class="loading-spinner"></span>Loading...';
        button.disabled = true;
        
        // Get market cap data
        const result = await api.getMarketCap(address);
        
        if (result.success) {
            // Show market cap info
            document.getElementById('current-market-cap').textContent = `$${formatNumber(result.market_cap)}`;
            document.getElementById('current-bracket').innerHTML = `<span class="bracket-badge bracket-${result.bracket}">${result.bracket}</span>`;
            document.getElementById('bracket-description').textContent = result.bracket_info.description;
            
            // Show the info box
            document.getElementById('market-cap-info').classList.remove('hidden');
            
            // Auto-fill the address in the bracket address field if it was searched
            document.getElementById('bracket-address').value = result.address;
            
            showBracketMessage('Market cap retrieved successfully', 'success');
        } else {
            showBracketMessage('Failed to get market cap', 'error');
        }
    } catch (error) {
        console.error('Error getting market cap:', error);
        showBracketMessage(`Error: ${error.message}`, 'error');
    } finally {
        // Reset button state
        const button = document.getElementById('get-market-cap-btn');
        button.textContent = 'Get Market Cap';
        button.disabled = false;
    }
}

/**
 * Handle preview bracket button click
 */
async function handlePreviewBracket() {
    const address = document.getElementById('bracket-address').value.trim();
    const amount = parseFloat(document.getElementById('bracket-amount').value);
    
    if (!address) {
        showBracketMessage('Please enter a token address', 'error');
        return;
    }
    
    if (!amount || amount <= 0) {
        showBracketMessage('Please enter a valid investment amount', 'error');
        return;
    }
    
    try {
        // Show loading state
        const button = document.getElementById('preview-bracket-btn');
        const originalText = button.innerHTML;
        button.innerHTML = '<span class="loading-spinner"></span>Loading Preview...';
        button.disabled = true;
        
        // Get bracket preview
        const result = await api.getBracketPreview(address, amount);
        
        if (result.success) {
            // Show preview details
            const previewDetails = document.getElementById('bracket-preview-details');
            previewDetails.innerHTML = `
                <div class="bracket-summary">
                    <div class="bracket-stat">
                        <span class="stat-value">${result.bracket}</span>
                        <span class="stat-label">Bracket</span>
                    </div>
                    <div class="bracket-stat">
                        <span class="stat-value">$${formatNumber(result.current_market_cap)}</span>
                        <span class="stat-label">Current Market Cap</span>
                    </div>
                    <div class="bracket-stat">
                        <span class="stat-value">${formatNumber(result.total_amount)} SOL</span>
                        <span class="stat-label">Total Investment</span>
                    </div>
                    <div class="bracket-stat">
                        <span class="stat-value">${result.orders.length}</span>
                        <span class="stat-label">Orders</span>
                    </div>
                </div>
                <p><strong>Bracket Description:</strong> ${result.bracket_info.description}</p>
            `;
            
            // Populate preview table
            const previewBody = document.getElementById('bracket-preview-body');
            previewBody.innerHTML = '';
            
            result.orders.forEach(order => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>Bracket ${order.bracket_id}</td>
                    <td><span class="order-type-badge order-type-${order.order_type.toLowerCase()}">${order.order_type}</span></td>
                    <td><span class="strategy-name">${order.strategy_name}</span></td>
                    <td class="market-cap">$${formatNumber(order.entry_price)}</td>
                    <td class="market-cap">$${formatNumber(order.take_profit)}</td>
                    <td class="market-cap">$${formatNumber(order.stop_loss)}</td>
                    <td class="amount-cell">${order.amount.toFixed(6)} SOL</td>
                    <td class="percentage-cell">${(order.trade_size_pct * 100).toFixed(1)}%</td>
                `;
                previewBody.appendChild(row);
            });
            
            // Show the preview section
            document.getElementById('bracket-preview').classList.remove('hidden');
            
            showBracketMessage('Preview generated successfully', 'success');
        } else {
            showBracketMessage('Failed to generate preview', 'error');
        }
    } catch (error) {
        console.error('Error generating preview:', error);
        showBracketMessage(`Error: ${error.message}`, 'error');
    } finally {
        // Reset button state
        const button = document.getElementById('preview-bracket-btn');
        button.innerHTML = originalText;
        button.disabled = false;
    }
}

/**
 * Handle execute bracket button click
 */
async function handleExecuteBracket() {
    const address = document.getElementById('bracket-address').value.trim();
    const amount = parseFloat(document.getElementById('bracket-amount').value);
    const strategyNumber = parseInt(document.getElementById('bracket-strategy-number').value);
    
    if (!address) {
        showBracketMessage('Please enter a token address', 'error');
        return;
    }
    
    if (!amount || amount <= 0) {
        showBracketMessage('Please enter a valid investment amount', 'error');
        return;
    }
    
    // Confirm execution
    const confirmed = confirm(`Are you sure you want to execute the bracket strategy for ${address} with $${amount}?`);
    if (!confirmed) {
        return;
    }
    
    try {
        // Show loading state
        const button = document.getElementById('execute-bracket-btn');
        const originalText = button.innerHTML;
        button.innerHTML = '<span class="loading-spinner"></span>Executing...';
        button.disabled = true;
        
        // Execute bracket strategy
        const result = await api.executeBracketStrategy(address, amount, strategyNumber);
        
        if (result.success) {
            // Show success result
            const resultDetails = document.getElementById('bracket-result-details');
            resultDetails.innerHTML = `
                <div class="result-success">
                    <div class="bracket-summary">
                        <div class="bracket-stat">
                            <span class="stat-value">${result.bracket}</span>
                            <span class="stat-label">Bracket</span>
                        </div>
                        <div class="bracket-stat">
                            <span class="stat-value">$${formatNumber(result.current_market_cap)}</span>
                            <span class="stat-label">Current Market Cap</span>
                        </div>
                        <div class="bracket-stat">
                            <span class="stat-value">${result.total_placed}</span>
                            <span class="stat-label">Orders Placed</span>
                        </div>
                        <div class="bracket-stat">
                            <span class="stat-value">${result.total_failed}</span>
                            <span class="stat-label">Orders Failed</span>
                        </div>
                    </div>
                    
                    <h4>Placed Orders:</h4>
                    <div class="placed-orders">
            `;
            
            result.placed_orders.forEach(order => {
                resultDetails.innerHTML += `
                    <div class="order-result">
                        <strong>${order.strategy_name}</strong> (${order.order_type}): 
                        ${order.amount.toFixed(6)} SOL - 
                        Entry: $${formatNumber(order.entry_market_cap)}, 
                        TP: $${formatNumber(order.take_profit_market_cap)}, 
                        SL: $${formatNumber(order.stop_loss_market_cap)}
                    </div>
                `;
            });
            
            if (result.failed_orders.length > 0) {
                resultDetails.innerHTML += `
                    <h4>Failed Orders:</h4>
                    <div class="failed-orders">
                `;
                
                result.failed_orders.forEach(failed => {
                    resultDetails.innerHTML += `
                        <div class="order-error">
                            <strong>Bracket ${failed.bracket_id}:</strong> ${failed.error}
                        </div>
                    `;
                });
                
                resultDetails.innerHTML += '</div>';
            }
            
            resultDetails.innerHTML += '</div>';
            
            // Show the result section
            document.getElementById('bracket-result').classList.remove('hidden');
            
            // Refresh orders and coins
            loadOrders();
            loadCoins();
            
            showBracketMessage(`Bracket strategy executed! ${result.total_placed} orders placed successfully.`, 'success');
        } else {
            showBracketMessage('Failed to execute bracket strategy', 'error');
        }
    } catch (error) {
        console.error('Error executing bracket strategy:', error);
        showBracketMessage(`Error: ${error.message}`, 'error');
    } finally {
        // Reset button state - stop animation and restore original text
        const button = document.getElementById('execute-bracket-btn');
        button.innerHTML = '<i class="fas fa-rocket"></i> Execute Bracket Strategy';
        button.disabled = false;
    }
}

/**
 * Show a message in the bracket strategy section
 * @param {string} message - Message to display
 * @param {string} type - Message type (success, error, info, warning)
 */
function showBracketMessage(message, type = 'info') {
    // Create or update message element
    let messageElement = document.getElementById('bracket-message');
    if (!messageElement) {
        messageElement = document.createElement('div');
        messageElement.id = 'bracket-message';
        messageElement.className = 'message';
        
        // Insert after the description
        const description = document.querySelector('.card h2 + .description');
        if (description) {
            description.parentNode.insertBefore(messageElement, description.nextSibling);
        }
    }
    
    messageElement.textContent = message;
    messageElement.className = `message ${type}`;
    messageElement.classList.remove('hidden');
    
    // Auto-hide success messages after 5 seconds
    if (type === 'success') {
        setTimeout(() => {
            messageElement.classList.add('hidden');
        }, 5000);
    }
}

/**
 * Format market cap with appropriate class for styling
 * @param {number} marketCap - Market cap value
 * @returns {string} - Formatted market cap with CSS class
 */
function formatMarketCapWithClass(marketCap) {
    const bracket = calculateBracketFromMarketCap(marketCap);
    const classes = ['', 'micro', 'small', 'medium', 'large', 'mega'];
    const className = classes[bracket] || '';
    
    return `<span class="market-cap ${className}">$${formatNumber(marketCap)}</span>`;
}
