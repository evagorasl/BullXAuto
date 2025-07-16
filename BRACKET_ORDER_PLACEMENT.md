# Bracket Order Placement System Documentation

## Overview

The Bracket Order Placement System is an advanced trading automation feature for BullXAuto that enables placing multiple orders for a single token based on market cap brackets. This system automatically determines order types (market vs limit), configures auto-sell strategies, and manages order placement through the BullX interface.

## Key Features

- **Automatic Bracket Detection**: Determines market cap bracket (1-5) based on current token market cap
- **Smart Order Type Selection**: Places market orders when current market cap < entry market cap, limit orders otherwise
- **Multi-Order Placement**: Places up to 4 orders per token with different entry points and amounts
- **Auto-Sell Integration**: Configures take profit and stop loss strategies for each order
- **Order Replacement**: Replace fulfilled orders while maintaining bracket structure
- **Preview Functionality**: Preview orders before placement

## Architecture

### Core Components

1. **BracketOrderPlacer**: Main class handling order placement logic
2. **BracketOrderManager**: High-level interface for bracket operations
3. **Bracket Configuration**: Market cap ranges, trade sizes, and entry points
4. **API Endpoints**: RESTful API for bracket order operations

### File Structure

```
bracket_order_placement.py          # Core order placement logic
bracket_config.py                   # Bracket configuration and calculations
example_bracket_order_usage.py      # Usage examples and demonstrations
test_bracket_order_placement.py     # Comprehensive test suite
routers/secure.py                   # API endpoints (updated)
```

## Market Cap Brackets

| Bracket | Market Cap Range | Description | Strategy Focus |
|---------|------------------|-------------|----------------|
| 1 | $20K - $120K | Micro Cap | High risk, aggressive entries |
| 2 | $200K - $1.2M | Small Cap | Medium risk, balanced approach |
| 3 | $2M - $12M | Medium Cap | Balanced risk and reward |
| 4 | $12M - $120M | Large Cap | Lower risk, conservative entries |
| 5 | $120M - $1.2B | Mega Cap | Very conservative, tight stops |

## Order Placement Logic

### Market vs Limit Order Determination

```python
# Order type is determined by comparing current market cap to entry market cap
is_market_order = current_market_cap < entry_market_cap

if is_market_order:
    # Place market order immediately
    place_market_order()
else:
    # Set up limit order at entry market cap
    setup_limit_order(entry_market_cap)
```

### Trade Size Distribution

Orders are distributed across 4 bracket IDs with the following default percentages:
- Bracket ID 1: 33.33% of total amount
- Bracket ID 2: 33.33% of total amount  
- Bracket ID 3: 16.67% of total amount
- Bracket ID 4: 16.67% of total amount

### Auto-Sell Strategy Naming

Each order gets a unique auto-sell strategy name following the pattern:
`Bracket{bracket}_{bracket_id}`

Examples:
- `Bracket1_1` - Bracket 1, Order 1
- `Bracket2_3` - Bracket 2, Order 3
- `Bracket5_4` - Bracket 5, Order 4

## API Endpoints

### Execute Bracket Strategy
**POST** `/api/v1/bracket-strategy`

Execute complete bracket strategy for a token (places all 4 orders).

**Parameters:**
- `address` (string): Token contract address
- `total_amount` (float): Total investment amount to distribute
- `strategy_number` (int, optional): Strategy number (default: 1)

**Response:**
```json
{
  "success": true,
  "message": "Bracket strategy executed successfully",
  "bracket": 2,
  "current_market_cap": 500000,
  "placed_orders": [...],
  "failed_orders": [],
  "total_placed": 4,
  "total_failed": 0,
  "total_amount": 1000.0
}
```

### Replace Bracket Order
**POST** `/api/v1/bracket-order-replace/{address}/{bracket_id}`

Replace a specific bracket order with a new one.

**Parameters:**
- `address` (string): Token contract address
- `bracket_id` (int): Bracket ID to replace (1-4)
- `new_amount` (float): New order amount
- `strategy_number` (int, optional): Strategy number (default: 1)

### Preview Bracket Orders
**GET** `/api/v1/bracket-preview/{address}?total_amount={amount}`

