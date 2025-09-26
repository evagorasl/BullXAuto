#!/usr/bin/env python3
"""
Test script to verify bracket calculation fallback when no bracket is stored for a coin
"""

import asyncio
import logging
from background_tasks import OrderMonitor
from database import db_manager, create_tables
from models import Coin, Order

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_test_coin_without_bracket():
    """Set up test coin without bracket but with market_cap"""
    try:
        # Create tables
        create_tables()
        
        # Create test coin WITHOUT bracket but WITH market_cap
        test_coin = db_manager.create_or_update_coin(
            address="0x999test",
            data={
                "name": "NOBRACKETCOIN",
                "market_cap": 750000,  # This should be bracket 2
                # Note: NO bracket field provided
                "current_price": 0.002
            }
        )
        
        logger.info(f"Created coin without bracket: {test_coin.name} (ID: {test_coin.id})")
        logger.info(f"Market cap: ${test_coin.market_cap:,.0f}, Bracket: {test_coin.bracket}")
        
        return test_coin
        
    except Exception as e:
        logger.error(f"Error setting up test data: {e}")
        return None

def create_test_order_info():
    """Create test order info for coin without bracket"""
    return [
        {
            "button_index": 1,
            "rows": [
                {
                    "main_text": "B\nAuto Buy\nNOBRACKETCOIN\n150.0\n$75.00\n$0.001\n08h 45m 30s\nWallet1\n2\nBuy below $131k\nActive",
                    "href": "https://bullx.io/order/999"
                }
            ]
        }
    ]

async def test_bracket_calculation_fallback():
    """Test that bracket is calculated from market_cap when not stored"""
    try:
        logger.info("=== Testing Bracket Calculation Fallback ===")
        
        # Set up test coin without bracket
        test_coin = setup_test_coin_without_bracket()
        if not test_coin:
            logger.error("Failed to set up test coin")
            return
        
        # Verify coin has no bracket initially
        logger.info(f"Initial coin state - Bracket: {test_coin.bracket}, Market Cap: ${test_coin.market_cap:,.0f}")
        
        # Create test order info
        test_order_info = create_test_order_info()
        
        # Create OrderMonitor instance
        order_monitor = OrderMonitor()
        
        # Process the order information - this should trigger bracket calculation
        await order_monitor.process_order_information("Saruman", test_order_info)
        
        # Check if bracket was calculated and stored
        updated_coin = db_manager.get_coin_by_address("0x999test")
        logger.info(f"After processing - Bracket: {updated_coin.bracket}, Market Cap: ${updated_coin.market_cap:,.0f}")
        
        if updated_coin.bracket:
            logger.info("✅ SUCCESS: Bracket was calculated and stored from market_cap")
        else:
            logger.error("❌ FAILED: Bracket was not calculated")
        
        logger.info("=== Test completed ===")
        
    except Exception as e:
        logger.error(f"Error in test: {e}")

async def main():
    """Main test function"""
    await test_bracket_calculation_fallback()

if __name__ == "__main__":
    asyncio.run(main())
