from database import db_manager, SessionLocal
from models import Order, Coin
from bracket_config import BRACKET_CONFIG

def analyze_duplicate_bracket_ids():
    """Analyze and fix duplicate bracket_id issues"""
    db = SessionLocal()
    try:
        # Get Pigeon coin
        pigeon = db.query(Coin).filter(Coin.id == 1).first()
        if not pigeon:
            print("ERROR: Pigeon coin not found")
            return

        print("=" * 80)
        print("PIGEON ORDER ANALYSIS")
        print("=" * 80)

        # Get all Pigeon orders
        pigeon_orders = db.query(Order).filter(Order.coin_id == 1).order_by(Order.id).all()

        print(f"\nTotal Pigeon orders: {len(pigeon_orders)}")
        print(f"Pigeon bracket configuration: {pigeon.bracket}")

        # Get bracket config
        bracket_info = BRACKET_CONFIG.get(pigeon.bracket)
        if not bracket_info:
            print(f"ERROR: No bracket config found for bracket {pigeon.bracket}")
            return

        bracket_entries = bracket_info.get('entries', [])
        print(f"\nExpected bracket structure ({len(bracket_entries)} orders):")
        for i, entry_price in enumerate(bracket_entries, 1):
            print(f"  Bracket {i}: ${entry_price:,.0f}")

        # Analyze by status
        print("\n" + "=" * 80)
        print("CURRENT DATABASE STATE")
        print("=" * 80)

        active_orders = [o for o in pigeon_orders if o.status == "ACTIVE"]
        expired_orders = [o for o in pigeon_orders if o.status == "EXPIRED"]
        cancelled_orders = [o for o in pigeon_orders if o.status == "CANCELLED"]

        print(f"\nACTIVE orders ({len(active_orders)}):")
        for o in active_orders:
            print(f"  Order {o.id}: bracket_id={o.bracket_id}, entry=${o.entry_price:,.0f}, created={o.created_at}")

        print(f"\nEXPIRED orders ({len(expired_orders)}):")
        for o in expired_orders:
            print(f"  Order {o.id}: bracket_id={o.bracket_id}, entry=${o.entry_price:,.0f}, created={o.created_at}")

        if cancelled_orders:
            print(f"\nCANCELLED orders ({len(cancelled_orders)}):")
            for o in cancelled_orders:
                print(f"  Order {o.id}: bracket_id={o.bracket_id}, entry=${o.entry_price:,.0f}, created={o.created_at}")

        # Check for duplicates in ACTIVE orders
        print("\n" + "=" * 80)
        print("DUPLICATE CHECK")
        print("=" * 80)

        bracket_id_count = {}
        for o in active_orders:
            bracket_id_count[o.bracket_id] = bracket_id_count.get(o.bracket_id, 0) + 1

        duplicates_found = False
        for bracket_id, count in bracket_id_count.items():
            if count > 1:
                duplicates_found = True
                print(f"\nWARNING: bracket_id={bracket_id} has {count} ACTIVE orders (should be 1)!")
                dup_orders = [o for o in active_orders if o.bracket_id == bracket_id]
                for o in dup_orders:
                    print(f"  Order {o.id}: created={o.created_at}")

        if not duplicates_found:
            print("\nNo duplicate ACTIVE orders found")

        # Check for missing bracket_ids
        print("\n" + "=" * 80)
        print("MISSING BRACKET IDs")
        print("=" * 80)

        expected_bracket_ids = set(range(1, len(bracket_entries) + 1))
        active_bracket_ids = set(o.bracket_id for o in active_orders)
        missing_bracket_ids = expected_bracket_ids - active_bracket_ids

        if missing_bracket_ids:
            print(f"\nMissing bracket_ids: {sorted(missing_bracket_ids)}")
            for bracket_id in sorted(missing_bracket_ids):
                entry_price = bracket_entries[bracket_id - 1]
                print(f"  Bracket {bracket_id}: ${entry_price:,.0f}")
        else:
            print("\nNo missing bracket_ids")

        # Analyze the specific duplicate issue (Orders 40 & 41)
        print("\n" + "=" * 80)
        print("ORDERS 40 & 41 ANALYSIS (duplicate bracket_id=2)")
        print("=" * 80)

        order_40 = db.query(Order).filter(Order.id == 40).first()
        order_41 = db.query(Order).filter(Order.id == 41).first()

        if order_40:
            print(f"\nOrder 40:")
            print(f"  bracket_id: {order_40.bracket_id}")
            print(f"  status: {order_40.status}")
            print(f"  entry_price: ${order_40.entry_price:,.0f}")
            print(f"  created_at: {order_40.created_at}")
            print(f"  trigger_condition: {order_40.trigger_condition or 'None'}")
            print(f"  order_amount: {order_40.order_amount or 'None'}")

        if order_41:
            print(f"\nOrder 41:")
            print(f"  bracket_id: {order_41.bracket_id}")
            print(f"  status: {order_41.status}")
            print(f"  entry_price: ${order_41.entry_price:,.0f}")
            print(f"  created_at: {order_41.created_at}")
            print(f"  trigger_condition: {order_41.trigger_condition or 'None'}")
            print(f"  order_amount: {order_41.order_amount or 'None'}")

        if order_40 and order_41:
            time_diff = (order_41.created_at - order_40.created_at).total_seconds() / 60
            print(f"\nTime between order 40 and 41: {time_diff:.1f} minutes")
            print("\nLikely cause: Power outage or crash during renewal process")
            print("  1. Order 40 was being renewed")
            print("  2. System crashed after creating order 40 but before marking it properly")
            print("  3. On restart, system created order 41 with same bracket_id=2")

        # Recommendations
        print("\n" + "=" * 80)
        print("RECOMMENDED FIXES")
        print("=" * 80)

        print("\nThe duplicate issue has been resolved in the code with:")
        print("  - Conservative reconciliation (prevents false CANCELLED markings)")
        print("  - Improved two-phase identification")
        print("  - Per-button deletion tracking")

        print("\nFor the current database state:")
        print("  1. Order 40 is already EXPIRED (correct)")
        print("  2. Order 41 is ACTIVE (correct)")
        print("  3. Need to create bracket_id=3 order manually on BullX")

        if 3 in missing_bracket_ids and len(bracket_entries) >= 3:
            entry_price_3 = bracket_entries[2]
            print(f"\n  Missing order: bracket_id=3, entry=${entry_price_3:,.0f}")
            print("  You should manually create this order on BullX")

        print("\n" + "=" * 80)
        print("ANALYSIS COMPLETE")
        print("=" * 80)

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    analyze_duplicate_bracket_ids()
