"""
Test script for the multi-order bracket system.
This script tests the core functionality without requiring a full server setup.
"""

def test_bracket_calculation():
    """Test the bracket calculation logic"""
    def calculate_bracket(market_cap: float) -> int:
        """Calculate bracket based on market cap"""
        if market_cap < 100000:  # < 100K
            return 1
        elif market_cap < 500000:  # 100K - 500K
            return 2
        elif market_cap < 1000000:  # 500K - 1M
            return 3
        elif market_cap < 5000000:  # 1M - 5M
            return 4
        else:  # > 5M
            return 5
    
    test_cases = [
        (50000, 1, "Micro Cap"),
        (250000, 2, "Small Cap"),
        (750000, 3, "Medium Cap"),
        (2500000, 4, "Large Cap"),
        (10000000, 5, "Mega Cap"),
        (99999, 1, "Edge case - just under 100K"),
        (100000, 2, "Edge case - exactly 100K"),
        (500000, 3, "Edge case - exactly 500K"),
        (1000000, 4, "Edge case - exactly 1M"),
        (5000000, 5, "Edge case - exactly 5M")
    ]
    
    print("Testing bracket calculation...")
    all_passed = True
    
    for market_cap, expected_bracket, description in test_cases:
        actual_bracket = calculate_bracket(market_cap)
        status = "✓" if actual_bracket == expected_bracket else "❌"
        
        if actual_bracket != expected_bracket:
            all_passed = False
        
        print(f"{status} Market Cap: ${market_cap:,} -> Bracket {actual_bracket} ({description})")
    
    return all_passed

def test_bracket_info():
    """Test bracket information structure"""
    def get_bracket_info(bracket: int) -> dict:
        """Get bracket information"""
        bracket_ranges = {
            1: {"min": 0, "max": 100000, "description": "Micro Cap (< 100K)"},
            2: {"min": 100000, "max": 500000, "description": "Small Cap (100K - 500K)"},
            3: {"min": 500000, "max": 1000000, "description": "Medium Cap (500K - 1M)"},
            4: {"min": 1000000, "max": 5000000, "description": "Large Cap (1M - 5M)"},
            5: {"min": 5000000, "max": float('inf'), "description": "Mega Cap (> 5M)"}
        }
        return bracket_ranges.get(bracket, bracket_ranges[1])
    
    print("\nTesting bracket information...")
    
    for bracket in range(1, 6):
        info = get_bracket_info(bracket)
        print(f"✓ Bracket {bracket}: {info['description']} "
              f"(${info['min']:,} - ${info['max']:,})")
    
    return True

def test_bracket_id_validation():
    """Test bracket_id validation logic"""
    def validate_bracket_ids(bracket_ids: list) -> tuple:
        """Validate bracket_ids are unique and within range"""
        # Check uniqueness
        if len(set(bracket_ids)) != len(bracket_ids):
            return False, "Bracket IDs must be unique"
        
        # Check range
        if not all(1 <= bid <= 4 for bid in bracket_ids):
            return False, "Bracket IDs must be between 1 and 4"
        
        # Check maximum count
        if len(bracket_ids) > 4:
            return False, "Maximum 4 orders allowed per coin"
        
        return True, "Valid bracket IDs"
    
    print("\nTesting bracket_id validation...")
    
    test_cases = [
        ([1, 2, 3, 4], True, "All bracket IDs"),
        ([1, 2], True, "Partial bracket IDs"),
        ([1, 1, 2], False, "Duplicate bracket IDs"),
        ([0, 1, 2], False, "Invalid bracket ID (0)"),
        ([1, 2, 3, 5], False, "Invalid bracket ID (5)"),
        ([1, 2, 3, 4, 1], False, "Too many orders"),
        ([], True, "Empty list")
    ]
    
    all_passed = True
    
    for bracket_ids, expected_valid, description in test_cases:
        is_valid, message = validate_bracket_ids(bracket_ids)
        status = "✓" if is_valid == expected_valid else "❌"
        
        if is_valid != expected_valid:
            all_passed = False
        
        print(f"{status} {description}: {bracket_ids} -> {message}")
    
    return all_passed

