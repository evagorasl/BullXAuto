"""
Fix duplicate ACTIVE orders in the database
Marks older duplicate orders as REPLACED when newer ones exist
"""
from database import db_manager, SessionLocal
from models import Order, Coin
from datetime import datetime
from collections import defaultdict

def fix_duplicate_orders(profile_name: str = None, dry_run: bool = True):
    """
    Fix duplicate ACTIVE orders by marking older duplicates as REPLACED
    
    Args:
        profile_name: Optional profile name to filter by
        dry_run: If True, only shows what would be done without making changes
    """
    db = SessionLocal()
    try:
        print("🔍 Scanning for duplicate ACTIVE orders...")
        print()
        
        # Get all active orders
        query = db.query(Order).filter(Order.status == "ACTIVE")
        if profile_name:
            query = query.filter(Order.profile_name == profile_name)
        
        active_orders = query.order_by(Order.coin_id, Order.bracket_id, Order.created_at).all()
        
        # Group by coin_id + profile_name + bracket_id
        grouped = defaultdict(list)
        for order in active_orders:
            key = (order.coin_id, order.profile_name, order.bracket_id)
            grouped[key].append(order)
        
        # Find duplicates
        duplicates_found = 0
        orders_to_replace = []
        
        for key, orders in grouped.items():
            if len(orders) > 1:
                coin_id, profile, bracket_id = key
                duplicates_found += 1
                
                # Get coin name
                coin = db.query(Coin).filter(Coin.id == coin_id).first()
                coin_name = coin.name if coin and coin.name else f"Coin {coin_id}"
                
                print(f"⚠️  Duplicate found: {coin_name} (Profile: {profile}, Bracket: {bracket_id})")
                print(f"   {len(orders)} ACTIVE orders found:")
                
                # Sort by created_at (oldest first)
                orders.sort(key=lambda o: o.created_at)
                
                for i, order in enumerate(orders):
                    is_newest = (i == len(orders) - 1)
                    status = "✓ KEEP (newest)" if is_newest else "✗ REPLACE (older)"
                    print(f"   - Order ID {order.id:2d}: Created {order.created_at} - {status}")
                    
                    # Mark older orders for replacement
                    if not is_newest:
                        orders_to_replace.append(order)
                
                print()
        
        if duplicates_found == 0:
            print("✅ No duplicate ACTIVE orders found!")
            return
        
        print(f"📊 Summary:")
        print(f"   Duplicate groups found: {duplicates_found}")
        print(f"   Orders to mark as REPLACED: {len(orders_to_replace)}")
        print()
        
        if dry_run:
            print("🔍 DRY RUN MODE - No changes made")
            print("   Run with dry_run=False to apply changes")
        else:
            print("💾 Applying changes...")
            for order in orders_to_replace:
                order.status = "REPLACED"
                order.updated_at = datetime.now()
                order.completed_at = datetime.now()
                print(f"   ✓ Order ID {order.id} marked as REPLACED")
            
            db.commit()
            print()
            print("✅ Changes applied successfully!")
        
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 80)
    print("🔧 DUPLICATE ORDER CLEANUP TOOL")
    print("=" * 80)
    print()
    
    # First run in dry-run mode
    print("=" * 80)
    print("STEP 1: DRY RUN (Preview)")
    print("=" * 80)
    print()
    fix_duplicate_orders(dry_run=True)
    
    print()
    print("=" * 80)
    print("STEP 2: Apply Changes")
    print("=" * 80)
    print()
    
    # Ask for confirmation
    response = input("Do you want to apply these changes? (yes/no): ").strip().lower()
    
    if response in ['yes', 'y']:
        fix_duplicate_orders(dry_run=False)
    else:
        print("❌ Cancelled - No changes made")
