"""
Example usage of the Bracket Order Placement System for BullXAuto.

This script demonstrates how to:
1. Execute a complete bracket strategy for a coin
2. Replace individual bracket orders
3. Preview bracket orders before placing them
4. Handle different market cap scenarios
"""

import logging
from bracket_order_placement import bracket_order_manager
from bracket_config import calculate_bracket, get_bracket_info

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def example_bracket_strategy_execution():
    """Example of executing a complete bracket strategy"""
    
    print("=== Bracket Strategy Execution Example ===\n")
    
    # Configuration
    profile_name = "Saruman"  # Your Chrome profile name
    token_address = "0x1234567890abcdef1234567890abcdef12345678"  # Example token address
    total_investment = 1000.0  # $1000 total investment
    strategy_number = 1
    
    print(f"Profile: {profile_name}")
    print(f"Token: {token_address}")
    print(f"Total Investment: ${total_investment}")
    print(f"Strategy Number: {strategy_number}\n")
    
    try:
        # Execute the bracket strategy
        result = bracket_order_manager.execute_bracket_strategy(
            profile_name=profile_name,
            address=token_address,
            total_amount=total_investment,
            strategy_number=strategy_number
        )
        
        if result["success"]:
            print("✓ Bracket strategy executed successfully!")
            print(f"  Bracket: {result['bracket']}")
            print(f"  Current Market Cap: ${result['current_market_cap']:,.0f}")
            print(f"  Orders Placed: {result['total_placed']}")
            print(f"  Orders Failed: {result['total_failed']}")
            
            print("\nPlaced Orders:")
            for order in result["placed_orders"]:
                print(f"  Bracket {order['bracket_id']} ({order['order_type']}):")
                print(f"    Strategy: {order['strategy_name']}")
                print(f"    Entry MC: ${order['entry_market_cap']:,.0f}")
                print(f"    Take Profit MC: ${order['take_profit_market_cap']:,.0f}")
                print(f"    Stop Loss MC: ${order['stop_loss_market_cap']:,.0f}")
                print(f"    Amount: ${order['amount']:.2f}")
                print()
            
            if result["failed_orders"]:
                print("Failed Orders:")
                for failed in result["failed_orders"]:
                    print(f"  Bracket {failed['bracket_id']}: {failed['error']}")
        else:
            print(f"❌ Failed to execute bracket strategy: {result['error']}")
    
    except Exception as e:
        print(f"❌ Error executing bracket strategy: {e}")

def example_order_replacement():
    """Example of replacing a specific bracket order"""
    
    print("=== Order Replacement Example ===\n")
    
    # Configuration
    profile_name = "Saruman"
    token_address = "0x1234567890abcdef1234567890abcdef12345678"
    bracket_id_to_replace = 2  # Replace bracket order 2
    new_amount = 500.0  # New investment amount for this order
    strategy_number = 1
    
    print(f"Replacing bracket order {bracket_id_to_replace} with new amount: ${new_amount}")
    
    try:
        result = bracket_order_manager.replace_order(
            profile_name=profile_name,
            address=token_address,
            bracket_id=bracket_id_to_replace,
            new_amount=new_amount,
            strategy_number=strategy_number
        )
        
        if result["success"]:
            print("✓ Order replaced successfully!")
            order = result["order"]
            print(f"  Bracket ID: {order['bracket_id']}")
            print(f"  Order Type: {order['order_type']}")
            print(f"  Strategy: {order['strategy_name']}")
            print(f"  Entry MC: ${order['entry_market_cap']:,.0f}")
            print(f"  Take Profit MC: ${order['take_profit_market_cap']:,.0f}")
            print(f"  Stop Loss MC: ${order['stop_loss_market_cap']:,.0f}")
            print(f"  Amount: ${order['amount']:.2f}")
        else:
            print(f"❌ Failed to replace order: {result['error']}")
    
    except Exception as e:
        print(f"❌ Error replacing order: {e}")

