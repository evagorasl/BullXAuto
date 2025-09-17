# THIS IS A WORK IN PROGRESS
# BullXAuto

A Python automation system for trading processes on neo.bullx.io using FastAPI and Selenium, with a web-based dashboard for easy management.

## Features

- **FastAPI REST API** for receiving and processing trading requests
- **Selenium WebDriver** automation for interacting with neo.bullx.io
- **Multiple Chrome Profiles** support (Saruman and Gandalf profiles)
- **Database Integration** with SQLAlchemy for tracking orders and profiles
- **Background Tasks** for monitoring active orders every 5 minutes
- **Strategy-based Trading** with configurable parameters
- **Automatic Re-entry** of completed orders with updated parameters
- **Web Dashboard** for visualizing and managing the automation system

## Project Structure

```
BullXAuto/
├── main.py                 # FastAPI application entry point
├── models.py               # Database and Pydantic models
├── database.py             # Database operations and management
├── chrome_driver.py        # Chrome WebDriver and BullX automation
├── background_tasks.py     # Order monitoring and background tasks
├── config.py               # Application configuration
├── auth.py                 # API key authentication
├── middleware.py           # Middleware for driver management
├── start.py                # Startup script
├── example_usage.py        # Basic API usage examples
├── example_usage_with_auth.py # API usage with authentication
├── test_setup.py           # Setup verification script
├── requirements.txt        # Python dependencies
├── README.md               # This file
├── .gitignore              # Git ignore rules
├── bullx_auto.db           # SQLite database (created automatically)
├── frontend/               # Web dashboard
│   ├── index.html          # Dashboard main page
│   ├── css/                # Stylesheets
│   │   └── styles.css      # Main stylesheet
│   ├── js/                 # JavaScript files
│   │   ├── api.js          # API client
│   │   └── app.js          # Dashboard application logic
│   └── README.md           # Dashboard documentation
└── routers/                # API route definitions
    ├── __init__.py         # Router package initialization
    ├── public.py           # Public API endpoints
    └── secure.py           # Secure API endpoints
```

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd BullXAuto
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up Chrome profiles:**
   - Create two Chrome profiles named "Saruman" and "Gandalf"
   - The profiles should be located at:
     - `%USERPROFILE%\AppData\Local\Google\Chrome\User Data\Profile Saruman`
     - `%USERPROFILE%\AppData\Local\Google\Chrome\User Data\Profile Gandalf`

## Usage

### Starting the API

**Option 1: Using the startup script (recommended)**
```bash
python start.py
```

**Option 2: Direct execution**
```bash
python main.py
```

The API and dashboard will be available at:
- **API Base URL:** http://localhost:8000
- **Dashboard:** http://localhost:8000/dashboard
- **Interactive API Documentation:** http://localhost:8000/docs
- **Alternative API Documentation:** http://localhost:8000/redoc

### Web Dashboard

The web dashboard provides a user-friendly interface for interacting with the BullX Automation API:

- **Authentication**: Secure login with API key
- **Token Search**: Search for tokens by address
- **Strategy Execution**: Execute trading strategies with customizable parameters
- **Order Management**: View and manage active orders
- **Database Visualization**: View coins and their associated orders

To access the dashboard, navigate to:
```
http://localhost:8000/dashboard
```

### API Endpoints

All secure endpoints are prefixed with `/api/v1`. The API also provides basic health check endpoints at the root level.

#### Root Endpoints
- `GET /` - Root endpoint
- `GET /health` - Health check endpoint

#### Secure API Endpoints (Prefix: `/api/v1`)

#### 1. Login
Opens browser and navigates to BullX for login.

```http
POST /api/v1/login
Authorization: Bearer bullx_your_api_key_here
Content-Type: application/json
```

#### 2. Search Address
Search for a specific token address.

```http
POST /api/v1/search
Authorization: Bearer bullx_your_api_key_here
Content-Type: application/json

{
    "address": "0x1234567890abcdef..."
}
```

#### 3. Execute Strategy
Execute a trading strategy with specified parameters.

```http
POST /api/v1/strategy
Authorization: Bearer bullx_your_api_key_here
Content-Type: application/json

{
    "strategy_number": 1,
    "address": "0x1234567890abcdef...",
    "order_type": "BUY",
    "entry_price": 0.001,
    "take_profit": 0.0015,
    "stop_loss": 0.0008
}
```

