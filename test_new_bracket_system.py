"""
Test script for the updated bracket system with new market cap ranges and configurations.
"""

from bracket_config import (
    calculate_bracket, get_bracket_info, calculate_order_parameters,
    BRACKET_CONFIG, BRACKET_RANGES, TRADE_SIZES, TAKE_PROFIT_PERCENTAGES,
    validate_bracket_config
)

def test_new_bracket_calculation():
    """Test the new bracket calculation logic"""
    print("Testing new bracket calculation...")
    
    test_cases = [
        # Bracket 1: 20K - 200K
        (50000, 1, "Micro Cap - middle range"),
        (20000, 1, "Micro Cap - minimum"),
        (199999, 1, "Micro Cap - maximum"),
        (19999, 1, "Below minimum - defaults to bracket 1"),
        
        # Bracket 2: 200K - 2M
        (500000, 2, "Small Cap - middle range"),
        (200000, 2, "Small Cap - minimum"),
        (1999999, 2, "Small Cap - maximum"),
        
        # Bracket 3: 2M - 20M
        (5000000, 3, "Medium Cap - middle range"),
        (2000000, 3, "Medium Cap - minimum"),
        (19999999, 3, "Medium Cap - maximum"),
        
        # Bracket 4: 20M - 120M
        (50000000, 4, "Large Cap - middle range"),
        (20000000, 4, "Large Cap - minimum"),
        (119999999, 4, "Large Cap - maximum"),
        
        # Bracket 5: 120M - 1.2B
        (500000000, 5, "Mega Cap - middle range"),
        (120000000, 5, "Mega Cap - minimum"),
        (1199999999, 5, "Mega Cap - maximum"),
        
        # Edge cases
        (150000, 1, "Middle of bracket 1"),
        (1500000, 2, "Middle of bracket 2"),
        (15000000, 3, "Middle of bracket 3"),
        (2000000000, 1, "Above maximum - defaults to 1")
    ]
    
    all_passed = True
    
    for market_cap, expected_bracket, description in test_cases:
        actual_bracket = calculate_bracket(market_cap)
        status = "✓" if actual_bracket == expected_bracket else "❌"
        
        if actual_bracket != expected_bracket:
            all_passed = False
        
        print(f"{status} Market Cap: ${market_cap:,} -> Bracket {actual_bracket} ({description})")
    
    return all_passed

def test_bracket_info():
    """Test bracket information with new ranges"""
    print("\nTesting bracket information...")
    
    expected_ranges = {
        1: (20000, 199999, "Micro Cap (20K - 200K)"),
        2: (200000, 1999999, "Small Cap (200K - 2M)"),
        3: (2000000, 19999999, "Medium Cap (2M - 20M)"),
        4: (20000000, 119999999, "Large Cap (20M - 120M)"),
        5: (120000000, 1199999999, "Mega Cap (120M - 1.2B)")
    }
    
    all_passed = True
    
    for bracket in range(1, 6):
        info = get_bracket_info(bracket)
        expected_min, expected_max, expected_desc = expected_ranges[bracket]
        
        if (info["min_market_cap"] == expected_min and 
            info["max_market_cap"] == expected_max and 
            info["description"] == expected_desc):
            print(f"✓ Bracket {bracket}: {info['description']} "
                  f"(${info['min_market_cap']:,} - ${info['max_market_cap']:,})")
        else:
            print(f"❌ Bracket {bracket}: Expected {expected_desc}, got {info['description']}")
            all_passed = False
    
    return all_passed

def test_trade_sizes_and_take_profits():
    """Test trade sizes and take profit percentages"""
    print("\nTesting trade sizes and take profit percentages...")
    
    expected_trade_sizes = [0.3333, 0.3333, 0.1667, 0.1667]
    expected_take_profits = [1.12, 0.89, 0.81, 0.56]  # 112%, 89%, 81%, 56%
    
    print("Trade sizes (should sum to ~1.0):")
    total_trade_size = sum(TRADE_SIZES)
    for i, size in enumerate(TRADE_SIZES):
        print(f"  Bracket ID {i+1}: {size:.4f} ({size*100:.2f}%)")
    
    print(f"  Total: {total_trade_size:.4f} ({total_trade_size*100:.2f}%)")
    
    print("\nTake profit percentages:")
    for i, tp in enumerate(TAKE_PROFIT_PERCENTAGES):
        print(f"  Bracket ID {i+1}: {tp:.2f} ({tp*100:.1f}%)")
    
    # Validate
    trade_sizes_ok = abs(total_trade_size - 1.0) < 0.001
    take_profits_ok = TAKE_PROFIT_PERCENTAGES == expected_take_profits
    
    status_trade = "✓" if trade_sizes_ok else "❌"
    status_tp = "✓" if take_profits_ok else "❌"
    
    print(f"\n{status_trade} Trade sizes sum to 100%: {trade_sizes_ok}")
    print(f"{status_tp} Take profit percentages match expected: {take_profits_ok}")
    
    return trade_sizes_ok and take_profits_ok

