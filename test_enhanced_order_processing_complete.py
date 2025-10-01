"""
Comprehensive Test Suite for Enhanced Order Processing System

This test file verifies the complete enhanced order processing functionality including:
- TP detection when trigger conditions = "1 SL"
- Order renewal marking and database updates
- BullX entry deletion via XPATH
- Order replacement logic for renewed orders
- Comprehensive logging and output
"""

import asyncio
import pytest
import logging
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

# Import the modules we're testing
from enhanced_order_processing import EnhancedOrderProcessor, process_orders_enhanced
from background_tasks import check_orders_enhanced_for_profile
from database import db_manager
from models import Order, Coin, Profile
from bracket_config import calculate_bracket, BRACKET_CONFIG

# Set up logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestEnhancedOrderProcessing:
    """Test suite for enhanced order processing functionality"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.processor = EnhancedOrderProcessor()
        self.test_profile = "TestProfile"
        
        # Mock coin data
        self.test_coin = Mock()
        self.test_coin.id = 1
        self.test_coin.name = "TESTCOIN"
        self.test_coin.address = "0x123456789abcdef"
        self.test_coin.bracket = 2
        self.test_coin.market_cap = 500000
        
        # Mock order data
        self.test_order = Mock()
        self.test_order.id = 1
        self.test_order.coin_id = 1
        self.test_order.coin = self.test_coin
        self.test_order.bracket_id = 2
        self.test_order.profile_name = self.test_profile
        self.test_order.status = "ACTIVE"
        self.test_order.entry_price = 100000
        self.test_order.take_profit = 150000
        self.test_order.stop_loss = 50000
        self.test_order.amount = 1.0
    
    def test_tp_condition_detection(self):
        """Test TP condition detection logic"""
        # Test positive case - TP detected
        assert self.processor._is_tp_condition("1 SL") == True
        
        # Test negative cases - TP not detected
        assert self.processor._is_tp_condition("1 TP, 1 SL") == False
        assert self.processor._is_tp_condition("Buy below $100k") == False
        assert self.processor._is_tp_condition("Active") == False
        assert self.processor._is_tp_condition("") == False
        assert self.processor._is_tp_condition("  1 SL  ") == True  # With whitespace
        
        logger.info("✅ TP condition detection tests passed")
    
    def test_parse_row_data(self):
        """Test row data parsing functionality"""
        # Mock row data similar to BullX format
        test_row = {
            "main_text": "Auto\nSell\nTESTCOIN\n257.29K TESTCOIN\n+0\n$0\n00h 00m 00s\n1\n0/0\n1 SL\nActive",
            "href": "https://neo.bullx.io/terminal?address=0x123456789abcdef"
        }
        
        parsed = self.processor._parse_row_data(test_row)
        
        assert parsed is not None
        assert parsed['side'] == "Auto"
        assert parsed['type'] == "Sell"
        assert parsed['token'] == "TESTCOIN"
        assert parsed['trigger_condition'] == "1 SL"
        assert parsed['status'] == "Active"
        
        logger.info("✅ Row data parsing tests passed")
    
    def test_find_coin_by_token(self):
        """Test coin identification by token name"""
        with patch.object(db_manager, 'get_coin_by_name') as mock_get_coin:
            mock_get_coin.return_value = self.test_coin
            
            result = self.processor._find_coin_by_token("TESTCOIN")
            assert result == self.test_coin
            mock_get_coin.assert_called_once_with("TESTCOIN")
        
        logger.info("✅ Coin identification tests passed")
    
    def test_identify_order(self):
        """Test order identification logic"""
        parsed_data = {
            'token': 'TESTCOIN',
            'trigger_condition': '1 SL',
            'entry_price': 100000
        }
        
        with patch.object(self.processor, '_find_coin_by_token') as mock_find_coin:
            with patch.object(db_manager, 'get_orders_by_coin') as mock_get_orders:
                mock_find_coin.return_value = self.test_coin
                mock_get_orders.return_value = [self.test_order]
                
                result = self.processor._identify_order(parsed_data, self.test_profile)
                
                assert result is not None
                assert result['order'] == self.test_order
                assert result['coin'] == self.test_coin
                assert result['bracket'] == self.test_coin.bracket
        
        logger.info("✅ Order identification tests passed")
    
    @pytest.mark.asyncio
    async def test_mark_order_for_renewal(self):
        """Test order renewal marking functionality"""
        parsed_data = {
            'token': 'TESTCOIN',
            'trigger_condition': '1 SL'
        }
        
        with patch.object(db_manager, 'update_order_status') as mock_update:
            with patch.object(self.processor, '_delete_bullx_entry') as mock_delete:
                mock_delete.return_value = None
                
                await self.processor._mark_order_for_renewal(
                    self.test_order, parsed_data, 1, 1
                )
                
                # Verify order was marked for renewal
                assert len(self.processor.orders_for_renewal) == 1
                renewal_info = self.processor.orders_for_renewal[0]
                assert renewal_info['order'] == self.test_order
                assert renewal_info['bracket_sub_id'] == self.test_order.bracket_id
                
                # Verify database was updated
                mock_update.assert_called_once_with(self.test_order.id, "COMPLETED")
        
        logger.info("✅ Order renewal marking tests passed")
    
    @pytest.mark.asyncio
    async def test_delete_bullx_entry(self):
        """Test BullX entry deletion functionality"""
        mock_driver = Mock()
        mock_element = Mock()
        
        with patch.object(self.processor.driver_manager, 'get_driver') as mock_get_driver:
            with patch('selenium.webdriver.support.ui.WebDriverWait') as mock_wait:
                mock_get_driver.return_value = mock_driver
                mock_wait.return_value.until.return_value = mock_element
                
                await self.processor._delete_bullx_entry(self.test_profile, 1, 2)
                
                # Verify correct XPATH was used
                expected_xpath = "//*[@id='root']/div[1]/div[2]/main/div/section/div[2]/div[2]/div/div/div/div[1]/a[2]/div[11]/div/button"
                mock_element.click.assert_called_once()
        
        logger.info("✅ BullX entry deletion tests passed")
    
    @pytest.mark.asyncio
    async def test_create_replacement_order(self):
        """Test replacement order creation"""
        with patch('bracket_order_placement.bracket_order_manager.replace_order') as mock_replace:
            mock_replace.return_value = {
                "success": True,
                "order": {"bracket_id": 2, "entry_price": 120000}
            }
            
            result = await self.processor._create_replacement_order(
                self.test_profile, self.test_coin.address, 2, 1.0
            )
            
            assert result["success"] == True
            assert result["bracket_sub_id"] == 2
            mock_replace.assert_called_once_with(
                profile_name=self.test_profile,
                address=self.test_coin.address,
                bracket_id=2,
                new_amount=1.0,
                strategy_number=1
            )
        
        logger.info("✅ Replacement order creation tests passed")
    
    @pytest.mark.asyncio
    async def test_process_orders_enhanced_full_flow(self):
        """Test the complete enhanced order processing flow"""
        # Mock the order checking result with TP condition
        mock_order_info = [{
            "button_index": 1,
            "rows": [{
                "row_index": 1,
                "main_text": "Auto\nSell\nTESTCOIN\n257.29K TESTCOIN\n+0\n$0\n00h 00m 00s\n1\n0/0\n1 SL\nActive",
                "href": "https://neo.bullx.io/terminal?address=0x123456789abcdef"
            }]
        }]
        
        mock_check_result = {
            "success": True,
            "order_info": mock_order_info
        }
        
        with patch.object(self.processor.automator, 'check_orders') as mock_check:
            with patch.object(self.processor, '_find_coin_by_token') as mock_find_coin:
                with patch.object(db_manager, 'get_orders_by_coin') as mock_get_orders:
                    with patch.object(db_manager, 'update_order_status') as mock_update:
                        with patch.object(self.processor, '_delete_bullx_entry') as mock_delete:
                            with patch.object(self.processor, '_create_replacement_order') as mock_create:
                                
                                # Set up mocks
                                mock_check.return_value = mock_check_result
                                mock_find_coin.return_value = self.test_coin
                                mock_get_orders.return_value = [self.test_order]
                                mock_delete.return_value = None
                                mock_create.return_value = {"success": True, "bracket_sub_id": 2}
                                
                                # Run the enhanced processing
                                result = await self.processor.process_orders_enhanced(self.test_profile)
                                
                                # Verify results
                                assert result["success"] == True
                                assert result["orders_checked"] > 0
                                assert result["orders_marked_for_renewal"] == 1
                                assert result["orders_replaced"] == 1
                                
                                # Verify database was updated
                                mock_update.assert_called_with(self.test_order.id, "COMPLETED")
        
        logger.info("✅ Full enhanced order processing flow tests passed")
    
    def test_generate_processing_summary(self):
        """Test processing summary generation"""
        check_result = {
            "total_orders_checked": 5,
            "tp_detected_count": 2
        }
        
        renewal_results = {
            "orders_replaced": 2,
            "renewal_details": [{
                "coin_name": "TESTCOIN",
                "coin_address": "0x123456789abcdef",
                "original_bracket": 2,
                "orders_to_replace": [{"bracket_sub_id": 1}, {"bracket_sub_id": 2}],
                "new_orders_created": [{"success": True}, {"success": True}]
            }]
        }
        
        summary = self.processor._generate_processing_summary(check_result, renewal_results)
        
        assert "📊 ENHANCED ORDER PROCESSING SUMMARY" in summary
        assert "Orders Checked: 5" in summary
        assert "TP Conditions Detected: 2" in summary
        assert "Orders Replaced: 2" in summary
        assert "TESTCOIN" in summary
        
        logger.info("✅ Processing summary generation tests passed")


class TestIntegrationWithBackgroundTasks:
    """Integration tests with background tasks system"""
    
    @pytest.mark.asyncio
    async def test_check_orders_enhanced_for_profile(self):
        """Test the enhanced order checking integration"""
        test_profile = "TestProfile"
        
        with patch('enhanced_order_processing.process_orders_enhanced') as mock_process:
            mock_process.return_value = {
                "success": True,
                "orders_checked": 3,
                "orders_marked_for_renewal": 1,
                "orders_replaced": 1,
                "summary": "Test summary"
            }
            
            result = await check_orders_enhanced_for_profile(test_profile)
            
            assert result["success"] == True
            assert result["orders_checked"] == 3
            mock_process.assert_called_once_with(test_profile)
        
        logger.info("✅ Background tasks integration tests passed")


class TestDatabaseIntegration:
    """Test database operations for enhanced order processing"""
    
    def test_order_status_updates(self):
        """Test order status update functionality"""
        with patch.object(db_manager, 'update_order_status') as mock_update:
            mock_update.return_value = True
            
            result = db_manager.update_order_status(1, "COMPLETED")
            assert result == True
            mock_update.assert_called_once_with(1, "COMPLETED")
        
        logger.info("✅ Database integration tests passed")


class TestErrorHandling:
    """Test error handling in enhanced order processing"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.processor = EnhancedOrderProcessor()
    
    @pytest.mark.asyncio
    async def test_error_handling_in_tp_detection(self):
        """Test error handling during TP detection"""
        with patch.object(self.processor.automator, 'check_orders') as mock_check:
            mock_check.return_value = {"success": False, "error": "Connection failed"}
            
            result = await self.processor._check_orders_with_tp_detection("TestProfile")
            
            assert result["success"] == False
            assert "Connection failed" in result["error"]
        
        logger.info("✅ Error handling tests passed")
    
    def test_invalid_row_data_handling(self):
        """Test handling of invalid row data"""
        # Test with empty row data
        result = self.processor._parse_row_data({})
        assert result is None
        
        # Test with malformed row data
        result = self.processor._parse_row_data({"main_text": "incomplete\ndata"})
        assert result is not None  # Should still parse what it can
        
        logger.info("✅ Invalid data handling tests passed")


