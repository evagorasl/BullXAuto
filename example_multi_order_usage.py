"""
Example usage of the new multi-order bracket system for BullXAuto.

This script demonstrates how to:
1. Create multiple orders for a coin with different bracket_ids
2. Replace individual orders when they get fulfilled
3. Query orders by bracket and coin
4. Get order summaries grouped by coin and bracket
"""

import requests
import json
from typing import List, Dict, Any

class BullXAutoMultiOrderClient:
    def __init__(self, base_url: str = "http://localhost:8000", api_key: str = None):
        self.base_url = base_url
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": api_key
        }
    
    def create_multi_order(self, address: str, strategy_number: int, order_type: str, orders: List[Dict]) -> Dict[str, Any]:
        """Create multiple orders for a coin"""
        url = f"{self.base_url}/api/v1/multi-order"
        
        payload = {
            "strategy_number": strategy_number,
            "address": address,
            "order_type": order_type,
            "orders": orders
        }
        
        response = requests.post(url, json=payload, headers=self.headers)
        return response.json()
    
    def replace_order(self, coin_address: str, bracket_id: int, new_order: Dict) -> Dict[str, Any]:
        """Replace an order with the same bracket_id"""
        url = f"{self.base_url}/api/v1/replace-order/{coin_address}/{bracket_id}"
        
        response = requests.post(url, json=new_order, headers=self.headers)
        return response.json()
    
    def get_orders_summary(self) -> Dict[str, Any]:
        """Get summary of all active orders grouped by coin and bracket_id"""
        url = f"{self.base_url}/api/v1/orders-summary"
        
        response = requests.get(url, headers=self.headers)
        return response.json()
    
    def get_next_bracket_id(self, address: str) -> Dict[str, Any]:
        """Get the next available bracket_id for a coin"""
        url = f"{self.base_url}/api/v1/coins/{address}/next-bracket-id"
        
        response = requests.get(url, headers=self.headers)
        return response.json()
    
    def get_bracket_info(self) -> List[Dict[str, Any]]:
        """Get information about market cap brackets"""
        url = f"{self.base_url}/api/v1/brackets"
        
        response = requests.get(url, headers=self.headers)
        return response.json()
    
    def get_coin_orders(self, address: str, status: str = None) -> List[Dict[str, Any]]:
        """Get all orders for a specific coin"""
        url = f"{self.base_url}/api/v1/coins/{address}/orders"
        
        params = {}
        if status:
            params["status"] = status
        
        response = requests.get(url, params=params, headers=self.headers)
        return response.json()

