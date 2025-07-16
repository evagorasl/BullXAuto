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
            
            # Get current market cap
            current_market_cap = self.automator.get_market_cap(profile_name)
            if current_market_cap <= 0:
                return {"success": False, "error": "Failed to get market cap"}
            
            # Calculate bracket and order parameters
            bracket = calculate_bracket(current_market_cap)
            bracket_info = get_bracket_info(bracket)
            order_params = calculate_order_parameters(bracket, total_amount)
            
            logger.info(f"Placing bracket {bracket} orders for {address} with market cap ${current_market_cap:,.0f}")
            
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
            if not self._navigate_to_buy_interface(driver):
                return {"success": False, "error": "Failed to navigate to buy interface"}
            
            # Enter order amount
            if not self._enter_order_amount(driver, amount):
                return {"success": False, "error": "Failed to enter order amount"}
            
            # Handle market vs limit order placement
            if is_market_order:
                # Place market order immediately
                if not self._place_market_order(driver):
                    return {"success": False, "error": "Failed to place market order"}
            else:
                # Set up limit order at entry market cap
                if not self._setup_limit_order(driver, entry_market_cap):
                    return {"success": False, "error": "Failed to setup limit order"}
            
            # Open auto-sell frame and configure strategy
            strategy_name = f"Bracket{bracket}_{bracket_id}"
            if not self._configure_auto_sell_strategy(
                driver, strategy_name, take_profit_market_cap, stop_loss_market_cap
            ):
                return {"success": False, "error": "Failed to configure auto-sell strategy"}
            
            # Confirm the order
            if not self._confirm_order(driver):
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
                    "db_order_id": db_result.get("order_id") if db_result else None
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
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Buy') or contains(@class, 'buy')]"))
            )
            buy_button.click()
            
            # Wait for buy interface to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[@placeholder='0.0' or contains(@placeholder, 'amount')]"))
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
                EC.element_to_be_clickable((By.XPATH, "//input[@placeholder='0.0' or contains(@placeholder, 'amount')]"))
            )
            
            # Clear and enter amount
            amount_input.clear()
            amount_input.send_keys(str(amount))
            
            # Verify amount was entered
            time.sleep(0.5)  # Brief pause for UI update
            entered_value = amount_input.get_attribute("value")
            
            if not entered_value or float(entered_value) != amount:
                logger.warning(f"Amount verification failed. Expected: {amount}, Got: {entered_value}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to enter order amount: {e}")
            return False
    
    def _place_market_order(self, driver) -> bool:
        """Place a market order immediately"""
        try:
            # Look for market order button or immediate buy button
            market_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Market') or contains(text(), 'Buy Now')]"))
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
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Limit') or contains(@class, 'limit')]"))
            )
            limit_button.click()
            
            # Enter limit price (this would need to be converted from market cap to actual price)
            # For now, we'll use the market cap value directly as a placeholder
            limit_price_input = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//input[contains(@placeholder, 'price') or contains(@placeholder, 'limit')]"))
            )
            
            limit_price_input.clear()
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
        
        Note: The actual element selectors will need to be provided later
        based on the BullX UI structure.
        """
        try:
            # Open auto-sell frame
            auto_sell_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Auto Sell') or contains(@class, 'auto-sell')]"))
            )
            auto_sell_button.click()
            
            # Wait for auto-sell frame to open
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'auto-sell-frame') or contains(@class, 'strategy-selector')]"))
            )
            
            # Select strategy by name (e.g., "Bracket1_1")
            strategy_selector = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, f"//option[text()='{strategy_name}'] | //button[text()='{strategy_name}']"))
            )
            strategy_selector.click()
            
            # Configure take profit
            tp_input = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//input[contains(@placeholder, 'take profit') or contains(@name, 'tp')]"))
            )
            tp_input.clear()
            tp_input.send_keys(str(take_profit_market_cap))
            
            # Configure stop loss
            sl_input = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//input[contains(@placeholder, 'stop loss') or contains(@name, 'sl')]"))
            )
            sl_input.clear()
            sl_input.send_keys(str(stop_loss_market_cap))
            
            # Confirm auto-sell configuration
            confirm_auto_sell = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Confirm') or contains(text(), 'Apply')]"))
            )
            confirm_auto_sell.click()
            
            logger.info(f"Configured auto-sell strategy: {strategy_name}")
            logger.info(f"TP: ${take_profit_market_cap:,.0f}, SL: ${stop_loss_market_cap:,.0f}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure auto-sell strategy: {e}")
            return False
    
    def _confirm_order(self, driver) -> bool:
        """Confirm and place the order"""
        try:
            # Look for final confirm/place order button
            confirm_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Place Order') or contains(text(), 'Confirm') or contains(text(), 'Buy')]"))
            )
            confirm_button.click()
            
            # Wait for order confirmation or success message
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'success') or contains(text(), 'placed') or contains(@class, 'success')]"))
                )
                logger.info("Order placed successfully")
            except TimeoutException:
                logger.warning("Order confirmation message not found, but order may have been placed")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to confirm order: {e}")
            return False
    
    def replace_bracket_order(self, profile_name: str, address: str, bracket_id: int,
                            new_amount: float, strategy_number: int = 1) -> Dict:
        """
        Replace a specific bracket order with a new one.
        
        Args:
            profile_name: Chrome profile name
            address: Token contract address
            bracket_id: Bracket ID to replace (1-4)
            new_amount: New order amount
            strategy_number: Strategy number
            
        Returns:
            Dict with success status and order details
        """
        try:
            # Get current market cap and bracket info
            if not self.automator.search_address(profile_name, address):
                return {"success": False, "error": "Failed to search address"}
            
            current_market_cap = self.automator.get_market_cap(profile_name)
            bracket = calculate_bracket(current_market_cap)
            
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
                     new_amount: float, strategy_number: int = 1) -> Dict:
        """
        Replace a specific bracket order.
        """
        return self.order_placer.replace_bracket_order(
            profile_name=profile_name,
            address=address,
            bracket_id=bracket_id,
            new_amount=new_amount,
            strategy_number=strategy_number
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
