#!/usr/bin/env python3
"""
Test script to simulate SAMAI trigger condition update from entry to TP
"""

from database import db_manager
from enhanced_order_processing import enhanced_order_processor
from models import Order, Coin
import asyncio

def create_test_samai_order():
    """Create a test SAMAI order with entry trigger condition"""
    try:
        print("🧪 Creating test SAMAI order...")
        
        # Create or get SAMAI coin
        coin = db_manager.create_or_update_coin(
            address="test_samai_address",
            data={
                "name": "SAMAI",
                "bracket": 2,  # Example bracket
                "market_cap": 50000000  # 50M market cap
            }
        )
        
        # Create test order with entry trigger condition
        order_data = {
            "coin_id": coin.id,
            "strategy_number": 1,
            "order_type": "BUY_LIMIT",
            "bracket_id": 1,
            "market_cap": 50000000,
            "entry_price": 131000,
            "take_profit": 200000,
            "stop_loss": 25000000,
            "amount": 1.0,
            "profile_name": "Saruman",
            "status": "ACTIVE",
            "trigger_condition": "Buy below $131K"  # Initial entry condition
        }
        
        order = db_manager.create_order(order_data)
        print(f"✅ Created test order ID {order.id} with trigger: '{order.trigger_condition}'")
        
        return order, coin
        
    except Exception as e:
        print(f"💥 Error creating test order: {e}")
        return None, None

def simulate_bullx_data():
    """Simulate BullX data showing SAMAI with TP condition"""
    return {
        'token': 'SAMAI',
        'trigger_condition': '1 TP, 1 SL',  # Changed from entry to TP
        'expiry': '56h 42m 17s',  # Example expiry
        'side': 'Auto',
        'type': 'Sell',
        'order_amount': '1000 SAMAI',
        'cost': '+0',
        'avg_exec': '$0',
        'wallets': '1',
        'transactions': '0/0',
        'status': 'Active'
    }

async def test_trigger_condition_update():
    """Test the trigger condition update process"""
    try:
        print("🚀 TESTING SAMAI TRIGGER CONDITION UPDATE")
        print("=" * 50)
        
        # Step 1: Create test order
        order, coin = create_test_samai_order()
        if not order or not coin:
            print("❌ Failed to create test order")
            return
        
        print(f"\n📋 Initial state:")
        print(f"   Order ID: {order.id}")
        print(f"   Coin: {coin.name} ({coin.address})")
        print(f"   Trigger condition: '{order.trigger_condition}'")
        print(f"   Updated at: {order.updated_at}")
        
        # Step 2: Simulate BullX data with TP condition
        bullx_data = simulate_bullx_data()
        print(f"\n📡 Simulated BullX data:")
        print(f"   Token: {bullx_data['token']}")
        print(f"   Trigger: {bullx_data['trigger_condition']}")
        print(f"   Expiry: {bullx_data['expiry']}")
        
        # Step 3: Test order identification
        print(f"\n🔍 Testing order identification...")
        order_match = enhanced_order_processor._identify_order(bullx_data, "Saruman")
        
        if order_match and order_match.get('order'):
            matched_order = order_match['order']
            print(f"✅ Order identified successfully:")
            print(f"   Matched Order ID: {matched_order.id}")
            print(f"   Method: {order_match.get('identification_method', 'Unknown')}")
            
            # Step 4: Check if trigger condition was updated
            updated_order = db_manager.get_order_with_coin(matched_order.id)
            if updated_order:
                print(f"\n📝 After identification:")
                print(f"   Trigger condition: '{updated_order.trigger_condition}'")
                print(f"   Updated at: {updated_order.updated_at}")
                
                if updated_order.trigger_condition == bullx_data['trigger_condition']:
                    print("✅ Trigger condition successfully updated!")
                else:
                    print("❌ Trigger condition NOT updated")
                    print(f"   Expected: '{bullx_data['trigger_condition']}'")
                    print(f"   Actual: '{updated_order.trigger_condition}'")
            else:
                print("❌ Could not retrieve updated order")
        else:
            print("❌ Order identification failed")
            print("   This explains why SAMAI trigger conditions are not being updated")
        
        # Step 5: Cleanup
        print(f"\n🧹 Cleaning up test data...")
        db_manager.complete_order(order.id, "COMPLETED")
        print("✅ Test completed")
        
    except Exception as e:
        print(f"💥 Error in test: {e}")
        import traceback
        traceback.print_exc()

async def main():
    await test_trigger_condition_update()

if __name__ == "__main__":
    asyncio.run(main())