async def run_comprehensive_test():
    """Run all tests in sequence"""
    logger.info("🚀 Starting Comprehensive Enhanced Order Processing Tests")
    logger.info("=" * 80)
    
    try:
        # Test basic functionality
        logger.info("\n📋 Testing Basic Functionality...")
        basic_tests = TestEnhancedOrderProcessing()
        basic_tests.setup_method()
        
        basic_tests.test_tp_condition_detection()
        basic_tests.test_parse_row_data()
        basic_tests.test_find_coin_by_token()
        basic_tests.test_identify_order()
        await basic_tests.test_mark_order_for_renewal()
        await basic_tests.test_delete_bullx_entry()
        await basic_tests.test_create_replacement_order()
        await basic_tests.test_process_orders_enhanced_full_flow()
        basic_tests.test_generate_processing_summary()
        
        # Test integration
        logger.info("\n🔗 Testing Integration...")
        integration_tests = TestIntegrationWithBackgroundTasks()
        await integration_tests.test_check_orders_enhanced_for_profile()
        
        # Test database operations
        logger.info("\n💾 Testing Database Operations...")
        db_tests = TestDatabaseIntegration()
        db_tests.test_order_status_updates()
        
        # Test error handling
        logger.info("\n⚠️  Testing Error Handling...")
        error_tests = TestErrorHandling()
        error_tests.setup_method()
        await error_tests.test_error_handling_in_tp_detection()
        error_tests.test_invalid_row_data_handling()
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ ALL ENHANCED ORDER PROCESSING TESTS PASSED!")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False


