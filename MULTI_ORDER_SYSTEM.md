# Multi-Order Bracket System Documentation

## Overview

The BullXAuto Multi-Order Bracket System allows you to place up to 4 orders per coin with different price points and amounts. Each order is identified by a `bracket_id` (1-4) and coins are categorized into brackets based on their market cap.

## Key Features

- **Multiple Orders per Coin**: Place up to 4 orders per coin per profile
- **Bracket System**: Coins are automatically categorized into brackets based on market cap
- **Order Tracking**: Each order has a unique `bracket_id` for easy identification
- **Order Replacement**: Replace fulfilled orders while maintaining the same `bracket_id`
- **Efficient Management**: Query and manage orders by bracket and coin

## Market Cap Brackets

| Bracket | Market Cap Range | Description |
|---------|------------------|-------------|
| 1 | < $100K | Micro Cap |
| 2 | $100K - $500K | Small Cap |
| 3 | $500K - $1M | Medium Cap |
| 4 | $1M - $5M | Large Cap |
| 5 | > $5M | Mega Cap |

## Database Schema Changes

### Coins Table
- Added `bracket` column (INTEGER) - Market cap bracket (1-5)

### Orders Table  
- Added `bracket_id` column (INTEGER) - Sub-order identifier (1-4)

## API Endpoints

### 1. Create Multi-Order
**POST** `/api/v1/multi-order`

Create multiple orders for a coin with different bracket_ids.

**Request Body:**
```json
{
  "strategy_number": 1,
  "address": "0x1234567890abcdef1234567890abcdef12345678",
  "order_type": "BUY",
  "orders": [
    {
      "bracket_id": 1,
      "entry_price": 0.000001,
      "take_profit": 0.000002,
      "stop_loss": 0.0000008,
      "amount": 1000000
    },
    {
      "bracket_id": 2,
      "entry_price": 0.0000008,
      "take_profit": 0.0000015,
      "stop_loss": 0.0000006,
      "amount": 1500000
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "message": "Successfully created 2 orders for 0x1234...",
  "coin": {
    "id": 1,
    "address": "0x1234567890abcdef1234567890abcdef12345678",
    "bracket": 2,
    "market_cap": 250000
  },
  "orders": [
    {
      "id": 1,
      "bracket_id": 1,
      "entry_price": 0.000001,
      "take_profit": 0.000002,
      "stop_loss": 0.0000008,
      "status": "ACTIVE"
    }
  ],
  "total_orders_created": 2
}
```

### 2. Replace Order
**POST** `/api/v1/replace-order/{coin_address}/{bracket_id}`

Replace a completed/stopped order with a new one maintaining the same bracket_id.

**Request Body:**
```json
{
  "entry_price": 0.0000007,
  "take_profit": 0.0000014,
  "stop_loss": 0.0000005,
  "amount": 1800000
}
```

### 3. Get Orders Summary
**GET** `/api/v1/orders-summary`

Get a summary of active orders grouped by coin and bracket_id.

**Response:**
```json
{
  "success": true,
  "summary": {
    "0x1234567890abcdef1234567890abcdef12345678": {
      "coin": {
        "address": "0x1234567890abcdef1234567890abcdef12345678",
        "bracket": 2,
        "market_cap": 250000
      },
      "orders": {
        "1": {
          "id": 1,
          "bracket_id": 1,
          "entry_price": 0.000001,
          "status": "ACTIVE"
        },
        "2": {
          "id": 2,
          "bracket_id": 2,
          "entry_price": 0.0000008,
          "status": "ACTIVE"
        }
      }
    }
  },
  "total_coins": 1
}
```

### 4. Get Next Available Bracket ID
**GET** `/api/v1/coins/{address}/next-bracket-id`

Get the next available bracket_id for a coin.

**Response:**
```json
{
  "success": true,
  "next_bracket_id": 3,
  "message": "Next available bracket ID is 3"
}
```

### 5. Get Bracket Information
**GET** `/api/v1/brackets`

Get information about market cap brackets.

**Response:**
```json
[
  {
    "bracket": 1,
    "min_market_cap": 0,
    "max_market_cap": 100000,
    "description": "Micro Cap (< 100K)"
  },
  {
    "bracket": 2,
    "min_market_cap": 100000,
    "max_market_cap": 500000,
    "description": "Small Cap (100K - 500K)"
  }
]
```

## Usage Examples

### Basic Multi-Order Creation

```python
import requests

# API configuration
api_key = "your_api_key_here"
base_url = "http://localhost:8000"
headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

# Create multiple orders
orders = [
    {
        "bracket_id": 1,
        "entry_price": 0.000001,
        "take_profit": 0.000002,
        "stop_loss": 0.0000008,
        "amount": 1000000
    },
    {
        "bracket_id": 2,
        "entry_price": 0.0000008,
        "take_profit": 0.0000015,
        "stop_loss": 0.0000006,
        "amount": 1500000
    }
]

payload = {
    "strategy_number": 1,
    "address": "0x1234567890abcdef1234567890abcdef12345678",
    "order_type": "BUY",
    "orders": orders
}

response = requests.post(f"{base_url}/api/v1/multi-order", json=payload, headers=headers)
result = response.json()

if result["success"]:
    print(f"Created {result['total_orders_created']} orders")
```

### Order Replacement Workflow

