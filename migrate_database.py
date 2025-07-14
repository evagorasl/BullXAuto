"""
Database migration script to add new columns for the multi-order bracket system.
This script will add the 'bracket' column to the coins table and 'bracket_id' column to the orders table.
"""

import sqlite3
import os
from datetime import datetime

def migrate_database():
    """Migrate the existing database to support the new bracket system"""
    db_path = "bullx_auto.db"
    
    if not os.path.exists(db_path):
        print("Database file not found. Creating new database with updated schema.")
        # If no database exists, the new schema will be created automatically
        return True
    
    print("Starting database migration...")
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if the bracket column already exists in coins table
        cursor.execute("PRAGMA table_info(coins)")
        coins_columns = [column[1] for column in cursor.fetchall()]
        
        if 'bracket' not in coins_columns:
            print("Adding 'bracket' column to coins table...")
            cursor.execute("ALTER TABLE coins ADD COLUMN bracket INTEGER")
            print("✓ Added 'bracket' column to coins table")
        else:
            print("✓ 'bracket' column already exists in coins table")
        
        # Check if the bracket_id column already exists in orders table
        cursor.execute("PRAGMA table_info(orders)")
        orders_columns = [column[1] for column in cursor.fetchall()]
        
        if 'bracket_id' not in orders_columns:
            print("Adding 'bracket_id' column to orders table...")
            # Add the column with a default value of 1 for existing orders
            cursor.execute("ALTER TABLE orders ADD COLUMN bracket_id INTEGER DEFAULT 1")
            print("✓ Added 'bracket_id' column to orders table")
            
            # Update existing orders to have sequential bracket_ids per coin/profile combination
            print("Updating existing orders with bracket_ids...")
            cursor.execute("""
                SELECT id, coin_id, profile_name 
                FROM orders 
                WHERE status = 'ACTIVE' 
                ORDER BY coin_id, profile_name, created_at
            """)
            
            orders = cursor.fetchall()
            bracket_counters = {}  # Track bracket_id per coin/profile
            
            for order_id, coin_id, profile_name in orders:
                key = f"{coin_id}_{profile_name}"
                if key not in bracket_counters:
                    bracket_counters[key] = 1
                else:
                    bracket_counters[key] += 1
                
                # Ensure we don't exceed 4 orders per coin/profile
                bracket_id = min(bracket_counters[key], 4)
                
                cursor.execute(
                    "UPDATE orders SET bracket_id = ? WHERE id = ?",
                    (bracket_id, order_id)
                )
            
            print("✓ Updated existing orders with bracket_ids")
        else:
            print("✓ 'bracket_id' column already exists in orders table")
        
        # Update coin brackets based on market cap
        print("Updating coin brackets based on market cap...")
        cursor.execute("SELECT id, market_cap FROM coins WHERE market_cap IS NOT NULL")
        coins_with_market_cap = cursor.fetchall()
        
        for coin_id, market_cap in coins_with_market_cap:
            # Calculate bracket based on market cap
            if market_cap < 100000:  # < 100K
                bracket = 1
            elif market_cap < 500000:  # 100K - 500K
                bracket = 2
            elif market_cap < 1000000:  # 500K - 1M
                bracket = 3
            elif market_cap < 5000000:  # 1M - 5M
                bracket = 4
            else:  # > 5M
                bracket = 5
            
            cursor.execute("UPDATE coins SET bracket = ? WHERE id = ?", (bracket, coin_id))
        
        print("✓ Updated coin brackets based on market cap")
        
        # Commit all changes
        conn.commit()
        print("✓ Database migration completed successfully!")
        
        # Print summary
        cursor.execute("SELECT COUNT(*) FROM coins WHERE bracket IS NOT NULL")
        coins_with_brackets = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM orders WHERE bracket_id IS NOT NULL")
        orders_with_bracket_ids = cursor.fetchone()[0]
        
        print(f"\nMigration Summary:")
        print(f"- Coins with brackets: {coins_with_brackets}")
        print(f"- Orders with bracket_ids: {orders_with_bracket_ids}")
        
        return True
        
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

def verify_migration():
    """Verify that the migration was successful"""
    db_path = "bullx_auto.db"
    
    if not os.path.exists(db_path):
        print("Database file not found.")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check coins table structure
        cursor.execute("PRAGMA table_info(coins)")
        coins_columns = [column[1] for column in cursor.fetchall()]
        
        # Check orders table structure
        cursor.execute("PRAGMA table_info(orders)")
        orders_columns = [column[1] for column in cursor.fetchall()]
        
        print("Database Schema Verification:")
        print(f"✓ Coins table columns: {', '.join(coins_columns)}")
        print(f"✓ Orders table columns: {', '.join(orders_columns)}")
        
        # Verify required columns exist
        required_coins_columns = ['bracket']
        required_orders_columns = ['bracket_id']
        
        missing_coins_columns = [col for col in required_coins_columns if col not in coins_columns]
        missing_orders_columns = [col for col in required_orders_columns if col not in orders_columns]
        
        if missing_coins_columns:
            print(f"❌ Missing columns in coins table: {', '.join(missing_coins_columns)}")
            return False
        
        if missing_orders_columns:
            print(f"❌ Missing columns in orders table: {', '.join(missing_orders_columns)}")
            return False
        
        print("✓ All required columns are present!")
        return True
        
    except Exception as e:
        print(f"Error during verification: {e}")
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    print("BullXAuto Database Migration Tool")
    print("=" * 40)
    
    # Run migration
    success = migrate_database()
    
    if success:
        print("\n" + "=" * 40)
        print("Verifying migration...")
        verify_migration()
    else:
        print("❌ Migration failed!")
        exit(1)
    
    print("\n" + "=" * 40)
    print("Migration completed! You can now use the new multi-order bracket system.")
