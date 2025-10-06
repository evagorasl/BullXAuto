"""
Migration script to add order_amount field to orders table.

This migration adds the order_amount column to store the order amount displayed in BullX.
Format: "0.5" for SOL amounts or "289.55K STIMMY" for token amounts.

Run this script to update existing databases with the new field.
"""

import sqlite3
import os

def migrate_add_order_amount():
    """Add order_amount column to orders table"""
    
    db_path = "./bullx_auto.db"
    
    if not os.path.exists(db_path):
        print(f"Database file not found at {db_path}")
        print("No migration needed - database will be created with the new schema.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(orders)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'order_amount' in columns:
            print("✅ order_amount column already exists in orders table")
            return
        
        # Add order_amount column
        print("Adding order_amount column to orders table...")
        cursor.execute("""
            ALTER TABLE orders 
            ADD COLUMN order_amount VARCHAR
        """)
        
        conn.commit()
        print("✅ Successfully added order_amount column to orders table")
        print("   Format: '0.5' for SOL or '289.55K STIMMY' for tokens")
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Migration: Add order_amount field to orders table")
    print("=" * 60)
    migrate_add_order_amount()
    print("=" * 60)
    print("Migration completed!")
    print("=" * 60)
