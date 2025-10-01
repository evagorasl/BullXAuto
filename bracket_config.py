"""
Bracket configuration for the multi-order system.
This file contains all bracket-related parameters that can be easily modified.
"""

# Market cap ranges for each bracket
BRACKET_RANGES = {
    1: {"min": 20000, "max": 199999},
    2: {"min": 200000, "max": 1999999},
    3: {"min": 2000000, "max": 19999999},
    4: {"min": 20000000, "max": 119999999},
    5: {"min": 120000000, "max": 1199999999}
}

# Trade sizes for each bracket_id (order within bracket)
# These are percentages of the total investment amount
TRADE_SIZES = [1/3, 1/3, 1/6, 1/6]  # bracket_id 1, 2, 3, 4

# Take profit percentages for each bracket_id
TAKE_PROFIT_PERCENTAGES = [1.12, 0.89, 0.81, 0.56]  # 112%, 89%, 81%, 56%

# Bracket-specific configurations
BRACKET_CONFIG = {
    1: {
        "stop_loss_market_cap": 7800,
        "entries": [9310, 13100, 23100, 33100],
        "description": "Micro Cap (20K - 200K)"
    },
    2: {
        "stop_loss_market_cap": 78000,
        "entries": [93100, 131000, 231000, 331000],
        "description": "Small Cap (200K - 2M)"
    },
    3: {
        "stop_loss_market_cap": 780000,
        "entries": [931000, 1310000, 2310000, 3310000],
        "description": "Medium Cap (2M - 20M)"
    },
    4: {
        "stop_loss_market_cap": 7800000,
        "entries": [9310000, 13100000, 23100000, 33100000],
        "description": "Large Cap (20M - 120M)"
    },
    5: {
        "stop_loss_market_cap": 78000000,
        "entries": [93100000, 131000000, 231000000, 331000000],
        "description": "Mega Cap (120M - 1.2B)"
    }
}

def calculate_bracket(market_cap: float) -> int:
    """Calculate bracket based on market cap"""
    if market_cap >= 20000 and market_cap < 200000:
        return 1
    elif market_cap >= 200000 and market_cap < 2000000:
        return 2
    elif market_cap >= 2000000 and market_cap < 20000000:
        return 3
    elif market_cap >= 20000000 and market_cap < 120000000:
        return 4
    elif market_cap >= 120000000 and market_cap < 1200000000:
        return 5
    else:
        # Default to bracket 1 for market caps outside defined ranges
        return 1

def get_bracket_info(bracket: int) -> dict:
    """Get bracket information"""
    if bracket not in BRACKET_CONFIG:
        return BRACKET_CONFIG[1]  # Default to bracket 1
    
    config = BRACKET_CONFIG[bracket]
    range_info = BRACKET_RANGES[bracket]
    
    return {
        "bracket": bracket,
        "min_market_cap": range_info["min"],
        "max_market_cap": range_info["max"],
        "description": config["description"],
        "stop_loss_market_cap": config["stop_loss_market_cap"],
        "entries": config["entries"]
    }

def calculate_order_parameters(bracket: int, total_amount: float, current_price: float = None) -> list:
    """
    Calculate order parameters for all bracket_ids within a bracket
    
    Args:
        bracket: Market cap bracket (1-5)
        total_amount: Total investment amount
        current_price: Current token price (optional, will use entries if not provided)
    
    Returns:
        List of order parameters for bracket_ids 1-4
    """
    if bracket not in BRACKET_CONFIG:
        bracket = 1  # Default to bracket 1
    
    config = BRACKET_CONFIG[bracket]
    orders = []
    
    for i in range(4):  # bracket_ids 1-4
        bracket_id = i + 1
        
        # Calculate trade size (amount)
        trade_amount = total_amount * TRADE_SIZES[i]
        
        # Entry price (use market cap values directly)
        entry_market_cap = config["entries"][i]
        entry_price = entry_market_cap  # Use market cap as entry target
        
        # Take profit calculation (use market cap values directly)
        take_profit_multiplier = TAKE_PROFIT_PERCENTAGES[i]
        take_profit_price = entry_price + entry_price * take_profit_multiplier
        
        # Stop loss calculation (use market cap value directly)
        stop_loss_market_cap = config["stop_loss_market_cap"]
        stop_loss_price = stop_loss_market_cap  # Use market cap as stop loss target
        
        orders.append({
            "bracket_id": bracket_id,
            "entry_price": entry_price,
            "take_profit": take_profit_price,
            "stop_loss": stop_loss_price,
            "amount": trade_amount,
            "trade_size_pct": TRADE_SIZES[i],
            "take_profit_pct": TAKE_PROFIT_PERCENTAGES[i]
        })
    
    return orders

def validate_bracket_config():
    """Validate that the bracket configuration is consistent"""
    errors = []
    
    # Check that all brackets have the required fields
    for bracket in range(1, 6):
        if bracket not in BRACKET_CONFIG:
            errors.append(f"Missing configuration for bracket {bracket}")
            continue
        
        config = BRACKET_CONFIG[bracket]
        required_fields = ["stop_loss_market_cap", "entries", "description"]
        
        for field in required_fields:
            if field not in config:
                errors.append(f"Missing field '{field}' in bracket {bracket}")
        
        # Check that entries has exactly 4 values
        if "entries" in config and len(config["entries"]) != 4:
            errors.append(f"Bracket {bracket} entries must have exactly 4 values, got {len(config['entries'])}")
    
    # Check that trade sizes and take profit percentages have exactly 4 values
    if len(TRADE_SIZES) != 4:
        errors.append(f"TRADE_SIZES must have exactly 4 values, got {len(TRADE_SIZES)}")
    
    if len(TAKE_PROFIT_PERCENTAGES) != 4:
        errors.append(f"TAKE_PROFIT_PERCENTAGES must have exactly 4 values, got {len(TAKE_PROFIT_PERCENTAGES)}")
    
    # Check that trade sizes sum to approximately 1.0
    total_trade_size = sum(TRADE_SIZES)
    if abs(total_trade_size - 1.0) > 0.001:
        errors.append(f"TRADE_SIZES should sum to 1.0, got {total_trade_size}")
    
    return errors

# Validate configuration on import
_validation_errors = validate_bracket_config()
if _validation_errors:
    print("Bracket configuration validation errors:")
    for error in _validation_errors:
        print(f"  - {error}")
