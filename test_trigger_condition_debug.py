#!/usr/bin/env python3
"""
Debug script to check trigger_condition field and database updates
"""

from database import db_manager
from models import Order
from sqlalchemy import inspect
import sys

def check_database_schema():
    """Check if trigger_condition column exists"""
    print("🔍 Checking database schema...")
    
    try:
        engine = db_manager.SessionLocal().bind
        inspector = inspect(engine)
        columns = inspector.get_columns('orders')
        
        print(f"📋 Found {len(columns)} columns in orders table:")
        for col in columns:
            print(f"  - {col['name']}: {col['type']}")
        
        trigger_col = [col for col in columns if col['name'] == 'trigger_condition']
        
        if trigger_col:
            print(f"✅ trigger_condition column exists: {trigger_col[0]}")
            return True
        else:
            print("❌ trigger_condition column NOT found")
            return False
            
    except Exception as e:
        print(f"💥 Error checking schema: {e}")
        return False

def check_active_orders():
    """Check current orders and their trigger conditions"""
    print("\n🔍 Checking active orders...")
    
    try:
        orders = db_manager.get_active_orders()
        print(f"📋 Found {len(orders)} active orders:")
        
        for order in orders:
            trigger = order.trigger_condition if hasattr(order, 'trigger_condition') else 'NO ATTRIBUTE'
            print(f"  Order {order.id}: trigger_condition = '{trigger}' | updated_at = {order.updated_at}")
            
        return len(orders)
        
    except Exception as e:
        print(f"💥 Error checking orders: {e}")
        return 0

def test_trigger_update():
    """Test updating trigger condition"""
    print("\n🧪 Testing trigger condition update...")
    
    try:
        orders = db_manager.get_active_orders()
        if not orders:
            print("❌ No active orders to test with")
            return False
        
        test_order = orders[0]
        original_trigger = test_order.trigger_condition if hasattr(test_order, 'trigger_condition') else None
        test_trigger = "TEST: 1 TP, 1 SL"
        
        print(f"📝 Testing with Order {test_order.id}")
        print(f"   Original trigger: '{original_trigger}'")
        print(f"   Test trigger: '{test_trigger}'")
        
        # Test the update
        success = db_manager.update_order_trigger_condition(test_order.id, test_trigger)
        
        if success:
            print("✅ Update method returned success")
            
            # Verify the update
            updated_order = db_manager.get_order_with_coin(test_order.id)
            if updated_order and hasattr(updated_order, 'trigger_condition'):
                actual_trigger = updated_order.trigger_condition
                print(f"   Verified trigger: '{actual_trigger}'")
                
                if actual_trigger == test_trigger:
                    print("✅ Trigger condition successfully updated!")
                    
                    # Restore original
                    if original_trigger:
                        db_manager.update_order_trigger_condition(test_order.id, original_trigger)
                        print(f"🔄 Restored original trigger: '{original_trigger}'")
                    
                    return True
                else:
                    print(f"❌ Trigger not updated correctly. Expected: '{test_trigger}', Got: '{actual_trigger}'")
            else:
                print("❌ Could not verify update - order not found or no trigger_condition attribute")
        else:
            print("❌ Update method returned failure")
            
        return False
        
    except Exception as e:
        print(f"💥 Error testing trigger update: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("🚀 TRIGGER CONDITION DEBUG SCRIPT")
    print("=" * 50)
    
    # Check schema
    schema_ok = check_database_schema()
    
    # Check orders
    order_count = check_active_orders()
    
    # Test update if schema is OK
    if schema_ok and order_count > 0:
        update_ok = test_trigger_update()
        
        print(f"\n📊 SUMMARY:")
        print(f"  Schema OK: {schema_ok}")
        print(f"  Active Orders: {order_count}")
        print(f"  Update Test: {update_ok}")
        
        if not update_ok:
            print("\n🚨 ISSUE DETECTED: Trigger condition updates are not working properly!")
            print("   This explains why SAMAI trigger conditions are not being updated.")
        else:
            print("\n✅ All tests passed - trigger condition updates should work.")
    else:
        print(f"\n❌ Cannot run full tests - Schema OK: {schema_ok}, Orders: {order_count}")

if __name__ == "__main__":
    main()
