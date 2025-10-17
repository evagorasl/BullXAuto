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
        self.expired_coins = []  # Track coins with SL hit + any expired (cancel all + sell)
        self.individual_expired_orders = []  # Track individually expired orders for renewal
        self.current_selected_filter = None  # Track currently active filter button
        
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
            
            # Clear previous lists and reset filter state
            self.orders_for_renewal = []
            self.expired_coins = []
            self.individual_expired_orders = []
            self.current_selected_filter = None  # Reset filter tracking
            
            # Step 1: Check orders and detect conditions (TP + expired)
            logger.info("📋 Step 1: Checking orders and detecting conditions...")
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
            
            # Step 2: Process expired coins FIRST (SL hit + any expired - cancel all + sell)
            expired_results = {"coins_processed": 0, "expired_details": []}
            if self.expired_coins:
                logger.info(f"\n🚨 Step 2: Processing {len(self.expired_coins)} expired coins (cancel all + sell)...")
                expired_results = await self._process_expired_coins(profile_name)
            else:
                logger.info(f"\n✅ Step 2: No expired coins detected (cancel all + sell)")
            
            # Step 3: Process individual expired orders (delete individually + renewal)
            individual_expired_results = {"orders_processed": 0}
            if self.individual_expired_orders:
                logger.info(f"\n⏰ Step 3: Processing {len(self.individual_expired_orders)} individual expired orders...")
                individual_expired_results = await self._process_individual_expired_orders(profile_name)
            else:
                logger.info(f"\n✅ Step 3: No individual expired orders detected")
            
            # Step 4: Process TP renewal orders (only non-expired coins)
            logger.info(f"\n📝 Step 4: Processing {len(self.orders_for_renewal)} orders marked for renewal...")
            renewal_results = await self._process_renewal_orders(profile_name)
            
            # Step 5: Generate comprehensive output
            logger.info("\n📊 Step 5: Generating processing summary...")
            summary = self._generate_processing_summary(check_result, renewal_results, expired_results, individual_expired_results)
            
            logger.info(f"\n{'='*80}")
            logger.info(f"✅ ENHANCED ORDER PROCESSING COMPLETED FOR {profile_name.upper()}")
            logger.info(f"{'='*80}")
            
            return {
                "success": True,
                "profile_name": profile_name,
                "orders_checked": check_result.get("total_orders_checked", 0),
                "expired_coins_processed": expired_results.get("coins_processed", 0),
                "orders_marked_for_renewal": len(self.orders_for_renewal),
                "orders_replaced": renewal_results.get("orders_replaced", 0),
                "renewal_details": renewal_results.get("renewal_details", []),
                "expired_details": expired_results.get("expired_details", []),
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
            
            # PRIORITY 1: Check for SL hit + any expired condition
            logger.info(f"  🔍 PRIORITY 1: Checking for SL hit + any expired...")
            if self._check_sl_with_any_expired(coin_orders):
                # This coin has SL hit + any expired - mark for expired cleanup (cancel all + sell)
                expired_coin_info = {
                    'coin': coin,
                    'coin_orders': coin_orders,
                    'button_index': coin_orders[0]['button_index'] if coin_orders else None,
                    'profile_name': profile_name,
                    'token': token
                }
                self.expired_coins.append(expired_coin_info)
                logger.info(f"  ⚠️  Coin marked for expired cleanup - SKIPPING further processing")
                return  # Early return - skip all other checks
            
            logger.info(f"  ✅ No SL hit with expired - checking for individual expired orders...")
            
            # PRIORITY 2: Check for individually expired orders (no SL hit)
            logger.info(f"  🔍 PRIORITY 2: Checking for individual expired orders...")
            individual_expired = self._get_individual_expired_orders(coin_orders)
            
            if individual_expired:
                logger.info(f"  ⏰ Found {len(individual_expired)} individually expired orders")
                logger.info(f"  📝 Marking expired orders for individual renewal...")
                
                # Process each expired order for renewal
                for expired_order_info in individual_expired:
                    try:
                        # Identify the order in database
                        order_match = self._identify_order(expired_order_info['parsed_data'], profile_name)
                        
                        if order_match and order_match.get('order'):
                            # Add to individual expired list for processing
                            expired_renewal_info = {
                                'order': order_match['order'],
                                'order_info': expired_order_info,
                                'coin': coin,
                                'profile_name': profile_name
                            }
                            self.individual_expired_orders.append(expired_renewal_info)
                            logger.info(f"     ✅ Expired order identified for renewal: Order ID {order_match['order'].id}")
                        else:
                            logger.warning(f"     ❌ Could not identify expired order in database")
                            
                    except Exception as e:
                        logger.error(f"     💥 Error processing expired order: {e}")
                
                # Don't return - continue to check for TP on non-expired orders
                logger.info(f"  ℹ️  Will also check non-expired orders for TP conditions...")
            else:
                logger.info(f"  ✅ No individual expired orders found")
            
            logger.info(f"  🔍 PRIORITY 3: Proceeding with normal TP and missing order processing...")
            
            # Check if we have less than 4 orders and identify missing ones
            missing_orders = []
            if len(coin_orders) < 4:
                missing_orders = await self._identify_missing_orders(coin, coin_orders, profile_name)
            
            # Update trigger conditions for all orders during coin processing
            logger.info(f"  📝 Updating trigger conditions for all {token} orders...")
            await self._update_trigger_conditions_for_coin(profile_name, coin, coin_orders)
            
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
        
        We always expect 4 bracket orders (IDs 1-4) for each coin.
        Missing orders are those that should exist but aren't on BullX.
        
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
            
            # Expected bracket IDs: We always expect 4 orders (1, 2, 3, 4)
            expected_bracket_ids = {1, 2, 3, 4}
            
            # Find which bracket IDs are present in BullX (from parsed orders)
            bullx_bracket_ids = set()
            for order_info in coin_orders:
                parsed_data = order_info.get('parsed_data', {})
                # Try to identify bracket_id from parsed data
                order_match = self._identify_order(parsed_data, profile_name)
                if order_match and order_match.get('sub_id'):
                    bullx_bracket_ids.add(order_match['sub_id'])
            
            # Missing bracket IDs = Expected - What's on BullX
            missing_bracket_ids = expected_bracket_ids - bullx_bracket_ids
            
            missing_orders = []
            
            if missing_bracket_ids:
                logger.info(f"    🚨 MISSING ORDERS DETECTED!")
                logger.info(f"    📋 Expected bracket IDs: {sorted(expected_bracket_ids)}")
                logger.info(f"    📋 BullX shows bracket IDs: {sorted(bullx_bracket_ids)}")
                logger.info(f"    ❌ Missing bracket IDs: {sorted(missing_bracket_ids)}")
                
                # For each missing bracket ID, we need to create a renewal entry
                # We'll use coin data to determine the amount
                for bracket_id in missing_bracket_ids:
                    entry_price = bracket_entries[bracket_id - 1]  # Convert to 0-based index
                    logger.info(f"      🔍 Missing Bracket ID {bracket_id}: Entry ${entry_price:,.0f}")
                    
                    # Try to find if there's a completed order with this bracket_id to get amount
                    db_orders = db_manager.get_orders_by_coin(coin.id)
                    profile_orders = [o for o in db_orders if o.profile_name == profile_name and o.bracket_id == bracket_id]
                    
                    # Use amount from most recent order if available
                    amount = None
                    order_id_ref = None
                    
                    if profile_orders:
                        # Sort by updated_at or created_at to get most recent
                        profile_orders.sort(key=lambda x: x.updated_at if x.updated_at else x.created_at, reverse=True)
                        amount = profile_orders[0].amount
                        order_id_ref = profile_orders[0].id
                        
                        if amount:
                            logger.info(f"         Using amount {amount} from previous order (ID: {order_id_ref})")
                        else:
                            logger.warning(f"         Previous order (ID: {order_id_ref}) has no amount stored")
                    
                    # Only create renewal entry if we have a valid amount
                    if amount and amount > 0:
                        # Create missing order info for renewal processing
                        missing_order_info = {
                            'order': None,  # No active order exists
                            'coin': coin,
                            'bracket_id': bracket_id,
                            'is_missing': True,
                            'amount': amount,
                            'reason': f'Bracket ID {bracket_id} missing from BullX (expected 4 orders total)'
                        }
                        missing_orders.append(missing_order_info)
                    else:
                        logger.warning(f"         ⚠️  Skipping bracket ID {bracket_id} - no valid amount found in previous orders")
                        logger.warning(f"            Cannot safely create order without knowing the amount")
                        
            else:
                logger.info(f"    ✅ All expected orders (4) found on BullX")
            
            return missing_orders
            
        except Exception as e:
            logger.error(f"Error identifying missing orders: {e}")
            return []
    
    async def _process_missing_orders(self, profile_name: str, missing_orders: List[Dict]):
        """Process missing orders by marking them for renewal without BullX deletion"""
        try:
            logger.info(f"    🔄 Processing {len(missing_orders)} missing orders...")
            
            for missing_order_info in missing_orders:
                coin = missing_order_info['coin']
                bracket_id = missing_order_info['bracket_id']
                reason = missing_order_info['reason']
                amount = missing_order_info['amount']
                
                logger.info(f"      📝 Processing missing bracket ID {bracket_id}")
                logger.info(f"         Reason: {reason}")
                
                # Add to renewal list (no database order to update since it doesn't exist)
                renewal_info = {
                    'order_id': None,  # No existing order in database
                    'coin_address': coin.address,
                    'coin_name': coin.name,
                    'parsed_data': {'token': coin.name or 'Unknown', 'reason': reason},
                    'button_index': 0,  # Not applicable for missing orders
                    'row_index': 0,     # Not applicable for missing orders
                    'original_bracket': coin.bracket,  # Use original bracket from coin
                    'bracket_sub_id': bracket_id,
                    'profile_name': profile_name,
                    'amount': amount,
                    'is_missing_order': True
                }
                
                self.orders_for_renewal.append(renewal_info)
                logger.info(f"      ✅ Missing bracket ID {bracket_id} marked for renewal (amount: {amount})")
                    
        except Exception as e:
            logger.error(f"💥 Error processing missing orders: {e}")
    
    async def _batch_delete_bullx_entries(self, profile_name: str, tp_orders: List[Dict]):
        """
        Batch delete BullX entries for TP orders of a specific coin.
        Uses order count verification to ensure deletion succeeded before updating database.
        """
        try:
            successful_deletions = []
            coin_name = tp_orders[0]['coin'].name if tp_orders else "Unknown"
            
            for i, tp_order in enumerate(tp_orders):
                order = tp_order['order']
                order_info = tp_order['order_info']
                coin = tp_order['coin']
                button_index = order_info['button_index']
                
                logger.info(f"    📝 Processing order {order.id} for deletion ({i+1}/{len(tp_orders)})...")
                
                # Re-click the filter button for this coin before each deletion
                # This ensures we have the correct view and row indices after previous deletions
                filter_success = await self._click_coin_filter_button(profile_name, button_index)
                
                if not filter_success:
                    logger.error(f"    ❌ Failed to click filter button for {coin_name} - skipping deletion")
                    continue
                
                # Try to delete entry from BullX
                logger.info(f"    🗑️  Attempting to delete BullX entry...")
                deletion_clicked = await self._delete_bullx_entry(
                    profile_name, 
                    button_index, 
                    order_info['row_index']
                )
                
                if not deletion_clicked:
                    logger.error(f"    ❌ Failed to click delete button - skipping order {order.id}")
                    continue
                
                # Wait for BullX to process the deletion
                logger.info(f"    ⏳ Waiting for BullX to process deletion...")
                time.sleep(2)
                
                # Verify deletion by counting orders
                logger.info(f"    🔍 Verifying deletion success by counting orders...")
                order_count = await self._count_bullx_orders_for_coin(profile_name, button_index)
                
                if order_count == -1:
                    logger.error(f"    ❌ Could not verify deletion (count failed) - skipping order {order.id}")
                    continue
                
                if order_count < 4:
                    # Deletion successful - count is less than 4
                    logger.info(f"    ✅ Deletion verified successful! Order count: {order_count} < 4")
                    
                    # Update database to COMPLETED
                    db_update_success = db_manager.update_order_status(order.id, "COMPLETED")
                    
                    if db_update_success:
                        logger.info(f"    ✅ Database updated - order {order.id} marked as COMPLETED")
                        
                        # Add to renewal list
                        renewal_info = {
                            'order_id': order.id,
                            'coin_address': coin.address,
                            'coin_name': coin.name,
                            'parsed_data': order_info['parsed_data'],
                            'button_index': button_index,
                            'row_index': order_info['row_index'],
                            'original_bracket': coin.bracket,
                            'bracket_sub_id': order.bracket_id,
                            'profile_name': order.profile_name,
                            'amount': order.amount or 1.0
                        }
                        
                        self.orders_for_renewal.append(renewal_info)
                        successful_deletions.append(order.id)
                        logger.info(f"    ✅ Order {order.id} marked for renewal")
                    else:
                        logger.error(f"    ❌ Database update failed for order {order.id}")
                else:
                    # Deletion failed - still 4 or more orders
                    logger.error(f"    ❌ Deletion FAILED! Order count: {order_count} >= 4")
                    logger.error(f"    ⚠️  BullX still shows {order_count} orders - order was not deleted")
                    logger.error(f"    ⚠️  Skipping database update and renewal for order {order.id}")
            
            logger.info(f"  ✅ Successfully processed {len(successful_deletions)} orders for deletion")
            
        except Exception as e:
            logger.error(f"💥 Error in batch delete: {e}")
    
    async def _click_coin_filter_button(self, profile_name: str, button_index: int, force: bool = False) -> bool:
        """
        Click the filter button for a specific coin to refresh the view.
        Uses state tracking to avoid accidentally toggling filters off.
        
        Args:
            profile_name: Chrome profile name
            button_index: Filter button index (1-based)
            force: If True, click even if already selected
            
        Returns:
            True if successful (either clicked or already selected), False on error
        """
        try:
            # Skip if already selected (unless forced)
            if not force and self.current_selected_filter == button_index:
                logger.info(f"    ✅ Filter {button_index} already selected, skipping click")
                return True
            
            driver = self.driver_manager.get_driver(profile_name)
            
            # Find the button using the button_index from the original order checking
            # This corresponds to the filter buttons that were clicked during order checking
            button_selector = "button.ant-btn.ant-btn-text.ant-btn-sm.\\!px-1"
            
            logger.info(f"    🔄 Clicking filter button {button_index} to refresh view...")
            
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
                    
                    # Update tracking after successful click
                    self.current_selected_filter = button_index
                    
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
    
    async def _count_bullx_orders_for_coin(self, profile_name: str, button_index: int) -> int:
        """
        Count the number of visible orders on BullX for a specific coin.
        
        Args:
            profile_name: Chrome profile name
            button_index: Filter button index for the coin
            
        Returns:
            Number of visible orders, or -1 if count failed
        """
        try:
            driver = self.driver_manager.get_driver(profile_name)
            
            logger.info(f"    📊 Counting orders for coin (button {button_index})...")
            
            # Re-click the filter button to ensure we have the correct view
            filter_success = await self._click_coin_filter_button(profile_name, button_index)
            if not filter_success:
                logger.error(f"    ❌ Failed to click filter button - cannot count orders")
                return -1
            
            # Wait a moment for the view to stabilize
            time.sleep(1)
            
            # Count order rows using the same container structure as the XPATH
            # The orders are in: //*[@id='root']/div[1]/div[2]/main/div/section/div[2]/div[2]/div/div/div/div[1]/a[*]
            try:
                # Use the container path to find all order rows
                container_xpath = "//*[@id='root']/div[1]/div[2]/main/div/section/div[2]/div[2]/div/div/div/div[1]"
                container = driver.find_element(By.XPATH, container_xpath)
                
                # Find all <a> elements within the container (each represents an order row)
                order_rows = container.find_elements(By.TAG_NAME, "a")
                order_count = len(order_rows)
                
                logger.info(f"    📊 Found {order_count} orders on BullX for this coin")
                return order_count
                
            except NoSuchElementException:
                logger.warning(f"    ⚠️  No order container found - assuming 0 orders")
                return 0
            except Exception as e:
                logger.error(f"    💥 Error counting order rows: {e}")
                return -1
                
        except Exception as e:
            logger.error(f"    💥 Error in count_bullx_orders_for_coin: {e}")
            return -1
    
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
    
    def _check_trigger_condition_type(self, trigger_condition: str) -> Dict[str, bool]:
        """
        Analyze trigger condition and return what types it contains.
        Uses simple string matching to avoid regex complexity.
        
        Args:
            trigger_condition: The trigger condition string from BullX
            
        Returns:
            Dict with keys: 'has_tp_only', 'has_sl_only', 'has_both', 'has_entry'
            
        Examples:
            "1 TP" → {'has_tp_only': True, 'has_sl_only': False, 'has_both': False}
            "1 TP," → {'has_tp_only': True, 'has_sl_only': False, 'has_both': False}
            "1 SL" → {'has_tp_only': False, 'has_sl_only': True, 'has_both': False}
            "1 TP, 1 SL" → {'has_tp_only': False, 'has_sl_only': False, 'has_both': True}
            "Buy below $231K" → {'has_entry': True}
        """
        if not trigger_condition:
            return {'has_tp_only': False, 'has_sl_only': False, 'has_both': False, 'has_entry': False}
        
        # Strip whitespace and remove trailing comma if present
        trigger = trigger_condition.strip().rstrip(',').strip()
        
        # Check for entry conditions
        has_entry = "Buy below" in trigger
        
        # Simple string matching for TP/SL conditions
        # Check for both first (most specific)
        has_both = ("1 TP" in trigger and "1 SL" in trigger)
        
        # Then check for individual ones (only if not both)
        has_tp_only = ("1 TP" in trigger and not has_both)
        has_sl_only = ("1 SL" in trigger and not has_both)
        
        return {
            'has_tp_only': has_tp_only,
            'has_sl_only': has_sl_only,
            'has_both': has_both,
            'has_entry': has_entry
        }
    
    def _is_tp_condition(self, trigger_condition: str) -> bool:
        """
        Check if trigger condition indicates TP has been met.
        According to requirements: trigger conditions = "1 SL" (only SL remains) means TP has been met.
        """
        trigger_type = self._check_trigger_condition_type(trigger_condition)
        return trigger_type['has_sl_only']
    
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
            
            # Note: Trigger condition updates are now handled separately during coin order processing
            
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
        Uses pattern-based trigger type detection for robust matching.
        
        Args:
            old_trigger: Previous trigger condition from database
            new_trigger: Current trigger condition from BullX
            
        Returns:
            True if this is a BullX automation refresh, False otherwise
        """
        try:
            if not old_trigger or not new_trigger:
                return False
            
            old_type = self._check_trigger_condition_type(old_trigger)
            new_type = self._check_trigger_condition_type(new_trigger)
            
            # Entry → TP/SL transition
            is_old_entry = old_type['has_entry']
            is_new_tp_sl = (new_type['has_tp_only'] or new_type['has_sl_only'] or new_type['has_both'])
            
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
    
    async def _update_trigger_conditions_for_coin(self, profile_name: str, coin: Coin, coin_orders: List[Dict]):
        """Update trigger conditions for all orders of a coin using order_amount-based identification"""
        try:
            logger.info(f"    🔄 Updating trigger conditions for {len(coin_orders)} {coin.name or coin.address} orders...")
            
            # Get all active orders for this coin and profile
            all_orders = db_manager.get_orders_by_coin(coin.id)
            active_orders = [o for o in all_orders if o.profile_name == profile_name and o.status == "ACTIVE"]
            
            if not active_orders:
                logger.info(f"      ❌ No active orders found in database for {coin.name or coin.address}")
                return
            
            # Get bracket configuration
            if not coin.bracket or coin.bracket not in BRACKET_CONFIG:
                logger.warning(f"      ❌ No valid bracket found for coin")
                return
            
            bracket_config = BRACKET_CONFIG[coin.bracket]
            bracket_entries = bracket_config['entries']  # [entry1, entry2, entry3, entry4]
            
            logger.info(f"      📊 Using bracket {coin.bracket} with entries: {bracket_entries}")
            logger.info(f"      📋 Found {len(active_orders)} active orders in database")
            
            # Track matched orders
            matched_orders = {}  # {order_id: order_info}
            unmatched_db_orders = list(active_orders)  # Start with all active orders
            
            logger.info(f"      🎯 3-STEP IDENTIFICATION PROCESS:")
            
            # STEP 1: Identify "Buy Limit" orders with "Buy below..." trigger conditions (unfulfilled entry orders)
            logger.info(f"      📍 STEP 1: Identifying unfulfilled 'Buy Limit' orders with 'Buy below...' triggers")
            
            for order_info in coin_orders:
                try:
                    parsed_data = order_info.get('parsed_data', {})
                    trigger_condition = parsed_data.get('trigger_condition', '')
                    order_type = parsed_data.get('type', '')
                    
                    if not trigger_condition:
                        continue
                    
                    # Step 1: Match by "Buy below..." trigger (unfulfilled limit orders)
                    if trigger_condition.startswith("Buy below"):
                        entry_price = self._parse_trigger_condition_entry_price(trigger_condition)
                        if entry_price:
                            sub_id = self._match_entry_to_sub_id(entry_price, bracket_entries)
                            if sub_id:
                                # Find the order with this sub_id from unmatched list
                                matched_order = None
                                for order in unmatched_db_orders:
                                    if order.bracket_id == sub_id:
                                        matched_order = order
                                        break
                                
                                if matched_order:
                                    matched_orders[matched_order.id] = order_info
                                    unmatched_db_orders.remove(matched_order)
                                    logger.info(f"         ✅ Step 1 Match: Entry price ${entry_price:,.0f} → Order ID {matched_order.id} (Bracket {sub_id})")
                                    
                                    # Update trigger condition AND order_amount
                                    await self._update_single_order_trigger_condition(
                                        matched_order, 
                                        trigger_condition, 
                                        parsed_data.get('expiry', ''),
                                        parsed_data.get('order_amount', '')
                                    )
                        
                except Exception as e:
                    logger.error(f"         💥 Error in Step 1 matching: {e}")
            
            # STEP 2: Match remaining orders by order_amount (fulfilled orders)
            logger.info(f"      📍 STEP 2: Matching {len(coin_orders) - len(matched_orders)} remaining orders by order_amount")
            
            # Group BullX orders by normalized order_amount to handle identical amounts
            orders_by_amount = {}
            for order_info in coin_orders:
                try:
                    parsed_data = order_info.get('parsed_data', {})
                    
                    # Skip if already matched in Step 1
                    if any(oi is order_info for oi in matched_orders.values()):
                        continue
                    
                    trigger_condition = parsed_data.get('trigger_condition', '')
                    bullx_amount = parsed_data.get('order_amount', '')
                    
                    if not trigger_condition or not bullx_amount:
                        continue
                    
                    # Normalize amount for grouping
                    amount_key = self._normalize_amount_string(bullx_amount)
                    
                    if amount_key not in orders_by_amount:
                        orders_by_amount[amount_key] = []
                    
                    orders_by_amount[amount_key].append(order_info)
                    
                except Exception as e:
                    logger.error(f"         💥 Error grouping orders: {e}")
            
            # Match each group of orders
            for amount_key, bullx_group in orders_by_amount.items():
                try:
                    if len(bullx_group) == 1:
                        # Single order with this amount - match normally
                        order_info = bullx_group[0]
                        parsed_data = order_info.get('parsed_data', {})
                        bullx_amount = parsed_data.get('order_amount', '')
                        trigger_condition = parsed_data.get('trigger_condition', '')
                        
                        if unmatched_db_orders:
                            matched_order = self._match_by_order_amount(bullx_amount, unmatched_db_orders, trigger_condition)
                            if matched_order:
                                matched_orders[matched_order.id] = order_info
                                unmatched_db_orders.remove(matched_order)
                                logger.info(f"         ✅ Step 2 Match: Amount '{bullx_amount}' → Order ID {matched_order.id} (Bracket {matched_order.bracket_id})")
                                
                                # Update trigger condition AND order_amount
                                await self._update_single_order_trigger_condition(
                                    matched_order, 
                                    trigger_condition, 
                                    parsed_data.get('expiry', ''),
                                    bullx_amount
                                )
                    
                    else:
                        # Multiple orders with same amount - use expiry-based tiebreaker
                        logger.info(f"         🔀 Found {len(bullx_group)} orders with same amount '{bullx_group[0].get('parsed_data', {}).get('order_amount', '')}'")
                        logger.info(f"         Using expiry-based tiebreaker (higher expiry = more recent = higher bracket)")
                        
                        # Sort BullX orders by expiry (descending: higher = more recent)
                        bullx_sorted = []
                        for order_info in bullx_group:
                            parsed_data = order_info.get('parsed_data', {})
                            expiry = parsed_data.get('expiry', '')
                            expiry_seconds = self._parse_expiry_to_seconds(expiry) if expiry else 0
                            
                            bullx_sorted.append({
                                'order_info': order_info,
                                'parsed_data': parsed_data,
                                'expiry': expiry,
                                'expiry_seconds': expiry_seconds
                            })
                        
                        bullx_sorted.sort(key=lambda x: x['expiry_seconds'], reverse=True)
                        
                        # Get potential DB matches for this amount
                        bullx_amount = bullx_sorted[0]['parsed_data'].get('order_amount', '')
                        trigger_condition = bullx_sorted[0]['parsed_data'].get('trigger_condition', '')
                        potential_db_matches = []
                        
                        for order in unmatched_db_orders:
                            if self._amounts_match(bullx_amount, order.order_amount, trigger_condition, order):
                                potential_db_matches.append(order)
                        
                        # Sort DB orders by bracket_id (descending: highest first)
                        potential_db_matches.sort(key=lambda x: x.bracket_id, reverse=True)
                        
                        logger.info(f"         BullX orders sorted by expiry (highest first):")
                        for idx, bo in enumerate(bullx_sorted):
                            logger.info(f"           {idx+1}. Expiry: {bo['expiry']} ({bo['expiry_seconds']}s)")
                        
                        logger.info(f"         DB orders sorted by bracket_id (highest first):")
                        for idx, do in enumerate(potential_db_matches):
                            logger.info(f"           {idx+1}. Order ID {do.id} (Bracket {do.bracket_id})")
                        
                        # Match position-wise: highest expiry → highest bracket
                        matches_made = min(len(bullx_sorted), len(potential_db_matches))
                        for i in range(matches_made):
                            bullx_order = bullx_sorted[i]
                            db_order = potential_db_matches[i]
                            
                            logger.info(f"         ✅ Step 2 Match: Expiry '{bullx_order['expiry']}' → Order ID {db_order.id} (Bracket {db_order.bracket_id})")
                            
                            matched_orders[db_order.id] = bullx_order['order_info']
                            unmatched_db_orders.remove(db_order)
                            
                            # Update trigger condition AND order_amount
                            await self._update_single_order_trigger_condition(
                                db_order,
                                bullx_order['parsed_data'].get('trigger_condition', ''),
                                bullx_order['expiry'],
                                bullx_order['parsed_data'].get('order_amount', '')
                            )
                
                except Exception as e:
                    logger.error(f"         💥 Error matching group: {e}")
            
            # STEP 3: Auto-deduce remaining orders
            remaining_bullx_orders = len(coin_orders) - len(matched_orders)
            if remaining_bullx_orders > 0 and len(unmatched_db_orders) > 0:
                logger.info(f"      📍 STEP 3: Auto-deducing {remaining_bullx_orders} remaining order(s)")
                logger.info(f"         Remaining BullX orders: {remaining_bullx_orders}")
                logger.info(f"         Unmatched DB orders: {len(unmatched_db_orders)}")
                
                # Collect all unmatched BullX orders
                unmatched_bullx_orders = []
                for i, order_info in enumerate(coin_orders):
                    try:
                        parsed_data = order_info.get('parsed_data', {})
                        trigger_condition = parsed_data.get('trigger_condition', '')
                        order_amount = parsed_data.get('order_amount', '')
                        
                        # Check if THIS specific order_info has already been matched
                        # (not just if the trigger condition matches, since all fulfilled orders have same trigger)
                        is_already_matched = any(oi is order_info for oi in matched_orders.values())
                        
                        if is_already_matched:
                            continue
                        
                        # Extract numeric value for sorting
                        numeric_amount = self._extract_numeric_value(order_amount) if order_amount else None
                        
                        unmatched_bullx_orders.append({
                            'order_info': order_info,
                            'parsed_data': parsed_data,
                            'trigger_condition': trigger_condition,
                            'order_amount': order_amount,
                            'numeric_amount': numeric_amount
                        })
                        
                    except Exception as e:
                        logger.error(f"         💥 Error collecting unmatched order {i+1}: {e}")
                
                if not unmatched_bullx_orders:
                    logger.warning(f"         ⚠️  Could not find any unmatched BullX orders")
                else:
                    logger.info(f"         Found {len(unmatched_bullx_orders)} unmatched BullX orders")
                    
                    # Case 1: Single remaining order - simple auto-deduce
                    if len(unmatched_bullx_orders) == 1 and len(unmatched_db_orders) == 1:
                        logger.info(f"         Case 1: Single order auto-deduction")
                        
                        bullx_order = unmatched_bullx_orders[0]
                        matched_order = unmatched_db_orders[0]
                        
                        logger.info(f"         ✅ Step 3 Match: Auto-deduced → Order ID {matched_order.id} (Bracket {matched_order.bracket_id})")
                        logger.info(f"            BullX: Trigger='{bullx_order['trigger_condition']}', Amount='{bullx_order['order_amount']}'")
                        
                        matched_orders[matched_order.id] = bullx_order['order_info']
                        unmatched_db_orders.remove(matched_order)
                        
                        # Update trigger condition AND order_amount
                        await self._update_single_order_trigger_condition(
                            matched_order, 
                            bullx_order['trigger_condition'], 
                            bullx_order['parsed_data'].get('expiry', ''),
                            bullx_order['order_amount']
                        )
                    
                    # Case 2: Multiple remaining orders - match by order_amount heuristic
                    elif len(unmatched_bullx_orders) > 1 and len(unmatched_db_orders) > 1:
                        logger.info(f"         Case 2: Multiple orders - using order_amount heuristic")
                        logger.info(f"            Logic: Smallest amount → Highest bracket sub_id (since entries are ascending)")
                        
                        # Sort BullX orders by numeric amount (ascending: smallest first)
                        bullx_sorted = sorted(
                            [o for o in unmatched_bullx_orders if o['numeric_amount'] is not None],
                            key=lambda x: x['numeric_amount']
                        )
                        
                        # Sort DB orders by bracket_id (descending: highest first)
                        db_sorted = sorted(unmatched_db_orders, key=lambda x: x.bracket_id, reverse=True)
                        
                        logger.info(f"            BullX orders sorted by amount (smallest first):")
                        for idx, bo in enumerate(bullx_sorted):
                            logger.info(f"              {idx+1}. Amount: {bo['order_amount']} (numeric: {bo['numeric_amount']:.2f})")
                        
                        logger.info(f"            DB orders sorted by bracket_id (highest first):")
                        for idx, do in enumerate(db_sorted):
                            logger.info(f"              {idx+1}. Order ID {do.id} (Bracket {do.bracket_id})")
                        
                        # Match smallest amount to highest bracket_id, second smallest to second highest, etc.
                        matches_made = min(len(bullx_sorted), len(db_sorted))
                        for i in range(matches_made):
                            bullx_order = bullx_sorted[i]
                            db_order = db_sorted[i]
                            
                            logger.info(f"         ✅ Step 3 Match: Amount '{bullx_order['order_amount']}' → Order ID {db_order.id} (Bracket {db_order.bracket_id})")
                            
                            matched_orders[db_order.id] = bullx_order['order_info']
                            unmatched_db_orders.remove(db_order)
                            
                            # Update trigger condition AND order_amount
                            await self._update_single_order_trigger_condition(
                                db_order, 
                                bullx_order['trigger_condition'], 
                                bullx_order['parsed_data'].get('expiry', ''),
                                bullx_order['order_amount']
                            )
                    
                    # Case 3: Mismatch in counts - log warning
                    else:
                        logger.warning(f"         ⚠️  Order count mismatch:")
                        logger.warning(f"            BullX: {len(unmatched_bullx_orders)} orders, DB: {len(unmatched_db_orders)} orders")
                        logger.warning(f"            Cannot reliably auto-deduce")
            
            # Log any unmatched orders
            if len(unmatched_db_orders) > 0 or remaining_bullx_orders > len(unmatched_db_orders):
                logger.warning(f"      ⚠️  Identification incomplete:")
                logger.warning(f"         BullX orders: {len(coin_orders)}, Matched: {len(matched_orders)}")
                logger.warning(f"         DB orders: {len(active_orders)}, Unmatched: {len(unmatched_db_orders)}")
                for order in unmatched_db_orders:
                    logger.warning(f"         ❌ Unmatched DB Order ID {order.id} (Bracket {order.bracket_id})")
            
            logger.info(f"      📊 Identification complete: {len(matched_orders)}/{len(coin_orders)} BullX orders matched")
                        
        except Exception as e:
            logger.error(f"💥 Error updating trigger conditions for coin: {e}")
    
    def _identify_remaining_order(self, parsed_data: Dict[str, Any], unmatched_orders: List[Order], 
                                trigger_condition: str, expiry: str) -> Optional[Order]:
        """Identify remaining orders using alternative methods (trigger condition, expiry time, fallback)"""
        try:
            if not unmatched_orders:
                return None
            
            # Method 1: Try trigger condition exact match
            for order in unmatched_orders:
                if order.trigger_condition == trigger_condition:
                    logger.debug(f"         🎯 Trigger condition match: Order ID {order.id}")
                    return order
            
            # Method 2: Try expiry time matching if multiple orders
            if len(unmatched_orders) > 1:
                expiry_seconds = self._parse_expiry_to_seconds(expiry)
                if expiry_seconds is not None:
                    best_match = self._match_by_expiry_time(unmatched_orders, expiry_seconds, trigger_condition)
                    if best_match:
                        logger.debug(f"         🕐 Expiry time match: Order ID {best_match.id}")
                        return best_match
            
            # Method 3: TP condition fallback
            if self._is_tp_condition(trigger_condition) and unmatched_orders:
                logger.debug(f"         🎯 TP fallback match: Order ID {unmatched_orders[0].id}")
                return unmatched_orders[0]
            
            # Method 4: Sequential fallback (last resort)
            if unmatched_orders:
                unmatched_orders.sort(key=lambda x: x.bracket_id)
                logger.debug(f"         ⚠️  Sequential fallback: Order ID {unmatched_orders[0].id}")
                return unmatched_orders[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error identifying remaining order: {e}")
            return None
    
    async def _update_single_order_trigger_condition(self, order: Order, trigger_condition: str, expiry: str, order_amount: str = None):
        """Update trigger condition AND order_amount for a single order with BullX timing"""
        try:
            current_trigger = order.trigger_condition
            current_order_amount = order.order_amount
            
            # Check if trigger condition needs update
            trigger_needs_update = (
                current_trigger != trigger_condition or 
                current_trigger is None or 
                current_trigger == "" or 
                current_trigger == "None"
            )
            
            # Check if order_amount needs update (only if provided)
            amount_needs_update = False
            if order_amount:
                amount_needs_update = (
                    current_order_amount != order_amount or
                    current_order_amount is None or
                    current_order_amount == ""
                )
            
            # Update trigger condition if needed
            if trigger_needs_update:
                # Always try to calculate BullX update time for any trigger condition change
                bullx_update_time = self._calculate_bullx_update_time(expiry)
                
                if bullx_update_time:
                    # Use calculated BullX update time for all updates
                    self._update_order_with_bullx_refresh(
                        order.id, trigger_condition, bullx_update_time
                    )
                    
                    # Check if this is a BullX automation refresh (entry → TP/SL transition) for logging
                    is_bullx_refresh = self._is_bullx_automation_refresh(
                        current_trigger, trigger_condition
                    )
                    
                    if is_bullx_refresh:
                        logger.info(f"         🔄 BullX automation refresh detected for order {order.id}:")
                        logger.info(f"            Trigger: '{current_trigger}' → '{trigger_condition}'")
                        logger.info(f"            Calculated BullX update time: {bullx_update_time}")
                    elif current_trigger is None or current_trigger == "" or current_trigger == "None":
                        logger.info(f"         📝 Initial trigger condition set for order {order.id}: '{trigger_condition}'")
                        logger.info(f"            Calculated BullX update time: {bullx_update_time}")
                    else:
                        logger.info(f"         📝 Updated trigger condition for order {order.id}: '{current_trigger}' → '{trigger_condition}'")
                        logger.info(f"            Calculated BullX update time: {bullx_update_time}")
                else:
                    # Fallback to regular update if calculation fails
                    self._update_order_trigger_condition(order.id, trigger_condition)
                    logger.warning(f"         ⚠️  Could not calculate BullX update time, using regular update for order {order.id}")
                    
                    if current_trigger is None or current_trigger == "" or current_trigger == "None":
                        logger.info(f"         📝 Initial trigger condition set for order {order.id}: '{trigger_condition}'")
                    else:
                        logger.debug(f"         📝 Updated trigger condition for order {order.id}: '{current_trigger}' → '{trigger_condition}'")
            
            # Update order_amount if needed
            if amount_needs_update:
                success = db_manager.update_order_amount(order.id, order_amount)
                if success:
                    if current_order_amount:
                        logger.info(f"         💰 Updated order_amount for order {order.id}: '{current_order_amount}' → '{order_amount}'")
                    else:
                        logger.info(f"         💰 Set order_amount for order {order.id}: '{order_amount}'")
                else:
                    logger.warning(f"         ⚠️  Failed to update order_amount for order {order.id}")
            
            # Log if nothing changed
            if not trigger_needs_update and not amount_needs_update:
                logger.debug(f"         ✅ No updates needed for order {order.id}")
                
        except Exception as e:
            logger.error(f"Error updating order: {e}")
    
    def _identify_order_by_wallet_count(self, parsed_data: Dict[str, Any]) -> Optional[int]:
        """
        Primary identification method: Identify bracket sub ID by wallet count.
        
        Wallet count directly maps to bracket sub ID:
        - 1 wallet → Bracket Sub ID 1
        - 2 wallets → Bracket Sub ID 2  
        - 3 wallets → Bracket Sub ID 3
        - 4 wallets → Bracket Sub ID 4
        
        Args:
            parsed_data: Parsed row data from BullX
            
        Returns:
            Bracket sub ID (1-4) or None if not identifiable
        """
        try:
            wallets = parsed_data.get('wallets', '')
            
            if not wallets:
                logger.debug(f"No wallet count found in parsed data")
                return None
            
            try:
                wallet_count = int(wallets)
                
                if 1 <= wallet_count <= 4:
                    logger.debug(f"Wallet-based identification: {wallet_count} wallets → Bracket Sub ID {wallet_count}")
                    return wallet_count
                else:
                    logger.warning(f"Wallet count {wallet_count} is outside expected range (1-4)")
                    return None
                    
            except ValueError:
                logger.warning(f"Could not parse wallet count '{wallets}' as integer")
                return None
                
        except Exception as e:
            logger.error(f"Error identifying order by wallet count: {e}")
            return None
    
    def _amounts_match(self, bullx_amount: str, db_order_amount: str, bullx_trigger: str, order: Order) -> bool:
        """
        Check if a BullX amount matches a database order amount.
        Handles exact matches, fuzzy matches, and partial fills.
        
        Args:
            bullx_amount: Amount from BullX display
            db_order_amount: Amount from database
            bullx_trigger: BullX trigger condition
            order: Database order being checked
            
        Returns:
            True if amounts match, False otherwise
        """
        try:
            if not bullx_amount or not db_order_amount:
                return False
            
            # Normalize for comparison
            bullx_normalized = self._normalize_amount_string(bullx_amount)
            db_normalized = self._normalize_amount_string(db_order_amount)
            
            # Exact match
            if bullx_normalized == db_normalized:
                return True
            
            # Numeric fuzzy match
            bullx_numeric = self._extract_numeric_value(bullx_amount)
            db_numeric = self._extract_numeric_value(db_order_amount)
            
            if bullx_numeric is not None and db_numeric is not None:
                # Standard fuzzy match
                difference = abs(bullx_numeric - db_numeric)
                tolerance = max(bullx_numeric * 0.01, 0.001)
                
                if difference <= tolerance:
                    return True
                
                # Check partial fill match
                if order.trigger_condition == "1 TP, 1 SL":
                    partial_match = self._check_partial_fill_match(
                        bullx_numeric, db_numeric, bullx_trigger, order
                    )
                    if partial_match:
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking if amounts match: {e}")
            return False
    
    def _match_by_order_amount(self, bullx_amount: str, unmatched_orders: List[Order], bullx_trigger: str = "") -> Optional[Order]:
        """
        Match order by comparing BullX display amount with database order_amount field.
        Allows fuzzy matching for small differences in formatting.
        Enhanced to handle partial fills when TP or SL has been hit.
        
        Args:
            bullx_amount: Amount displayed in BullX (e.g., "0.5", "289.55K STIMMY")
            unmatched_orders: List of unmatched database orders
            bullx_trigger: BullX trigger condition (e.g., "1 SL", "1 TP", "1 TP, 1 SL")
            
        Returns:
            Best matching order or None if no match found
        """
        try:
            if not bullx_amount or not unmatched_orders:
                return None
            
            # Normalize BullX amount for comparison
            bullx_normalized = self._normalize_amount_string(bullx_amount)
            bullx_numeric = self._extract_numeric_value(bullx_amount)
            
            logger.info(f"         🔍 Matching BullX amount '{bullx_amount}':")
            logger.info(f"            Normalized: '{bullx_normalized}', Numeric: {bullx_numeric}")
            logger.info(f"            BullX trigger: '{bullx_trigger}'")
            logger.info(f"            Unmatched orders: {len(unmatched_orders)}")
            
            # Try exact match first
            for order in unmatched_orders:
                if order.order_amount:
                    db_normalized = self._normalize_amount_string(order.order_amount)
                    if bullx_normalized == db_normalized:
                        logger.debug(f"  ✅ Exact match: Order ID {order.id}, DB amount: '{order.order_amount}'")
                        return order
            
            # Try fuzzy match for numeric values (including partial fill logic)
            best_match = None
            smallest_difference = float('inf')
            
            for order in unmatched_orders:
                if not order.order_amount:
                    continue
                
                db_numeric = self._extract_numeric_value(order.order_amount)
                
                if bullx_numeric is not None and db_numeric is not None:
                    # Standard fuzzy match
                    difference = abs(bullx_numeric - db_numeric)
                    tolerance = max(bullx_numeric * 0.01, 0.001)
                    
                    if difference <= tolerance and difference < smallest_difference:
                        smallest_difference = difference
                        best_match = order
                        logger.debug(f"  🎯 Fuzzy match candidate: Order ID {order.id}, DB amount: '{order.order_amount}', diff: {difference}")
                    
                    # Enhanced: Check for partial fills if DB order has "1 TP, 1 SL" trigger
                    logger.info(f"            Checking Order ID {order.id}: DB trigger='{order.trigger_condition}', DB amount={db_numeric}")
                    if order.trigger_condition == "1 TP, 1 SL":
                        logger.info(f"            → Order has '1 TP, 1 SL' trigger, checking partial fill match...")
                        partial_match = self._check_partial_fill_match(
                            bullx_numeric, db_numeric, bullx_trigger, order
                        )
                        
                        if partial_match:
                            difference = partial_match['difference']
                            logger.info(f"            ✅ Partial fill detected: {partial_match['type']}")
                            logger.info(f"               Expected: {partial_match['expected_amount']:.2f}, Actual: {bullx_numeric:.2f}, Diff: {difference:.2f}")
                            if difference < smallest_difference:
                                smallest_difference = difference
                                best_match = order
                                logger.info(f"               → New best match (smallest difference)")
                        else:
                            logger.info(f"            ❌ No partial fill match found")
                    else:
                        logger.debug(f"            → Order trigger is '{order.trigger_condition}', not '1 TP, 1 SL', skipping partial fill check")
            
            if best_match:
                logger.debug(f"  ✅ Best match: Order ID {best_match.id}")
                return best_match
            
            logger.debug(f"  ❌ No match found for amount '{bullx_amount}'")
            return None
            
        except Exception as e:
            logger.error(f"Error matching by order amount: {e}")
            return None
    
    def _check_partial_fill_match(self, bullx_numeric: float, db_numeric: float, bullx_trigger: str, order: Order) -> Optional[Dict]:
        """
        Check if BullX amount matches a partial fill scenario (TP or SL hit).
        
        Logic:
        - Original amount is split: TP portion (db_amount / 1.9) + SL portion (db_amount / 1.9)
        - If ONLY "1 SL" trigger: Only SL remains = db_amount / 1.9
        - If ONLY "1 TP" trigger: Only TP remains = db_amount - (db_amount / 1.9)
        
        Args:
            bullx_numeric: Numeric value from BullX display
            db_numeric: Numeric value from database order_amount
            bullx_trigger: BullX trigger condition
            order: Database order being checked
            
        Returns:
            Match info dict if partial fill detected, None otherwise
        """
        try:
            # Only check for orders with "1 TP, 1 SL" in database
            if order.trigger_condition != "1 TP, 1 SL":
                return None
            
            # Use pattern-based trigger type detection
            trigger_type = self._check_trigger_condition_type(bullx_trigger)
            tolerance_percent = 0.05  # 5% tolerance for matching
            
            # Case 1: Only SL remains (TP was hit)
            if trigger_type['has_sl_only']:
                expected_amount = db_numeric / 1.9  # SL portion
                difference = abs(bullx_numeric - expected_amount)
                tolerance = expected_amount * tolerance_percent
                
                if difference <= tolerance:
                    return {
                        'type': 'SL_only (TP hit)',
                        'expected_amount': expected_amount,
                        'difference': difference
                    }
            
            # Case 2: Only TP remains (SL was hit)
            elif trigger_type['has_tp_only']:
                expected_amount = db_numeric - (db_numeric / 1.9)  # TP portion
                difference = abs(bullx_numeric - expected_amount)
                tolerance = expected_amount * tolerance_percent
                
                if difference <= tolerance:
                    return {
                        'type': 'TP_only (SL hit)',
                        'expected_amount': expected_amount,
                        'difference': difference
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking partial fill match: {e}")
            return None
    
    def _normalize_amount_string(self, amount_str: str) -> str:
        """
        Normalize amount string for comparison by removing whitespace and converting to lowercase.
        
        Examples:
        - "0.5" → "0.5"
        - "289.55K STIMMY" → "289.55kstimmy"
        - " 0.50 " → "0.50"
        """
        try:
            return amount_str.strip().lower().replace(" ", "")
        except Exception as e:
            logger.error(f"Error normalizing amount string '{amount_str}': {e}")
            return ""
    
    def _extract_numeric_value(self, amount_str: str) -> Optional[float]:
        """
        Extract numeric value from amount string.
        
        Examples:
        - "0.5" → 0.5
        - "289.55K" → 289.55
        - "289.55K STIMMY" → 289.55
        - "1.5M" → 1500 (converts M to actual number)
        
        Returns:
            Numeric value as float, or None if not parseable
        """
        try:
            import re
            
            # Extract number and suffix (K, M, B)
            pattern = r'([0-9]+(?:\.[0-9]+)?)(K|k|M|m|B|b)?'
            match = re.search(pattern, amount_str)
            
            if not match:
                return None
            
            number_str = match.group(1)
            suffix = match.group(2)
            
            number = float(number_str)
            
            # Apply suffix multiplier (if present)
            if suffix:
                suffix_lower = suffix.lower()
                if suffix_lower == 'k':
                    number *= 1000
                elif suffix_lower == 'm':
                    number *= 1000000
                elif suffix_lower == 'b':
                    number *= 1000000000
            
            return number
            
        except Exception as e:
            logger.error(f"Error extracting numeric value from '{amount_str}': {e}")
            return None
    
    def _verify_with_entry_price(self, bracket_sub_id: int, trigger_condition: str, bracket_entries: List[float]) -> bool:
        """
        Secondary verification: Verify wallet-based identification with entry price where possible.
        
        Args:
            bracket_sub_id: Bracket sub ID from wallet count (1-4)
            trigger_condition: Trigger condition from BullX
            bracket_entries: List of bracket entry prices [entry1, entry2, entry3, entry4]
            
        Returns:
            True if verified or verification not possible, False if mismatch detected
        """
        try:
            # Extract entry price from trigger condition
            entry_price = self._parse_trigger_condition_entry_price(trigger_condition)
            
            if not entry_price:
                # Can't verify without entry price, assume wallet ID is correct
                logger.debug(f"No entry price found for verification - assuming wallet-based ID is correct")
                return True
            
            # Get expected entry price for this bracket sub ID
            if bracket_sub_id < 1 or bracket_sub_id > len(bracket_entries):
                logger.warning(f"Bracket sub ID {bracket_sub_id} is outside bracket entries range")
                return False
            
            expected_entry = bracket_entries[bracket_sub_id - 1]  # Convert to 0-based index
            
            # Allow tolerance for floating point comparison
            tolerance = 1000  # 1000 unit tolerance
            difference = abs(entry_price - expected_entry)
            
            is_verified = difference <= tolerance
            
            logger.debug(f"Entry price verification:")
            logger.debug(f"  Bracket Sub ID: {bracket_sub_id}")
            logger.debug(f"  Expected Entry: ${expected_entry:,.0f}")
            logger.debug(f"  Actual Entry: ${entry_price:,.0f}")
            logger.debug(f"  Difference: ${difference:,.0f}")
            logger.debug(f"  Verified: {is_verified}")
            
            if not is_verified:
                logger.warning(f"Entry price verification failed: expected ${expected_entry:,.0f}, got ${entry_price:,.0f}")
            
            return is_verified
            
        except Exception as e:
            logger.error(f"Error verifying with entry price: {e}")
            return True  # Assume correct if verification fails
    
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
    
    def _check_sl_with_any_expired(self, coin_orders: List[Dict]) -> bool:
        """
        PRIORITY 1: Check if coin has SL hit ("1 TP") AND any expired orders.
        This triggers "cancel all + sell" regardless of whether SL order itself is expired.
        
        Args:
            coin_orders: List of order info dicts from BullX with parsed_data
            
        Returns:
            True if condition met (has SL hit + any expired), False otherwise
        """
        try:
            has_sl_hit = False
            has_any_expired = False
            
            for order_info in coin_orders:
                parsed_data = order_info.get('parsed_data', {})
                trigger = parsed_data.get('trigger_condition', '')
                expiry = parsed_data.get('expiry', '')
                
                # Check for "1 TP" (SL was hit)
                trigger_type = self._check_trigger_condition_type(trigger)
                if trigger_type['has_tp_only']:
                    has_sl_hit = True
                    logger.debug(f"      Found SL hit order: trigger='{trigger}'")
                
                # Check if expired
                if expiry == "00h 00m 00s":
                    has_any_expired = True
                    logger.debug(f"      Found expired order: expiry='{expiry}'")
            
            condition_met = has_sl_hit and has_any_expired
            
            if condition_met:
                logger.info(f"  🚨 PRIORITY 1: SL hit + ANY expired detected!")
                logger.info(f"     → Action: Cancel all + sell")
            
            return condition_met
            
        except Exception as e:
            logger.error(f"Error checking SL + any expired condition: {e}")
            return False
    
    def _get_individual_expired_orders(self, coin_orders: List[Dict]) -> List[Dict]:
        """
        PRIORITY 2: Get expired orders when NO SL hit.
        Returns list of expired orders for individual renewal.
        
        Args:
            coin_orders: List of order info dicts from BullX with parsed_data
            
        Returns:
            List of expired order info dicts
        """
        try:
            expired_orders = []
            
            for order_info in coin_orders:
                parsed_data = order_info.get('parsed_data', {})
                expiry = parsed_data.get('expiry', '')
                
                if expiry == "00h 00m 00s":
                    expired_orders.append(order_info)
                    logger.debug(f"      Found individually expired order")
            
            if expired_orders:
                logger.info(f"  ⏰ PRIORITY 2: {len(expired_orders)} individually expired orders detected!")
                logger.info(f"     → Action: Renew expired orders individually")
            
            return expired_orders
            
        except Exception as e:
            logger.error(f"Error getting individual expired orders: {e}")
            return []
    
    def _check_sl_expired_condition(self, coin_orders: List[Dict]) -> bool:
        """
        DEPRECATED: Use _check_sl_with_any_expired instead.
        Kept for backward compatibility.
        """
        return self._check_sl_with_any_expired(coin_orders)
    
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
    
    async def _process_individual_expired_orders(self, profile_name: str) -> Dict:
        """
        Process individual expired orders: Delete from BullX, update to COMPLETED, mark for renewal.
        
        Args:
            profile_name: Chrome profile name
            
        Returns:
            Dict with processing results
        """
        try:
            if not self.individual_expired_orders:
                logger.info("📝 No individual expired orders to process")
                return {"orders_processed": 0}
            
            logger.info(f"\n{'='*80}")
            logger.info(f"⏰ PROCESSING {len(self.individual_expired_orders)} INDIVIDUAL EXPIRED ORDERS")
            logger.info(f"{'='*80}")
            
            orders_processed = 0
            
            for expired_order_dict in self.individual_expired_orders:
                try:
                    order = expired_order_dict['order']
                    order_info = expired_order_dict['order_info']
                    coin = expired_order_dict['coin']
                    button_index = order_info['button_index']
                    row_index = order_info['row_index']
                    
                    logger.info(f"\n📝 Processing expired order: ID {order.id} (Bracket {order.bracket_id})")
                    logger.info(f"   Coin: {coin.name or coin.address}")
                    
                    # Step 1: Re-click filter button
                    filter_success = await self._click_coin_filter_button(profile_name, button_index)
                    if not filter_success:
                        logger.error(f"   ❌ Failed to click filter button - skipping")
                        continue
                    
                    # Step 2: Delete from BullX
                    logger.info(f"   🗑️  Deleting expired order from BullX...")
                    deletion_success = await self._delete_bullx_entry(profile_name, button_index, row_index)
                    
                    if not deletion_success:
                        logger.error(f"   ❌ Failed to delete from BullX - skipping")
                        continue
                    
                    # Wait for deletion to process
                    time.sleep(2)
                    
                    # Step 3: Update database to EXPIRED (not COMPLETED, since it expired individually)
                    logger.info(f"   📝 Updating database to EXPIRED...")
                    db_success = db_manager.update_order_status(order.id, "EXPIRED")
                    
                    if not db_success:
                        logger.error(f"   ❌ Failed to update database - skipping")
                        continue
                    
                    logger.info(f"   ✅ Order {order.id} marked as EXPIRED")
                    
                    # Step 4: Mark for renewal
                    renewal_info = {
                        'order_id': order.id,
                        'coin_address': coin.address,
                        'coin_name': coin.name,
                        'parsed_data': order_info['parsed_data'],
                        'button_index': button_index,
                        'row_index': row_index,
                        'original_bracket': coin.bracket,
                        'bracket_sub_id': order.bracket_id,
                        'profile_name': profile_name,
                        'amount': order.amount or 1.0
                    }
                    
                    self.orders_for_renewal.append(renewal_info)
                    orders_processed += 1
                    logger.info(f"   ✅ Order {order.id} marked for renewal")
                    
                except Exception as e:
                    logger.error(f"   💥 Error processing individual expired order: {e}")
                    continue
            
            logger.info(f"\n{'='*80}")
            logger.info(f"✅ INDIVIDUAL EXPIRED ORDERS COMPLETED: {orders_processed}/{len(self.individual_expired_orders)}")
            logger.info(f"{'='*80}")
            
            return {"orders_processed": orders_processed}
            
        except Exception as e:
            logger.error(f"💥 Error processing individual expired orders: {e}")
            return {"orders_processed": 0, "error": str(e)}
    
    async def _process_expired_coins(self, profile_name: str) -> Dict:
        """
        Process coins with SL hit + all expired: Cancel all orders, sell all coins, update DB.
        
        Args:
            profile_name: Chrome profile name
            
        Returns:
            Dict with processing results
        """
        try:
            if not self.expired_coins:
                logger.info("📝 No expired coins to process")
                return {"coins_processed": 0, "expired_details": []}
            
            logger.info(f"\n{'='*80}")
            logger.info(f"🚨 PROCESSING {len(self.expired_coins)} EXPIRED COINS")
            logger.info(f"{'='*80}")
            
            expired_details = []
            coins_processed = 0
            
            for expired_coin_info in self.expired_coins:
                try:
                    coin = expired_coin_info['coin']
                    button_index = expired_coin_info['button_index']
                    token = expired_coin_info['token']
                    coin_orders = expired_coin_info['coin_orders']
                    
                    logger.info(f"\n🪙 Processing expired coin: {coin.name or coin.address}")
                    logger.info(f"   Orders on BullX: {len(coin_orders)}")
                    
                    coin_detail = {
                        'coin_address': coin.address,
                        'coin_name': coin.name,
                        'orders_cancelled': 0,
                        'sell_success': False,
                        'db_orders_updated': 0
                    }
                    
                    # Step 1: Cancel all orders for this coin
                    logger.info(f"   📋 Step 1: Cancelling all orders...")
                    cancel_success = await self._cancel_all_orders_for_coin(profile_name, button_index)
                    
                    if cancel_success:
                        coin_detail['orders_cancelled'] = len(coin_orders)
                        logger.info(f"   ✅ Successfully cancelled all orders")
                    else:
                        logger.error(f"   ❌ Failed to cancel all orders")
                        expired_details.append(coin_detail)
                        continue
                    
                    # Step 2: Sell all remaining coins
                    logger.info(f"   💰 Step 2: Selling all remaining coins...")
                    sell_success = await self._sell_all_coins(profile_name, coin.url)
                    
                    coin_detail['sell_success'] = sell_success
                    if sell_success:
                        logger.info(f"   ✅ Successfully sold all coins")
                    else:
                        logger.error(f"   ❌ Failed to sell all coins (best effort)")
                    
                    # Step 3: Update database orders to EXPIRED
                    logger.info(f"   📝 Step 3: Updating database orders to EXPIRED...")
                    updated_count = self._update_orders_to_expired(coin.id, profile_name)
                    coin_detail['db_orders_updated'] = updated_count
                    
                    if updated_count > 0:
                        logger.info(f"   ✅ Updated {updated_count} orders to EXPIRED status")
                    else:
                        logger.warning(f"   ⚠️  No orders updated in database")
                    
                    coins_processed += 1
                    expired_details.append(coin_detail)
                    
                except Exception as e:
                    logger.error(f"   💥 Error processing expired coin {coin.name or coin.address}: {e}")
                    continue
            
            logger.info(f"\n{'='*80}")
            logger.info(f"✅ EXPIRED COIN PROCESSING COMPLETED: {coins_processed}/{len(self.expired_coins)}")
            logger.info(f"{'='*80}")
            
            return {
                "coins_processed": coins_processed,
                "expired_details": expired_details
            }
            
        except Exception as e:
            logger.error(f"💥 Error processing expired coins: {e}")
            return {"coins_processed": 0, "expired_details": [], "error": str(e)}
    
    async def _cancel_all_orders_for_coin(self, profile_name: str, button_index: int) -> bool:
        """
        Cancel all orders for a specific coin using the Cancel All button.
        
        Args:
            profile_name: Chrome profile name
            button_index: Filter button index for the coin
            
        Returns:
            True if successful, False otherwise
        """
        try:
            driver = self.driver_manager.get_driver(profile_name)
            
            # Re-click filter button to ensure correct view
            filter_success = await self._click_coin_filter_button(profile_name, button_index)
            if not filter_success:
                logger.error(f"      ❌ Failed to click filter button")
                return False
            
            # Find and click the Cancel All button
            cancel_all_xpath = "//*[@id='root']/div[1]/div[2]/main/div/section/div[2]/div[1]/button/span"
            
            try:
                # Try to find the button or its parent
                try:
                    cancel_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, cancel_all_xpath))
                    )
                except:
                    # Try parent button element
                    cancel_all_button_xpath = "//*[@id='root']/div[1]/div[2]/main/div/section/div[2]/div[1]/button"
                    cancel_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, cancel_all_button_xpath))
                    )
                
                # Scroll into view
                driver.execute_script("arguments[0].scrollIntoView(true);", cancel_button)
                time.sleep(0.5)
                
                # Click the button
                cancel_button.click()
                logger.info(f"      ✅ Clicked Cancel All button")
                
                # Wait for cancellation to process
                time.sleep(2)
                
                return True
                
            except TimeoutException:
                logger.error(f"      ❌ Cancel All button not found")
                return False
            except Exception as e:
                logger.error(f"      💥 Error clicking Cancel All button: {e}")
                return False
                
        except Exception as e:
            logger.error(f"      💥 Error in cancel_all_orders_for_coin: {e}")
            return False
    
    async def _sell_all_coins(self, profile_name: str, coin_url: str) -> bool:
        """
        Navigate to coin page and sell all remaining coins.
        
        Args:
            profile_name: Chrome profile name
            coin_url: URL of the coin page
            
        Returns:
            True if successful, False otherwise
        """
        try:
            driver = self.driver_manager.get_driver(profile_name)
            
            if not coin_url:
                logger.error(f"      ❌ No coin URL provided")
                return False
            
            # Navigate to coin page
            logger.info(f"      🌐 Navigating to coin page: {coin_url}")
            driver.get(coin_url)
            time.sleep(2)
            
            # Click Sell button
            sell_button_xpath = "//*[@id='root']/div[1]/div[2]/main/div/div[2]/aside/div/div[3]/div/div/div/div[1]/div[3]/div[1]/div/div/label[2]/div"
            
            try:
                sell_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, sell_button_xpath))
                )
                sell_button.click()
                logger.info(f"      ✅ Clicked Sell button")
                time.sleep(1)
            except Exception as e:
                logger.error(f"      ❌ Failed to click Sell button: {e}")
                return False
            
            # Click 100% button
            percent_100_xpath = "//*[contains(@id, 'panel-sell')]/div/div[2]/div/div[1]/div[2]/button[4]/span"
            
            try:
                # Try span first
                try:
                    percent_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, percent_100_xpath))
                    )
                except:
                    # Try parent button
                    percent_100_button_xpath = "//*[contains(@id, 'panel-sell')]/div/div[2]/div/div[1]/div[2]/button[4]"
                    percent_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, percent_100_button_xpath))
                    )
                
                percent_button.click()
                logger.info(f"      ✅ Clicked 100% button")
                time.sleep(1)
            except Exception as e:
                logger.error(f"      ❌ Failed to click 100% button: {e}")
                return False
            
            # Click final Sell button
            final_sell_xpath = "//*[contains(@id, 'panel-sell')]/div/div[2]/div/footer/div[3]/button"
            
            try:
                final_sell_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, final_sell_xpath))
                )
                final_sell_button.click()
                logger.info(f"      ✅ Clicked final Sell button")
                time.sleep(2)
            except Exception as e:
                logger.error(f"      ❌ Failed to click final Sell button: {e}")
                return False
            
            # Navigate back to automation tab
            logger.info(f"      🔙 Navigating back to automation tab...")
            automation_url = "https://bullx.io/terminal?chainId=1399811149"
            driver.get(automation_url)
            time.sleep(2)
            
            logger.info(f"      ✅ Successfully completed sell operation")
            return True
            
        except Exception as e:
            logger.error(f"      💥 Error in sell_all_coins: {e}")
            return False
    
    def _update_orders_to_expired(self, coin_id: int, profile_name: str) -> int:
        """
        Update all active orders for a coin and profile to EXPIRED status.
        
        Args:
            coin_id: Coin database ID
            profile_name: Chrome profile name
            
        Returns:
            Number of orders updated
        """
        try:
            # Get all active orders for this coin and profile
            all_orders = db_manager.get_orders_by_coin(coin_id)
            active_orders = [o for o in all_orders if o.profile_name == profile_name and o.status == "ACTIVE"]
            
            logger.info(f"      📋 Found {len(active_orders)} active orders to update")
            
            updated_count = 0
            for order in active_orders:
                success = db_manager.update_order_status(order.id, "EXPIRED")
                if success:
                    updated_count += 1
                    logger.debug(f"         ✅ Updated order {order.id} to EXPIRED")
                else:
                    logger.warning(f"         ⚠️  Failed to update order {order.id}")
            
            return updated_count
            
        except Exception as e:
            logger.error(f"      💥 Error updating orders to expired: {e}")
            return 0
    
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
    
    def _generate_processing_summary(self, check_result: Dict, renewal_results: Dict, expired_results: Dict = None) -> str:
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
            
            # Expired coins summary
            if expired_results:
                expired_coins = expired_results.get("coins_processed", 0)
                summary_lines.append(f"🚨 Expired Coins Processed: {expired_coins}")
            
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
