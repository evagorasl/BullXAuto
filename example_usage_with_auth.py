#!/usr/bin/env python3
"""
Example usage script for BullX Automation API with API Key Authentication

This script demonstrates how to interact with the BullX automation API using API keys.
Make sure the API server is running before executing this script.
"""

import requests
import json
import time
from typing import Dict, Any, Optional

# API base URL
API_BASE_URL = "http://localhost:8000"

class BullXAPIClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def make_request(self, method: str, endpoint: str, data: Optional[Dict[Any, Any]] = None) -> Dict[Any, Any]:
        """Make an authenticated request to the API"""
        url = f"{API_BASE_URL}{endpoint}"
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=self.headers)
            elif method.upper() == "POST":
                response = requests.post(url, headers=self.headers, json=data or {})
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            print(f"Error making request to {url}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    return {"error": error_detail.get("detail", str(e))}
                except:
                    return {"error": str(e)}
            return {"error": str(e)}
    
    def check_api_health(self):
        """Check if the API is running (no auth required)"""
        print("Checking API health...")
        try:
            response = requests.get(f"{API_BASE_URL}/health")
            response.raise_for_status()
            result = response.json()
            print(f"✓ API is healthy: {result}")
            return True
        except Exception as e:
            print(f"✗ API health check failed: {e}")
            return False
    
    def get_profile(self):
        """Get current profile information"""
        print("\nGetting profile information...")
        result = self.make_request("GET", "/api/v1/profile")
        
        if "error" not in result:
            print(f"✓ Profile: {result['name']}")
            print(f"  Logged in: {result['is_logged_in']}")
            print(f"  Active: {result['is_active']}")
            if result.get('last_login'):
                print(f"  Last login: {result['last_login']}")
            return result
        else:
            print(f"✗ Failed to get profile: {result}")
            return None
    
    def login(self):
        """Login with the current profile"""
        print(f"\nAttempting login...")
        
        result = self.make_request("POST", "/api/v1/login")
        
        if "error" not in result and result.get("success"):
            print(f"✓ Login successful: {result['message']}")
            return True
        else:
            print(f"✗ Login failed: {result}")
            return False
    
    def search_address(self, address: str):
        """Search for a token address"""
        print(f"\nSearching for address: {address}")
        
        data = {"address": address}
        result = self.make_request("POST", "/api/v1/search", data)
        
        if "error" not in result and result.get("success"):
            print(f"✓ Search successful: {result['message']}")
            if result.get("market_cap"):
                print(f"  Market Cap: ${result['market_cap']:,.2f}")
            return True
        else:
            print(f"✗ Search failed: {result}")
            return False
    
    def execute_strategy(self, strategy_number: int, address: str, order_type: str, 
                        entry_price: Optional[float] = None, 
                        take_profit: Optional[float] = None, 
                        stop_loss: Optional[float] = None):
        """Execute a trading strategy"""
        print(f"\nExecuting Strategy {strategy_number} ({order_type}) for {address}")
        
        data = {
            "strategy_number": strategy_number,
            "address": address,
            "order_type": order_type
        }
        
        # Add optional price parameters
        if entry_price is not None:
            data["entry_price"] = entry_price
        if take_profit is not None:
            data["take_profit"] = take_profit
        if stop_loss is not None:
            data["stop_loss"] = stop_loss
        
        result = self.make_request("POST", "/api/v1/strategy", data)
        
        if "error" not in result and result.get("success"):
            print(f"✓ Strategy executed successfully:")
            print(f"  Entry Price: {result.get('entry_price')}")
            print(f"  Take Profit: {result.get('take_profit')}")
            print(f"  Stop Loss: {result.get('stop_loss')}")
            return True
        else:
            print(f"✗ Strategy execution failed: {result}")
            return False
    
    def get_orders(self):
        """Get all active orders for the current profile"""
        print("\nGetting active orders...")
        
        result = self.make_request("GET", "/api/v1/orders")
        
        if "error" not in result:
            if isinstance(result, list):
                print(f"✓ Found {len(result)} active orders:")
                for i, order in enumerate(result, 1):
                    print(f"  Order {i}:")
                    print(f"    Address: {order.get('address')}")
                    print(f"    Strategy: {order.get('strategy_number')}")
                    print(f"    Type: {order.get('order_type')}")
                    print(f"    Status: {order.get('status')}")
                    print(f"    Entry Price: {order.get('entry_price')}")
                    print(f"    Take Profit: {order.get('take_profit')}")
                    print(f"    Stop Loss: {order.get('stop_loss')}")
            else:
                print(f"✓ Orders response: {result}")
            return True
        else:
            print(f"✗ Failed to get orders: {result}")
            return False
    
    def close_driver(self):
        """Close Chrome driver for the current profile"""
        print(f"\nClosing Chrome driver...")
        
        result = self.make_request("POST", "/api/v1/close-driver")
        
        if "error" not in result and result.get("success"):
            print(f"✓ Driver closed: {result['message']}")
            return True
        else:
            print(f"✗ Failed to close driver: {result}")
            return False

def main():
    """Main example function"""
    print("=" * 60)
    print("BullX Automation API - Authenticated Example Usage")
    print("=" * 60)
    
    # Get API key from user
    api_key = input("Enter your API key: ").strip()
    
    if not api_key:
        print("No API key provided. Exiting.")
        return
    
    if not api_key.startswith("bullx_"):
        print("Invalid API key format. API keys should start with 'bullx_'")
        return
    
    # Create API client
    client = BullXAPIClient(api_key)
    
    # Check if API is running
    if not client.check_api_health():
        print("\nPlease start the API server first:")
        print("python start.py")
        return
    
    # Get profile information
    profile = client.get_profile()
    if not profile:
        print("Failed to authenticate. Please check your API key.")
        return
    
    print(f"\nAuthenticated as profile: {profile['name']}")
    
    # Example token address (replace with actual address)
    example_address = input("\nEnter token address to test (or press Enter for demo): ").strip()
    if not example_address:
        example_address = "0x1234567890abcdef1234567890abcdef12345678"
        print(f"Using demo address: {example_address}")
    
    print("\n" + "=" * 60)
    print("EXAMPLE WORKFLOW")
    print("=" * 60)
    
    # Step 1: Login
    print("\n1. LOGIN EXAMPLE")
    login_success = client.login()
    
    if login_success:
        # Wait a bit for login to complete
        print("   Waiting 5 seconds for login to complete...")
        time.sleep(5)
        
        # Step 2: Search for address
        print("\n2. SEARCH EXAMPLE")
        search_success = client.search_address(example_address)
        
        if search_success:
            # Step 3: Execute strategy
            print("\n3. STRATEGY EXECUTION EXAMPLE")
            strategy_choice = input("Enter strategy number (1-3) or press Enter for default (1): ").strip()
            try:
                strategy_number = int(strategy_choice) if strategy_choice else 1
            except ValueError:
                strategy_number = 1
            
            order_type = input("Enter order type (BUY/SELL) or press Enter for BUY: ").strip().upper()
            if order_type not in ["BUY", "SELL"]:
                order_type = "BUY"
            
            client.execute_strategy(strategy_number, example_address, order_type)
            
            # Wait a bit
            time.sleep(2)
            
            # Step 4: Get orders
            print("\n4. GET ORDERS EXAMPLE")
            client.get_orders()
    
    # Step 5: Close driver (optional)
    print("\n5. CLOSE DRIVER EXAMPLE")
    close_response = input("Do you want to close the Chrome driver? (y/n): ")
    if close_response.lower() in ['y', 'yes']:
        client.close_driver()
    
    print("\n" + "=" * 60)
    print("Example completed!")
    print("=" * 60)
    print("\nAPI Documentation: http://localhost:8000/docs")
    print("Note: Each API key corresponds to a specific Chrome profile.")
    print("Your orders and data are isolated to your profile.")

if __name__ == "__main__":
    main()