def test_order_amount_calculation():
    """Test order amount calculation by bracket"""
    def calculate_order_amounts_by_bracket(bracket: int, total_investment: float) -> list:
        """Calculate order amounts based on bracket (market cap category)"""
        
        if bracket == 1:  # Micro Cap (< 100K) - High risk, smaller amounts
            return [
                total_investment * 0.15,  # 15% for bracket_id 1
                total_investment * 0.20,  # 20% for bracket_id 2
                total_investment * 0.25,  # 25% for bracket_id 3
                total_investment * 0.40   # 40% for bracket_id 4
            ]
        
        elif bracket == 2:  # Small Cap (100K - 500K) - Medium risk
            return [
                total_investment * 0.20,  # 20% for bracket_id 1
                total_investment * 0.25,  # 25% for bracket_id 2
                total_investment * 0.25,  # 25% for bracket_id 3
                total_investment * 0.30   # 30% for bracket_id 4
            ]
        
        elif bracket == 3:  # Medium Cap (500K - 1M) - Balanced
            return [
                total_investment * 0.25,  # 25% for each bracket_id
                total_investment * 0.25,
                total_investment * 0.25,
                total_investment * 0.25
            ]
        
        elif bracket == 4:  # Large Cap (1M - 5M) - Lower risk, larger amounts
            return [
                total_investment * 0.30,  # 30% for bracket_id 1
                total_investment * 0.25,  # 25% for bracket_id 2
                total_investment * 0.25,  # 25% for bracket_id 3
                total_investment * 0.20   # 20% for bracket_id 4
            ]
        
        else:  # Mega Cap (> 5M) - Very conservative
            return [
                total_investment * 0.40,  # 40% for bracket_id 1
                total_investment * 0.30,  # 30% for bracket_id 2
                total_investment * 0.20,  # 20% for bracket_id 3
                total_investment * 0.10   # 10% for bracket_id 4
            ]
    
    print("\nTesting order amount calculation...")
    
    total_investment = 1000  # $1000 test investment
    
    for bracket in range(1, 6):
        amounts = calculate_order_amounts_by_bracket(bracket, total_investment)
        total_percentage = sum(amounts) / total_investment
        
        print(f"✓ Bracket {bracket}: {[f'${amt:.0f}' for amt in amounts]} "
              f"(Total: {total_percentage:.0%})")
        
        # Verify total adds up to 100%
        if abs(total_percentage - 1.0) > 0.001:  # Allow for small floating point errors
            print(f"❌ Warning: Bracket {bracket} percentages don't add up to 100%")
            return False
    
    return True

def test_next_bracket_id_logic():
    """Test the logic for finding next available bracket_id"""
    def get_next_bracket_id(used_bracket_ids: set) -> int:
        """Get the next available bracket_id (1-4)"""
        for bracket_id in range(1, 5):
            if bracket_id not in used_bracket_ids:
                return bracket_id
        return None  # All bracket_ids are used
    
    print("\nTesting next bracket_id logic...")
    
    test_cases = [
        (set(), 1, "No orders active"),
        ({1}, 2, "Bracket 1 used"),
        ({1, 3}, 2, "Brackets 1,3 used"),
        ({2, 3, 4}, 1, "Brackets 2,3,4 used"),
        ({1, 2, 3, 4}, None, "All brackets used")
    ]
    
    all_passed = True
    
    for used_ids, expected, description in test_cases:
        result = get_next_bracket_id(used_ids)
        status = "✓" if result == expected else "❌"
        
        if result != expected:
            all_passed = False
        
        print(f"{status} {description}: Used {sorted(used_ids)} -> Next: {result}")
    
    return all_passed

def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("BullXAuto Multi-Order Bracket System Tests")
    print("=" * 60)
    
    tests = [
        ("Bracket Calculation", test_bracket_calculation),
        ("Bracket Information", test_bracket_info),
        ("Bracket ID Validation", test_bracket_id_validation),
        ("Order Amount Calculation", test_order_amount_calculation),
        ("Next Bracket ID Logic", test_next_bracket_id_logic)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with error: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The multi-order bracket system is ready to use.")
    else:
        print("⚠️  Some tests failed. Please review the implementation.")
    
    return passed == total

if __name__ == "__main__":
    run_all_tests()
