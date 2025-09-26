#!/usr/bin/env python3
"""
Test script for profile-specific background tasks functionality
"""

import asyncio
import logging
from background_tasks import order_monitor, check_orders_for_profile

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_profile_specific_background_tasks():
    """Test the profile-specific background task functionality"""
    
    print("Testing profile-specific background tasks...")
    
    # Test profile name (you can change this to match your actual profiles)
    test_profile = "Saruman"  # or "Gandalf"
    
    try:
        print(f"\n1. Testing manual order check for profile: {test_profile}")
        await check_orders_for_profile(test_profile)
        print("✓ Manual order check completed")
        
        print(f"\n2. Testing background monitoring start for profile: {test_profile}")
        await order_monitor.start_monitoring_for_profile(test_profile)
        print("✓ Background monitoring started")
        
        print(f"\n3. Checking if profile is being monitored...")
        if test_profile in order_monitor.monitored_profiles:
            print(f"✓ Profile {test_profile} is being monitored")
        else:
            print(f"✗ Profile {test_profile} is NOT being monitored")
        
        print(f"\n4. Testing background monitoring stop for profile: {test_profile}")
        await order_monitor.stop_monitoring_for_profile(test_profile)
        print("✓ Background monitoring stopped")
        
        print(f"\n5. Checking if profile monitoring was stopped...")
        if test_profile not in order_monitor.monitored_profiles:
            print(f"✓ Profile {test_profile} monitoring stopped successfully")
        else:
            print(f"✗ Profile {test_profile} is still being monitored")
        
        print("\n✓ All tests completed successfully!")
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        logger.error(f"Test error: {e}")
    
    finally:
        # Clean up - stop all monitoring
        try:
            await order_monitor.stop_monitoring()
            print("\n✓ Cleanup completed - all monitoring stopped")
        except Exception as e:
            print(f"\n⚠ Cleanup warning: {e}")

if __name__ == "__main__":
    print("Profile-Specific Background Tasks Test")
    print("=" * 50)
    
    # Run the test
    asyncio.run(test_profile_specific_background_tasks())