**Note:** If `entry_price`, `take_profit`, and `stop_loss` are not provided, they will be calculated automatically based on the strategy and current market conditions.

#### 4. Get Orders
Retrieve all active orders for the authenticated profile.

```http
GET /api/v1/orders
Authorization: Bearer bullx_your_api_key_here
```

#### 5. Get Profile
Get information about the authenticated profile.

```http
GET /api/v1/profile
Authorization: Bearer bullx_your_api_key_here
```

#### 6. Close Driver
Close Chrome driver for the authenticated profile.

```http
POST /api/v1/close-driver
Authorization: Bearer bullx_your_api_key_here
```

### Trading Strategies

The system supports multiple predefined strategies:

#### Strategy 1: Conservative
- **Description:** Low risk, moderate returns
- **Buy Orders:** Entry 2% below current price, 5% take profit, 5% stop loss
- **Sell Orders:** Entry 2% above current price, 5% take profit, 5% stop loss

#### Strategy 2: Aggressive
- **Description:** High risk, high returns
- **Buy Orders:** Entry 5% below current price, 15% take profit, 10% stop loss
- **Sell Orders:** Entry 5% above current price, 15% take profit, 10% stop loss

#### Strategy 3: Market Cap Based
- **Description:** Adjusts parameters based on token market capitalization
- **Large Cap (>1M):** More conservative approach
- **Small Cap (<1M):** More aggressive approach

### Background Monitoring

The system automatically monitors active orders every 5 minutes and:
- Checks order status on BullX
- Re-enters completed or stopped orders with updated parameters
- Adjusts parameters based on current market conditions
- Logs all activities for tracking

## Configuration

### Chrome Profiles
Update the profile paths in `config.py` if your Chrome profiles are located elsewhere:

```python
CHROME_PROFILES = {
    "Saruman": r"C:\Users\your_username\AppData\Local\Google\Chrome\User Data\Profile Saruman",
    "Gandalf": r"C:\Users\your_username\AppData\Local\Google\Chrome\User Data\Profile Gandalf"
}
```

### Database
The system uses SQLite by default. To use a different database, update the `DATABASE_URL` in `config.py`:

```python
DATABASE_URL = "postgresql://user:password@localhost/bullx_auto"
```

### Order Monitoring Interval
To change the order checking frequency, update `ORDER_CHECK_INTERVAL_MINUTES` in `config.py`:

```python
ORDER_CHECK_INTERVAL_MINUTES = 10  # Check every 10 minutes
```

## Development

### Adding New Strategies
1. Add strategy configuration to `config.py` in the `DEFAULT_STRATEGIES` dictionary
2. Update the `apply_strategy_adjustments` method in `background_tasks.py`
3. Update the `calculate_strategy_prices` function in `main.py`

### Customizing BullX Selectors
The CSS selectors used to interact with BullX are located in `chrome_driver.py`. You may need to update these based on changes to the BullX interface:

- Search input: `"input[placeholder*='search'], input[type='search']"`
- Market cap element: `".market-cap, [data-testid='market-cap']"`
- Trade button: `".trade-button, [data-testid='trade']"`
- Order placement: `".place-order, [data-testid='place-order']"`

## Troubleshooting

### Common Issues

1. **Chrome Profile Not Found**
   - Ensure Chrome profiles exist at the specified paths
   - Check that profile names match exactly (case-sensitive)

2. **Selenium WebDriver Issues**
   - Chrome WebDriver is automatically managed by webdriver-manager
   - Ensure Chrome browser is installed and up to date

3. **Database Errors**
   - Database tables are created automatically on first run
   - Check file permissions for SQLite database creation

4. **BullX Interface Changes**
   - Update CSS selectors in `chrome_driver.py` if BullX UI changes
   - Check browser console for JavaScript errors

### Logging
The application logs important events and errors. Check the console output for debugging information.

## Security Considerations

- **Chrome Profiles:** Store sensitive login information
- **Database:** Contains trading history and order information
- **API Authentication:** Secured with API key authentication
- **Network:** API runs on all interfaces (0.0.0.0) by default
- **API Keys:** Generated automatically on first run, store them securely

## License

This project is for educational and personal use. Please ensure compliance with neo.bullx.io terms of service.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs for error messages
3. Ensure all dependencies are properly installed
4. Verify Chrome profiles are correctly configured
