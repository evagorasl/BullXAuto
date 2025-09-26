#!/usr/bin/env python3
"""
Test script for the order check functionality.

This script tests:
1. The coin name fix in multi-order bracket strategy
2. The new order check functionality
"""

import requests
import json
import time
from typing import Dict, Any

class BullXAutoTestClient:
    def __init__(self, base_url: str = "http://localhost:8000", api_key: str = None):
        self.base_url = base_url
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json"
        }
        if api_key:
            self.headers["X-API-Key"] = api_key
    
    def login(self) -> Dict[str, Any]:
        """Test login functionality"""
        url = f"{self.base_url}/api/v1/login"
        response = requests.post(url, headers=self.headers)
        return response.json()
    
    def search_address(self, address: str) -> Dict[str, Any]:
        """Test search functionality"""
        url = f"{self.base_url}/api/v1/search"
        payload = {"address": address}
        response = requests.post(url, json=payload, headers=self.headers)
        return response.json()
    
    def check_orders(self) -> Dict[str, Any]:
        """Test order check functionality"""
        url = f"{self.base_url}/api/v1/check-orders"
        response = requests.post(url, headers=self.headers)
        return response.json()
    
    def get_coin(self, address: str) -> Dict[str, Any]:
        """Get coin information to verify name is stored"""
        url = f"{self.base_url}/api/v1/coins/{address}"
        response = requests.get(url, headers=self.headers)
        return response.json()
    
    def create_bracket_strategy(self, address: str, total_amount: float) -> Dict[str, Any]:
        """Test bracket strategy creation"""
        url = f"{self.base_url}/api/v1/bracket-strategy"
        params = {
            "address": address,
            "total_amount": total_amount,
            "strategy_number": 1
        }
        response = requests.post(url, params=params, headers=self.headers)
        return response.json()

def test_coin_name_fix():
    """Test that coin names are properly extracted and stored"""
    print("=== Testing Coin Name Fix ===")
    
    # You'll need to replace this with a valid API key
    api_key = "bullx_zPF5NZTt_k8x2pfUJfGdNWi0RVCyhog8ajhGw-bCwK8"  # Replace with actual API key
    client = BullXAutoTestClient(api_key=api_key)
    
    # Test address - replace with a real token address
    test_address = "0x1234567890abcdef1234567890abcdef12345678"
    
    print(f"1. Searching for address: {test_address}")
    search_result = client.search_address(test_address)
    print(f"Search result: {json.dumps(search_result, indent=2)}")
    
    if search_result.get("success"):
        print("2. Checking if coin name was stored...")
        coin_result = client.get_coin(test_address)
        print(f"Coin data: {json.dumps(coin_result, indent=2)}")
        
        if coin_result.get("name"):
            print(f"✓ Coin name successfully stored: {coin_result['name']}")
        else:
            print("❌ Coin name not found in database")
    else:
        print(f"❌ Search failed: {search_result}")

def test_order_check():
    """Test the order check functionality"""
    print("\n=== Testing Order Check Functionality ===")
    
    # You'll need to replace this with a valid API key
    api_key = "bullx_zPF5NZTt_k8x2pfUJfGdNWi0RVCyhog8ajhGw-bCwK8"  # Replace with actual API key
    client = BullXAutoTestClient(api_key=api_key)
    
    print("1. Logging in...")
    login_result = client.login()
    print(f"Login result: {json.dumps(login_result, indent=2)}")
    
    if login_result.get("success"):
        print("2. Checking orders...")
        order_check_result = client.check_orders()
        print(f"Order check result: {json.dumps(order_check_result, indent=2)}")
        
        if order_check_result.get("success"):
            print(f"✓ Successfully processed {order_check_result.get('total_buttons', 0)} buttons")
            
            # Print summary of found information
            order_info = order_check_result.get("order_info", [])
            for button_info in order_info:
                button_index = button_info.get("button_index", "Unknown")
                rows = button_info.get("rows", [])
                print(f"  Button {button_index}: Found {len(rows)} rows")
                
                for row in rows[:3]:  # Show first 3 rows as example
                    main_text = row.get("main_text", "")[:100]  # First 100 chars
                    print(f"    Row: {main_text}...")
        else:
            print(f"❌ Order check failed: {order_check_result}")
    else:
        print(f"❌ Login failed: {login_result}")

def test_bracket_strategy_with_coin_name():
    """Test bracket strategy to ensure coin name is captured"""
    print("\n=== Testing Bracket Strategy with Coin Name ===")
    
    # You'll need to replace this with a valid API key
    api_key = "bullx_zPF5NZTt_k8x2pfUJfGdNWi0RVCyhog8ajhGw-bCwK8"  # Replace with actual API key
    client = BullXAutoTestClient(api_key=api_key)
    
    # Test address - replace with a real token address
    test_address = "0x1234567890abcdef1234567890abcdef12345678"
    total_amount = 100.0  # $100 test amount
    
    print(f"1. Creating bracket strategy for address: {test_address}")
    print(f"   Total amount: ${total_amount}")
    
    bracket_result = client.create_bracket_strategy(test_address, total_amount)
    print(f"Bracket strategy result: {json.dumps(bracket_result, indent=2)}")
    
    if bracket_result.get("success"):
        print("2. Verifying coin name was stored...")
        coin_result = client.get_coin(test_address)
        
        if coin_result.get("name"):
            print(f"✓ Coin name successfully stored during bracket strategy: {coin_result['name']}")
        else:
            print("❌ Coin name not found after bracket strategy")
    else:
        print(f"❌ Bracket strategy failed: {bracket_result}")

def main():
    """Run all tests"""
    print("BullXAuto Order Check and Coin Name Fix Tests")
    print("=" * 50)
    
    # Note: You need to update the API key and test addresses before running
    print("⚠️  IMPORTANT: Update API key and test addresses before running!")
    print("⚠️  Make sure the BullXAuto server is running on localhost:8000")
    print()
    
    try:
        # Test 1: Coin name fix
        test_coin_name_fix()
        
        # Test 2: Order check functionality
        test_order_check()
        
        # Test 3: Bracket strategy with coin name
        test_bracket_strategy_with_coin_name()
        
        print("\n" + "=" * 50)
        print("All tests completed!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