def example_bracket_preview():
    """Example of previewing bracket orders before placing them"""
    
    print("=== Bracket Preview Example ===\n")
    
    # Configuration
    token_address = "0x1234567890abcdef1234567890abcdef12345678"
    total_investment = 2000.0  # $2000 total investment
    profile_name = "Saruman"  # Optional: to get current market cap
    
    print(f"Previewing bracket orders for: {token_address}")
    print(f"Total Investment: ${total_investment}")
    
    try:
        preview = bracket_order_manager.get_bracket_preview(
            address=token_address,
            total_amount=total_investment,
            profile_name=profile_name  # Optional
        )
        
        if preview["success"]:
            print("✓ Bracket preview generated successfully!")
            print(f"  Bracket: {preview['bracket']}")
            print(f"  Current Market Cap: ${preview['current_market_cap']:,.0f}")
            print(f"  Bracket Description: {preview['bracket_info']['description']}")
            print(f"  Total Amount: ${preview['total_amount']}")
            
            print("\nProposed Orders:")
            for order in preview["orders"]:
                print(f"  Bracket {order['bracket_id']} ({order['order_type']}):")
                print(f"    Strategy: {order['strategy_name']}")
                print(f"    Entry MC: ${order['entry_price']:,.0f}")
                print(f"    Take Profit MC: ${order['take_profit']:,.0f}")
                print(f"    Stop Loss MC: ${order['stop_loss']:,.0f}")
                print(f"    Amount: ${order['amount']:.2f} ({order['trade_size_pct']*100:.1f}%)")
                print(f"    TP Multiplier: {order['take_profit_pct']*100:.0f}%")
                print()
        else:
            print(f"❌ Failed to generate preview: {preview['error']}")
    
    except Exception as e:
        print(f"❌ Error generating preview: {e}")

def example_market_cap_scenarios():
    """Example showing different market cap scenarios and their bracket assignments"""
    
    print("=== Market Cap Scenarios Example ===\n")
    
    # Different market cap scenarios
    scenarios = [
        {"name": "Micro Cap", "market_cap": 50000},
        {"name": "Small Cap", "market_cap": 300000},
        {"name": "Medium Cap", "market_cap": 5000000},
        {"name": "Large Cap", "market_cap": 50000000},
        {"name": "Mega Cap", "market_cap": 500000000}
    ]
    
    total_investment = 1000.0
    
    for scenario in scenarios:
        market_cap = scenario["market_cap"]
        bracket = calculate_bracket(market_cap)
        bracket_info = get_bracket_info(bracket)
        
        print(f"{scenario['name']} - Market Cap: ${market_cap:,.0f}")
        print(f"  Assigned Bracket: {bracket}")
        print(f"  Description: {bracket_info['description']}")
        print(f"  Stop Loss MC: ${bracket_info['stop_loss_market_cap']:,.0f}")
        
        # Show entry points for this bracket
        entries = bracket_info['entries']
        print(f"  Entry Points:")
        for i, entry in enumerate(entries, 1):
            order_type = "MARKET" if market_cap < entry else "LIMIT"
            print(f"    Bracket {i}: ${entry:,.0f} ({order_type})")
        
        print()

def example_strategy_naming():
    """Example showing how strategy names are generated"""
    
    print("=== Strategy Naming Example ===\n")
    
    brackets = [1, 2, 3, 4, 5]
    bracket_ids = [1, 2, 3, 4]
    
    print("Strategy naming convention: Bracket{bracket}_{bracket_id}")
    print("Examples:")
    
    for bracket in brackets:
        bracket_info = get_bracket_info(bracket)
        print(f"\nBracket {bracket} ({bracket_info['description']}):")
        
        for bracket_id in bracket_ids:
            strategy_name = f"Bracket{bracket}_{bracket_id}"
            print(f"  Order {bracket_id}: {strategy_name}")

