import asyncio
import logging
import re
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from database import db_manager
from chrome_driver import bullx_automator
from typing import List, Dict, Optional, Any
from models import Order
from bracket_config import BRACKET_CONFIG, calculate_bracket
from enhanced_order_processing import process_orders_enhanced

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OrderMonitor:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
        self.monitored_profiles = set()
    
    async def start_monitoring_for_profile(self, profile_name: str):
        """Start background order monitoring for a specific profile"""
        if not self.is_running:
            self.scheduler.start()
            self.is_running = True
            logger.info("Order monitoring scheduler started")
        
        # Add profile-specific job if not already monitoring this profile
        job_id = f'order_checker_{profile_name}'
        if profile_name not in self.monitored_profiles:
            self.scheduler.add_job(
                self.check_orders_enhanced,
                trigger=IntervalTrigger(minutes=5),
                args=[profile_name],
                id=job_id,
                name=f'Check Orders Status for {profile_name}',
                replace_existing=True
            )
            self.monitored_profiles.add(profile_name)
            logger.info(f"Order monitoring started for profile {profile_name} - checking every 5 minutes")
    
    async def stop_monitoring_for_profile(self, profile_name: str):
        """Stop background order monitoring for a specific profile"""
        job_id = f'order_checker_{profile_name}'
        try:
            self.scheduler.remove_job(job_id)
            self.monitored_profiles.discard(profile_name)
            logger.info(f"Order monitoring stopped for profile {profile_name}")
        except Exception as e:
            logger.error(f"Error stopping monitoring for profile {profile_name}: {e}")
    
    async def start_monitoring(self):
        """Start the background order monitoring (deprecated - use start_monitoring_for_profile)"""
        logger.warning("start_monitoring() is deprecated. Use start_monitoring_for_profile(profile_name) instead.")
        # For backward compatibility, we'll start monitoring for all profiles
        profiles = self._get_all_profiles()
        for profile_name in profiles:
            await self.start_monitoring_for_profile(profile_name)
    
    async def stop_monitoring(self):
        """Stop the background order monitoring"""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("Order monitoring stopped")
    
    async def check_orders(self, profile_name: str):
        """Check active orders for a specific profile by navigating to automation page and extracting information"""
        try:
            logger.info(f"Starting order check for profile: {profile_name}")
            
            # Use chrome_driver directly to get order information
            try:
                logger.info(f"Checking orders for profile: {profile_name}")
                
                # Use the chrome_driver check_orders function directly
                result = bullx_automator.check_orders(profile_name)
                
                if result["success"]:
                    logger.info(f"Successfully processed {result['total_buttons']} buttons for {profile_name}")
                    
                    # Process the extracted order information
                    await self.process_order_information(profile_name, result["order_info"])
                    
                else:
                    logger.error(f"Order check failed for {profile_name}: {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                logger.error(f"Error checking orders for profile {profile_name}: {e}")
            
            # Also check individual active orders from database for this profile
            active_orders = db_manager.get_active_orders_by_profile(profile_name)
            logger.info(f"Also checking {len(active_orders)} active orders from database for {profile_name}")
            
            for order in active_orders:
                await self.check_single_order(order)
            
            # Close the driver when done
            try:
                from chrome_driver import chrome_driver_manager
                chrome_driver_manager.close_driver(profile_name)
                logger.info(f"Closed Chrome driver for profile: {profile_name}")
            except Exception as e:
                logger.error(f"Error closing driver for profile {profile_name}: {e}")
                
        except Exception as e:
            logger.error(f"Error in check_orders for profile {profile_name}: {e}")
    
    async def check_orders_enhanced(self, profile_name: str):
        """Enhanced order checking with TP detection, renewal marking, and order replacement"""
        try:
            logger.info(f"Starting ENHANCED order check for profile: {profile_name}")
            
            # Use the enhanced order processing system
            result = await process_orders_enhanced(profile_name)
            
            if result["success"]:
                logger.info(f"✅ Enhanced order processing completed for {profile_name}")
                logger.info(f"📊 Summary:")
                logger.info(f"   Orders Checked: {result.get('orders_checked', 0)}")
                logger.info(f"   Orders Marked for Renewal: {result.get('orders_marked_for_renewal', 0)}")
                logger.info(f"   Orders Replaced: {result.get('orders_replaced', 0)}")
                
                # Print detailed summary
                summary = result.get('summary', '')
                if summary:
                    logger.info(f"\n{summary}")
                
                return result
            else:
                logger.error(f"❌ Enhanced order processing failed for {profile_name}: {result.get('error')}")
                return result
                
        except Exception as e:
            logger.error(f"💥 Error in enhanced order check for profile {profile_name}: {e}")
            return {"success": False, "error": str(e)}
    
    def _get_all_profiles(self) -> List[str]:
        """Get all profile names from database"""
        try:
            # Get all profiles from database
            profiles = []
            saruman_profile = db_manager.get_profile_by_name("Saruman")
            gandalf_profile = db_manager.get_profile_by_name("Gandalf")
            
            if saruman_profile:
                profiles.append("Saruman")
            if gandalf_profile:
                profiles.append("Gandalf")
            
            return profiles
        except Exception as e:
            logger.error(f"Error getting profiles: {e}")
            return ["Saruman", "Gandalf"]  # Fallback to default profiles
    
    async def process_order_information(self, profile_name: str, order_info: list):
        """Enhanced processing of extracted order information with identification and status updates"""
        try:
            print(f"\n{'='*60}")
            print(f"🔍 PROCESSING ORDER INFORMATION FOR {profile_name.upper()}")
            print(f"{'='*60}")
            logger.info(f"=== Processing Order Information for {profile_name} ===")
            
            # Track all processed orders for missing order analysis
            processed_orders = {}  # {coin_address: {bracket_id: order_data}}
            total_rows_processed = 0
            
            for button_info in order_info:
                button_index = button_info.get("button_index", "Unknown")
                rows = button_info.get("rows", [])
                
                print(f"\n📋 Button {button_index}: Found {len(rows)} rows")
                logger.info(f"Processing button {button_index} with {len(rows)} rows")
                
                for row_index, row in enumerate(rows):
                    try:
                        total_rows_processed += 1
                        print(f"\n  🔸 Row {row_index + 1}:")
                        
                        # Phase 1: Parse row data
                        parsed_data = self.parse_row_data(row)
                        
                        if not parsed_data:
                            print(f"    ❌ Could not parse row data")
                            logger.warning(f"  Row {row_index + 1}: Could not parse row data")
                            continue
                        
                        # Print parsed data for verification
                        print(f"    🏷️  Side: {parsed_data.get('side', 'N/A')} | Type: {parsed_data.get('type', 'N/A')}")
                        print(f"    🪙 Token: {parsed_data.get('token', 'N/A')}")
                        print(f"    💰 Amount: {parsed_data.get('order_amount', 'N/A')}")
                        print(f"    ⏰ Expiry: {parsed_data.get('expiry', 'N/A')}")
                        print(f"    🎯 Trigger: {parsed_data.get('trigger_condition', 'N/A')}")
                        print(f"    📊 Status: {parsed_data.get('order_status', 'N/A')}")
                        if parsed_data.get('entry_price'):
                            print(f"    💵 Entry Price: ${parsed_data.get('entry_price'):,.0f}")
                        
                        # Phase 2: Identify order
                        order_match = self.identify_order(parsed_data, profile_name)
                        
                        # Phase 3: Update order status if matched
                        if order_match and order_match.get('order'):
                            self.update_order_status(order_match['order'], parsed_data)
                            
                            # Track processed order
                            coin_address = order_match['coin'].address
                            sub_id = order_match['sub_id']
                            
                            if coin_address not in processed_orders:
                                processed_orders[coin_address] = {}
                            processed_orders[coin_address][sub_id] = {
                                'order': order_match['order'],
                                'parsed_data': parsed_data,
                                'coin': order_match['coin']
                            }
                            
                            print(f"    ✅ Order Found: ID {order_match['order'].id}, Bracket {order_match['bracket']}, Sub ID {sub_id}")
                        else:
                            print(f"    ❌ No matching order found in database")
                        
                        # Phase 4: Log identification results
                        self.log_order_identification(row_index + 1, parsed_data, order_match)
                        
                    except Exception as e:
                        print(f"    💥 Error processing row: {e}")
                        logger.error(f"Error processing row {row_index + 1} in button {button_index}: {e}")
            
            # Phase 5: Analyze missing orders
            print(f"\n{'='*60}")
            print(f"📊 SUMMARY: Processed {total_rows_processed} total rows")
            await self.analyze_missing_orders(profile_name, processed_orders)
            print(f"{'='*60}\n")
                        
        except Exception as e:
            print(f"💥 ERROR: {e}")
            logger.error(f"Error processing order information for {profile_name}: {e}")
    
    def parse_row_data(self, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse row data to extract order information"""
        try:
            main_text = row.get("main_text", "")
            href = row.get("href", "")
            
            if not main_text:
                return None
            
            # Split the main text by newlines first to get individual data points
            lines = main_text.strip().split('\n')
            
            # Remove empty lines
            lines = [line.strip() for line in lines if line.strip()]
            
            if len(lines) < 10:
                logger.warning(f"Row has fewer than expected columns: {len(lines)}")
                logger.debug(f"Raw text: {main_text}")
                logger.debug(f"Lines: {lines}")
            
            # Column mapping based on user specification and the real data structure:
            # From the example: Auto, Sell, STIMMY, 257.29K STIMMY, +0, $0, 00h 00m 00s, 1, 0/0, 1 TP, 1 SL, Active
            # This maps to: side, type, token, amount, cost, avg exec, expiry, wallets, transactions, trigger condition, status
            parsed = {
                'raw_text': main_text,
                'href': href,
                'side': lines[0] if len(lines) > 0 else "",  # "Auto"
                'type': lines[1] if len(lines) > 1 else "",  # "Sell", "Buy Limit", etc.
                'token': lines[2] if len(lines) > 2 else "",  # "STIMMY"
                'order_amount': lines[3] if len(lines) > 3 else "",  # "257.29K STIMMY"
                'cost': lines[4] if len(lines) > 4 else "",  # "+0"
                'avg_exec': lines[5] if len(lines) > 5 else "",  # "$0"
                'expiry': lines[6] if len(lines) > 6 else "",  # "00h 00m 00s"
                'wallets': lines[7] if len(lines) > 7 else "",  # "1"
                'transactions': lines[8] if len(lines) > 8 else "",  # "0/0"
                'trigger_condition': lines[9] if len(lines) > 9 else "",  # "1 TP, 1 SL"
                'status': lines[10] if len(lines) > 10 else ""  # "Active"
            }
            
            # Determine order status based on conditions
            parsed['order_status'] = self.determine_order_status(parsed)
            
            # Extract entry price from trigger condition if available
            parsed['entry_price'] = self.extract_entry_price(parsed['trigger_condition'])
            
            return parsed
            
        except Exception as e:
            logger.error(f"Error parsing row data: {e}")
            return None
    
    def determine_order_status(self, parsed_data: Dict[str, Any]) -> str:
        """Determine order status based on parsed data"""
        try:
            order_amount = parsed_data.get('order_amount', '')
            trigger_condition = parsed_data.get('trigger_condition', '')
            expiry = parsed_data.get('expiry', '')
            token = parsed_data.get('token', '')
            
            # Check if expired
            if expiry == "00h 00m 00s":
                return "EXPIRED"
            
            # Check if fulfilled
            if trigger_condition == "1 TP, 1 SL":
                return "FULFILLED"
            
            # Check if order amount includes token name (fulfilled)
            if token and token.lower() in order_amount.lower():
                return "FULFILLED"
            
            # Check if pending (Buy below pattern)
            if trigger_condition.startswith("Buy below"):
                return "PENDING"
            
            return "UNKNOWN"
            
        except Exception as e:
            logger.error(f"Error determining order status: {e}")
            return "UNKNOWN"
    
    def extract_entry_price(self, trigger_condition: str) -> Optional[float]:
        """Extract entry price from trigger condition like 'Buy below $13.1k'"""
        try:
            if not trigger_condition or not trigger_condition.startswith("Buy below"):
                return None
            
            # Extract number from patterns like "$13.1k", "$131k", "$1.31M"
            price_match = re.search(r'\$([0-9]+\.?[0-9]*)(k|K|m|M|b|B)?', trigger_condition)
            if not price_match:
                return None
            
            number = float(price_match.group(1))
            suffix = price_match.group(2)
            
            if suffix:
                suffix = suffix.lower()
                if suffix == 'k':
                    number *= 1000
                elif suffix == 'm':
                    number *= 1000000
                elif suffix == 'b':
                    number *= 1000000000
            
            return number
            
        except Exception as e:
            logger.error(f"Error extracting entry price from '{trigger_condition}': {e}")
            return None
    
    def identify_order(self, parsed_data: Dict[str, Any], profile_name: str) -> Optional[Dict[str, Any]]:
        """Identify which database order corresponds to this row (read-only)"""
        try:
            token = parsed_data.get('token', '')
            entry_price = parsed_data.get('entry_price')
            
            if not token:
                return None
            
            # Find coin by token name (try different approaches)
            coin = self.find_coin_by_token(token)
            if not coin:
                logger.warning(f"Could not find coin for token: {token}")
                return None
            
            # Use stored bracket from coin, or calculate from market_cap if not available
            stored_bracket = coin.bracket
            if not stored_bracket:
                if coin.market_cap and coin.market_cap > 0:
                    # Calculate bracket from stored market_cap
                    stored_bracket = calculate_bracket(coin.market_cap)
                    # Update coin with calculated bracket
                    db_manager.create_or_update_coin(
                        address=coin.address,
                        data={"bracket": stored_bracket}
                    )
                    logger.info(f"Calculated and stored bracket {stored_bracket} for coin {coin.name or coin.address} based on market_cap ${coin.market_cap:,.0f}")
                else:
                    logger.warning(f"No bracket or market_cap stored for coin {coin.name or coin.address}")
                    return None
            
            # Get bracket configuration entries for stored bracket
            if stored_bracket not in BRACKET_CONFIG:
                logger.error(f"Invalid bracket {stored_bracket} for coin {coin.name or coin.address}")
                return None
            
            bracket_config = BRACKET_CONFIG[stored_bracket]
            bracket_entries = bracket_config['entries']  # [entry1, entry2, entry3, entry4]
            
            # Match entry price to sub_id (1-4) if we have entry price
            sub_id = None
            if entry_price:
                sub_id = self.match_entry_to_sub_id(entry_price, bracket_entries)
            
            # If we couldn't match by entry price, try to find by other means
            if not sub_id:
                # For fulfilled orders, we might need to check existing orders
                if parsed_data.get('order_status') == 'FULFILLED':
                    sub_id = self.find_fulfilled_order_sub_id(coin.id, profile_name, parsed_data)
            
            # Find order in database if we have sub_id
            order = None
            if sub_id:
                order = self.get_order_by_coin_sub_id(coin.id, sub_id, profile_name)
            
            return {
                'order': order,
                'coin': coin,
                'bracket': stored_bracket,  # Coin's bracket
                'sub_id': sub_id,          # Order's sub ID within the bracket
                'entry_price': entry_price,
                'bracket_entries': bracket_entries
            }
            
        except Exception as e:
            logger.error(f"Error identifying order: {e}")
            return None
    
    def find_coin_by_token(self, token: str) -> Optional[Any]:
        """Find coin by token name using various approaches"""
        try:
            # Try exact name match first
            coin = db_manager.get_coin_by_name(token)
            if coin:
                return coin
            
            # Try partial name match
            all_coins = db_manager.get_all_coins()
            for coin in all_coins:
                if coin.name and token.lower() in coin.name.lower():
                    return coin
                if coin.address and token.lower() in coin.address.lower():
                    return coin
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding coin by token '{token}': {e}")
            return None
    
    def match_entry_to_sub_id(self, entry_price: float, bracket_entries: List[float]) -> Optional[int]:
        """Match entry price to sub_id (1-4) based on bracket configuration"""
        try:
            # bracket_entries = [entry1, entry2, entry3, entry4] for sub_ids [1, 2, 3, 4]
            tolerance = 1000  # Allow 1000 unit tolerance for matching
            
            for i, bracket_entry in enumerate(bracket_entries):
                if abs(entry_price - bracket_entry) <= tolerance:
                    return i + 1  # sub_id is 1-based
            
            logger.warning(f"Could not match entry price {entry_price} to any bracket entry in {bracket_entries}")
            return None
            
        except Exception as e:
            logger.error(f"Error matching entry price to sub_id: {e}")
            return None
    
    def find_fulfilled_order_sub_id(self, coin_id: int, profile_name: str, parsed_data: Dict[str, Any]) -> Optional[int]:
        """Try to find sub_id for fulfilled orders by checking active orders"""
        try:
            # Get all active orders for this coin and profile
            active_orders = db_manager.get_orders_by_coin(coin_id)
            active_orders = [o for o in active_orders if o.profile_name == profile_name and o.status == "ACTIVE"]
            
            # This is a placeholder - you might need more sophisticated logic
            # to match fulfilled orders to specific sub_ids
            return None
            
        except Exception as e:
            logger.error(f"Error finding fulfilled order sub_id: {e}")
            return None
    
    def get_order_by_coin_sub_id(self, coin_id: int, sub_id: int, profile_name: str) -> Optional[Any]:
        """Get order by coin_id, sub_id, and profile_name"""
        try:
            orders = db_manager.get_orders_by_coin(coin_id)
            for order in orders:
                if (order.bracket_id == sub_id and 
                    order.profile_name == profile_name and 
                    order.status == "ACTIVE"):
                    return order
            return None
            
        except Exception as e:
            logger.error(f"Error getting order by coin/sub_id: {e}")
            return None
    
    def update_order_status(self, order: Any, parsed_data: Dict[str, Any]) -> None:
        """Update order status in database based on parsed data"""
        try:
            order_status = parsed_data.get('order_status')
            
            # Only update if status has changed and is a final status
            if order_status in ['FULFILLED', 'EXPIRED'] and order.status != order_status:
                db_manager.update_order_status(order.id, order_status)
                logger.info(f"Updated order {order.id} status to {order_status}")
                
        except Exception as e:
            logger.error(f"Error updating order status: {e}")
    
    def log_order_identification(self, row_number: int, parsed_data: Dict[str, Any], order_match: Optional[Dict[str, Any]]) -> None:
        """Log order identification results for console output"""
        try:
            token = parsed_data.get('token', 'Unknown')
            order_status = parsed_data.get('order_status', 'Unknown')
            entry_price = parsed_data.get('entry_price')
            trigger_condition = parsed_data.get('trigger_condition', '')
            
            if order_match and order_match.get('order'):
                order = order_match['order']
                coin = order_match['coin']
                sub_id = order_match['sub_id']
                bracket = order_match['bracket']
                
                logger.info(f"  Row {row_number}: {token} → Coin ID: {coin.id}, Bracket: {bracket}")
                logger.info(f"    Trigger: {trigger_condition} → Entry: {entry_price} → Sub ID: {sub_id}")
                logger.info(f"    Status: {order_status} → Order Found: Yes (ID: {order.id})")
            else:
                logger.info(f"  Row {row_number}: {token} → Status: {order_status}")
                logger.info(f"    Trigger: {trigger_condition} → Entry: {entry_price}")
                logger.info(f"    Order Found: No")
                
        except Exception as e:
            logger.error(f"Error logging order identification: {e}")
    
    async def analyze_missing_orders(self, profile_name: str, processed_orders: Dict[str, Dict[int, Any]]) -> None:
        """Analyze and report missing orders for each coin"""
        try:
            logger.info(f"\n=== Missing Orders Analysis for {profile_name} ===")
            
            for coin_address, bracket_orders in processed_orders.items():
                coin = list(bracket_orders.values())[0]['coin']  # Get coin from first order
                stored_bracket = coin.bracket
                
                if not stored_bracket or stored_bracket not in BRACKET_CONFIG:
                    continue
                
                # Check which bracket_ids (1-4) are missing
                found_bracket_ids = set(bracket_orders.keys())
                all_bracket_ids = {1, 2, 3, 4}
                missing_bracket_ids = all_bracket_ids - found_bracket_ids
                
                if missing_bracket_ids:
                    bracket_config = BRACKET_CONFIG[stored_bracket]
                    entries = bracket_config['entries']
                    
                    logger.info(f"Token: {coin.name or coin.address} (Bracket {stored_bracket})")
                    logger.info(f"  Found Orders: Bracket IDs {sorted(found_bracket_ids)}")
                    
                    missing_details = []
                    for bracket_id in sorted(missing_bracket_ids):
                        entry_price = entries[bracket_id - 1]  # Convert to 0-based index
                        missing_details.append(f"Bracket ID {bracket_id} (Entry: ${entry_price:,.0f})")
                    
                    logger.info(f"  Missing Orders: {', '.join(missing_details)}")
                else:
                    logger.info(f"Token: {coin.name or coin.address} → All 4 bracket orders found")
            
            if not processed_orders:
                logger.info("No orders found in the processed data")
                
        except Exception as e:
            logger.error(f"Error analyzing missing orders: {e}")
    
    async def check_single_order(self, order: Order):
        """Check a single order status and re-enter if completed"""
        try:
            # This is a placeholder for actual order status checking
            # You'll need to implement the actual logic based on BullX UI
            
            # For now, we'll simulate checking order status
            order_status = await self.get_order_status_from_bullx(order)
            
            if order_status in ["COMPLETED", "STOPPED"]:
                logger.info(f"Order {order.id} has {order_status}, re-entering...")
                
                # Update order status in database
                db_manager.update_order_status(order.id, order_status)
                
                # Calculate new parameters based on current market cap
                new_params = await self.calculate_new_order_parameters(order)
                
                if new_params:
                    # Place new order
                    success = bullx_automator.execute_strategy(
                        profile_name=order.profile_name,
                        strategy_number=order.strategy_number,
                        address=order.address,
                        order_type=order.order_type,
                        entry_price=new_params['entry_price'],
                        take_profit=new_params['take_profit'],
                        stop_loss=new_params['stop_loss']
                    )
                    
                    if success:
                        logger.info(f"Successfully re-entered order for {order.address}")
                    else:
                        logger.error(f"Failed to re-enter order for {order.address}")
                        
        except Exception as e:
            logger.error(f"Error checking order {order.id}: {e}")
    
    async def get_order_status_from_bullx(self, order: Order) -> str:
        """Get order status from BullX interface"""
        try:
            # This is a placeholder implementation
            # You'll need to implement actual order status checking based on BullX UI
            
            # For now, we'll return ACTIVE (you can implement actual checking later)
            return "ACTIVE"
            
            # Example implementation (to be customized based on actual BullX UI):
            # driver = bullx_automator.driver_manager.get_driver(order.profile_name)
            # 
            # # Navigate to orders page
            # driver.get("https://neo.bullx.io/orders")  # Adjust URL as needed
            # 
            # # Find the specific order by ID or other identifier
            # order_element = driver.find_element(By.CSS_SELECTOR, f"[data-order-id='{order.order_id_bullx}']")
            # 
            # # Get status from the element
            # status_element = order_element.find_element(By.CSS_SELECTOR, ".order-status")
            # status = status_element.text.upper()
            # 
            # return status
            
        except Exception as e:
            logger.error(f"Error getting order status for order {order.id}: {e}")
            return "UNKNOWN"
    
    async def calculate_new_order_parameters(self, order: Order) -> dict:
        """Calculate new order parameters based on current market conditions and NEW bracket"""
        try:
            # Get current market cap
            current_market_cap = bullx_automator.get_market_cap(order.profile_name)
            
            if current_market_cap == 0:
                logger.error(f"Could not get market cap for {order.address}")
                return None
            
            # Calculate NEW bracket based on current market cap
            new_bracket = calculate_bracket(current_market_cap)
            
            # Update coin's bracket in database if it changed
            coin = db_manager.get_coin_by_address(order.coin.address)
            if coin and coin.bracket != new_bracket:
                db_manager.create_or_update_coin(
                    address=coin.address,
                    data={"bracket": new_bracket, "market_cap": current_market_cap}
                )
                logger.info(f"Updated coin {coin.name or coin.address} bracket from {coin.bracket} to {new_bracket}")
            
            # Get bracket configuration for NEW bracket
            if new_bracket not in BRACKET_CONFIG:
                logger.error(f"Invalid new bracket {new_bracket} for current market cap {current_market_cap}")
                return None
            
            bracket_config = BRACKET_CONFIG[new_bracket]
            bracket_entries = bracket_config['entries']  # [entry1, entry2, entry3, entry4]
            
            # Use the same bracket_id position but with NEW bracket's entry price
            bracket_id = order.bracket_id  # Keep same position (1-4)
            new_entry_price = bracket_entries[bracket_id - 1]  # Convert to 0-based index
            
            # Calculate take profit and stop loss based on NEW bracket strategy
            from bracket_config import TAKE_PROFIT_PERCENTAGES
            take_profit_multiplier = TAKE_PROFIT_PERCENTAGES[bracket_id - 1]
            new_take_profit = new_entry_price + (new_entry_price * take_profit_multiplier)
            
            # Stop loss is the same for all orders in the bracket
            new_stop_loss = bracket_config['stop_loss_market_cap']
            
            new_params = {
                'entry_price': new_entry_price,
                'take_profit': new_take_profit,
                'stop_loss': new_stop_loss,
                'market_cap': current_market_cap,
                'bracket': new_bracket
            }
            
            logger.info(f"Calculated new parameters for order {order.id}:")
            logger.info(f"  Old bracket: {coin.bracket if coin else 'Unknown'} → New bracket: {new_bracket}")
            logger.info(f"  Entry: ${new_entry_price:,.0f}, TP: ${new_take_profit:,.0f}, SL: ${new_stop_loss:,.0f}")
            
            return new_params
            
        except Exception as e:
            logger.error(f"Error calculating new parameters for order {order.id}: {e}")
            return None
    

# Global order monitor instance
order_monitor = OrderMonitor()

async def start_background_tasks():
    """Start all background tasks"""
    await order_monitor.start_monitoring()

async def stop_background_tasks():
    """Stop all background tasks"""
    await order_monitor.stop_monitoring()

async def start_background_tasks_for_profile(profile_name: str):
    """Start background tasks for a specific profile"""
    await order_monitor.start_monitoring_for_profile(profile_name)

async def stop_background_tasks_for_profile(profile_name: str):
    """Stop background tasks for a specific profile"""
    await order_monitor.stop_monitoring_for_profile(profile_name)

async def check_orders_for_profile(profile_name: str):
    """Manually trigger order check for a specific profile"""
    await order_monitor.check_orders(profile_name)

async def check_orders_enhanced_for_profile(profile_name: str):
    """Manually trigger enhanced order check for a specific profile"""
    return await order_monitor.check_orders_enhanced(profile_name)
