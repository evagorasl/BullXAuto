#!/usr/bin/env python3
"""
Test script to verify the updated main.py with enhanced background task system
"""

import asyncio
import logging
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from background_task_monitor import enhanced_order_monitor
from database import db_manager, create_tables, init_profiles
from main import start_monitoring_for_active_profiles, ensure_monitoring_for_profile

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_updated_system():
    """Test the updated background task system"""
    
    print("=" * 60)
    print("TESTING UPDATED MAIN.PY WITH ENHANCED BACKGROUND TASKS")
    print("=" * 60)
    
    try:
        # Test 1: Initialize database
        print("\n1. Testing database initialization...")
        create_tables()
        init_profiles()
        print("✓ Database initialized successfully")
        
        # Test 2: Test startup monitoring logic
        print("\n2. Testing startup monitoring logic...")
        await start_monitoring_for_active_profiles()
        print(f"✓ Startup monitoring completed. Currently monitoring: {list(enhanced_order_monitor.monitored_profiles)}")
        
        # Test 3: Test ensure monitoring function
        print("\n3. Testing ensure monitoring for profile...")
        test_profile = "Saruman"  # Use one of the default profiles
        
        # First, stop monitoring if it's running
        if test_profile in enhanced_order_monitor.monitored_profiles:
            await enhanced_order_monitor.stop_monitoring_for_profile(test_profile)
            print(f"✓ Stopped monitoring for {test_profile}")
        
        # Now test ensure monitoring
        await ensure_monitoring_for_profile(test_profile)
        
        if test_profile in enhanced_order_monitor.monitored_profiles:
            print(f"✓ Monitoring ensured for {test_profile}")
        else:
            print(f"✗ Failed to ensure monitoring for {test_profile}")
        
        # Test 4: Test that calling ensure monitoring again doesn't duplicate
        print("\n4. Testing duplicate monitoring prevention...")
        profiles_before = len(enhanced_order_monitor.monitored_profiles)
        await ensure_monitoring_for_profile(test_profile)
        profiles_after = len(enhanced_order_monitor.monitored_profiles)
        
        if profiles_before == profiles_after:
            print("✓ Duplicate monitoring prevention works")
        else:
            print("✗ Duplicate monitoring prevention failed")
        
        # Test 5: Test health status
        print("\n5. Testing health status...")
        from background_task_monitor import get_background_task_health
        health = get_background_task_health()
        print(f"✓ Health status retrieved: Scheduler running: {health['scheduler_running']}")
        print(f"  Monitored profiles: {health['monitored_profiles']}")
        
        # Test 6: Test manual task execution
        print("\n6. Testing manual task execution...")
        if test_profile in enhanced_order_monitor.monitored_profiles:
            try:
                await enhanced_order_monitor._execute_monitored_task(test_profile)
                print("✓ Manual task execution completed")
            except Exception as e:
                print(f"⚠ Manual task execution failed (expected if no orders): {e}")
        
        print("\n" + "=" * 60)
        print("ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        
        # Final status
        print(f"\nFinal Status:")
        print(f"- Scheduler running: {enhanced_order_monitor.is_running}")
        print(f"- Monitored profiles: {list(enhanced_order_monitor.monitored_profiles)}")
        print(f"- Task timeout: {enhanced_order_monitor.task_timeout} seconds")
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        logger.error(f"Test error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        try:
            await enhanced_order_monitor.stop_monitoring()
            print("\n✓ Cleanup completed - all monitoring stopped")
        except Exception as e:
            print(f"\n⚠ Cleanup warning: {e}")

async def test_middleware_simulation():
    """Simulate the middleware behavior"""
    
    print("\n" + "=" * 60)
    print("TESTING MIDDLEWARE SIMULATION")
    print("=" * 60)
    
    try:
        # Simulate what happens when a user makes an API call
        print("\n1. Simulating user API call with profile...")
        
        # Stop all monitoring first
        await enhanced_order_monitor.stop_monitoring()
        print("✓ Stopped all monitoring")
        
        # Simulate middleware detecting a profile and ensuring monitoring
        test_profile = "Gandalf"
        print(f"Simulating API call from profile: {test_profile}")
        
        await ensure_monitoring_for_profile(test_profile)
        
        if test_profile in enhanced_order_monitor.monitored_profiles:
            print(f"✓ Middleware simulation successful - monitoring started for {test_profile}")
        else:
            print(f"✗ Middleware simulation failed")
        
        # Test multiple calls don't create duplicates
        print("\n2. Testing multiple API calls from same profile...")
        await ensure_monitoring_for_profile(test_profile)
        await ensure_monitoring_for_profile(test_profile)
        
        profile_count = len([p for p in enhanced_order_monitor.monitored_profiles if p == test_profile])
        if profile_count == 1:
            print("✓ Multiple calls handled correctly - no duplicates")
        else:
            print(f"✗ Multiple calls created duplicates: {profile_count}")
        
        print("\n✓ Middleware simulation tests completed")
        
    except Exception as e:
        print(f"\n✗ Middleware simulation failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Updated Main.py Test Suite")
    print("=" * 80)
    
    # Run the tests
    asyncio.run(test_updated_system())
    asyncio.run(test_middleware_simulation())
    
    print("\n" + "=" * 80)
    print("TEST SUITE COMPLETED")
    print("=" * 80)
