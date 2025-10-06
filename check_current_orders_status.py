#!/usr/bin/env python3
"""
Check current status of all orders and their trigger conditions
"""

from database import db_manager
from datetime import datetime, timedelta

def check_orders_status():
    """Check current status of all orders"""
    try:
        print("🔍 CHECKING CURRENT ORDERS STATUS")
        print("=" * 50)
        
        # Get all active orders
        active_orders = db_manager.get_active_orders()
        print(f"📋 Found {len(active_orders)} active orders")
        
        if not active_orders:
            print("❌ No active orders found")
            return
        
        # Group by coin
        orders_by_coin = {}
        for order in active_orders:
            try:
                # Get coin info safely
                coin_name = "Unknown"
                coin_address = "Unknown"
                
                if hasattr(order, 'coin') and order.coin:
                    coin_name = order.coin.name or "Unknown"
                    coin_address = order.coin.address or "Unknown"
                elif order.coin_id:
                    # Try to get coin by ID
                    from database import SessionLocal
                    from models import Coin
                    db = SessionLocal()
                    try:
                        coin = db.query(Coin).filter(Coin.id == order.coin_id).first()
                        if coin:
                            coin_name = coin.name or "Unknown"
                            coin_address = coin.address or "Unknown"
                    finally:
                        db.close()
                
                coin_key = f"{coin_name} ({coin_address})"
                if coin_key not in orders_by_coin:
                    orders_by_coin[coin_key] = []
                orders_by_coin[coin_key].append(order)
                
            except Exception as e:
                print(f"⚠️  Error processing order {order.id}: {e}")
        
        # Display orders by coin
        current_time = datetime.now()
        recent_threshold = current_time - timedelta(hours=1)  # Last hour
        
        for coin_key, orders in orders_by_coin.items():
            print(f"\n🪙 {coin_key}:")
            
            for order in sorted(orders, key=lambda x: x.bracket_id):
                trigger = order.trigger_condition or "None"
                updated_at = order.updated_at
                
                # Check if recently updated
                is_recent = updated_at and updated_at > recent_threshold
                recent_indicator = "🔥" if is_recent else "  "
                
                print(f"   {recent_indicator} Order {order.id} (Bracket {order.bracket_id}):")
                print(f"      Trigger: '{trigger}'")
                print(f"      Updated: {updated_at}")
                print(f"      Profile: {order.profile_name}")
        
        # Summary
        total_with_triggers = sum(1 for order in active_orders if order.trigger_condition and order.trigger_condition != "None")
        total_recently_updated = sum(1 for order in active_orders if order.updated_at and order.updated_at > recent_threshold)
        
        print(f"\n📊 SUMMARY:")
        print(f"   Total active orders: {len(active_orders)}")
        print(f"   Orders with trigger conditions: {total_with_triggers}")
        print(f"   Orders updated in last hour: {total_recently_updated}")
        
        if total_with_triggers == 0:
            print(f"\n🚨 ISSUE: No orders have trigger conditions set!")
            print(f"   This suggests the enhanced order processing hasn't run yet")
            print(f"   or there's an issue with order identification.")
        elif total_recently_updated > 0:
            print(f"\n✅ Good: {total_recently_updated} orders were updated recently")
        else:
            print(f"\n⚠️  Warning: No orders updated recently")
            print(f"   The background monitoring might not be running")
        
    except Exception as e:
        print(f"💥 Error checking orders: {e}")
        import traceback
        traceback.print_exc()

def check_samai_specifically():
    """Check SAMAI orders specifically"""
    try:
        print(f"\n🔍 CHECKING SAMAI ORDERS SPECIFICALLY")
        print("=" * 40)
        
        # Get all coins
        all_coins = db_manager.get_all_coins()
        samai_coins = [coin for coin in all_coins if coin.name and "SAMAI" in coin.name.upper()]
        
        if not samai_coins:
            print("❌ No SAMAI coins found in database")
            return
        
        for coin in samai_coins:
            print(f"\n🪙 SAMAI Coin: {coin.name} ({coin.address})")
            print(f"   Bracket: {coin.bracket}")
            print(f"   Market Cap: ${coin.market_cap:,.0f}" if coin.market_cap else "   Market Cap: Unknown")
            
            # Get orders for this coin
            orders = db_manager.get_orders_by_coin(coin.id)
            active_orders = [o for o in orders if o.status == "ACTIVE"]
            
            print(f"   Active Orders: {len(active_orders)}")
            
            for order in active_orders:
                trigger = order.trigger_condition or "None"
                print(f"      Order {order.id} (Bracket {order.bracket_id}): '{trigger}' | Updated: {order.updated_at}")
        
    except Exception as e:
        print(f"💥 Error checking SAMAI: {e}")

if __name__ == "__main__":
    check_orders_status()
    check_samai_specifically()