def example_multi_order_workflow():
    """Example workflow demonstrating the multi-order bracket system"""
    
    # Initialize client (replace with your actual API key)
    client = BullXAutoMultiOrderClient(api_key="your_api_key_here")
    
    # Example coin address
    coin_address = "0x1234567890abcdef1234567890abcdef12345678"
    
    print("=== BullXAuto Multi-Order Bracket System Example ===\n")
    
    # 1. Get bracket information
    print("1. Getting bracket information...")
    try:
        brackets = client.get_bracket_info()
        print("Market Cap Brackets:")
        for bracket in brackets:
            print(f"  Bracket {bracket['bracket']}: {bracket['description']} "
                  f"({bracket['min_market_cap']:,.0f} - {bracket['max_market_cap']:,.0f})")
    except Exception as e:
        print(f"Error getting bracket info: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # 2. Create multiple orders for a coin
    print("2. Creating multiple orders for a coin...")
    
    # Define 4 different orders with different price points and amounts
    orders = [
        {
            "bracket_id": 1,
            "entry_price": 0.000001,
            "take_profit": 0.000002,
            "stop_loss": 0.0000008,
            "amount": 1000000
        },
        {
            "bracket_id": 2,
            "entry_price": 0.0000008,
            "take_profit": 0.0000015,
            "stop_loss": 0.0000006,
            "amount": 1500000
        },
        {
            "bracket_id": 3,
            "entry_price": 0.0000006,
            "take_profit": 0.0000012,
            "stop_loss": 0.0000004,
            "amount": 2000000
        },
        {
            "bracket_id": 4,
            "entry_price": 0.0000004,
            "take_profit": 0.000001,
            "stop_loss": 0.0000002,
            "amount": 2500000
        }
    ]
    
    try:
        result = client.create_multi_order(
            address=coin_address,
            strategy_number=1,
            order_type="BUY",
            orders=orders
        )
        
        if result.get("success"):
            print(f"✓ Successfully created {result['total_orders_created']} orders")
            print(f"  Coin: {result['coin']['address']}")
            print(f"  Bracket: {result['coin']['bracket']}")
            print("  Orders created:")
            for order in result['orders']:
                print(f"    - Bracket ID {order['bracket_id']}: Entry ${order['entry_price']:.8f}, "
                      f"TP ${order['take_profit']:.8f}, SL ${order['stop_loss']:.8f}")
        else:
            print(f"❌ Failed to create orders: {result}")
    
    except Exception as e:
        print(f"Error creating multi-order: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # 3. Get orders summary
    print("3. Getting orders summary...")
    try:
        summary = client.get_orders_summary()
        
        if summary.get("success"):
            print(f"Active orders for {summary['total_coins']} coins:")
            
            for address, data in summary['summary'].items():
                coin = data['coin']
                print(f"\n  Coin: {address[:10]}...{address[-8:]}")
                print(f"  Market Cap: ${coin['market_cap']:,.0f}" if coin['market_cap'] else "  Market Cap: Unknown")
                print(f"  Bracket: {coin['bracket']}" if coin['bracket'] else "  Bracket: Unknown")
                print(f"  Active Orders:")
                
                for bracket_id, order in data['orders'].items():
                    print(f"    Bracket {bracket_id}: Entry ${order['entry_price']:.8f}, "
                          f"TP ${order['take_profit']:.8f}, SL ${order['stop_loss']:.8f}")
        else:
            print("No active orders found")
    
    except Exception as e:
        print(f"Error getting orders summary: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # 4. Check next available bracket_id
    print("4. Checking next available bracket_id...")
    try:
        next_bracket = client.get_next_bracket_id(coin_address)
        
        if next_bracket.get("success"):
            if next_bracket['next_bracket_id']:
                print(f"✓ Next available bracket ID: {next_bracket['next_bracket_id']}")
            else:
                print("❌ All bracket IDs (1-4) are currently in use")
        else:
            print(f"Info: {next_bracket['message']}")
    
    except Exception as e:
        print(f"Error checking next bracket ID: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # 5. Replace an order (simulate order fulfillment)
    print("5. Replacing an order (simulating order fulfillment)...")
    
    # Let's say bracket_id 2 order was fulfilled and we want to replace it
    new_order = {
        "bracket_id": 2,  # This will be ignored in the API call, but kept for clarity
        "entry_price": 0.0000007,
        "take_profit": 0.0000014,
        "stop_loss": 0.0000005,
        "amount": 1800000
    }
    
    try:
        replace_result = client.replace_order(
            coin_address=coin_address,
            bracket_id=2,
            new_order=new_order
        )
        
        if replace_result.get("success"):
            print("✓ Order replaced successfully")
            order = replace_result['order']
            print(f"  New Order - Bracket ID {order['bracket_id']}: "
                  f"Entry ${order['entry_price']:.8f}, "
                  f"TP ${order['take_profit']:.8f}, SL ${order['stop_loss']:.8f}")
        else:
            print(f"❌ Failed to replace order: {replace_result}")
    
    except Exception as e:
        print(f"Error replacing order: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # 6. Get specific coin orders
    print("6. Getting all orders for the coin...")
    try:
        coin_orders = client.get_coin_orders(coin_address, status="ACTIVE")
        
        print(f"Active orders for coin {coin_address[:10]}...{coin_address[-8:]}:")
        for order in coin_orders:
            print(f"  Order ID {order['id']} (Bracket {order['bracket_id']}): "
                  f"Entry ${order['entry_price']:.8f}, "
                  f"TP ${order['take_profit']:.8f}, SL ${order['stop_loss']:.8f}")
    
    except Exception as e:
        print(f"Error getting coin orders: {e}")
    
    print("\n" + "="*50)
    print("Example completed!")

def example_bracket_strategy():
    """Example of how to implement different strategies based on market cap brackets"""
    
    def calculate_order_amounts_by_bracket(bracket: int, total_investment: float) -> List[float]:
        """Calculate order amounts based on bracket (market cap category)"""
        
        if bracket == 1:  # Micro Cap (< 100K) - High risk, smaller amounts
            return [
                total_investment * 0.15,  # 15% for bracket_id 1
                total_investment * 0.20,  # 20% for bracket_id 2
                total_investment * 0.25,  # 25% for bracket_id 3
                total_investment * 0.40   # 40% for bracket_id 4
            ]
        
        elif bracket == 2:  # Small Cap (100K - 500K) - Medium risk
            return [
                total_investment * 0.20,  # 20% for bracket_id 1
                total_investment * 0.25,  # 25% for bracket_id 2
                total_investment * 0.25,  # 25% for bracket_id 3
                total_investment * 0.30   # 30% for bracket_id 4
            ]
        
        elif bracket == 3:  # Medium Cap (500K - 1M) - Balanced
            return [
                total_investment * 0.25,  # 25% for each bracket_id
                total_investment * 0.25,
                total_investment * 0.25,
                total_investment * 0.25
            ]
        
        elif bracket == 4:  # Large Cap (1M - 5M) - Lower risk, larger amounts
            return [
                total_investment * 0.30,  # 30% for bracket_id 1
                total_investment * 0.25,  # 25% for bracket_id 2
                total_investment * 0.25,  # 25% for bracket_id 3
                total_investment * 0.20   # 20% for bracket_id 4
            ]
        
        else:  # Mega Cap (> 5M) - Very conservative
            return [
                total_investment * 0.40,  # 40% for bracket_id 1
                total_investment * 0.30,  # 30% for bracket_id 2
                total_investment * 0.20,  # 20% for bracket_id 3
                total_investment * 0.10   # 10% for bracket_id 4
            ]
    
    def calculate_price_levels_by_bracket(bracket: int, current_price: float) -> List[Dict]:
        """Calculate entry, take profit, and stop loss levels based on bracket"""
        
        if bracket == 1:  # Micro Cap - More aggressive
            multipliers = [
                {"entry": 0.90, "tp": 1.50, "sl": 0.80},  # bracket_id 1
                {"entry": 0.85, "tp": 1.75, "sl": 0.75},  # bracket_id 2
                {"entry": 0.80, "tp": 2.00, "sl": 0.70},  # bracket_id 3
                {"entry": 0.75, "tp": 2.50, "sl": 0.65}   # bracket_id 4
            ]
        
        elif bracket == 2:  # Small Cap
            multipliers = [
                {"entry": 0.92, "tp": 1.30, "sl": 0.82},  # bracket_id 1
                {"entry": 0.88, "tp": 1.50, "sl": 0.78},  # bracket_id 2
                {"entry": 0.84, "tp": 1.70, "sl": 0.74},  # bracket_id 3
                {"entry": 0.80, "tp": 2.00, "sl": 0.70}   # bracket_id 4
            ]
        
        elif bracket == 3:  # Medium Cap - Balanced
            multipliers = [
                {"entry": 0.95, "tp": 1.20, "sl": 0.85},  # bracket_id 1
                {"entry": 0.90, "tp": 1.35, "sl": 0.80},  # bracket_id 2
                {"entry": 0.85, "tp": 1.50, "sl": 0.75},  # bracket_id 3
                {"entry": 0.80, "tp": 1.70, "sl": 0.70}   # bracket_id 4
            ]
        
        elif bracket == 4:  # Large Cap - Conservative
            multipliers = [
                {"entry": 0.97, "tp": 1.15, "sl": 0.88},  # bracket_id 1
                {"entry": 0.94, "tp": 1.25, "sl": 0.84},  # bracket_id 2
                {"entry": 0.91, "tp": 1.35, "sl": 0.81},  # bracket_id 3
                {"entry": 0.88, "tp": 1.45, "sl": 0.78}   # bracket_id 4
            ]
        
        else:  # Mega Cap - Very conservative
            multipliers = [
                {"entry": 0.98, "tp": 1.10, "sl": 0.90},  # bracket_id 1
                {"entry": 0.96, "tp": 1.15, "sl": 0.88},  # bracket_id 2
                {"entry": 0.94, "tp": 1.20, "sl": 0.86},  # bracket_id 3
                {"entry": 0.92, "tp": 1.25, "sl": 0.84}   # bracket_id 4
            ]
        
        # Calculate actual prices
        price_levels = []
        for i, mult in enumerate(multipliers):
            price_levels.append({
                "bracket_id": i + 1,
                "entry_price": current_price * mult["entry"],
                "take_profit": current_price * mult["tp"],
                "stop_loss": current_price * mult["sl"]
            })
        
        return price_levels
    
    # Example usage
    print("=== Bracket-Based Strategy Example ===\n")
    
    # Example coin with different market caps
    examples = [
        {"market_cap": 50000, "bracket": 1, "current_price": 0.000001},
        {"market_cap": 250000, "bracket": 2, "current_price": 0.000005},
        {"market_cap": 750000, "bracket": 3, "current_price": 0.00001},
        {"market_cap": 2500000, "bracket": 4, "current_price": 0.00005},
        {"market_cap": 10000000, "bracket": 5, "current_price": 0.0001}
    ]
    
    total_investment = 1000  # $1000 total investment
    
    for example in examples:
        print(f"Market Cap: ${example['market_cap']:,} (Bracket {example['bracket']})")
        print(f"Current Price: ${example['current_price']:.8f}")
        
        # Calculate amounts
        amounts = calculate_order_amounts_by_bracket(example['bracket'], total_investment)
        
        # Calculate price levels
        price_levels = calculate_price_levels_by_bracket(example['bracket'], example['current_price'])
        
        print("Recommended Orders:")
        for i, (amount, levels) in enumerate(zip(amounts, price_levels)):
            print(f"  Bracket ID {levels['bracket_id']}: ${amount:.2f} - "
                  f"Entry ${levels['entry_price']:.8f}, "
                  f"TP ${levels['take_profit']:.8f}, "
                  f"SL ${levels['stop_loss']:.8f}")
        
        print()

if __name__ == "__main__":
    print("Choose an example to run:")
    print("1. Multi-Order Workflow Example")
    print("2. Bracket-Based Strategy Example")
    
    choice = input("Enter your choice (1 or 2): ").strip()
    
    if choice == "1":
        example_multi_order_workflow()
    elif choice == "2":
        example_bracket_strategy()
    else:
        print("Invalid choice. Running both examples...")
        example_multi_order_workflow()
        print("\n" + "="*60 + "\n")
        example_bracket_strategy()
