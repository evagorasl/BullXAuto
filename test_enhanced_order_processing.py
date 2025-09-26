#!/usr/bin/env python3
"""
Test script for the enhanced process_order_information function
This demonstrates how the function parses, identifies, and reports on order data
"""

import asyncio
import logging
from background_tasks import OrderMonitor
from database import db_manager, create_tables
from models import Coin, Order

# Set up logging to see the detailed output
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_test_data():
    """Set up test data in the database"""
    try:
        # Create tables
        create_tables()
        
        # Create test coins with brackets
        test_coin_1 = db_manager.create_or_update_coin(
            address="0x123abc",
            data={
                "name": "TESTCOIN",
                "market_cap": 500000,  # This will be bracket 2
                "bracket": 2,
                "current_price": 0.001
            }
        )
        
        test_coin_2 = db_manager.create_or_update_coin(
            address="0x456def", 
            data={
                "name": "ANOTHERCOIN",
                "market_cap": 50000,  # This will be bracket 1
                "bracket": 1,
                "current_price": 0.0005
            }
        )
        
        # Create test orders for the coins
        # For TESTCOIN (bracket 2), create orders with bracket 2 entries
        test_orders = [
            {
                "coin_id": test_coin_1.id,
                "strategy_number": 1,
                "order_type": "BUY",
                "bracket_id": 1,
                "market_cap": 500000,
                "entry_price": 93100,  # Bracket 2, entry 1
                "take_profit": 104272,
                "stop_loss": 78000,
                "amount": 100.0,
                "profile_name": "Saruman",
                "status": "ACTIVE"
            },
            {
                "coin_id": test_coin_1.id,
                "strategy_number": 1,
                "order_type": "BUY", 
                "bracket_id": 2,
                "market_cap": 500000,
                "entry_price": 131000,  # Bracket 2, entry 2
                "take_profit": 116590,
                "stop_loss": 78000,
                "amount": 100.0,
                "profile_name": "Saruman",
                "status": "ACTIVE"
            },
            {
                "coin_id": test_coin_1.id,
                "strategy_number": 1,
                "order_type": "BUY",
                "bracket_id": 3,
                "market_cap": 500000,
                "entry_price": 231000,  # Bracket 2, entry 3
                "take_profit": 187110,
                "stop_loss": 78000,
                "amount": 50.0,
                "profile_name": "Saruman",
                "status": "ACTIVE"
            }
        ]
        
        for order_data in test_orders:
            db_manager.create_order(order_data)
        
        logger.info("Test data setup complete")
        logger.info(f"Created coin: {test_coin_1.name} (ID: {test_coin_1.id}, Bracket: {test_coin_1.bracket})")
        logger.info(f"Created coin: {test_coin_2.name} (ID: {test_coin_2.id}, Bracket: {test_coin_2.bracket})")
        logger.info(f"Created {len(test_orders)} test orders")
        
        return test_coin_1, test_coin_2
        
    except Exception as e:
        logger.error(f"Error setting up test data: {e}")
        return None, None

def create_sample_order_info():
    """Create sample order_info data that simulates what would come from BullX automation page"""
    
    # This simulates the real structure with 11 columns: side, type, token, amount, cost, avg exec, expiry, wallets, transactions, trigger condition, status
    # Side: "S" or "B", Type: "Auto Sell" or "Buy Limit", etc.
    sample_order_info = [
        {
            "button_index": 1,
            "rows": [
                {
                    "main_text": "B\nAuto Buy\nTESTCOIN\n100.0\n$50.00\n$0.0005\n12h 30m 15s\nWallet1\n5\nBuy below $131k\nActive",
                    "href": "https://bullx.io/order/123"
                },
                {
                    "main_text": "S\nAuto Sell\nTESTCOIN\n50.0 TESTCOIN\n$25.00\n$0.0005\n00h 00m 00s\nWallet1\n3\n1 TP, 1 SL\nCompleted",
                    "href": "https://bullx.io/order/124"
                },
                {
                    "main_text": "B\nBuy Limit\nTESTCOIN\n75.0\n$37.50\n$0.0005\n00h 00m 00s\nWallet1\n4\nBuy below $231k\nExpired",
                    "href": "https://bullx.io/order/125"
                },
                {
                    "main_text": "S\nAuto Sell\nANOTHERCOIN\n200.0\n$100.00\n$0.0005\n05h 15m 30s\nWallet2\n2\nBuy below $13.1k\nActive",
                    "href": "https://bullx.io/order/126"
                }
            ]
        }
    ]
    
    return sample_order_info

async def test_enhanced_processing():
    """Test the enhanced order processing function"""
    try:
        logger.info("=== Starting Enhanced Order Processing Test ===")
        
        # Set up test data
        test_coin_1, test_coin_2 = setup_test_data()
        if not test_coin_1 or not test_coin_2:
            logger.error("Failed to set up test data")
            return
        
        # Create sample order info
        sample_order_info = create_sample_order_info()
        
        # Create OrderMonitor instance
        order_monitor = OrderMonitor()
        
        # Process the sample order information
        await order_monitor.process_order_information("Saruman", sample_order_info)
        
        logger.info("=== Test completed successfully ===")
        
    except Exception as e:
        logger.error(f"Error in test: {e}")

async def main():
    """Main test function"""
    await test_enhanced_processing()

if __name__ == "__main__":
    asyncio.run(main())