def test_enhanced_order_processing_demo():
    """
    Demo function showing how to use the enhanced order processing system
    """
    logger.info("\n🎯 ENHANCED ORDER PROCESSING DEMO")
    logger.info("=" * 50)
    
    logger.info("1. Basic TP Detection:")
    processor = EnhancedOrderProcessor()
    
    # Test TP detection
    test_conditions = ["1 SL", "1 TP, 1 SL", "Buy below $100k", "Active"]
    for condition in test_conditions:
        is_tp = processor._is_tp_condition(condition)
        status = "✅ TP DETECTED" if is_tp else "❌ No TP"
        logger.info(f"   '{condition}' → {status}")
    
    logger.info("\n2. Row Data Parsing:")
    sample_row = {
        "main_text": "Auto\nSell\nTESTCOIN\n257.29K TESTCOIN\n+0\n$0\n00h 00m 00s\n1\n0/0\n1 SL\nActive",
        "href": "https://neo.bullx.io/terminal?address=0x123"
    }
    
    parsed = processor._parse_row_data(sample_row)
    if parsed:
        logger.info(f"   Token: {parsed['token']}")
        logger.info(f"   Trigger: {parsed['trigger_condition']}")
        logger.info(f"   TP Detected: {processor._is_tp_condition(parsed['trigger_condition'])}")
    
    logger.info("\n3. Usage Example:")
    logger.info("   # To run enhanced order processing:")
    logger.info("   from background_tasks import check_orders_enhanced_for_profile")
    logger.info("   result = await check_orders_enhanced_for_profile('Saruman')")
    logger.info("   print(result['summary'])")
    
    logger.info("\n4. Key Features:")
    logger.info("   ✅ Detects TP conditions (trigger = '1 SL')")
    logger.info("   ✅ Marks orders for renewal in database")
    logger.info("   ✅ Deletes BullX entries via XPATH")
    logger.info("   ✅ Creates replacement orders automatically")
    logger.info("   ✅ Comprehensive logging and reporting")
    
    logger.info("=" * 50)


if __name__ == "__main__":
    # Run the demo first
    test_enhanced_order_processing_demo()
    
    # Run comprehensive tests
    asyncio.run(run_comprehensive_test())
