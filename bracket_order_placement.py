"""
Bracket Order Placement System for BullXAuto

This module handles the placement of orders in the bracket strategy system,
including market vs limit order logic, auto-sell frame interactions, and
bracket-specific strategy selection.
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.keys import Keys
import time
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from bracket_config import (
    calculate_bracket, 
    get_bracket_info, 
    calculate_order_parameters,
    BRACKET_CONFIG
)
from chrome_driver import BullXAutomator
from database import db_manager

logger = logging.getLogger(__name__)

class BracketOrderPlacer:
    def __init__(self, bullx_automator: BullXAutomator):
        self.automator = bullx_automator
        self.driver_manager = bullx_automator.driver_manager
    
    def place_bracket_orders(self, profile_name: str, address: str, total_amount: float, 
                           strategy_number: int = 1) -> Dict:
        """
        Place all four bracket orders for a coin based on its market cap bracket.
        
        Args:
            profile_name: Chrome profile name
            address: Token contract address
            total_amount: Total investment amount to split across orders
            strategy_number: Strategy number for tracking
            
        Returns:
            Dict with success status and order details
        """
        try:
            # Ensure we're logged in and search for the coin
            if not self.automator._ensure_logged_in(profile_name):
                return {"success": False, "error": "Failed to login"}
            
            if not self.automator.search_address(profile_name, address):
                return {"success": False, "error": "Failed to search address"}
            
            # Ensure coin data is extracted and stored (including name)
            driver = self.driver_manager.get_driver(profile_name)
            coin_data = self.automator._extract_coin_data(driver, address)
            
            # Get current market cap
            current_market_cap = self.automator.get_market_cap(profile_name)
            if current_market_cap <= 0:
                return {"success": False, "error": "Failed to get market cap"}
            
            # Calculate bracket and ensure coin data includes bracket and current market cap
            bracket = calculate_bracket(current_market_cap)
            
            # Update coin data with bracket and current market cap
            if coin_data:
                coin_data["bracket"] = bracket
                coin_data["market_cap"] = current_market_cap
            else:
                coin_data = {
                    "bracket": bracket,
                    "market_cap": current_market_cap
                }
            
            # Store/update coin information with bracket
            db_manager.create_or_update_coin(address, coin_data)
            logger.info(f"Stored coin information: bracket {bracket}, market cap ${current_market_cap:,.0f}")
            
            # Get bracket info and calculate order parameters
            bracket_info = get_bracket_info(bracket)
            order_params = calculate_order_parameters(bracket, total_amount)
            
            logger.info(f"Placing bracket {bracket} orders for {address} with market cap ${current_market_cap:,.0f}")
            logger.info(f"Total amount: {total_amount}, Order parameters:")
            for i, param in enumerate(order_params):
                logger.info(f"  Bracket ID {param['bracket_id']}: Amount={param['amount']:.6f} (Trade size: {param['trade_size_pct']:.4f})")
            
            # Place each order
            placed_orders = []
            failed_orders = []
            
            for order_param in order_params:
                try:
                    order_result = self._place_single_bracket_order(
                        profile_name=profile_name,
                        address=address,
                        bracket=bracket,
                        bracket_id=order_param["bracket_id"],
                        current_market_cap=current_market_cap,
                        entry_market_cap=order_param["entry_price"],  # Using market cap as entry target
                        take_profit_market_cap=order_param["take_profit"],
                        stop_loss_market_cap=order_param["stop_loss"],
                        amount=order_param["amount"],
                        strategy_number=strategy_number
                    )
                    
                    if order_result["success"]:
                        placed_orders.append(order_result["order"])
                    else:
                        failed_orders.append({
                            "bracket_id": order_param["bracket_id"],
                            "error": order_result["error"]
                        })
                        
                except Exception as e:
                    logger.error(f"Failed to place bracket order {order_param['bracket_id']}: {e}")
                    failed_orders.append({
                        "bracket_id": order_param["bracket_id"],
                        "error": str(e)
                    })
            
            return {
                "success": len(placed_orders) > 0,
                "bracket": bracket,
                "current_market_cap": current_market_cap,
                "placed_orders": placed_orders,
                "failed_orders": failed_orders,
                "total_placed": len(placed_orders),
                "total_failed": len(failed_orders)
            }
            
        except Exception as e:
            logger.error(f"Failed to place bracket orders: {e}")
            return {"success": False, "error": str(e)}
    
    def _place_single_bracket_order(self, profile_name: str, address: str, bracket: int,
                                  bracket_id: int, current_market_cap: float,
                                  entry_market_cap: float, take_profit_market_cap: float,
                                  stop_loss_market_cap: float, amount: float,
                                  strategy_number: int) -> Dict:
        """
        Place a single bracket order.
        
        Args:
            profile_name: Chrome profile name
            address: Token contract address
            bracket: Market cap bracket (1-5)
            bracket_id: Order ID within bracket (1-4)
            current_market_cap: Current token market cap
            entry_market_cap: Target entry market cap
            take_profit_market_cap: Take profit market cap target
            stop_loss_market_cap: Stop loss market cap target
            amount: Order amount
            strategy_number: Strategy number
            
        Returns:
            Dict with success status and order details
        """
        try:
            driver = self.driver_manager.get_driver(profile_name)
            
            # Determine order type based on market cap comparison
            is_market_order = current_market_cap < entry_market_cap
            order_type = "MARKET" if is_market_order else "LIMIT"
            
            logger.info(f"Placing {order_type} order for bracket {bracket}, bracket_id {bracket_id}")
            logger.info(f"Current MC: ${current_market_cap:,.0f}, Entry MC: ${entry_market_cap:,.0f}")
            
            # Navigate to buy interface
            #if not self._navigate_to_buy_interface(driver):
            #    return {"success": False, "error": "Failed to navigate to buy interface"}
            
            # Handle market vs limit order placement
            if is_market_order:
                # Place market order immediately
                if not self._place_market_order(driver):
                    return {"success": False, "error": "Failed to place market order"}
            else:
                # Set up limit order at entry market cap
                if not self._setup_limit_order(driver, entry_market_cap):
                    return {"success": False, "error": "Failed to setup limit order"}

            # Enter order amount
            if not self._enter_order_amount(driver, amount):
                return {"success": False, "error": "Failed to enter order amount"}

            # Open auto-sell frame and configure strategy
            strategy_name = f"Bracket{bracket}_{bracket_id}"
            if not self._configure_auto_sell_strategy(
                driver, strategy_name, take_profit_market_cap, stop_loss_market_cap
            ):
                return {"success": False, "error": "Failed to configure auto-sell strategy"}
            
            # Get token name from database for screenshot
            coin = db_manager.get_coin_by_address(address)
            token_name = coin.name if coin and coin.name else "Unknown"
            
            # Confirm the order
            if not self._confirm_order(driver, token_name, bracket, bracket_id):
                return {"success": False, "error": "Failed to confirm order"}
            
            # Save order to database
            order_data = {
                "strategy_number": strategy_number,
                "order_type": "BUY",
                "market_cap": current_market_cap,
                "entry_price": entry_market_cap,
                "take_profit": take_profit_market_cap,
                "stop_loss": stop_loss_market_cap,
                "amount": amount,
                "profile_name": profile_name,
                "bracket_id": bracket_id,
                "is_market_order": is_market_order
            }
            
            # Create order with coin relationship
            db_result = db_manager.create_order_with_coin(address, order_data)
            
            return {
                "success": True,
                "order": {
                    "bracket_id": bracket_id,
                    "order_type": order_type,
                    "entry_market_cap": entry_market_cap,
                    "take_profit_market_cap": take_profit_market_cap,
                    "stop_loss_market_cap": stop_loss_market_cap,
                    "amount": amount,
                    "strategy_name": strategy_name,
                    "db_order_id": db_result.id if db_result else None
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to place single bracket order: {e}")
            return {"success": False, "error": str(e)}
    
    def _navigate_to_buy_interface(self, driver) -> bool:
        """Navigate to the buy interface on BullX"""
        try:
            # Look for buy button - adjust selector based on actual BullX UI
            buy_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button/span[contains(text(), 'Buy')]"))
            )
            logger.info("pressed buy button")
            buy_button.click()
            
            # Wait for buy interface to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[@placeholder='0' or contains(@placeholder, 'amount')]"))
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to navigate to buy interface: {e}")
            return False
    
    def _enter_order_amount(self, driver, amount: float) -> bool:
        """Enter the order amount in the buy interface"""
        try:
            # Find amount input field
            amount_input = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div[1]/div[2]/main/div/div[2]/aside/div/div[3]/div/div/div/div[1]/div[3]/div[2]/div/div/div/div[2]/div/div[1]/div[1]/div/div/div[2]/div/div/input"))
            )
            
            logger.info(f"Attempting to enter amount: {amount}")
            
            # Get initial value before clearing
            initial_value = amount_input.get_attribute("value")
            logger.info(f"Initial input value: '{initial_value}'")
            
            # Clear and enter amount
            amount_input.send_keys(Keys.CONTROL + "A")
            amount_input.send_keys(Keys.DELETE)
            # Check if cleared successfully
            cleared_value = amount_input.get_attribute("value")
            logger.info(f"Value after clear: '{cleared_value}'")
            
            # Enter the amount
            amount_str = str(amount)
            logger.info(f"Sending keys: '{amount_str}'")
            amount_input.send_keys(amount_str)
            
            # Verify amount was entered
            time.sleep(0.5)  # Brief pause for UI update
            entered_value = amount_input.get_attribute("value")
            logger.info(f"Final entered value: '{entered_value}'")
            
            if not entered_value:
                logger.warning(f"Amount verification failed. No value entered.")
            else:
                try:
                    entered_float = float(entered_value)
                    # Use more generous tolerance for floating point comparison (1% tolerance)
                    tolerance = max(abs(amount * 0.01), 0.001)  # 1% tolerance with minimum of 0.001
                    difference = abs(entered_float - amount)
                    
                    logger.info(f"Amount comparison - Expected: {amount}, Got: {entered_float}, Difference: {difference}, Tolerance: {tolerance}")
                    
                    if difference > tolerance:
                        logger.warning(f"Amount verification failed. Expected: {amount}, Got: {entered_value}, Difference: {difference} > Tolerance: {tolerance}")
                        
                        # Try to correct the value if it seems like it was doubled or has precision issues
                        if abs(entered_float - (amount * 2)) < tolerance:
                            logger.info("Detected doubled value, attempting to correct...")
                            amount_input.send_keys(Keys.CONTROL + "A")
                            amount_input.send_keys(Keys.DELETE)
                            time.sleep(0.2)
                            amount_input.send_keys(str(amount))
                            time.sleep(0.5)
                            corrected_value = amount_input.get_attribute("value")
                            logger.info(f"Corrected value: '{corrected_value}'")
                    else:
                        logger.info("Amount verification passed")
                        
                except ValueError:
                    logger.warning(f"Amount verification failed. Invalid value: '{entered_value}'")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to enter order amount: {e}")
            return False
    
    def _place_market_order(self, driver) -> bool:
        """Place a market order immediately"""
        try:
            # Look for market order button or immediate buy button
            market_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'Market')]"))
            )
            market_button.click()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to place market order: {e}")
            return False
    
    def _setup_limit_order(self, driver, entry_market_cap: float) -> bool:
        """Setup a limit order at the specified entry market cap"""
        try:
            # Look for limit order option
            limit_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'Limit')]"))
            )
            limit_button.click()
            time.sleep(1)
            # Enter limit price (this would need to be converted from market cap to actual price)
            # For now, we'll use the market cap value directly as a placeholder
            limit_price_input = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div[1]/div[2]/main/div/div[2]/aside/div/div[3]/div/div/div/div[1]/div[3]/div[2]/div/div/div/div[2]/div/div[2]/div/div[1]/div/div[2]/div/div/input"))
            )
            limit_price_input.send_keys(Keys.CONTROL + "A")
            limit_price_input.send_keys(Keys.DELETE)
            limit_price_input.send_keys(str(entry_market_cap))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup limit order: {e}")
            return False
    
    def _configure_auto_sell_strategy(self, driver, strategy_name: str, 
                                    take_profit_market_cap: float, 
                                    stop_loss_market_cap: float) -> bool:
        """
        Configure auto-sell strategy with take profit and stop loss.
        Handles both cases where strategy needs to be selected or is already selected.
        """
        try:
            # Open auto-sell frame
            auto_sell_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button/span[contains(text(), 'Auto Sell') or contains(@class, 'auto-sell')]"))
            )
            auto_sell_button.click()
            
            # Wait for auto-sell frame to open - look for either Select or Disable buttons
            WebDriverWait(driver, 10).until(
                EC.any_of(
                    EC.presence_of_element_located((By.XPATH, "//button/span[contains(text(), 'Select')]")),
                    EC.presence_of_element_located((By.XPATH, "//button/span[contains(text(), 'Disable')]"))
                )
            )
            time.sleep(2)
            
            # Find strategy by name (e.g., "Bracket1_1")
            strategies_names = driver.find_elements(By.XPATH, "//div[@class='flex flex-col gap-y-3 mt-4 pb-4']/div")
            strategy_found = False
            
            for strategy in strategies_names:
                try:
                    strategy_name_found = strategy.find_element(By.XPATH, "./div/div/span").text
                    if strategy_name_found == f"{strategy_name}":
                        strategy_found = True
                        
                        # Check if strategy is already selected (button says "Disable")
                        try:
                            disable_button = strategy.find_element(By.XPATH, "./div/div[2]/button[2]/span[contains(text(), 'Disable')]")
                            logger.info(f"✅ Auto-sell strategy '{strategy_name}' is already selected")
                            
                            # Click the button to proceed with the already selected strategy
                            proceed_button = WebDriverWait(driver, 10).until(
                                EC.element_to_be_clickable((By.XPATH, "//*[@id='root']/div[1]/div[2]/main/div/div[2]/aside/div[2]/div[3]/div/div/div[1]/div/button"))
                            )
                            proceed_button.click()
                            logger.info(f"✅ Clicked proceed button for already selected strategy")
                            
                        except NoSuchElementException:
                            # Strategy is not selected, look for Select button
                            try:
                                select_button = strategy.find_element(By.XPATH, "./div/div[2]/button[2]/span[contains(text(), 'Select')]")
                                select_button.click()
                                logger.info(f"✅ Selected auto-sell strategy '{strategy_name}'")
                                time.sleep(2)
                                
                            except NoSuchElementException:
                                logger.error(f"❌ Neither 'Select' nor 'Disable' button found for strategy '{strategy_name}'")
                                return False
                        
                        break
                        
                except Exception as e:
                    logger.debug(f"Error checking strategy element: {e}")
                    continue
            
            if not strategy_found:
                logger.error(f"❌ Strategy '{strategy_name}' not found in available strategies")
                return False
            
            logger.info(f"Configured auto-sell strategy: {strategy_name}")
            logger.info(f"TP: ${take_profit_market_cap:,.0f}, SL: ${stop_loss_market_cap:,.0f}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure auto-sell strategy: {e}")
            return False
    
    def _take_order_screenshot(self, driver, token_name: str, bracket: int, bracket_id: int) -> Optional[str]:
        """
        Take a screenshot when an order is placed successfully.
        
        Args:
            driver: Selenium WebDriver instance
            token_name: Name of the token
            bracket: Market cap bracket (1-5)
            bracket_id: Order ID within bracket (1-4)
            
        Returns:
            Screenshot file path if successful, None otherwise
        """
        # SCREENSHOT FUNCTIONALITY - Comment out the next line to disable screenshots
        ENABLE_SCREENSHOTS = True
        
        if not ENABLE_SCREENSHOTS:
            return None
            
        try:
            # Create screenshots directory if it doesn't exist
            screenshots_dir = "order_placement_screenshots"
            if not os.path.exists(screenshots_dir):
                os.makedirs(screenshots_dir)
                logger.info(f"Created screenshots directory: {screenshots_dir}")
            
            # Generate timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Clean token name for filename (remove special characters)
            clean_token_name = "".join(c for c in token_name if c.isalnum() or c in ('-', '_')).rstrip()
            if not clean_token_name:
                clean_token_name = "Unknown"
            
            # Create filename with timestamp, token name, bracket, and bracket_id
            filename = f"{timestamp}_{clean_token_name}_B{bracket}_S{bracket_id}.png"
            filepath = os.path.join(screenshots_dir, filename)
            
            # Take screenshot
            driver.save_screenshot(filepath)
            
            logger.info(f"📸 Screenshot saved: {filename}")
            logger.info(f"   Token: {token_name}, Bracket: {bracket}, Sub ID: {bracket_id}")
            
            return filepath
            
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            return None
    
    def _confirm_order(self, driver, token_name: str = "Unknown", bracket: int = 0, bracket_id: int = 0) -> bool:
        """Confirm and place the order"""
        try:
            # Look for final confirm/place order button
            confirm_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button/span[contains(text(), 'Buy')]"))
            )
            confirm_button.click()
            time.sleep(1)
            
            # Wait for order confirmation or success message
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, "//div/span[contains(text(), 'success') or contains(text(), 'completed') or contains(@class, 'success')]"))
                )
                logger.info("Order placed successfully")
                
                # Take screenshot when order is placed successfully
                self._take_order_screenshot(driver, token_name, bracket, bracket_id)
                
            except TimeoutException:
                logger.warning("Order confirmation message not found, but order may have been placed")
                
                # Still take screenshot even if confirmation message not found
                self._take_order_screenshot(driver, token_name, bracket, bracket_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to confirm order: {e}")
            return False
    
    def replace_bracket_order(self, profile_name: str, address: str, bracket_id: int,
                            new_amount: float, strategy_number: int = 1, 
                            original_bracket: int = None) -> Dict:
        """
        Replace a specific bracket order with a new one.
        
        Args:
            profile_name: Chrome profile name
            address: Token contract address
            bracket_id: Bracket ID to replace (1-4)
            new_amount: New order amount
            strategy_number: Strategy number
            original_bracket: Original bracket to use (preserves bracket consistency)
            
        Returns:
            Dict with success status and order details
        """
        try:
            # Get current market cap for order placement logic
            if not self.automator.search_address(profile_name, address):
                return {"success": False, "error": "Failed to search address"}
            
            current_market_cap = self.automator.get_market_cap(profile_name)
            
            # Use original bracket if provided, otherwise calculate from current market cap
            if original_bracket and original_bracket in BRACKET_CONFIG:
                bracket = original_bracket
                logger.info(f"Using original bracket {bracket} for replacement order (preserving bracket consistency)")
            else:
                bracket = calculate_bracket(current_market_cap)
                logger.info(f"Calculated bracket {bracket} from current market cap ${current_market_cap:,.0f}")
            
            # Get bracket configuration for the specific bracket_id
            bracket_config = BRACKET_CONFIG[bracket]
            entry_market_cap = bracket_config["entries"][bracket_id - 1]
            
            # Calculate take profit and stop loss based on bracket configuration
            from bracket_config import TAKE_PROFIT_PERCENTAGES
            take_profit_multiplier = TAKE_PROFIT_PERCENTAGES[bracket_id - 1]
            take_profit_market_cap = entry_market_cap + entry_market_cap * take_profit_multiplier
            stop_loss_market_cap = bracket_config["stop_loss_market_cap"]
            
            # Place the replacement order
            order_result = self._place_single_bracket_order(
                profile_name=profile_name,
                address=address,
                bracket=bracket,
                bracket_id=bracket_id,
                current_market_cap=current_market_cap,
                entry_market_cap=entry_market_cap,
                take_profit_market_cap=take_profit_market_cap,
                stop_loss_market_cap=stop_loss_market_cap,
                amount=new_amount,
                strategy_number=strategy_number
            )
            
            return order_result
            
        except Exception as e:
            logger.error(f"Failed to replace bracket order: {e}")
            return {"success": False, "error": str(e)}


class BracketOrderManager:
    """
    High-level manager for bracket order operations.
    Provides simplified interface for common bracket order tasks.
    """
    
    def __init__(self):
        from chrome_driver import bullx_automator
        self.order_placer = BracketOrderPlacer(bullx_automator)
    
    def execute_bracket_strategy(self, profile_name: str, address: str, 
                                total_amount: float, strategy_number: int = 1) -> Dict:
        """
        Execute complete bracket strategy for a coin.
        
        This is the main entry point for placing bracket orders.
        """
        return self.order_placer.place_bracket_orders(
            profile_name=profile_name,
            address=address,
            total_amount=total_amount,
            strategy_number=strategy_number
        )
    
    def replace_order(self, profile_name: str, address: str, bracket_id: int,
                     new_amount: float, strategy_number: int = 1, 
                     original_bracket: int = None) -> Dict:
        """
        Replace a specific bracket order.
        """
        return self.order_placer.replace_bracket_order(
            profile_name=profile_name,
            address=address,
            bracket_id=bracket_id,
            new_amount=new_amount,
            strategy_number=strategy_number,
            original_bracket=original_bracket
        )
    
    def get_bracket_preview(self, address: str, total_amount: float, 
                           profile_name: str = None) -> Dict:
        """
        Get a preview of what bracket orders would be placed without actually placing them.
        
        Args:
            address: Token contract address
            total_amount: Total investment amount
            profile_name: Optional profile name to get current market cap
            
        Returns:
            Dict with bracket info and order parameters
        """
        try:
            current_market_cap = 0
            
            # Try to get current market cap if profile is provided
            if profile_name:
                try:
                    if self.order_placer.automator.search_address(profile_name, address):
                        current_market_cap = self.order_placer.automator.get_market_cap(profile_name)
                except Exception as e:
                    logger.warning(f"Could not get current market cap: {e}")
            
            # If we couldn't get current market cap, use a default for preview
            if current_market_cap <= 0:
                current_market_cap = 100000  # Default to bracket 1 for preview
            
            bracket = calculate_bracket(current_market_cap)
            bracket_info = get_bracket_info(bracket)
            order_params = calculate_order_parameters(bracket, total_amount)
            
            # Add order type information
            for order_param in order_params:
                entry_market_cap = order_param["entry_price"]
                is_market_order = current_market_cap < entry_market_cap
                order_param["order_type"] = "MARKET" if is_market_order else "LIMIT"
                order_param["strategy_name"] = f"Bracket{bracket}_{order_param['bracket_id']}"
            
            return {
                "success": True,
                "bracket": bracket,
                "bracket_info": bracket_info,
                "current_market_cap": current_market_cap,
                "total_amount": total_amount,
                "orders": order_params
            }
            
        except Exception as e:
            logger.error(f"Failed to generate bracket preview: {e}")
            return {"success": False, "error": str(e)}


# Global instance for easy access
bracket_order_manager = BracketOrderManager()