Preview bracket orders without placing them.

**Response:**
```json
{
  "success": true,
  "bracket": 2,
  "bracket_info": {...},
  "current_market_cap": 500000,
  "total_amount": 1000.0,
  "orders": [
    {
      "bracket_id": 1,
      "order_type": "MARKET",
      "strategy_name": "Bracket2_1",
      "entry_price": 93100,
      "take_profit": 176189,
      "stop_loss": 78000,
      "amount": 333.33
    }
  ]
}
```

### Get Current Market Cap
**GET** `/api/v1/market-cap/{address}`

Get current market cap and bracket information for a token.

## Usage Examples

### Basic Bracket Strategy Execution

```python
from bracket_order_placement import bracket_order_manager

# Execute bracket strategy
result = bracket_order_manager.execute_bracket_strategy(
    profile_name="Saruman",
    address="0x1234567890abcdef1234567890abcdef12345678",
    total_amount=1000.0,
    strategy_number=1
)

if result["success"]:
    print(f"Placed {result['total_placed']} orders for bracket {result['bracket']}")
    for order in result["placed_orders"]:
        print(f"Order {order['bracket_id']}: {order['order_type']} - ${order['amount']}")
```

### Order Replacement

```python
# Replace bracket order 2 with new amount
result = bracket_order_manager.replace_order(
    profile_name="Saruman",
    address="0x1234567890abcdef1234567890abcdef12345678",
    bracket_id=2,
    new_amount=500.0,
    strategy_number=1
)

if result["success"]:
    print(f"Replaced order {result['order']['bracket_id']} successfully")
```

### Preview Orders

```python
# Preview orders before placing
preview = bracket_order_manager.get_bracket_preview(
    address="0x1234567890abcdef1234567890abcdef12345678",
    total_amount=2000.0,
    profile_name="Saruman"
)

if preview["success"]:
    print(f"Bracket {preview['bracket']} orders:")
    for order in preview["orders"]:
        print(f"  {order['strategy_name']}: ${order['amount']} ({order['order_type']})")
```

## Configuration

### Bracket Configuration

The bracket system is configured in `bracket_config.py`:

```python
# Market cap ranges for each bracket
BRACKET_RANGES = {
    1: {"min": 20000, "max": 120000},
    2: {"min": 200000, "max": 1200000},
    # ... more brackets
}

# Trade sizes for each bracket_id
TRADE_SIZES = [0.3333, 0.3333, 0.1667, 0.1667]

# Take profit percentages for each bracket_id
TAKE_PROFIT_PERCENTAGES = [1.12, 0.89, 0.81, 0.56]

# Bracket-specific configurations
BRACKET_CONFIG = {
    1: {
        "stop_loss_market_cap": 7800,
        "entries": [9310, 13100, 23100, 33100],
        "description": "Micro Cap (20K - 120K)"
    },
    # ... more brackets
}
```

### Customizing Bracket Parameters

To modify bracket behavior:

1. **Adjust Market Cap Ranges**: Modify `BRACKET_RANGES` in `bracket_config.py`
2. **Change Trade Sizes**: Update `TRADE_SIZES` array (must sum to 1.0)
3. **Modify Take Profit Levels**: Adjust `TAKE_PROFIT_PERCENTAGES`
4. **Update Entry Points**: Change `entries` arrays in `BRACKET_CONFIG`

## Error Handling

The system includes comprehensive error handling for:

- **Login Failures**: Automatic retry and error reporting
- **Search Failures**: Token not found or network issues
- **Market Cap Retrieval**: Fallback mechanisms and validation
- **UI Interaction Failures**: Element not found, timeout handling
- **Order Placement Failures**: Individual order failure tracking

### Common Error Scenarios

1. **"Failed to login"**: Chrome profile authentication issues
2. **"Failed to search address"**: Invalid token address or network problems
3. **"Failed to get market cap"**: Token data not available or UI changes
4. **"Failed to navigate to buy interface"**: BullX UI structure changes
5. **"Failed to configure auto-sell strategy"**: Strategy selection issues

## Testing

### Running Tests

```bash
python test_bracket_order_placement.py
```

