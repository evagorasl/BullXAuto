"""
Check database orders and identify issues
"""
from database import db_manager, SessionLocal
from models import Order, Coin
from datetime import datetime

def check_database_orders():
    """Check database for order issues"""
    db = SessionLocal()
    try:
        # Get all orders for CODEC coin
        codec_coin = db.query(Coin).filter(Coin.name == "CODEC").first()
        if not codec_coin:
            print("❌ CODEC coin not found")
            return
        
        print(f"🪙 CODEC Coin (ID: {codec_coin.id}, Address: {codec_coin.address})")
        print(f"   Bracket: {codec_coin.bracket}")
        print()
        
        # Get all orders for this coin
        all_orders = db.query(Order).filter(Order.coin_id == codec_coin.id).order_by(Order.id).all()
        
        print(f"📊 Total Orders: {len(all_orders)}")
        print()
        
        # Group by status
        active_orders = [o for o in all_orders if o.status == "ACTIVE"]
        expired_orders = [o for o in all_orders if o.status == "EXPIRED"]
        completed_orders = [o for o in all_orders if o.status == "COMPLETED"]
        
        print(f"✅ Active Orders: {len(active_orders)}")
        print(f"⏰ Expired Orders: {len(expired_orders)}")
        print(f"✔️  Completed Orders: {len(completed_orders)}")
        print()
        
        # Show all orders
        print("📋 All Orders:")
        print("-" * 100)
        for order in all_orders:
            print(f"ID: {order.id:2d} | Bracket: {order.bracket_id} | Status: {order.status:10s} | "
                  f"Created: {order.created_at.strftime('%m/%d/%Y %H:%M:%S') if order.created_at else 'N/A':20s} | "
                  f"Entry: ${order.entry_price:,}")
        print("-" * 100)
        print()
        
        # Check for duplicate bracket IDs among ACTIVE orders
        active_bracket_ids = [o.bracket_id for o in active_orders]
        if len(active_bracket_ids) != len(set(active_bracket_ids)):
            print("⚠️  DUPLICATE BRACKET IDs DETECTED IN ACTIVE ORDERS!")
            from collections import Counter
            duplicates = [bid for bid, count in Counter(active_bracket_ids).items() if count > 1]
            print(f"   Duplicate bracket IDs: {duplicates}")
            print()
            
            for bid in duplicates:
                duplicate_orders = [o for o in active_orders if o.bracket_id == bid]
                print(f"   Bracket ID {bid} has {len(duplicate_orders)} active orders:")
                for o in duplicate_orders:
                    print(f"      - Order ID {o.id}, Created: {o.created_at}")
            print()
        
        # Check if orders 1-4 should be expired
        print("🔍 Checking Orders 1-4 (should be EXPIRED):")
        for i in range(1, 5):
            order = db.query(Order).filter(Order.id == i).first()
            if order:
                print(f"   Order {i}: Status = {order.status}")
            else:
                print(f"   Order {i}: Not found")
        print()
        
        # Check orders 5-6 (potential duplicates)
        print("🔍 Checking Orders 5-6 (potential duplicates):")
        for i in range(5, 7):
            order = db.query(Order).filter(Order.id == i).first()
            if order:
                print(f"   Order {i}: Status = {order.status}, Bracket = {order.bracket_id}, Created: {order.created_at}")
            else:
                print(f"   Order {i}: Not found")
        print()
        
        # Check new orders 7-10
        print("🔍 Checking Orders 7-10 (new renewal orders):")
        for i in range(7, 11):
            order = db.query(Order).filter(Order.id == i).first()
            if order:
                print(f"   Order {i}: Status = {order.status}, Bracket = {order.bracket_id}, Created: {order.created_at}")
            else:
                print(f"   Order {i}: Not found")
        
    finally:
        db.close()

if __name__ == "__main__":
    check_database_orders()
