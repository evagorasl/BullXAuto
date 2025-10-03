#!/usr/bin/env python3
"""
Migration script to add trigger_condition field to orders table
"""

import sqlite3
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_add_trigger_condition():
    """Add trigger_condition column to orders table"""
    
    db_path = "bullx_auto.db"
    
    if not os.path.exists(db_path):
        logger.error(f"Database file {db_path} not found!")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(orders)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'trigger_condition' in columns:
            logger.info("trigger_condition column already exists")
            return True
        
        # Add the new column
        logger.info("Adding trigger_condition column to orders table...")
        cursor.execute("ALTER TABLE orders ADD COLUMN trigger_condition TEXT")
        
        conn.commit()
        logger.info("✅ Successfully added trigger_condition column")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False
        
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    success = migrate_add_trigger_condition()
    if success:
        print("✅ Migration completed successfully")
    else:
        print("❌ Migration failed")
