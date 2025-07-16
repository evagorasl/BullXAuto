"""
Test suite for the Bracket Order Placement System.

This test file verifies the functionality of:
1. Bracket order placement logic
2. Market vs limit order determination
3. Auto-sell strategy configuration
4. Order replacement functionality
5. Preview generation
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bracket_order_placement import BracketOrderPlacer, BracketOrderManager
from bracket_config import calculate_bracket, get_bracket_info, calculate_order_parameters
from chrome_driver import BullXAutomator

class TestBracketOrderPlacement(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock the BullXAutomator
        self.mock_automator = Mock(spec=BullXAutomator)
        self.mock_driver_manager = Mock()
        self.mock_automator.driver_manager = self.mock_driver_manager
        
        # Create the order placer with mocked automator
        self.order_placer = BracketOrderPlacer(self.mock_automator)
        
        # Test data
        self.test_address = "0x1234567890abcdef1234567890abcdef12345678"
        self.test_profile = "TestProfile"
        self.test_amount = 1000.0
        
    def test_market_vs_limit_order_logic(self):
        """Test that market vs limit order logic works correctly"""
        
        # Test case 1: Current market cap < entry market cap = MARKET order
        current_mc = 50000
        entry_mc = 100000
        
        # Mock the automator methods
        self.mock_automator._ensure_logged_in.return_value = True
        self.mock_automator.search_address.return_value = True
        self.mock_automator.get_market_cap.return_value = current_mc
        
        # Mock driver and UI interactions
        mock_driver = Mock()
        self.mock_driver_manager.get_driver.return_value = mock_driver
        
        # Mock successful UI interactions
        with patch.object(self.order_placer, '_navigate_to_buy_interface', return_value=True), \
             patch.object(self.order_placer, '_enter_order_amount', return_value=True), \
             patch.object(self.order_placer, '_place_market_order', return_value=True), \
             patch.object(self.order_placer, '_configure_auto_sell_strategy', return_value=True), \
             patch.object(self.order_placer, '_confirm_order', return_value=True), \
             patch('bracket_order_placement.db_manager') as mock_db:
            
            mock_db.create_order_with_coin.return_value = {"order_id": 1}
            
            result = self.order_placer._place_single_bracket_order(
                profile_name=self.test_profile,
                address=self.test_address,
                bracket=1,
                bracket_id=1,
                current_market_cap=current_mc,
                entry_market_cap=entry_mc,
                take_profit_market_cap=150000,
                stop_loss_market_cap=30000,
                amount=250.0,
                strategy_number=1
            )
            
            self.assertTrue(result["success"])
            self.assertEqual(result["order"]["order_type"], "MARKET")
            
        # Test case 2: Current market cap > entry market cap = LIMIT order
        current_mc = 100000
        entry_mc = 50000
        
        self.mock_automator.get_market_cap.return_value = current_mc
        
        with patch.object(self.order_placer, '_navigate_to_buy_interface', return_value=True), \
             patch.object(self.order_placer, '_enter_order_amount', return_value=True), \
             patch.object(self.order_placer, '_setup_limit_order', return_value=True), \
             patch.object(self.order_placer, '_configure_auto_sell_strategy', return_value=True), \
             patch.object(self.order_placer, '_confirm_order', return_value=True), \
             patch('bracket_order_placement.db_manager') as mock_db:
            
            mock_db.create_order_with_coin.return_value = {"order_id": 2}
            
            result = self.order_placer._place_single_bracket_order(
                profile_name=self.test_profile,
                address=self.test_address,
                bracket=1,
                bracket_id=2,
                current_market_cap=current_mc,
                entry_market_cap=entry_mc,
                take_profit_market_cap=150000,
                stop_loss_market_cap=30000,
                amount=250.0,
                strategy_number=1
            )
            
            self.assertTrue(result["success"])
            self.assertEqual(result["order"]["order_type"], "LIMIT")
    
    def test_bracket_calculation_and_order_parameters(self):
        """Test bracket calculation and order parameter generation"""
        
        # Test different market cap scenarios
        test_cases = [
            {"market_cap": 50000, "expected_bracket": 1},
            {"market_cap": 300000, "expected_bracket": 2},
            {"market_cap": 5000000, "expected_bracket": 3},
            {"market_cap": 50000000, "expected_bracket": 4},
            {"market_cap": 500000000, "expected_bracket": 5}
        ]
        
        for case in test_cases:
            bracket = calculate_bracket(case["market_cap"])
            self.assertEqual(bracket, case["expected_bracket"])
            
            # Test order parameters calculation
            order_params = calculate_order_parameters(bracket, self.test_amount)
            
            # Should have 4 orders
            self.assertEqual(len(order_params), 4)
            
            # Each order should have required fields
            for i, order in enumerate(order_params):
                self.assertEqual(order["bracket_id"], i + 1)
                self.assertIn("entry_price", order)
                self.assertIn("take_profit", order)
                self.assertIn("stop_loss", order)
                self.assertIn("amount", order)
                self.assertGreater(order["amount"], 0)
            
            # Total amounts should equal input amount
            total_amount = sum(order["amount"] for order in order_params)
            self.assertAlmostEqual(total_amount, self.test_amount, places=2)
    
    def test_strategy_naming_convention(self):
        """Test that strategy names are generated correctly"""
        
        test_cases = [
            {"bracket": 1, "bracket_id": 1, "expected": "Bracket1_1"},
            {"bracket": 2, "bracket_id": 3, "expected": "Bracket2_3"},
            {"bracket": 5, "bracket_id": 4, "expected": "Bracket5_4"}
        ]
        
        for case in test_cases:
            # Mock the necessary methods
            self.mock_automator._ensure_logged_in.return_value = True
            self.mock_automator.search_address.return_value = True
            self.mock_automator.get_market_cap.return_value = 50000
            
            mock_driver = Mock()
            self.mock_driver_manager.get_driver.return_value = mock_driver
            
            with patch.object(self.order_placer, '_navigate_to_buy_interface', return_value=True), \
                 patch.object(self.order_placer, '_enter_order_amount', return_value=True), \
                 patch.object(self.order_placer, '_place_market_order', return_value=True), \
                 patch.object(self.order_placer, '_configure_auto_sell_strategy', return_value=True) as mock_config, \
                 patch.object(self.order_placer, '_confirm_order', return_value=True), \
                 patch('bracket_order_placement.db_manager') as mock_db:
                
                mock_db.create_order_with_coin.return_value = {"order_id": 1}
                
                result = self.order_placer._place_single_bracket_order(
                    profile_name=self.test_profile,
                    address=self.test_address,
                    bracket=case["bracket"],
                    bracket_id=case["bracket_id"],
                    current_market_cap=50000,
                    entry_market_cap=100000,
                    take_profit_market_cap=150000,
                    stop_loss_market_cap=30000,
                    amount=250.0,
                    strategy_number=1
                )
                
                # Verify strategy name was passed correctly
                mock_config.assert_called_once()
                args = mock_config.call_args[0]
                strategy_name = args[1]  # Second argument is strategy_name
                self.assertEqual(strategy_name, case["expected"])
    
    def test_bracket_order_manager_preview(self):
        """Test the bracket order manager preview functionality"""
        
        manager = BracketOrderManager()
        
        # Mock the automator in the manager
        with patch.object(manager.order_placer, 'automator') as mock_automator:
            mock_automator.search_address.return_value = True
            mock_automator.get_market_cap.return_value = 100000  # Bracket 1
            
            preview = manager.get_bracket_preview(
                address=self.test_address,
                total_amount=self.test_amount,
                profile_name=self.test_profile
            )
            
            self.assertTrue(preview["success"])
            self.assertEqual(preview["bracket"], 1)
            self.assertEqual(preview["current_market_cap"], 100000)
            self.assertEqual(preview["total_amount"], self.test_amount)
            self.assertEqual(len(preview["orders"]), 4)
            
            # Check that order types are determined correctly
            for order in preview["orders"]:
                self.assertIn("order_type", order)
                self.assertIn("strategy_name", order)
                self.assertTrue(order["strategy_name"].startswith("Bracket1_"))
    
    def test_error_handling(self):
        """Test error handling in various scenarios"""
        
        # Test login failure
        self.mock_automator._ensure_logged_in.return_value = False
        
        result = self.order_placer.place_bracket_orders(
            profile_name=self.test_profile,
            address=self.test_address,
            total_amount=self.test_amount
        )
        
        self.assertFalse(result["success"])
        self.assertIn("Failed to login", result["error"])
        
        # Test search failure
        self.mock_automator._ensure_logged_in.return_value = True
        self.mock_automator.search_address.return_value = False
        
        result = self.order_placer.place_bracket_orders(
            profile_name=self.test_profile,
            address=self.test_address,
            total_amount=self.test_amount
        )
        
        self.assertFalse(result["success"])
        self.assertIn("Failed to search address", result["error"])
        
        # Test market cap retrieval failure
        self.mock_automator.search_address.return_value = True
        self.mock_automator.get_market_cap.return_value = 0
        
        result = self.order_placer.place_bracket_orders(
            profile_name=self.test_profile,
            address=self.test_address,
            total_amount=self.test_amount
        )
        
        self.assertFalse(result["success"])
        self.assertIn("Failed to get market cap", result["error"])
    
    def test_order_replacement(self):
        """Test order replacement functionality"""
        
        # Mock successful search and market cap retrieval
        self.mock_automator.search_address.return_value = True
        self.mock_automator.get_market_cap.return_value = 100000
        
        mock_driver = Mock()
        self.mock_driver_manager.get_driver.return_value = mock_driver
        
        with patch.object(self.order_placer, '_navigate_to_buy_interface', return_value=True), \
             patch.object(self.order_placer, '_enter_order_amount', return_value=True), \
             patch.object(self.order_placer, '_place_market_order', return_value=True), \
             patch.object(self.order_placer, '_configure_auto_sell_strategy', return_value=True), \
             patch.object(self.order_placer, '_confirm_order', return_value=True), \
             patch('bracket_order_placement.db_manager') as mock_db:
            
            mock_db.create_order_with_coin.return_value = {"order_id": 1}
            
            result = self.order_placer.replace_bracket_order(
                profile_name=self.test_profile,
                address=self.test_address,
                bracket_id=2,
                new_amount=500.0,
                strategy_number=1
            )
            
            self.assertTrue(result["success"])
            self.assertEqual(result["order"]["bracket_id"], 2)
            self.assertEqual(result["order"]["amount"], 500.0)
    
    def test_full_bracket_strategy_execution(self):
        """Test full bracket strategy execution"""
        
        # Mock all necessary methods for successful execution
        self.mock_automator._ensure_logged_in.return_value = True
        self.mock_automator.search_address.return_value = True
        self.mock_automator.get_market_cap.return_value = 100000  # Bracket 1
        
        mock_driver = Mock()
        self.mock_driver_manager.get_driver.return_value = mock_driver
        
        with patch.object(self.order_placer, '_navigate_to_buy_interface', return_value=True), \
             patch.object(self.order_placer, '_enter_order_amount', return_value=True), \
             patch.object(self.order_placer, '_place_market_order', return_value=True), \
             patch.object(self.order_placer, '_configure_auto_sell_strategy', return_value=True), \
             patch.object(self.order_placer, '_confirm_order', return_value=True), \
             patch('bracket_order_placement.db_manager') as mock_db:
            
            mock_db.create_order_with_coin.return_value = {"order_id": 1}
            
            result = self.order_placer.place_bracket_orders(
                profile_name=self.test_profile,
                address=self.test_address,
                total_amount=self.test_amount,
                strategy_number=1
            )
            
            self.assertTrue(result["success"])
            self.assertEqual(result["bracket"], 1)
            self.assertEqual(result["current_market_cap"], 100000)
            self.assertEqual(result["total_placed"], 4)
            self.assertEqual(result["total_failed"], 0)
            self.assertEqual(len(result["placed_orders"]), 4)
            
            # Verify all bracket IDs are present
            bracket_ids = [order["bracket_id"] for order in result["placed_orders"]]
            self.assertEqual(sorted(bracket_ids), [1, 2, 3, 4])


class TestBracketConfiguration(unittest.TestCase):
    """Test bracket configuration functionality"""
    
    def test_bracket_ranges(self):
        """Test that bracket ranges are correctly defined"""
        from bracket_config import BRACKET_RANGES
        
        # Should have 5 brackets
        self.assertEqual(len(BRACKET_RANGES), 5)
        
        # Each bracket should have min and max
        for bracket_id, range_info in BRACKET_RANGES.items():
            self.assertIn("min", range_info)
            self.assertIn("max", range_info)
            self.assertLess(range_info["min"], range_info["max"])
    
    def test_trade_sizes_sum_to_one(self):
        """Test that trade sizes sum to approximately 1.0"""
        from bracket_config import TRADE_SIZES
        
        total = sum(TRADE_SIZES)
        self.assertAlmostEqual(total, 1.0, places=3)
        self.assertEqual(len(TRADE_SIZES), 4)  # Should have 4 trade sizes
    
    def test_bracket_config_completeness(self):
        """Test that bracket configuration is complete"""
        from bracket_config import BRACKET_CONFIG
        
        # Should have configurations for brackets 1-5
        for bracket in range(1, 6):
            self.assertIn(bracket, BRACKET_CONFIG)
            
            config = BRACKET_CONFIG[bracket]
            self.assertIn("stop_loss_market_cap", config)
            self.assertIn("entries", config)
            self.assertIn("description", config)
            
            # Should have 4 entry points
            self.assertEqual(len(config["entries"]), 4)


if __name__ == "__main__":
    # Create a test suite
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTest(unittest.makeSuite(TestBracketOrderPlacement))
    suite.addTest(unittest.makeSuite(TestBracketConfiguration))
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"Test Summary:")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.failures:
        print(f"\nFailures:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
    
    if result.errors:
        print(f"\nErrors:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
    
    if result.wasSuccessful():
        print(f"\n✅ All tests passed!")
    else:
        print(f"\n❌ Some tests failed!")
    
    print(f"{'='*60}")