def test_bracket_specific_configs():
    """Test bracket-specific configurations"""
    print("\nTesting bracket-specific configurations...")
    
    expected_configs = {
        1: {"stop_loss_mc": 7800, "entries": [9310, 13100, 23100, 33100]},
        2: {"stop_loss_mc": 78000, "entries": [93100, 131000, 231000, 331000]},
        3: {"stop_loss_mc": 780000, "entries": [931000, 1310000, 2310000, 3310000]},
        4: {"stop_loss_mc": 7800000, "entries": [9310000, 13100000, 23100000, 33100000]},
        5: {"stop_loss_mc": 78000000, "entries": [93100000, 131000000, 231000000, 331000000]}
    }
    
    all_passed = True
    
    for bracket in range(1, 6):
        config = BRACKET_CONFIG[bracket]
        expected = expected_configs[bracket]
        
        stop_loss_ok = config["stop_loss_market_cap"] == expected["stop_loss_mc"]
        entries_ok = config["entries"] == expected["entries"]
        
        status = "✓" if stop_loss_ok and entries_ok else "❌"
        
        if not (stop_loss_ok and entries_ok):
            all_passed = False
        
        print(f"{status} Bracket {bracket}:")
        print(f"    Stop loss MC: {config['stop_loss_market_cap']:,}")
        print(f"    Entries: {config['entries']}")
    
    return all_passed

def test_order_parameter_calculation():
    """Test order parameter calculation"""
    print("\nTesting order parameter calculation...")
    
    # Test with bracket 1 and $1000 total amount
    bracket = 1
    total_amount = 1000
    
    print(f"Testing bracket {bracket} with ${total_amount} total amount:")
    
    order_params = calculate_order_parameters(bracket, total_amount)
    
    expected_amounts = [333.3, 333.3, 166.7, 166.7]  # Based on trade sizes
    
    all_passed = True
    
    for i, params in enumerate(order_params):
        bracket_id = params['bracket_id']
        amount = params['amount']
        entry_price = params['entry_price']
        take_profit = params['take_profit']
        stop_loss = params['stop_loss']
        
        expected_amount = expected_amounts[i]
        amount_ok = abs(amount - expected_amount) < 0.1
        
        status = "✓" if amount_ok else "❌"
        
        if not amount_ok:
            all_passed = False
        
        print(f"  {status} Bracket ID {bracket_id}:")
        print(f"      Amount: ${amount:.1f} (expected ~${expected_amount:.1f})")
        print(f"      Entry: {entry_price:,}")
        print(f"      Take Profit: {take_profit:,}")
        print(f"      Stop Loss: {stop_loss:,}")
    
    return all_passed

def test_config_validation():
    """Test configuration validation"""
    print("\nTesting configuration validation...")
    
    errors = validate_bracket_config()
    
    if not errors:
        print("✓ Configuration validation passed - no errors found")
        return True
    else:
        print("❌ Configuration validation failed:")
        for error in errors:
            print(f"    - {error}")
        return False

def run_all_tests():
    """Run all tests for the new bracket system"""
    print("=" * 70)
    print("BullXAuto New Bracket System Tests")
    print("=" * 70)
    
    tests = [
        ("New Bracket Calculation", test_new_bracket_calculation),
        ("Bracket Information", test_bracket_info),
        ("Trade Sizes and Take Profits", test_trade_sizes_and_take_profits),
        ("Bracket-Specific Configurations", test_bracket_specific_configs),
        ("Order Parameter Calculation", test_order_parameter_calculation),
        ("Configuration Validation", test_config_validation)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with error: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 70)
    print("Test Results Summary")
    print("=" * 70)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The new bracket system is working correctly.")
        print("\nKey Features Verified:")
        print("- New market cap ranges (20K-200K, 200K-2M, 2M-20M, 20M-120M, 120M-1.2B)")
        print("- Trade sizes: 33.33%, 33.33%, 16.67%, 16.67%")
        print("- Take profit percentages: 112%, 89%, 81%, 56%")
        print("- Bracket-specific entry points and stop losses")
        print("- Automatic order parameter calculation")
    else:
        print("⚠️  Some tests failed. Please review the implementation.")
    
    return passed == total

if __name__ == "__main__":
    run_all_tests()
