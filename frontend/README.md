# BullX Automation Dashboard

A web-based dashboard for the BullX Automation API that allows users to:

- Login with their API key
- Search for tokens
- Execute trading strategies
- View and manage orders
- Visualize the database (coins, orders, etc.)

## Features

- **Authentication**: Secure login with API key
- **Token Search**: Search for tokens by address
- **Strategy Execution**: Execute trading strategies with customizable parameters
- **Order Management**: View and manage active orders
- **Database Visualization**: View coins and their associated orders

## Usage

1. Start the BullX Automation API server:
   ```
   python start.py
   ```

2. Access the dashboard at:
   ```
   http://localhost:8000/dashboard
   ```

3. Login with your API key (starts with `bullx_`)

4. Use the dashboard to interact with the BullX Automation API

## API Documentation

The API documentation is available at:
```
http://localhost:8000/docs
```

## Technical Details

The dashboard is built with:

- HTML5
- CSS3
- JavaScript (ES6+)
- FastAPI (backend)

The dashboard communicates with the BullX Automation API using RESTful endpoints.

## Security

- API keys are stored in the browser's local storage for convenience
- All API requests are authenticated using Bearer token authentication
- CORS is enabled to allow cross-origin requests

## Development

To modify the dashboard:

1. Edit the files in the `frontend` directory
2. The server will automatically reload when changes are detected
3. Refresh the browser to see your changes
