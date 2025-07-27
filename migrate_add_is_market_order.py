"""
Migration script to add is_market_order column to orders table
"""

import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def migrate_add_is_market_order():
    """Add is_market_order column to orders table"""
    
    # Database path
    db_path = Path("bullx_auto.db")
    
    if not db_path.exists():
        logger.info("Database doesn't exist yet, no migration needed")
        return True
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(orders)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'is_market_order' in columns:
            logger.info("is_market_order column already exists")
            conn.close()
            return True
        
        # Add the new column
        cursor.execute("""
            ALTER TABLE orders 
            ADD COLUMN is_market_order BOOLEAN
        """)
        
        conn.commit()
        logger.info("Successfully added is_market_order column to orders table")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Failed to migrate database: {e}")
        if 'conn' in locals():
            conn.close()
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    success = migrate_add_is_market_order()
    if success:
        print("Migration completed successfully")
    else:
        print("Migration failed")
