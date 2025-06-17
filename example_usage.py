#!/usr/bin/env python3
"""
Example usage script for BullX Automation API

This script demonstrates how to interact with the BullX automation API.
Make sure the API server is running before executing this script.
"""

import requests
import json
import time
from typing import Dict, Any

# API base URL
API_BASE_URL = "http://localhost:8000"

def make_request(method: str, endpoint: str, data: Dict[Any, Any] = None) -> Dict[Any, Any]:
    """Make a request to the API"""
    url = f"{API_BASE_URL}{endpoint}"
    
    try:
        if method.upper() == "GET":
            response = requests.get(url)
        elif method.upper() == "POST":
            response = requests.post(url, json=data)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.RequestException as e:
        print(f"Error making request to {url}: {e}")
        return {"error": str(e)}

def check_api_health():
    """Check if the API is running"""
    print("Checking API health...")
    result = make_request("GET", "/health")
    
    if "error" not in result:
        print(f"✓ API is healthy: {result}")
        return True
    else:
        print(f"✗ API health check failed: {result}")
        return False

def get_profiles():
    """Get available profiles"""
    print("\nGetting available profiles...")
    result = make_request("GET", "/api/v1/profiles")
    
    if "error" not in result:
        print(f"✓ Available profiles: {result['profiles']}")
        return result['profiles']
    else:
        print(f"✗ Failed to get profiles: {result}")
        return []

def login_example(profile_name: str):
    """Example: Login with a profile"""
    print(f"\nAttempting login with profile: {profile_name}")
    
    data = {
        "profile_name": profile_name
    }
    
    result = make_request("POST", "/api/v1/login", data)
    
    if "error" not in result and result.get("success"):
        print(f"✓ Login successful: {result['message']}")
        return True
    else:
        print(f"✗ Login failed: {result}")
        return False

def search_example(profile_name: str, address: str):
    """Example: Search for a token address"""
    print(f"\nSearching for address: {address}")
    
    data = {
        "address": address,
        "profile_name": profile_name
    }
    
    result = make_request("POST", "/api/v1/search", data)
    
    if "error" not in result and result.get("success"):
        print(f"✓ Search successful: {result['message']}")
        if result.get("market_cap"):
            print(f"  Market Cap: ${result['market_cap']:,.2f}")
        return True
    else:
        print(f"✗ Search failed: {result}")
        return False

def strategy_example(profile_name: str, address: str, strategy_number: int, order_type: str):
    """Example: Execute a trading strategy"""
    print(f"\nExecuting Strategy {strategy_number} ({order_type}) for {address}")
    
    data = {
        "strategy_number": strategy_number,
        "address": address,
        "order_type": order_type,
        "profile_name": profile_name
        # Note: entry_price, take_profit, stop_loss are optional
        # If not provided, they will be calculated based on strategy
    }
    
    result = make_request("POST", "/api/v1/strategy", data)
    
    if "error" not in result and result.get("success"):
        print(f"✓ Strategy executed successfully:")
        print(f"  Entry Price: {result.get('entry_price')}")
        print(f"  Take Profit: {result.get('take_profit')}")
        print(f"  Stop Loss: {result.get('stop_loss')}")
        return True
    else:
        print(f"✗ Strategy execution failed: {result}")
        return False

def get_orders_example():
    """Example: Get all active orders"""
    print("\nGetting active orders...")
    
    result = make_request("GET", "/api/v1/orders")
    
    if "error" not in result:
        if isinstance(result, list):
            print(f"✓ Found {len(result)} active orders:")
            for i, order in enumerate(result, 1):
                print(f"  Order {i}:")
                print(f"    Address: {order.get('address')}")
                print(f"    Strategy: {order.get('strategy_number')}")
                print(f"    Type: {order.get('order_type')}")
                print(f"    Status: {order.get('status')}")
                print(f"    Profile: {order.get('profile_name')}")
        else:
            print(f"✓ Orders response: {result}")
        return True
    else:
        print(f"✗ Failed to get orders: {result}")
        return False

def close_driver_example(profile_name: str):
    """Example: Close Chrome driver for a profile"""
    print(f"\nClosing Chrome driver for profile: {profile_name}")
    
    result = make_request("POST", f"/api/v1/close-driver/{profile_name}")
    
    if "error" not in result and result.get("success"):
        print(f"✓ Driver closed: {result['message']}")
        return True
    else:
        print(f"✗ Failed to close driver: {result}")
        return False

def main():
    """Main example function"""
    print("=" * 60)
    print("BullX Automation API - Example Usage")
    print("=" * 60)
    
    # Check if API is running
    if not check_api_health():
        print("\nPlease start the API server first:")
        print("python start.py")
        return
    
    # Get available profiles
    profiles = get_profiles()
    if not profiles:
        return
    
    # Use the first available profile
    profile_name = profiles[0]
    print(f"\nUsing profile: {profile_name}")
    
    # Example token address (replace with actual address)
    example_address = "0x1234567890abcdef1234567890abcdef12345678"
    
    print("\n" + "=" * 60)
    print("EXAMPLE WORKFLOW")
    print("=" * 60)
    
    # Step 1: Login
    print("\n1. LOGIN EXAMPLE")
    login_success = login_example(profile_name)
    
    if login_success:
        # Wait a bit for login to complete
        print("   Waiting 5 seconds for login to complete...")
        time.sleep(5)
        
        # Step 2: Search for address
        print("\n2. SEARCH EXAMPLE")
        search_success = search_example(profile_name, example_address)
        
        if search_success:
            # Step 3: Execute strategy
            print("\n3. STRATEGY EXECUTION EXAMPLE")
            strategy_example(profile_name, example_address, 1, "BUY")
            
            # Wait a bit
            time.sleep(2)
            
            # Step 4: Get orders
            print("\n4. GET ORDERS EXAMPLE")
            get_orders_example()
    
    # Step 5: Close driver (optional)
    print("\n5. CLOSE DRIVER EXAMPLE")
    close_response = input(f"Do you want to close the Chrome driver for {profile_name}? (y/n): ")
    if close_response.lower() in ['y', 'yes']:
        close_driver_example(profile_name)
    
    print("\n" + "=" * 60)
    print("Example completed!")
    print("=" * 60)
    print("\nNOTE: This example uses a dummy address.")
    print("Replace 'example_address' with a real token address for actual trading.")
    print("\nAPI Documentation: http://localhost:8000/docs")

if __name__ == "__main__":
    main()