```python
# When an order gets fulfilled, replace it with a new one
new_order = {
    "entry_price": 0.0000007,
    "take_profit": 0.0000014,
    "stop_loss": 0.0000005,
    "amount": 1800000
}

coin_address = "0x1234567890abcdef1234567890abcdef12345678"
bracket_id = 2  # Replace the order with bracket_id 2

response = requests.post(
    f"{base_url}/api/v1/replace-order/{coin_address}/{bracket_id}",
    json=new_order,
    headers=headers
)

result = response.json()
if result["success"]:
    print(f"Order replaced successfully for bracket_id {bracket_id}")
```

## Strategy Recommendations by Bracket

### Micro Cap (Bracket 1) - High Risk
- **Investment Distribution**: 15%, 20%, 25%, 40% across bracket_ids 1-4
- **Price Levels**: More aggressive entry points and higher profit targets
- **Risk Management**: Smaller individual amounts due to high volatility

### Small Cap (Bracket 2) - Medium Risk
- **Investment Distribution**: 20%, 25%, 25%, 30% across bracket_ids 1-4
- **Price Levels**: Balanced approach with moderate profit targets
- **Risk Management**: Medium-sized positions

### Medium Cap (Bracket 3) - Balanced
- **Investment Distribution**: 25%, 25%, 25%, 25% across bracket_ids 1-4
- **Price Levels**: Equal distribution with steady profit targets
- **Risk Management**: Balanced position sizing

### Large Cap (Bracket 4) - Lower Risk
- **Investment Distribution**: 30%, 25%, 25%, 20% across bracket_ids 1-4
- **Price Levels**: Conservative entry points with moderate targets
- **Risk Management**: Larger positions due to lower volatility

### Mega Cap (Bracket 5) - Very Conservative
- **Investment Distribution**: 40%, 30%, 20%, 10% across bracket_ids 1-4
- **Price Levels**: Very conservative with small profit margins
- **Risk Management**: Largest positions with tight stop losses

## Database Operations

### Key Methods in DatabaseManager

```python
# Create multiple orders
result = db_manager.create_multi_order(
    address="0x1234...",
    strategy_number=1,
    order_type="BUY",
    profile_name="Saruman",
    sub_orders=[
        {
            'bracket_id': 1,
            'entry_price': 0.000001,
            'take_profit': 0.000002,
            'stop_loss': 0.0000008,
            'amount': 1000000
        }
    ]
)

# Replace an order
new_order = db_manager.replace_order(
    coin_id=1,
    bracket_id=2,
    profile_name="Saruman",
    new_order_data={
        "strategy_number": 1,
        "order_type": "BUY",
        "market_cap": 250000,
        "entry_price": 0.0000007,
        "take_profit": 0.0000014,
        "stop_loss": 0.0000005,
        "amount": 1800000
    }
)

# Get next available bracket_id
next_bracket_id = db_manager.get_next_bracket_id(coin_id=1, profile_name="Saruman")

# Get orders summary
summary = db_manager.get_active_orders_summary(profile_name="Saruman")
```

## Migration

To migrate your existing database to support the new bracket system:

```bash
python migrate_database.py
```

This will:
1. Add the `bracket` column to the coins table
2. Add the `bracket_id` column to the orders table
3. Update existing orders with sequential bracket_ids
4. Calculate and set brackets for existing coins based on market cap

## Best Practices

### 1. Order Management
- Always check available bracket_ids before creating new orders
- Use the orders summary endpoint to get a complete overview
- Replace orders promptly when they get fulfilled to maintain your strategy

### 2. Risk Management
- Adjust order amounts based on coin bracket (market cap category)
- Use tighter stop losses for higher bracket coins
- Diversify across different bracket_ids to spread risk

### 3. Strategy Implementation
- Implement different strategies for different market cap brackets
- Use the bracket information to automatically adjust price levels
- Monitor order performance by bracket to optimize strategies

### 4. Error Handling
- Always validate bracket_ids are between 1-4
- Check for duplicate bracket_ids in multi-order requests
- Handle cases where all bracket_ids are in use

## Troubleshooting

### Common Issues

1. **"Bracket ID already in use"**
   - Check which bracket_ids are available using the next-bracket-id endpoint
   - Use the replace-order endpoint instead of creating a new order

2. **"Maximum 4 orders per coin"**
   - Complete or stop existing orders before creating new ones
   - Use the orders summary to see current active orders

3. **"Bracket IDs must be unique"**
   - Ensure no duplicate bracket_ids in your multi-order request
   - Each bracket_id can only be used once per coin per profile

### Debugging

Use the orders summary endpoint to debug order states:

```python
summary = client.get_orders_summary()
for address, data in summary['summary'].items():
    print(f"Coin: {address}")
    print(f"Active bracket_ids: {list(data['orders'].keys())}")
```

## Performance Considerations

- The bracket system is optimized for up to 4 orders per coin per profile
- Database queries are indexed on coin_id, profile_name, and bracket_id
- Use the summary endpoint for dashboard views instead of individual queries
- Batch operations when possible to reduce API calls

## Future Enhancements

Potential future improvements to the system:
- Dynamic bracket thresholds based on market conditions
- Automated order replacement based on predefined rules
- Advanced analytics by bracket performance
- Integration with external market data for bracket updates
