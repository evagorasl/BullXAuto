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

# Get logger (configured at application level in main.py)
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
        """Process all orders for a specific coin, including missing order identification and processing"""
        try:
            logger.info(f"\n🪙 Processing {len(coin_orders)} orders for {token}:")
            
            # Find coin in database
            coin = self._find_coin_by_token(token)
            if not coin:
                logger.warning(f"  ❌ Could not find coin for token: {token}")
                return
            
            # Check if we have less than 4 orders and identify missing ones
            missing_orders = []
            if len(coin_orders) < 4:
                missing_orders = await self._identify_missing_orders(coin, coin_orders, profile_name)
            
            # Process TP conditions and prepare for deletion
            tp_orders = []
            for order_info in coin_orders:
                if order_info['is_tp']:
                    logger.info(f" 🎯 TP DETECTED in row {order_info['row_index']}!")
                    
                    # Identify the order in database
                    order_match = self._identify_order(order_info['parsed_data'], profile_name)
                    
                    if order_match and order_match.get('order'):
                        tp_orders.append({
                            'order': order_match['order'],
                            'order_info': order_info,
                            'coin': coin
                        })
                    else:
                        logger.warning(f" ❌ Could not identify order in database for renewal")
            
            # Process missing orders (mark for renewal without BullX deletion)
            if missing_orders:
                logger.info(f"  🔄 Processing {len(missing_orders)} missing orders for renewal...")
                await self._process_missing_orders(profile_name, missing_orders)
            
            # Batch delete BullX entries for TP orders only
            if tp_orders:
                logger.info(f"  🗑️  Batch deleting {len(tp_orders)} BullX entries for {token}...")
                await self._batch_delete_bullx_entries(profile_name, tp_orders)
            
        except Exception as e:
            logger.error(f"💥 Error processing coin orders for {token}: {e}")
    
    async def _identify_missing_orders(self, coin: Coin, coin_orders: List[Dict], profile_name: str) -> List[Dict]:
        """
        Identify which bracket orders are missing for a coin and return missing order data.
        
        Returns:
            List of missing order dictionaries with order info for renewal
        """
        try:
            logger.info(f"  📊 Analyzing missing orders for {coin.name or coin.address} ({len(coin_orders)}/4 orders found):")
            
            # Get bracket configuration
            if not coin.bracket or coin.bracket not in BRACKET_CONFIG:
                logger.warning(f"    ❌ No valid bracket found for coin")
                return []
            
            bracket_config = BRACKET_CONFIG[coin.bracket]
            bracket_entries = bracket_config['entries']  # [entry1, entry2, entry3, entry4]
            
            # Get active orders from database for this coin
            db_orders = db_manager.get_orders_by_coin(coin.id)
            active_db_orders = [o for o in db_orders if o.profile_name == profile_name and o.status == "ACTIVE"]
            
            # Find which bracket IDs are present in BullX (from parsed orders)
            bullx_bracket_ids = set()
            for order_info in coin_orders:
                parsed_data = order_info.get('parsed_data', {})
                # Try to identify bracket_id from parsed data
                order_match = self._identify_order(parsed_data, profile_name)
                if order_match and order_match.get('sub_id'):
                    bullx_bracket_ids.add(order_match['sub_id'])
            
            # Find which bracket IDs are present in database
            db_bracket_ids = {order.bracket_id for order in active_db_orders}
            
            # Find orders that are in database but missing from BullX
            missing_bracket_ids = db_bracket_ids - bullx_bracket_ids
            
            missing_orders = []
            
            if missing_bracket_ids:
                logger.info(f"    🚨 MISSING ORDERS DETECTED!")
                logger.info(f"    📋 Database has bracket IDs: {sorted(db_bracket_ids)}")
                logger.info(f"    📋 BullX shows bracket IDs: {sorted(bullx_bracket_ids)}")
                logger.info(f"    ❌ Missing bracket IDs: {sorted(missing_bracket_ids)}")
                
                # Find the actual database orders that are missing
                for bracket_id in missing_bracket_ids:
                    missing_db_order = None
                    for db_order in active_db_orders:
                        if db_order.bracket_id == bracket_id:
                            missing_db_order = db_order
                            break
                    
                    if missing_db_order:
                        entry_price = bracket_entries[bracket_id - 1]  # Convert to 0-based index
                        logger.info(f"      🔍 Missing Bracket ID {bracket_id}: Entry ${entry_price:,.0f} (Order ID: {missing_db_order.id})")
                        
                        # Create missing order info for renewal processing
                        missing_order_info = {
                            'order': missing_db_order,
                            'coin': coin,
                            'bracket_id': bracket_id,
                            'is_missing': True,
                            'reason': 'Order present in database but missing from BullX'
                        }
                        missing_orders.append(missing_order_info)
                        
            else:
                logger.info(f"    ✅ All database orders found on BullX")
            
            # Compare with BullX orders
            logger.info(f"    📋 BullX shows {len(coin_orders)} orders, Database has {len(active_db_orders)} active orders")
            
            return missing_orders
            
        except Exception as e:
            logger.error(f"Error identifying missing orders: {e}")
            return []
    
    async def _process_missing_orders(self, profile_name: str, missing_orders: List[Dict]):
        """Process missing orders by marking them for renewal without BullX deletion"""
        try:
            logger.info(f"    🔄 Processing {len(missing_orders)} missing orders...")
            
            for missing_order_info in missing_orders:
                order = missing_order_info['order']
                coin = missing_order_info['coin']
                bracket_id = missing_order_info['bracket_id']
                reason = missing_order_info['reason']
                
                logger.info(f"      📝 Processing missing order ID {order.id} (Bracket Sub ID {bracket_id})")
                logger.info(f"         Reason: {reason}")
                
                # Update database status to COMPLETED (since it's missing from BullX)
                db_update_success = db_manager.update_order_status(order.id, "COMPLETED")
                
                if db_update_success:
                    logger.info(f"      ✅ Updated missing order {order.id} status to COMPLETED")
                    
                    # Add to renewal list (using original bracket from the order's coin)
                    renewal_info = {
                        'order_id': order.id,
                        'coin_address': coin.address,
                        'coin_name': coin.name,
                        'parsed_data': {'token': coin.name or 'Unknown', 'reason': reason},
                        'button_index': 0,  # Not applicable for missing orders
                        'row_index': 0,     # Not applicable for missing orders
                        'original_bracket': coin.bracket,  # Use original bracket from coin
                        'bracket_sub_id': bracket_id,
                        'profile_name': order.profile_name,
                        'amount': order.amount or 1.0,
                        'is_missing_order': True
                    }
                    
                    self.orders_for_renewal.append(renewal_info)
                    logger.info(f"      ✅ Missing order {order.id} marked for renewal")
                    
                else:
                    logger.error(f"      ❌ Failed to update missing order {order.id} status")
                    
        except Exception as e:
            logger.error(f"💥 Error processing missing orders: {e}")
    
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
    
    def _parse_trigger_condition_entry_price(self, trigger_condition: str) -> Optional[float]:
        """
        Parse trigger condition to extract entry price.
        
        Examples:
        - "Buy below $231K" -> 231000.0
        - "Buy below $93.1K" -> 93100.0
        - "Buy below $1.5M" -> 1500000.0
        - "1 SL" -> None (TP condition)
        
        Returns:
            Entry price as float, or None if not parseable
        """
        try:
            import re
            
            if not trigger_condition or trigger_condition.strip() == "1 SL":
                return None
            
            # Look for pattern like "Buy below $XXX.XK" or "Buy below $XXXM"
            pattern = r'Buy below \$([0-9]+(?:\.[0-9]+)?)(K|k|M|m|B|b)?'
            match = re.search(pattern, trigger_condition)
            
            if not match:
                logger.debug(f"Could not parse trigger condition: '{trigger_condition}'")
                return None
            
            number_str = match.group(1)
            suffix = match.group(2)
            
            try:
                number = float(number_str)
                
                if suffix:
                    suffix_lower = suffix.lower()
                    if suffix_lower == 'k':
                        number *= 1000
                    elif suffix_lower == 'm':
                        number *= 1000000
                    elif suffix_lower == 'b':
                        number *= 1000000000
                
                logger.debug(f"Parsed trigger condition '{trigger_condition}' -> ${number:,.0f}")
                return number
                
            except ValueError:
                logger.debug(f"Could not convert number '{number_str}' to float")
                return None
                
        except Exception as e:
            logger.error(f"Error parsing trigger condition '{trigger_condition}': {e}")
            return None
    
    def _identify_order(self, parsed_data: Dict[str, Any], profile_name: str) -> Optional[Dict[str, Any]]:
        """Enhanced order identification with trigger condition storage and expiry time matching"""
        try:
            token = parsed_data.get('token', '')
            trigger_condition = parsed_data.get('trigger_condition', '')
            expiry = parsed_data.get('expiry', '')
            
            if not token:
                logger.debug(f"No token found in parsed data")
                return None
            
            logger.info(f"🔍 IDENTIFYING ORDER:")
            logger.info(f"   Token: {token}")
            logger.info(f"   Trigger: {trigger_condition}")
            logger.info(f"   Expiry: {expiry}")
            
            # Find coin by token name
            coin = self._find_coin_by_token(token)
            if not coin:
                logger.info(f"   ❌ Could not find coin for token: {token}")
                return None
            
            logger.info(f"   ✅ Found coin: {coin.name or coin.address} (ID: {coin.id})")
            
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
                    logger.info(f"   📊 Calculated and stored bracket {stored_bracket} based on market_cap ${coin.market_cap:,.0f}")
                else:
                    logger.warning(f"   ❌ No bracket or market_cap stored for coin")
                    return None
            
            # Get bracket configuration entries for stored bracket
            if stored_bracket not in BRACKET_CONFIG:
                logger.error(f"   ❌ Invalid bracket {stored_bracket} for coin")
                return None
            
            bracket_config = BRACKET_CONFIG[stored_bracket]
            bracket_entries = bracket_config['entries']  # [entry1, entry2, entry3, entry4]
            
            logger.info(f"   📊 Using bracket {stored_bracket} with entries: {bracket_entries}")
            
            # Get all active orders for this coin and profile
            all_orders = db_manager.get_orders_by_coin(coin.id)
            active_orders = [o for o in all_orders if o.profile_name == profile_name and o.status == "ACTIVE"]
            
            logger.info(f"   📋 Found {len(active_orders)} active orders in database")
            
            # Method 1: Try to match by trigger condition (exact match)
            sub_id = None
            matched_order = None
            identification_method = None
            
            logger.info(f"   🎯 METHOD 1: Trigger condition matching...")
            for order in active_orders:
                if order.trigger_condition == trigger_condition:
                    sub_id = order.bracket_id
                    matched_order = order
                    identification_method = "trigger_condition_exact"
                    logger.info(f"      ✅ Exact trigger match found: Order ID {order.id}, Bracket ID {sub_id}")
                    break
            
            # Method 2: Try to match by entry price from trigger condition
            if not sub_id:
                logger.info(f"   🎯 METHOD 2: Entry price matching...")
                entry_price = self._parse_trigger_condition_entry_price(trigger_condition)
                if entry_price:
                    logger.info(f"      📊 Extracted entry price: ${entry_price:,.0f}")
                    sub_id = self._match_entry_to_sub_id(entry_price, bracket_entries)
                    if sub_id:
                        matched_order = self._get_order_by_coin_sub_id(coin.id, sub_id, profile_name)
                        if matched_order:
                            identification_method = "entry_price"
                            logger.info(f"      ✅ Entry price match found: Order ID {matched_order.id}, Bracket ID {sub_id}")
                        else:
                            logger.info(f"      ❌ No order found for calculated sub_id {sub_id}")
                            sub_id = None
                    else:
                        logger.info(f"      ❌ Could not match entry price to bracket entries")
                else:
                    logger.info(f"      ❌ Could not extract entry price from trigger condition")
            
            # Method 3: Try to match by expiry time (for cases where multiple orders exist)
            if not sub_id and len(active_orders) > 1:
                logger.info(f"   🎯 METHOD 3: Expiry time matching...")
                expiry_seconds = self._parse_expiry_to_seconds(expiry)
                if expiry_seconds is not None:
                    logger.info(f"      ⏰ Parsed expiry: {expiry_seconds} seconds")
                    best_match = self._match_by_expiry_time(active_orders, expiry_seconds, trigger_condition)
                    if best_match:
                        sub_id = best_match.bracket_id
                        matched_order = best_match
                        identification_method = "expiry_time"
                        logger.info(f"      ✅ Expiry time match found: Order ID {best_match.id}, Bracket ID {sub_id}")
                else:
                    logger.info(f"      ❌ Could not parse expiry time: '{expiry}'")
            
            # Method 4: TP condition handling
            if not sub_id and self._is_tp_condition(trigger_condition):
                logger.info(f"   🎯 METHOD 4: TP condition handling...")
                # For TP conditions, try to find any active order and mark it
                if active_orders:
                    matched_order = active_orders[0]  # Take first available
                    sub_id = matched_order.bracket_id
                    identification_method = "tp_fallback"
                    logger.info(f"      ✅ TP fallback match: Order ID {matched_order.id}, Bracket ID {sub_id}")
            
            # Method 5: Sequential fallback (last resort)
            if not sub_id and active_orders:
                logger.info(f"   🎯 METHOD 5: Sequential fallback...")
                active_orders.sort(key=lambda x: x.bracket_id)
                matched_order = active_orders[0]
                sub_id = matched_order.bracket_id
                identification_method = "sequential_fallback"
                logger.info(f"      ⚠️  Sequential fallback: Order ID {matched_order.id}, Bracket ID {sub_id}")
            
            # Update trigger condition in database if we found a match AND it's different
            if matched_order and trigger_condition:
                if matched_order.trigger_condition != trigger_condition:
                    # Check if this is a BullX automation refresh (entry → TP/SL transition)
                    is_bullx_refresh = self._is_bullx_automation_refresh(
                        matched_order.trigger_condition, trigger_condition
                    )
                    
                    if is_bullx_refresh:
                        # Calculate when BullX updated the order using expiry time
                        bullx_update_time = self._calculate_bullx_update_time(expiry)
                        if bullx_update_time:
                            self._update_order_with_bullx_refresh(
                                matched_order.id, trigger_condition, bullx_update_time
                            )
                            logger.info(f"🔄 BullX automation refresh detected for order {matched_order.id}:")
                            logger.info(f"   Trigger: '{matched_order.trigger_condition}' → '{trigger_condition}'")
                            logger.info(f"   Calculated BullX update time: {bullx_update_time}")
                        else:
                            # Fallback to regular update if calculation fails
                            self._update_order_trigger_condition(matched_order.id, trigger_condition)
                            logger.warning(f"Could not calculate BullX update time, using regular update for order {matched_order.id}")
                    else:
                        # Regular trigger condition update
                        self._update_order_trigger_condition(matched_order.id, trigger_condition)
                        logger.debug(f"Updated trigger condition for order {matched_order.id}: '{matched_order.trigger_condition}' -> '{trigger_condition}'")
                else:
                    logger.debug(f"Trigger condition unchanged for order {matched_order.id}: '{trigger_condition}'")
            
            # Final result
            if sub_id and matched_order:
                logger.info(f"   ✅ IDENTIFICATION SUCCESSFUL:")
                logger.info(f"      Method: {identification_method}")
                logger.info(f"      Order ID: {matched_order.id}")
                logger.info(f"      Bracket ID: {sub_id}")
                logger.info(f"      Trigger: {trigger_condition}")
            else:
                logger.info(f"   ❌ IDENTIFICATION FAILED: No matching order found")
            
            return {
                'order': matched_order,
                'coin': coin,
                'bracket': stored_bracket,
                'sub_id': sub_id,
                'entry_price': self._parse_trigger_condition_entry_price(trigger_condition),
                'bracket_entries': bracket_entries,
                'identification_method': identification_method
            }
            
        except Exception as e:
            logger.error(f"💥 Error identifying order: {e}")
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
    
    def _parse_expiry_to_seconds(self, expiry: str) -> Optional[int]:
        """
        Parse expiry time string to total seconds.
        
        Examples:
        - "63h 09m 52s" -> 227392 seconds
        - "56h 42m 17s" -> 204137 seconds
        - "33h 52m 13s" -> 121933 seconds
        - "00h 00m 00s" -> 0 seconds (expired)
        
        Returns:
            Total seconds as int, or None if not parseable
        """
        try:
            import re
            
            if not expiry:
                return None
            
            # Pattern to match "XXh XXm XXs" format
            pattern = r'(\d+)h\s+(\d+)m\s+(\d+)s'
            match = re.search(pattern, expiry)
            
            if not match:
                logger.debug(f"Could not parse expiry format: '{expiry}'")
                return None
            
            hours = int(match.group(1))
            minutes = int(match.group(2))
            seconds = int(match.group(3))
            
            total_seconds = hours * 3600 + minutes * 60 + seconds
            
            logger.debug(f"Parsed expiry '{expiry}' -> {total_seconds} seconds")
            return total_seconds
            
        except Exception as e:
            logger.error(f"Error parsing expiry '{expiry}': {e}")
            return None
    
    def _match_by_expiry_time(self, active_orders: List[Order], expiry_seconds: int, trigger_condition: str = "") -> Optional[Order]:
        """
        Match order by comparing expiry time with order timestamp.
        
        For TP conditions ("1 TP, 1 SL"), uses updated_at since BullX updates expiry when order is entered.
        For entry conditions ("Buy below $XXX"), uses created_at since order hasn't been entered yet.
        
        Logic: current_time - reference_time ≈ total_order_duration - expiry_seconds
        Where total_order_duration is typically 72 hours (259200 seconds) for limit orders.
        
        Args:
            active_orders: List of active orders for the coin
            expiry_seconds: Remaining seconds from BullX
            trigger_condition: The trigger condition to determine which timestamp to use
            
        Returns:
            Best matching order or None
        """
        try:
            from datetime import datetime, timezone
            
            current_time = datetime.now(timezone.utc)
            
            # Assume typical order duration is 72 hours (can be adjusted)
            TYPICAL_ORDER_DURATION_SECONDS = 72 * 3600  # 72 hours
            
            best_match = None
            smallest_difference = float('inf')
            
            # Determine which timestamp to use based on trigger condition
            is_tp_condition = self._is_tp_condition(trigger_condition) or "TP" in trigger_condition.upper()
            timestamp_type = "updated_at" if is_tp_condition else "created_at"
            
            logger.info(f"      🕐 Matching by expiry time ({expiry_seconds}s remaining):")
            logger.info(f"         Using {timestamp_type} timestamp (TP condition: {is_tp_condition})")
            
            for order in active_orders:
                try:
                    # Choose reference time based on trigger condition
                    if is_tp_condition and order.updated_at:
                        # For TP conditions, use updated_at since BullX updates expiry when order is entered
                        reference_time = order.updated_at
                        time_label = "Updated"
                    else:
                        # For entry conditions, use created_at since order hasn't been entered yet
                        reference_time = order.created_at
                        time_label = "Created"
                    
                    # Ensure timezone awareness
                    if reference_time.tzinfo is None:
                        reference_time_utc = reference_time.replace(tzinfo=timezone.utc)
                    else:
                        reference_time_utc = reference_time
                    
                    elapsed_seconds = (current_time - reference_time_utc).total_seconds()
                    
                    # Expected elapsed time based on expiry
                    expected_elapsed = TYPICAL_ORDER_DURATION_SECONDS - expiry_seconds
                    
                    # Calculate difference
                    time_difference = abs(elapsed_seconds - expected_elapsed)
                    
                    logger.info(f"         Order ID {order.id} (Bracket {order.bracket_id}):")
                    logger.info(f"           {time_label}: {reference_time_utc}")
                    logger.info(f"           Elapsed: {elapsed_seconds:.0f}s ({elapsed_seconds/3600:.1f}h)")
                    logger.info(f"           Expected: {expected_elapsed:.0f}s ({expected_elapsed/3600:.1f}h)")
                    logger.info(f"           Difference: {time_difference:.0f}s ({time_difference/3600:.1f}h)")
                    
                    if time_difference < smallest_difference:
                        smallest_difference = time_difference
                        best_match = order
                        
                except Exception as e:
                    logger.error(f"         Error processing order {order.id}: {e}")
                    continue
            
            if best_match:
                logger.info(f"      ✅ Best match: Order ID {best_match.id} (Bracket {best_match.bracket_id})")
                logger.info(f"         Time difference: {smallest_difference:.0f}s ({smallest_difference/3600:.1f}h)")
                logger.info(f"         Reference: {timestamp_type}")
            else:
                logger.info(f"      ❌ No suitable match found")
            
            return best_match
            
        except Exception as e:
            logger.error(f"Error matching by expiry time: {e}")
            return None
    
    def _update_order_trigger_condition(self, order_id: int, trigger_condition: str) -> bool:
        """Update the trigger condition for an order in the database"""
        try:
            success = db_manager.update_order_trigger_condition(order_id, trigger_condition)
            if success:
                logger.debug(f"Updated trigger condition for order {order_id}: '{trigger_condition}'")
            else:
                logger.warning(f"Failed to update trigger condition for order {order_id}")
            return success
            
        except Exception as e:
            logger.error(f"Error updating trigger condition for order {order_id}: {e}")
            return False
    
    def _is_bullx_automation_refresh(self, old_trigger: str, new_trigger: str) -> bool:
        """
        Detect if this is a BullX automation refresh (entry → TP/SL transition).
        
        Args:
            old_trigger: Previous trigger condition from database
            new_trigger: Current trigger condition from BullX
            
        Returns:
            True if this is a BullX automation refresh, False otherwise
        """
        try:
            if not old_trigger or not new_trigger:
                return False
            
            # Check if old trigger was an entry condition
            is_old_entry = "Buy below" in old_trigger
            
            # Check if new trigger is a TP/SL condition
            is_new_tp_sl = new_trigger in ["1 TP, 1 SL", "1 TP", "1 SL"]
            
            return is_old_entry and is_new_tp_sl
            
        except Exception as e:
            logger.error(f"Error detecting BullX automation refresh: {e}")
            return False
    
    def _calculate_bullx_update_time(self, expiry: str) -> Optional['datetime']:
        """
        Calculate when BullX updated the order using the 72h formula.
        
        Formula: bullx_update_time = current_time - (72h - current_expiry)
        
        Args:
            expiry: Current expiry time from BullX (e.g., "56h 42m 17s")
            
        Returns:
            Calculated BullX update time, or None if calculation fails
        """
        try:
            from datetime import datetime, timezone, timedelta
            
            # Parse current expiry to seconds
            expiry_seconds = self._parse_expiry_to_seconds(expiry)
            if expiry_seconds is None:
                logger.warning(f"Could not parse expiry time: '{expiry}'")
                return None
            
            current_time = datetime.now(timezone.utc)
            
            # 72 hours in seconds (typical BullX order duration)
            BULLX_ORDER_DURATION_SECONDS = 72 * 3600
            
            # Calculate elapsed time since BullX updated the order
            elapsed_since_update = BULLX_ORDER_DURATION_SECONDS - expiry_seconds
            
            # Calculate when BullX updated the order
            bullx_update_time = current_time - timedelta(seconds=elapsed_since_update)
            
            logger.debug(f"BullX update time calculation:")
            logger.debug(f"  Current time: {current_time}")
            logger.debug(f"  Expiry remaining: {expiry_seconds}s ({expiry_seconds/3600:.1f}h)")
            logger.debug(f"  Elapsed since update: {elapsed_since_update}s ({elapsed_since_update/3600:.1f}h)")
            logger.debug(f"  Calculated BullX update time: {bullx_update_time}")
            
            return bullx_update_time
            
        except Exception as e:
            logger.error(f"Error calculating BullX update time: {e}")
            return None
    
    def _update_order_with_bullx_refresh(self, order_id: int, trigger_condition: str, bullx_update_time: 'datetime') -> bool:
        """Update order with BullX automation refresh using calculated update time"""
        try:
            success = db_manager.update_order_with_bullx_refresh(order_id, trigger_condition, bullx_update_time)
            if success:
                logger.debug(f"Updated order {order_id} with BullX refresh: trigger='{trigger_condition}', updated_at={bullx_update_time}")
            else:
                logger.warning(f"Failed to update order {order_id} with BullX refresh")
            return success
            
        except Exception as e:
            logger.error(f"Error updating order with BullX refresh: {e}")
            return False
    
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
                            
                            # Create new order using bracket_order_placement with original bracket
                            new_order_result = await self._create_replacement_order(
                                profile_name, coin_address, bracket_sub_id, amount, original_bracket
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
                                      bracket_sub_id: int, amount: float, 
                                      original_bracket: int = None) -> Dict:
        """Create a replacement order using bracket_order_placement with original bracket preservation"""
        try:
            logger.info(f"      🔨 Creating replacement order for bracket sub ID {bracket_sub_id}...")
            if original_bracket:
                logger.info(f"         Using original bracket {original_bracket} (preserving bracket consistency)")
            
            # Use bracket_order_manager to replace the specific order with original bracket
            result = bracket_order_manager.replace_order(
                profile_name=profile_name,
                address=coin_address,
                bracket_id=bracket_sub_id,
                new_amount=amount,
                strategy_number=1,  # Default strategy number
                original_bracket=original_bracket  # Pass original bracket to preserve consistency
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