### Test Coverage

The test suite covers:
- Market vs limit order logic
- Bracket calculation and order parameters
- Strategy naming conventions
- Error handling scenarios
- Order replacement functionality
- Full bracket strategy execution

### Mock Testing

Tests use comprehensive mocking to simulate:
- Chrome driver interactions
- BullX UI elements
- Database operations
- Network requests

## Best Practices

### Order Management

1. **Monitor Order Status**: Regularly check order fulfillment
2. **Replace Fulfilled Orders**: Use replacement functionality to maintain strategy
3. **Adjust for Market Conditions**: Consider bracket changes as market cap evolves
4. **Risk Management**: Don't exceed comfortable investment amounts

### Strategy Implementation

1. **Start with Previews**: Always preview orders before placement
2. **Test with Small Amounts**: Validate functionality with minimal investments
3. **Monitor Performance**: Track success rates by bracket and market conditions
4. **Customize Configuration**: Adjust parameters based on your risk tolerance

### Technical Considerations

1. **Element Selectors**: Update UI selectors if BullX interface changes
2. **Timing**: Allow sufficient time for UI interactions
3. **Error Recovery**: Implement retry logic for transient failures
4. **Logging**: Monitor logs for debugging and optimization

## Troubleshooting

### Common Issues

1. **Orders Not Placing**
   - Check Chrome profile login status
   - Verify token address is correct
   - Ensure sufficient balance for orders

2. **Incorrect Order Types**
   - Verify market cap retrieval is working
   - Check bracket calculation logic
   - Validate entry point configuration

3. **Auto-Sell Strategy Failures**
   - Confirm strategy naming convention
   - Check BullX auto-sell interface availability
   - Verify take profit/stop loss values

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### UI Element Updates

If BullX updates their interface, update selectors in:
- `_navigate_to_buy_interface()`
- `_enter_order_amount()`
- `_configure_auto_sell_strategy()`
- `_confirm_order()`

## Performance Considerations

### Optimization Tips

1. **Batch Operations**: Process multiple tokens efficiently
2. **Connection Reuse**: Keep Chrome drivers active between operations
3. **Parallel Processing**: Consider async operations for multiple profiles
4. **Caching**: Cache market cap data for short periods

### Resource Management

1. **Memory Usage**: Close unused Chrome drivers
2. **Network Efficiency**: Minimize redundant API calls
3. **Database Optimization**: Use efficient queries for order tracking

## Security Considerations

### API Security

1. **Authentication**: All endpoints require valid API keys
2. **Input Validation**: Comprehensive parameter validation
3. **Rate Limiting**: Implement appropriate rate limits
4. **Error Information**: Avoid exposing sensitive data in errors

### Chrome Profile Security

1. **Profile Isolation**: Use separate profiles for different strategies
2. **Credential Management**: Secure storage of authentication data
3. **Session Management**: Proper cleanup of browser sessions

## Future Enhancements

### Planned Features

1. **Dynamic Bracket Adjustment**: Automatic bracket recalculation
2. **Advanced Strategy Types**: Custom entry/exit logic
3. **Performance Analytics**: Detailed success rate tracking
4. **Risk Management Tools**: Position sizing and exposure limits
5. **Integration Improvements**: Better BullX API integration

### Extension Points

1. **Custom Bracket Logic**: Pluggable bracket calculation
2. **Strategy Plugins**: Extensible strategy system
3. **Notification System**: Order status notifications
4. **Reporting Dashboard**: Visual performance tracking

## Support and Maintenance

### Regular Maintenance

1. **UI Selector Updates**: Monitor for BullX interface changes
2. **Configuration Tuning**: Adjust parameters based on market conditions
3. **Performance Monitoring**: Track system performance and optimize
4. **Security Updates**: Keep dependencies and security measures current

### Getting Help

1. **Documentation**: Refer to this guide and code comments
2. **Test Suite**: Run tests to verify functionality
3. **Example Code**: Use provided examples as reference
4. **Logging**: Enable debug logging for troubleshooting

---

This documentation provides a comprehensive guide to the Bracket Order Placement System. For specific implementation details, refer to the source code and test files.
