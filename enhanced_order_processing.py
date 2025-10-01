"""
Enhanced Order Processing System for BullXAuto

This module handles the improved order processing functionality including:
- TP (Take Profit) detection when trigger conditions = "1 SL"
- Order renewal marking and database updates
- BullX entry deletion via XPATH
- Order replacement logic for renewed orders
- Comprehensive logging and output
"""

import asyncio
import logging
import time
from typing import List, Dict, Optional, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from database import db_manager
from chrome_driver import bullx_automator
from bracket_order_placement import bracket_order_manager
from models import Order, Coin
from bracket_config import calculate_bracket, BRACKET_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnhancedOrderProcessor:
    def __init__(self):
        self.automator = bullx_automator
        self.driver_manager = bullx_automator.driver_manager
        self.orders_for_renewal = []  # Track orders marked for renewal
        
    async def process_orders_enhanced(self, profile_name: str) -> Dict:
        """
        Enhanced order processing with TP detection, renewal marking, and order replacement.
        
        Args:
            profile_name: Chrome profile name
            
        Returns:
            Dict with processing results and renewal information
        """
        try:
            logger.info(f"\n{'='*80}")
            logger.info(f"🚀 STARTING ENHANCED ORDER PROCESSING FOR {profile_name.upper()}")
            logger.info(f"{'='*80}")
            
            # Clear previous renewal list
            self.orders_for_renewal = []
            
            # Step 1: Check orders and detect TP conditions
            logger.info("📋 Step 1: Checking orders and detecting TP conditions...")
            check_result = await self._check_orders_with_tp_detection(profile_name)
            
            if not check_result["success"]:
                return {"success": False, "error": check_result["error"]}
            
            # Check if no orders were found
            if check_result.get("no_orders", False):
                logger.info(f"\n{'='*80}")
                logger.info(f"📭 NO ACTIVE ORDERS FOUND FOR {profile_name.upper()}")
                logger.info(f"{'='*80}")
                
                return {
                    "success": True,
                    "profile_name": profile_name,
                    "no_orders": True,
                    "orders_checked": 0,
                    "orders_marked_for_renewal": 0,
                    "orders_replaced": 0,
                    "renewal_details": [],
                    "message": check_result.get("message", "No active orders found"),
                    "summary": "📭 No active orders found on the website. Browser driver closed."
                }
            
            # Step 2: Process orders marked for renewal
            logger.info(f"\n📝 Step 2: Processing {len(self.orders_for_renewal)} orders marked for renewal...")
            renewal_results = await self._process_renewal_orders(profile_name)
            
            # Step 3: Generate comprehensive output
            logger.info("\n📊 Step 3: Generating processing summary...")
            summary = self._generate_processing_summary(check_result, renewal_results)
            
            logger.info(f"\n{'='*80}")
            logger.info(f"✅ ENHANCED ORDER PROCESSING COMPLETED FOR {profile_name.upper()}")
            logger.info(f"{'='*80}")
            
            return {
                "success": True,
                "profile_name": profile_name,
                "orders_checked": check_result.get("total_orders_checked", 0),
                "orders_marked_for_renewal": len(self.orders_for_renewal),
                "orders_replaced": renewal_results.get("orders_replaced", 0),
                "renewal_details": renewal_results.get("renewal_details", []),
                "summary": summary
            }
            
        except Exception as e:
            logger.error(f"💥 Enhanced order processing failed for {profile_name}: {e}")
            return {"success": False, "error": str(e)}
    
    async def _check_orders_with_tp_detection(self, profile_name: str) -> Dict:
        """
        Check orders and detect TP conditions (trigger conditions = "1 SL").
        Group by coin and batch delete operations.
        """
        try:
            logger.info(f"🔍 Checking orders for TP detection...")
            
            # Use existing order checking functionality
            result = self.automator.check_orders(profile_name)
            
            if not result["success"]:
                error_message = result.get("error", "Order check failed")
                
                # Check if the error indicates no active orders
                if "No buttons found with the specified selector" in error_message:
                    logger.info("📭 No active orders found on the website")
                    
                    # Close the driver gracefully
                    try:
                        self.driver_manager.close_driver(profile_name)
                        logger.info(f"🔒 Closed browser driver for {profile_name}")
                    except Exception as close_error:
                        logger.warning(f"⚠️  Could not close driver: {close_error}")
                    
                    return {
                        "success": True,
                        "no_orders": True,
                        "total_orders_checked": 0,
                        "tp_detected_count": 0,
                        "orders_for_renewal": 0,
                        "message": "No active orders found on the website"
                    }
                
                return {"success": False, "error": error_message}
            
            total_orders_checked = 0
            tp_detected_count = 0
            
            # Group orders by coin for batch processing
            orders_by_coin = {}
            deletion_queue = []  # Store deletion operations to batch by coin
            
            # Process each button's order information
            for button_info in result["order_info"]:
                button_index = button_info.get("button_index", "Unknown")
                rows = button_info.get("rows", [])
                
                logger.info(f"📋 Processing Button {button_index}: {len(rows)} rows")
                
                for row_index, row in enumerate(rows):
                    try:
                        total_orders_checked += 1
                        
                        # Parse row data
                        parsed_data = self._parse_row_data(row)
                        if not parsed_data:
                            continue
                        
                        token = parsed_data.get('token', 'Unknown')
                        trigger_condition = parsed_data.get('trigger_condition', '')
                        
                        logger.info(f"  🔸 Row {row_index + 1}: {token} - Trigger: {trigger_condition}")
                        
                        # Group orders by coin
                        if token not in orders_by_coin:
                            orders_by_coin[token] = []
                        orders_by_coin[token].append({
                            'parsed_data': parsed_data,
                            'button_index': button_index,
                            'row_index': row_index + 1,
                            'is_tp': self._is_tp_condition(trigger_condition)
                        })
                        
                        if self._is_tp_condition(trigger_condition):
                            tp_detected_count += 1
                        
                    except Exception as e:
                        logger.error(f"    💥 Error processing row {row_index + 1}: {e}")
            
            # Process each coin's orders
            for token, coin_orders in orders_by_coin.items():
                await self._process_coin_orders(profile_name, token, coin_orders)
            
            logger.info(f"✅ Order check completed: {total_orders_checked} orders checked, {tp_detected_count} TP conditions detected")
            
            return {
                "success": True,
                "total_orders_checked": total_orders_checked,
                "tp_detected_count": tp_detected_count,
                "orders_for_renewal": len(self.orders_for_renewal)
            }
            
        except Exception as e:
            logger.error(f"💥 Error in TP detection: {e}")
            return {"success": False, "error": str(e)}
    
    async def _process_coin_orders(self, profile_name: str, token: str, coin_orders: List[Dict]):
        """Process all orders for a specific coin, including missing order identification"""
        try:
            logger.info(f"\n🪙 Processing {len(coin_orders)} orders for {token}:")
            
            # Find coin in database
            coin = self._find_coin_by_token(token)
            if not coin:
                logger.warning(f"  ❌ Could not find coin for token: {token}")
                return
            
            # Check if we have less than 4 orders and identify missing ones
            if len(coin_orders) < 4:
                await self._identify_missing_orders(coin, coin_orders, profile_name)
            
            # Process TP conditions and prepare for deletion
            tp_orders = []
            for order_info in coin_orders:
                if order_info['is_tp']:
                    logger.info(f"  🎯 TP DETECTED in row {order_info['row_index']}!")
                    
                    # Identify the order in database
                    order_match = self._identify_order(order_info['parsed_data'], profile_name)
                    
                    if order_match and order_match.get('order'):
                        tp_orders.append({
                            'order': order_match['order'],
                            'order_info': order_info,
                            'coin': coin
                        })
                    else:
                        logger.warning(f"    ❌ Could not identify order in database for renewal")
            
            # Batch delete BullX entries for this coin
            if tp_orders:
                logger.info(f"  🗑️  Batch deleting {len(tp_orders)} BullX entries for {token}...")
                await self._batch_delete_bullx_entries(profile_name, tp_orders)
            
        except Exception as e:
            logger.error(f"💥 Error processing coin orders for {token}: {e}")
    
    async def _identify_missing_orders(self, coin: Coin, coin_orders: List[Dict], profile_name: str):
        """Identify which bracket orders are missing for a coin"""
        try:
            logger.info(f"  📊 Analyzing missing orders for {coin.name or coin.address} ({len(coin_orders)}/4 orders found):")
            
            # Get bracket configuration
            if not coin.bracket or coin.bracket not in BRACKET_CONFIG:
                logger.warning(f"    ❌ No valid bracket found for coin")
                return
            
            bracket_config = BRACKET_CONFIG[coin.bracket]
            bracket_entries = bracket_config['entries']  # [entry1, entry2, entry3, entry4]
            
            # Get active orders from database for this coin
            db_orders = db_manager.get_orders_by_coin(coin.id)
            active_db_orders = [o for o in db_orders if o.profile_name == profile_name and o.status == "ACTIVE"]
            
            # Find which bracket IDs are present in database
            present_bracket_ids = {order.bracket_id for order in active_db_orders}
            all_bracket_ids = {1, 2, 3, 4}
            missing_bracket_ids = all_bracket_ids - present_bracket_ids
            
            if missing_bracket_ids:
                logger.info(f"    📋 Database shows missing bracket IDs: {sorted(missing_bracket_ids)}")
                for bracket_id in sorted(missing_bracket_ids):
                    entry_price = bracket_entries[bracket_id - 1]  # Convert to 0-based index
                    logger.info(f"      - Bracket ID {bracket_id}: Entry ${entry_price:,.0f}")
            else:
                logger.info(f"    ✅ All 4 bracket orders present in database")
            
            # Compare with BullX orders
            logger.info(f"    📋 BullX shows {len(coin_orders)} orders for this coin")
            
        except Exception as e:
            logger.error(f"Error identifying missing orders: {e}")
    
    async def _batch_delete_bullx_entries(self, profile_name: str, tp_orders: List[Dict]):
        """Batch delete BullX entries for TP orders of a specific coin"""
        try:
            successful_deletions = []
            coin_name = tp_orders[0]['coin'].name if tp_orders else "Unknown"
            
            for i, tp_order in enumerate(tp_orders):
                order = tp_order['order']
                order_info = tp_order['order_info']
                coin = tp_order['coin']
                
                logger.info(f"    📝 Processing order {order.id} for deletion ({i+1}/{len(tp_orders)})...")
                
                # Re-click the filter button for this coin before each deletion
                # This ensures we have the correct view and row indices after previous deletions
                filter_success = await self._click_coin_filter_button(profile_name, order_info['button_index'])
                
                if not filter_success:
                    logger.error(f"    ❌ Failed to click filter button for {coin_name} - skipping deletion")
                    continue
                
                # Try to delete entry from BullX
                deletion_success = await self._delete_bullx_entry(
                    profile_name, 
                    order_info['button_index'], 
                    order_info['row_index']
                )
                
                if deletion_success:
                    # Only update database if BullX deletion succeeded
                    db_update_success = db_manager.update_order_status(order.id, "COMPLETED")
                    
                    if db_update_success:
                        logger.info(f"    ✅ Successfully processed order {order.id}")
                        
                        # Add to renewal list
                        renewal_info = {
                            'order_id': order.id,
                            'coin_address': coin.address,
                            'coin_name': coin.name,
                            'parsed_data': order_info['parsed_data'],
                            'button_index': order_info['button_index'],
                            'row_index': order_info['row_index'],
                            'original_bracket': coin.bracket,
                            'bracket_sub_id': order.bracket_id,
                            'profile_name': order.profile_name,
                            'amount': order.amount or 1.0
                        }
                        
                        self.orders_for_renewal.append(renewal_info)
                        successful_deletions.append(order.id)
                    else:
                        logger.error(f"    ❌ Database update failed for order {order.id}")
                else:
                    logger.error(f"    ❌ BullX deletion failed for order {order.id}")
            
            logger.info(f"  ✅ Successfully processed {len(successful_deletions)} orders for deletion")
            
        except Exception as e:
            logger.error(f"💥 Error in batch delete: {e}")
    
    async def _click_coin_filter_button(self, profile_name: str, button_index: int) -> bool:
        """Click the filter button for a specific coin to refresh the view"""
        try:
            driver = self.driver_manager.get_driver(profile_name)
            
            # Find the button using the button_index from the original order checking
            # This corresponds to the filter buttons that were clicked during order checking
            button_selector = "button.ant-btn.ant-btn-text.ant-btn-sm.\\!px-1"
            
            logger.info(f"    🔄 Re-clicking filter button {button_index} to refresh view...")
            
            try:
                # Find all filter buttons
                buttons = driver.find_elements(By.CSS_SELECTOR, button_selector)
                
                if button_index <= len(buttons):
                    target_button = buttons[button_index - 1]  # Convert to 0-based index
                    
                    # Find the grandparent element to click (same as in background_tasks.py)
                    grandParent = target_button.find_element(By.XPATH, '../..')
                    
                    # Scroll into view if needed
                    driver.execute_script("arguments[0].scrollIntoView(true);", grandParent)
                    time.sleep(0.5)
                    
                    # Click the filter button
                    grandParent.click()
                    logger.info(f"    ✅ Successfully clicked filter button {button_index}")
                    
                    # Wait for the view to refresh
                    time.sleep(1)
                    
                    return True
                else:
                    logger.error(f"    ❌ Button index {button_index} out of range (found {len(buttons)} buttons)")
                    return False
                    
            except Exception as e:
                logger.error(f"    💥 Error clicking filter button {button_index}: {e}")
                return False
                
        except Exception as e:
            logger.error(f"    💥 Error in click_coin_filter_button: {e}")
            return False
    
    def _parse_row_data(self, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse row data to extract order information"""
        try:
            main_text = row.get("main_text", "")
            href = row.get("href", "")
            
            if not main_text:
                return None
            
            # Split the main text by newlines to get individual data points
            lines = main_text.strip().split('\n')
            lines = [line.strip() for line in lines if line.strip()]
            
            if len(lines) < 10:
                logger.warning(f"Row has fewer than expected columns: {len(lines)}")
            
            # Parse according to BullX order structure
            parsed = {
                'raw_text': main_text,
                'href': href,
                'side': lines[0] if len(lines) > 0 else "",
                'type': lines[1] if len(lines) > 1 else "",
                'token': lines[2] if len(lines) > 2 else "",
                'order_amount': lines[3] if len(lines) > 3 else "",
                'cost': lines[4] if len(lines) > 4 else "",
                'avg_exec': lines[5] if len(lines) > 5 else "",
                'expiry': lines[6] if len(lines) > 6 else "",
                'wallets': lines[7] if len(lines) > 7 else "",
                'transactions': lines[8] if len(lines) > 8 else "",
                'trigger_condition': lines[9] if len(lines) > 9 else "",
                'status': lines[10] if len(lines) > 10 else ""
            }
            
            return parsed
            
        except Exception as e:
            logger.error(f"Error parsing row data: {e}")
            return None
    
    def _is_tp_condition(self, trigger_condition: str) -> bool:
        """
        Check if trigger condition indicates TP has been met.
        According to requirements: trigger conditions = "1 SL" means TP has been met.
        """
        return trigger_condition.strip() == "1 SL"
    
    def _identify_order(self, parsed_data: Dict[str, Any], profile_name: str) -> Optional[Dict[str, Any]]:
        """Identify which database order corresponds to this row"""
        try:
            token = parsed_data.get('token', '')
            entry_price = parsed_data.get('entry_price')
            
            if not token:
                return None
            
            # Find coin by token name
            coin = self._find_coin_by_token(token)
            if not coin:
                logger.warning(f"Could not find coin for token: {token}")
                return None
            
            # Use stored bracket from coin, or calculate from market_cap if not available
            stored_bracket = coin.bracket
            if not stored_bracket:
                if coin.market_cap and coin.market_cap > 0:
                    # Calculate bracket from stored market_cap
                    from bracket_config import calculate_bracket
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
                sub_id = self._match_entry_to_sub_id(entry_price, bracket_entries)
            
            # If we couldn't match by entry price, try to find by other means
            if not sub_id:
                # For fulfilled orders, we might need to check existing orders
                if parsed_data.get('order_status') == 'FULFILLED':
                    sub_id = self._find_fulfilled_order_sub_id(coin.id, profile_name, parsed_data)
                else:
                    # For orders without entry price, try to match any ACTIVE order
                    all_orders = db_manager.get_orders_by_coin(coin.id)
                    matching_orders = [o for o in all_orders if o.profile_name == profile_name and o.status == "ACTIVE"]
                    if matching_orders:
                        # Return the first matching order as a fallback
                        return {
                            'order': matching_orders[0],
                            'coin': coin,
                            'bracket': stored_bracket,
                            'sub_id': matching_orders[0].bracket_id,
                            'entry_price': entry_price,
                            'bracket_entries': bracket_entries
                        }
            
            # Find order in database if we have sub_id
            order = None
            if sub_id:
                order = self._get_order_by_coin_sub_id(coin.id, sub_id, profile_name)
            
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
    
    def _find_coin_by_token(self, token: str) -> Optional[Coin]:
        """Find coin by token name"""
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
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding coin by token '{token}': {e}")
            return None
    
    def _match_entry_to_sub_id(self, entry_price: float, bracket_entries: List[float]) -> Optional[int]:
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
    
    def _find_fulfilled_order_sub_id(self, coin_id: int, profile_name: str, parsed_data: Dict[str, Any]) -> Optional[int]:
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
    
    def _get_order_by_coin_sub_id(self, coin_id: int, sub_id: int, profile_name: str) -> Optional[Order]:
        """Get order by coin_id, sub_id, and profile_name"""
        try:
            orders = db_manager.get_orders_by_coin(coin_id)
            for order in orders:
                if (order.bracket_id == sub_id and 
                    order.profile_name == profile_name and 
                    order.status == "ACTIVE"):  # Only check ACTIVE orders
                    return order
            return None
            
        except Exception as e:
            logger.error(f"Error getting order by coin/sub_id: {e}")
            return None
    
    async def _mark_order_for_renewal(self, order: Order, parsed_data: Dict[str, Any], 
                                    button_index: int, row_index: int):
        """Mark order for renewal and update database - only if BullX deletion succeeds"""
        try:
            logger.info(f"    📝 Processing order {order.id} for renewal...")
            
            # First, get coin information safely
            coin = self._get_coin_safely(order)
            if not coin:
                logger.error(f"    ❌ Could not find coin for order {order.id}")
                return
            
            logger.info(f"    🪙 Found coin: {coin.name or coin.address} (Bracket: {coin.bracket})")
            
            # Try to delete entry from BullX first
            deletion_success = await self._delete_bullx_entry(order.profile_name, button_index, row_index)
            
            if not deletion_success:
                logger.error(f"    ❌ BullX deletion failed - skipping database update for order {order.id}")
                return
            
            # Only update database if BullX deletion succeeded
            logger.info(f"    📝 BullX deletion successful - updating database for order {order.id}")
            db_update_success = db_manager.update_order_status(order.id, "COMPLETED")
            
            if not db_update_success:
                logger.error(f"    ❌ Database update failed for order {order.id}")
                return
            
            logger.info(f"    ✅ Updated order {order.id} status to COMPLETED")
            
            # Add to renewal list with additional information
            renewal_info = {
                'order_id': order.id,  # Store ID instead of object to avoid session issues
                'coin_address': coin.address,
                'coin_name': coin.name,
                'parsed_data': parsed_data,
                'button_index': button_index,
                'row_index': row_index,
                'original_bracket': coin.bracket,
                'bracket_sub_id': order.bracket_id,
                'profile_name': order.profile_name,
                'amount': order.amount or 1.0
            }
            
            self.orders_for_renewal.append(renewal_info)
            
            logger.info(f"    ✅ Order {order.id} successfully marked for renewal")
            
        except Exception as e:
            logger.error(f"    💥 Error marking order for renewal: {e}")
            import traceback
            logger.error(f"    💥 Traceback: {traceback.format_exc()}")
    
    def _get_coin_safely(self, order: Order) -> Optional[Coin]:
        """Safely get coin information without session issues"""
        try:
            # Method 1: Try to get coin by coin_id directly
            from database import SessionLocal
            db = SessionLocal()
            try:
                from models import Coin
                coin = db.query(Coin).filter(Coin.id == order.coin_id).first()
                if coin:
                    # Create a detached copy to avoid session issues
                    coin_data = {
                        'id': coin.id,
                        'name': coin.name,
                        'address': coin.address,
                        'bracket': coin.bracket,
                        'market_cap': coin.market_cap
                    }
                    db.expunge(coin)  # Detach from session
                    return coin
            finally:
                db.close()
            
            # Method 2: Fallback - try to access the relationship if it's already loaded
            try:
                if hasattr(order, 'coin') and order.coin:
                    coin_address = order.coin.address
                    return db_manager.get_coin_by_address(coin_address)
            except Exception as e:
                logger.debug(f"Could not access order.coin relationship: {e}")
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting coin safely: {e}")
            return None
    
    async def _delete_bullx_entry(self, profile_name: str, button_index: int, row_index: int) -> bool:
        """Delete entry from BullX using the specified XPATH"""
        try:
            driver = self.driver_manager.get_driver(profile_name)
            
            # Construct the XPATH for the specific row
            xpath = f"//*[@id='root']/div[1]/div[2]/main/div/section/div[2]/div[2]/div/div/div/div[1]/a[{row_index}]/div[11]/div/button"
            
            logger.info(f"    🗑️  Deleting BullX entry for row {row_index}")
            
            try:
                # Wait for the element to be clickable
                delete_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                
                # Scroll into view if needed
                driver.execute_script("arguments[0].scrollIntoView(true);", delete_button)
                time.sleep(0.5)
                
                # Click the button
                delete_button.click()
                logger.info(f"    ✅ Successfully clicked delete button for row {row_index}")
                
                # Wait for deletion to process
                time.sleep(1)
                
                return True
                
            except TimeoutException:
                logger.error(f"    ❌ Delete button not found or not clickable for row {row_index}")
                return False
            except Exception as e:
                logger.error(f"    💥 Error clicking delete button: {e}")
                return False
                
        except Exception as e:
            logger.error(f"    💥 Error deleting BullX entry: {e}")
            return False
    
    async def _process_renewal_orders(self, profile_name: str) -> Dict:
        """Process all orders marked for renewal and create new orders"""
        try:
            if not self.orders_for_renewal:
                logger.info("📝 No orders marked for renewal")
                return {"orders_replaced": 0, "renewal_details": []}
            
            logger.info(f"📝 Processing {len(self.orders_for_renewal)} orders for renewal...")
            
            renewal_details = []
            orders_replaced = 0
            
            # Group orders by coin for better organization
            orders_by_coin = {}
            for renewal_info in self.orders_for_renewal:
                coin_address = renewal_info['coin_address']
                if coin_address not in orders_by_coin:
                    orders_by_coin[coin_address] = []
                orders_by_coin[coin_address].append(renewal_info)
            
            # Process each coin's renewal orders
            for coin_address, coin_renewals in orders_by_coin.items():
                try:
                    # Get coin info from first renewal
                    first_renewal = coin_renewals[0]
                    coin_name = first_renewal['coin_name']
                    original_bracket = first_renewal['original_bracket']
                    
                    logger.info(f"\n🪙 Processing renewals for {coin_name or coin_address}:")
                    logger.info(f"   Original Bracket: {original_bracket}")
                    logger.info(f"   Orders to replace: {len(coin_renewals)}")
                    
                    coin_renewal_details = {
                        'coin_address': coin_address,
                        'coin_name': coin_name,
                        'original_bracket': original_bracket,
                        'orders_to_replace': [],
                        'new_orders_created': []
                    }
                    
                    # Process each order renewal for this coin
                    for renewal_info in coin_renewals:
                        try:
                            order_id = renewal_info['order_id']
                            bracket_sub_id = renewal_info['bracket_sub_id']
                            amount = renewal_info['amount']
                            
                            logger.info(f"   🔄 Replacing order: ID {order_id}, Bracket Sub ID {bracket_sub_id}")
                            
                            # Add to replacement details
                            coin_renewal_details['orders_to_replace'].append({
                                'order_id': order_id,
                                'bracket_sub_id': bracket_sub_id,
                                'amount': amount
                            })
                            
                            # Create new order using bracket_order_placement
                            new_order_result = await self._create_replacement_order(
                                profile_name, coin_address, bracket_sub_id, amount
                            )
                            
                            if new_order_result["success"]:
                                orders_replaced += 1
                                coin_renewal_details['new_orders_created'].append(new_order_result)
                                logger.info(f"   ✅ Successfully created replacement order")
                            else:
                                logger.error(f"   ❌ Failed to create replacement order: {new_order_result.get('error')}")
                                
                        except Exception as e:
                            logger.error(f"   💥 Error processing renewal for order {renewal_info['order_id']}: {e}")
                    
                    renewal_details.append(coin_renewal_details)
                    
                except Exception as e:
                    logger.error(f"💥 Error processing renewals for coin {coin_address}: {e}")
            
            return {
                "orders_replaced": orders_replaced,
                "renewal_details": renewal_details
            }
            
        except Exception as e:
            logger.error(f"💥 Error processing renewal orders: {e}")
            return {"orders_replaced": 0, "renewal_details": [], "error": str(e)}
    
    async def _create_replacement_order(self, profile_name: str, coin_address: str, 
                                      bracket_sub_id: int, amount: float) -> Dict:
        """Create a replacement order using bracket_order_placement"""
        try:
            logger.info(f"      🔨 Creating replacement order for bracket sub ID {bracket_sub_id}...")
            
            # Use bracket_order_manager to replace the specific order
            result = bracket_order_manager.replace_order(
                profile_name=profile_name,
                address=coin_address,
                bracket_id=bracket_sub_id,
                new_amount=amount,
                strategy_number=1  # Default strategy number
            )
            
            if result["success"]:
                logger.info(f"      ✅ Replacement order created successfully")
                return {
                    "success": True,
                    "bracket_sub_id": bracket_sub_id,
                    "order_details": result.get("order", {})
                }
            else:
                logger.error(f"      ❌ Failed to create replacement order: {result.get('error')}")
                return {
                    "success": False,
                    "bracket_sub_id": bracket_sub_id,
                    "error": result.get("error")
                }
                
        except Exception as e:
            logger.error(f"      💥 Error creating replacement order: {e}")
            return {
                "success": False,
                "bracket_sub_id": bracket_sub_id,
                "error": str(e)
            }
    
    def _generate_processing_summary(self, check_result: Dict, renewal_results: Dict) -> str:
        """Generate comprehensive processing summary"""
        try:
            summary_lines = []
            summary_lines.append("📊 ENHANCED ORDER PROCESSING SUMMARY")
            summary_lines.append("=" * 50)
            
            # Order checking summary
            total_checked = check_result.get("total_orders_checked", 0)
            tp_detected = check_result.get("tp_detected_count", 0)
            summary_lines.append(f"📋 Orders Checked: {total_checked}")
            summary_lines.append(f"🎯 TP Conditions Detected: {tp_detected}")
            
            # Renewal summary
            orders_replaced = renewal_results.get("orders_replaced", 0)
            summary_lines.append(f"🔄 Orders Replaced: {orders_replaced}")
            
            # Detailed renewal information
            renewal_details = renewal_results.get("renewal_details", [])
            if renewal_details:
                summary_lines.append("\n🪙 COINS WITH RENEWED ORDERS:")
                for coin_detail in renewal_details:
                    coin_name = coin_detail.get('coin_name', 'Unknown')
                    coin_address = coin_detail.get('coin_address', 'Unknown')
                    original_bracket = coin_detail.get('original_bracket', 'Unknown')
                    orders_to_replace = coin_detail.get('orders_to_replace', [])
                    new_orders = coin_detail.get('new_orders_created', [])
                    
                    summary_lines.append(f"  • {coin_name} ({coin_address})")
                    summary_lines.append(f"    Bracket: {original_bracket}")
                    summary_lines.append(f"    Orders Replaced: {len(orders_to_replace)}")
                    
                    for order_info in orders_to_replace:
                        bracket_sub_id = order_info.get('bracket_sub_id', 'Unknown')
                        summary_lines.append(f"      - Bracket Sub ID {bracket_sub_id}")
                    
                    successful_new_orders = [o for o in new_orders if o.get('success')]
                    summary_lines.append(f"    New Orders Created: {len(successful_new_orders)}")
            
            return "\n".join(summary_lines)
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return f"Summary generation failed: {str(e)}"


# Global instance for easy access
enhanced_order_processor = EnhancedOrderProcessor()

# Convenience function for external use
async def process_orders_enhanced(profile_name: str) -> Dict:
    """
    Main entry point for enhanced order processing.
    
    Args:
        profile_name: Chrome profile name
        
    Returns:
        Dict with processing results
    """
    return await enhanced_order_processor.process_orders_enhanced(profile_name)