def interactive_example():
    """Interactive example allowing user to input their own parameters"""
    
    print("=== Interactive Bracket Order Example ===\n")
    
    try:
        # Get user input
        profile_name = input("Enter your Chrome profile name (default: Saruman): ").strip() or "Saruman"
        token_address = input("Enter token contract address: ").strip()
        
        if not token_address:
            print("Token address is required!")
            return
        
        total_amount_str = input("Enter total investment amount (default: 1000): ").strip() or "1000"
        total_amount = float(total_amount_str)
        
        strategy_number_str = input("Enter strategy number (default: 1): ").strip() or "1"
        strategy_number = int(strategy_number_str)
        
        # Ask what to do
        print("\nWhat would you like to do?")
        print("1. Preview bracket orders")
        print("2. Execute bracket strategy")
        print("3. Replace specific order")
        
        choice = input("Enter your choice (1-3): ").strip()
        
        if choice == "1":
            print("\nGenerating preview...")
            preview = bracket_order_manager.get_bracket_preview(
                address=token_address,
                total_amount=total_amount,
                profile_name=profile_name
            )
            
            if preview["success"]:
                print(f"\nBracket {preview['bracket']} orders for ${total_amount}:")
                for order in preview["orders"]:
                    print(f"  {order['strategy_name']}: ${order['amount']:.2f} ({order['order_type']})")
            else:
                print(f"Preview failed: {preview['error']}")
        
        elif choice == "2":
            confirm = input(f"\nExecute bracket strategy for {token_address} with ${total_amount}? (y/N): ")
            if confirm.lower() == 'y':
                print("Executing bracket strategy...")
                result = bracket_order_manager.execute_bracket_strategy(
                    profile_name=profile_name,
                    address=token_address,
                    total_amount=total_amount,
                    strategy_number=strategy_number
                )
                
                if result["success"]:
                    print(f"✓ Successfully placed {result['total_placed']} orders!")
                else:
                    print(f"❌ Failed: {result['error']}")
            else:
                print("Cancelled.")
        
        elif choice == "3":
            bracket_id_str = input("Enter bracket ID to replace (1-4): ").strip()
            bracket_id = int(bracket_id_str)
            
            new_amount_str = input("Enter new amount: ").strip()
            new_amount = float(new_amount_str)
            
            print(f"Replacing bracket order {bracket_id}...")
            result = bracket_order_manager.replace_order(
                profile_name=profile_name,
                address=token_address,
                bracket_id=bracket_id,
                new_amount=new_amount,
                strategy_number=strategy_number
            )
            
            if result["success"]:
                print("✓ Order replaced successfully!")
            else:
                print(f"❌ Failed: {result['error']}")
        
        else:
            print("Invalid choice!")
    
    except KeyboardInterrupt:
        print("\nCancelled by user.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("BullXAuto Bracket Order Placement Examples")
    print("=" * 50)
    
    print("\nChoose an example to run:")
    print("1. Bracket Strategy Execution")
    print("2. Order Replacement")
    print("3. Bracket Preview")
    print("4. Market Cap Scenarios")
    print("5. Strategy Naming")
    print("6. Interactive Example")
    print("7. Run All Examples")
    
    try:
        choice = input("\nEnter your choice (1-7): ").strip()
        
        if choice == "1":
            example_bracket_strategy_execution()
        elif choice == "2":
            example_order_replacement()
        elif choice == "3":
            example_bracket_preview()
        elif choice == "4":
            example_market_cap_scenarios()
        elif choice == "5":
            example_strategy_naming()
        elif choice == "6":
            interactive_example()
        elif choice == "7":
            print("Running all examples...\n")
            example_bracket_strategy_execution()
            print("\n" + "="*60 + "\n")
            example_order_replacement()
            print("\n" + "="*60 + "\n")
            example_bracket_preview()
            print("\n" + "="*60 + "\n")
            example_market_cap_scenarios()
            print("\n" + "="*60 + "\n")
            example_strategy_naming()
        else:
            print("Invalid choice!")
    
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Error: {e}")
